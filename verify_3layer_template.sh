#!/usr/bin/env bash
# ============================================================================
# 三层验证法 - 通用脚本模板 (Deploy Triple-Layer Verification Template)
# ----------------------------------------------------------------------------
# 用途：判定一次部署是否真正上线。必须三层证据全部通过才能宣布"上线"：
#   第1层 GitHub Actions 构建结果   -> 构建通过（代码/镜像链路 OK）
#   第2层 平台空间实例状态          -> 实例在线（运行平台 OK）
#   第3层 公网 Demo 端到端         -> 公网可用（用户可访问 OK）
#
# 特点：
#   - 纯 bash + curl，无第三方依赖；JSON 解析优先 python3，无 python 时自动
#     降级为 grep 模式匹配
#   - 所有参数支持"环境变量"与"命令行参数"两种方式，见下方可配置区
#   - 三层可整体跑，也可按 --layer 只跑指定层
#   - 退出码：全部通过=0；任一失败=1；参数错误=2
#
# 用法：
#   ./verify_3layer.sh                                  # 全量验证
#   ./verify_3layer.sh --layer 1                        # 只验第1层
#   ./verify_3layer.sh --layer 1,3                      # 验第1+3层
#   GH_TOKEN=ghp_xxx ./verify_3layer.sh                 # 用环境变量给 token
#
# 通用示例（魔搭 + GitHub Actions）：
#   GH_REPO=myorg/myapp \
#   STUDIO_URL=https://modelscope.cn/studios/owner/myapp \
#   PUBLIC_BASE_URL=https://<uid>-myapp.ms.show \
#   ./verify_3layer.sh
# ============================================================================
set -uo pipefail

# ---------------------------------------------------------------------------
# 0. 可配置区：按目标项目修改，或通过同名环境变量覆盖
# ---------------------------------------------------------------------------
GH_REPO="${GH_REPO:-}"              # GitHub 仓库 owner/repo，如 myorg/myapp；空则跳过第1层
GH_TOKEN="${GH_TOKEN:-}"            # GitHub token（g 开头 40 位）；推荐用环境变量注入
GH_TOKEN_FILE="${GH_TOKEN_FILE:-}"  # 或从文件读 token（自动提取 ghp_ 开头 40 位）
EXPECT_SHA="${EXPECT_SHA:-}"        # 期望匹配的 commit 前7位（可留空=只看最新一次 run 是否 success）
WORKFLOW_KEY="${WORKFLOW_KEY:-Deploy}"  # 第1层筛选的 workflow 名关键字

STUDIO_URL="${STUDIO_URL:-}"        # 平台空间页 URL，如 https://modelscope.cn/studios/owner/name；空则跳过第2层
STATUS_PATTERN="${STATUS_PATTERN:-Status[^,]{0,25}}"  # 第2层提取状态的 grep -E 模式
STATUS_EXPECT="${STATUS_EXPECT:-Running}"             # 第2层期望状态值（含即通过）

PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"  # 公网根地址；空则跳过第3层
HEALTH_PATH="${HEALTH_PATH:-/health}"   # 健康检查路径
HEALTH_EXPECT="${HEALTH_EXPECT:-\"ok\":true}" # /health 响应需包含的文本（注意 JSON 键带引号，默认 "ok":true）
API_SAMPLE_PATH="${API_SAMPLE_PATH:-}"  # 抽查的业务只读接口（可选，如 /api/markets）
UA="${UA:-Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36}"
TIMEOUT="${TIMEOUT:-20}"            # curl 超时秒数
# ---------------------------------------------------------------------------

LAYER_ALL="1,2,3"     # 全部层
LAYERS="${LAYER_ALL}"
FAIL=0

usage() {
  sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [ $# -gt 0 ]; do
  case "$1" in
    --layer) LAYERS="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "未知参数: $1 (用 --help 查看用法)"; exit 2 ;;
  esac
done

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
pass() { echo "  [PASS] $*"; }
fail() { echo "  [FAIL] $*"; FAIL=1; }

want() { case ",$LAYERS," in *",$1,"*) return 0;; *) return 1;; esac; }

