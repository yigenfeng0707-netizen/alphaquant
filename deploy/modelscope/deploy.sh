#!/usr/bin/env bash
# Assemble AlphaQuant Studio payload, push to ModelScope Git (no force), POST deploy, poll Running.
# Requires: MODELSCOPE_API_TOKEN, MS_STUDIO_OWNER, MS_STUDIO_NAME
# Never echo the token.

set -euo pipefail

: "${MODELSCOPE_API_TOKEN:?MODELSCOPE_API_TOKEN is required}"
: "${MS_STUDIO_OWNER:?MS_STUDIO_OWNER is required}"
: "${MS_STUDIO_NAME:?MS_STUDIO_NAME is required}"

MS_ENDPOINT="${MODELSCOPE_ENDPOINT:-https://modelscope.cn}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMMIT_MSG="${DEPLOY_COMMIT_MSG:-deploy: ${GITHUB_SHA:-manual}}"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
AUTH_BEARER="Authorization: Bearer ${MODELSCOPE_API_TOKEN}"
AUTH_X="X-Auth-Token: ${MODELSCOPE_API_TOKEN}"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

ms_curl() {
  # OpenAPI: Bearer (official). Also send X-Auth-Token for gateway compatibility.
  curl -sS -A "$UA" -H "$AUTH_BEARER" -H "$AUTH_X" -H "Accept: application/json" "$@"
}

echo "Checking studio ${MS_STUDIO_OWNER}/${MS_STUDIO_NAME}..."
get_code="$(ms_curl -o "$workdir/studio.json" -w '%{http_code}' \
  "${MS_ENDPOINT}/openapi/v1/studios/${MS_STUDIO_OWNER}/${MS_STUDIO_NAME}" || true)"
echo "GET studio -> HTTP ${get_code}"

if [[ "$get_code" == "404" ]]; then
  echo "Studio not found, creating Docker/CPU/public..."
  create_code="$(ms_curl -o "$workdir/create.json" -w '%{http_code}' \
    -X POST "${MS_ENDPOINT}/openapi/v1/studios" \
    -H "Content-Type: application/json" \
    -d "{\"owner\":\"${MS_STUDIO_OWNER}\",\"repo_name\":\"${MS_STUDIO_NAME}\",\"sdk_type\":\"docker\",\"visibility\":\"public\",\"hardware\":\"platform/2v-cpu-16g-mem\",\"display_name\":\"AlphaQuant\"}")"
  echo "POST studios -> HTTP ${create_code}"
  if [[ "$create_code" != "200" && "$create_code" != "201" ]]; then
    echo "ERROR: create studio failed HTTP ${create_code}" >&2
    python3 -c "import json,sys; p=json.load(open(sys.argv[1],encoding='utf-8')); print(p.get('message') or p.get('Message') or p.get('code') or p.get('Code') or 'see body')" "$workdir/create.json" >&2 || true
    exit 1
  fi
  echo "Created, waiting 20s..."
  sleep 20
elif [[ "$get_code" != "200" ]]; then
  echo "ERROR: unexpected GET studio HTTP ${get_code}" >&2
  python3 -c "import json,sys; p=json.load(open(sys.argv[1],encoding='utf-8')); print(p.get('message') or p.get('Message') or p.get('code') or p.get('Code') or 'see body')" "$workdir/studio.json" >&2 || true
  exit 1
else
  python3 -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); data=d.get('data') or d.get('Data') or {}; print('Studio status:', data.get('status') or data.get('Status') or 'unknown')" "$workdir/studio.json"
fi

echo "Assembling payload..."
pkg="$workdir/pkg"
mkdir -p "$pkg"
rsync -a \
  --exclude='.venv' --exclude='venv' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='.pytest_cache' --exclude='.env' --exclude='.env.*' \
  "$ROOT/backend/" "$pkg/backend/"
rsync -a \
  --exclude='node_modules' --exclude='dist' --exclude='.env' --exclude='.env.*' \
  "$ROOT/frontend/" "$pkg/frontend/"