# ---------------------------------------------------------------------------
# 第1层：GitHub Actions 构建结果
# ---------------------------------------------------------------------------
layer1() {
  echo "===== 第1层: GitHub Actions 构建结果 ====="
  [ -z "$GH_REPO" ] && { echo "  未配置 GH_REPO，跳过第1层"; return; }

  TOKEN="$GH_TOKEN"
  if [ -z "$TOKEN" ] && [ -n "$GH_TOKEN_FILE" ] && [ -f "$GH_TOKEN_FILE" ]; then
    TOKEN=$(grep -o 'ghp_[A-Za-z0-9]*' "$GH_TOKEN_FILE" | head -1)
  fi
  if [ -z "$TOKEN" ]; then
    echo "  警告: 无 GH_TOKEN/GH_TOKEN_FILE，第1层只能验最近一次 run 的结论，无法核对 commit"
  fi

  AUTH=()
  [ -n "$TOKEN" ] && AUTH=(-H "Authorization: token $TOKEN")
  resp=$(curl -s --max-time "$TIMEOUT" "${AUTH[@]:-}" -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${GH_REPO}/actions/runs?per_page=8" || true)
  if [ -z "$resp" ]; then fail "GitHub API 无响应"; return; fi

  # 优先 python3 解析；无 python 降级为 grep 关键词过滤
  if command -v python3 >/dev/null 2>&1; then
    line=$(echo "$resp" | python3 -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception as e: print('JSONERR'); sys.exit()
key='${WORKFLOW_KEY}'
runs=[r for r in d.get('workflow_runs',[]) if key.lower() in r['name'].lower()]
if not runs: print('NORUN'); sys.exit()
r=runs[0]
print(f\"{r['name'][:40]}|{r['head_sha'][:7]}|{r['status']}/{r['conclusion']}\")
")
    case "$line" in
      JSONERR) fail "GitHub API 返回异常（token 无效或仓库不存在）" ;;
      NORUN)   fail "未找到名称含 [$WORKFLOW_KEY] 的 run" ;;
      *)
        name="${line%%|*}"; rest="${line#*|}"; sha="${rest%%|*}"; conc="${rest#*|}"
        echo "  最新匹配 run: $name | $sha | $conc"
        [ "$conc" != "completed/success" ] && fail "最新 run 结论非 success"
        if [ -n "$EXPECT_SHA" ] && [ "$sha" != "$EXPECT_SHA" ]; then
          fail "HEAD 不匹配: 期望 $EXPECT_SHA, 实际 $sha (构建的是旧提交?)"
        else
          pass "构建结论 success${EXPECT_SHA:+ 且 HEAD=$sha}"
        fi ;;
    esac
  else
    echo "  (无 python3，降级文本匹配)"
    hit=$(echo "$resp" | grep -o "\"name\":\"[^\"]*$WORKFLOW_KEY[^\"]*\"" | head -1)
    conc=$(echo "$resp" | grep -o '"conclusion":"[^"]*"' | head -1)
    echo "  命中 run: ${hit:-?} | ${conc:-无 conclusion}"
    case "$conc" in *success*) pass "构建结论 success" ;; *) fail "最新 run 非 success" ;; esac
  fi
}

# ---------------------------------------------------------------------------
# 第2层：平台空间实例状态
# ---------------------------------------------------------------------------
layer2() {
  echo "===== 第2层: 平台实例状态 ====="
  [ -z "$STUDIO_URL" ] && { echo "  未配置 STUDIO_URL，跳过第2层"; return; }

  page=$(curl -sL -A "$UA" --max-time "$TIMEOUT" "$STUDIO_URL" || true)
  if [ -z "$page" ]; then fail "空间页无响应: $STUDIO_URL"; return; fi

  values=$(echo "$page" | grep -oE "$STATUS_PATTERN" | sort -u)
  if echo "$values" | grep -q "$STATUS_EXPECT"; then
    hit=$(echo "$values" | grep "$STATUS_EXPECT" | head -1)
    pass "实例状态命中 [$STATUS_EXPECT]（命中值: $hit）"
  else
    fail "未找到状态 [$STATUS_EXPECT]；页面字节 $(echo -n "$page" | wc -c)，可能未运行/构建失败/页面结构变化"
  fi
}

# ---------------------------------------------------------------------------
# 第3层：公网 Demo 端到端
# ---------------------------------------------------------------------------
layer3() {
  echo "===== 第3层: 公网 Demo 端到端 ====="
  [ -z "$PUBLIC_BASE_URL" ] && { echo "  未配置 PUBLIC_BASE_URL，跳过第3层"; return; }

  code=$(curl -s -A "$UA" -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${PUBLIC_BASE_URL}/" || true)
  echo "  主页 HTTP $code"
  [ "$code" = "200" ] && pass "主页 200" || fail "主页非 200 (实际 $code)"

  health=$(curl -s -A "$UA" --max-time "$TIMEOUT" "${PUBLIC_BASE_URL}${HEALTH_PATH}" || true)
  echo "  ${HEALTH_PATH}: ${health:0:200}"
  echo "$health" | grep -q "$HEALTH_EXPECT" && pass "${HEALTH_PATH} 含 [$HEALTH_EXPECT]" || fail "${HEALTH_PATH} 未含 [$HEALTH_EXPECT]"

  if [ -n "$API_SAMPLE_PATH" ]; then
    apicode=$(curl -s -A "$UA" -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "${PUBLIC_BASE_URL}${API_SAMPLE_PATH}" || true)
    echo "  业务接口 ${API_SAMPLE_PATH} HTTP $apicode"
    [ "$apicode" = "200" ] && pass "业务接口 200" || fail "业务接口非 200 (实际 $apicode)"
  fi
}

# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
want 1 && layer1
want 2 && layer2
want 3 && layer3

echo ""
if [ $FAIL -eq 0 ]; then
  echo "★★ 所选层全部通过：构建成功 + 实例在线 + 公网可用 ★★"
else
  echo "!! 存在失败项：按部署排障流程定位对应层，别跨层猜。"
  echo "   (403/网关提示先检查是否带 UA / 是否用错 token 类型)"
fi
exit $FAIL