mkdir -p "$pkg/data/offline"
rsync -a "$ROOT/data/offline/" "$pkg/data/offline/"
cp "$ROOT/deploy/modelscope/Dockerfile" "$pkg/Dockerfile"
cp "$ROOT/deploy/modelscope/ms_deploy.json" "$pkg/ms_deploy.json"
cp "$ROOT/deploy/modelscope/.dockerignore" "$pkg/.dockerignore"
cp "$ROOT/deploy/modelscope/STUDIO_README.md" "$pkg/README.md"
echo "Payload size: $(du -sh "$pkg" | cut -f1)"

git_url="https://oauth2:${MODELSCOPE_API_TOKEN}@www.modelscope.cn/studios/${MS_STUDIO_OWNER}/${MS_STUDIO_NAME}.git"
cd "$pkg"
git init -q -b master
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"
git add -A
git commit -q -m "$COMMIT_MSG"
git remote add origin "$git_url"

echo "Fetching ModelScope master (no force push)..."
fetched=1
for i in 1 2 3; do
  if git fetch origin master; then
    fetched=0
    break
  fi
  echo "WARN: fetch origin/master attempt ${i} failed, retry..."
  sleep 5
done
if [[ "$fetched" -eq 0 ]] && git rev-parse --verify origin/master >/dev/null 2>&1; then
  git merge origin/master --allow-unrelated-histories -X ours --no-edit -q || {
    git checkout --ours . >/dev/null 2>&1 || true
    git add -A
    git commit -q -m "merge remote history (ours)" || true
  }
fi

echo "Pushing to ModelScope master..."
pushed=1
for i in 1 2 3; do
  if git push origin HEAD:master 2> "$workdir/push.err"; then
    pushed=0
    break
  fi
  python3 -c "import pathlib,os; t=os.environ['MODELSCOPE_API_TOKEN']; p=pathlib.Path(r'$workdir/push.err'); print(p.read_text(errors='replace').replace(t,'***')[:800])"
  echo "WARN: push attempt ${i} failed, retry..."
  sleep 5
  git fetch origin master || true
  git merge origin/master --allow-unrelated-histories -X ours --no-edit -q || true
done
if [[ "$pushed" -ne 0 ]]; then
  echo "ERROR: git push to ModelScope failed" >&2
  exit 1
fi
echo "Pushed to ModelScope master"

echo "Triggering deploy..."
deploy_http="$(ms_curl -o "$workdir/deploy.json" -w '%{http_code}' \
  -X POST "${MS_ENDPOINT}/openapi/v1/studios/${MS_STUDIO_OWNER}/${MS_STUDIO_NAME}/deploy" \
  -H "Content-Type: application/json")"
echo "POST deploy -> HTTP ${deploy_http}"
if [[ "$deploy_http" != "200" && "$deploy_http" != "201" ]]; then
  echo "ERROR: deploy trigger failed HTTP ${deploy_http}" >&2
  python3 -c "import json,sys; p=json.load(open(sys.argv[1],encoding='utf-8')); print({k:p.get(k) for k in ('success','message','code','Code','Message') if k in p})" "$workdir/deploy.json" >&2 || true
  exit 1
fi

echo "Polling studio status..."
for i in $(seq 1 40); do
  ms_curl -o "$workdir/status.json" \
    "${MS_ENDPOINT}/openapi/v1/studios/${MS_STUDIO_OWNER}/${MS_STUDIO_NAME}"
  status="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); data=d.get('data') or d.get('Data') or {}; print(data.get('status') or data.get('Status') or '')" "$workdir/status.json")"
  url="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); data=d.get('data') or d.get('Data') or {}; print(data.get('independent_url') or data.get('IndependentUrl') or '')" "$workdir/status.json")"
  failed="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); data=d.get('data') or d.get('Data') or {}; print(data.get('failed_message') or data.get('FailedMessage') or '')" "$workdir/status.json")"
  echo "  [$i/40] Status: ${status:-unknown}"
  case "$status" in
    Running)
      demo="${url:-https://${MS_STUDIO_OWNER}-${MS_STUDIO_NAME}.ms.show}"
      echo "Deploy succeeded. Demo: $demo"
      exit 0
      ;;
    Failed|Error)
      echo "ERROR: deploy failed — ${failed:-see studio logs}" >&2
      exit 1
      ;;
  esac
  sleep 20
done

echo "ERROR: timed out waiting for Running (re-run workflow if build still going)" >&2
exit 1
