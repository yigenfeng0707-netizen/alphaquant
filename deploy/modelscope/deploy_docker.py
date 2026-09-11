#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# deploy_docker.py — ModelScope Studio Docker 部署脚本 (Python 版, 等价 deploy.sh)
# ----------------------------------------------------------------------------
# 流程：
#   1. 检查/创建 Studio (Docker, CPU, public)
#   2. 组装部署载荷 (backend + frontend dist 构建源 + offline 数据 + Dockerfile +
#      ms_deploy.json + .dockerignore + README)
#   3. 推送至 ModelScope Git (非强推, 合并远端历史, 自动重试)
#   4. 触发 deploy 并轮询实例状态直到 Running / Failed / 超时
#
# 环境变量：
#   MODELSCOPE_API_TOKEN  必填, 魔搭 token (永不回显)
#   MS_STUDIO_OWNER       必填, 空间属主
#   MS_STUDIO_NAME        必填, 空间名
#   MODELSCOPE_ENDPOINT   可选, 默认 https://modelscope.cn
#   DEPLOY_COMMIT_MSG     可选, 提交信息, 默认 deploy: <GITHUB_SHA|manual>
#
# 用法：
#   MODELSCOPE_API_TOKEN=ms-xxx MS_STUDIO_OWNER=me MS_STUDIO_NAME=demo \
#     python deploy_docker.py                                # 完整部署
#   python deploy_docker.py --dry-run                        # 只组装载荷不推送不部署
#   python deploy_docker.py --build                          # 部署前先本地 docker build 校验
#   python deploy_docker.py --poll-timeout 1800              # 轮询上限秒数(默认 800)
#
# 退出码：0=成功部署(Running) / 1=失败 / 2=参数或环境错误
# ============================================================================

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn

# Windows 控制台兼容：强制 UTF-8 输出（无 reconfigure 的旧解释器跳过）
for _s in (sys.stdout, sys.stderr):
    _rec = getattr(_s, "reconfigure", None)
    if _rec is not None:
        try:
            _rec(encoding="utf-8")
        except Exception:
            pass

MS_ENDPOINT = os.environ.get("MODELSCOPE_ENDPOINT", "https://modelscope.cn")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
ROOT = Path(__file__).resolve().parent.parent.parent  # 项目根目录
DEPLOY_DIR = Path(__file__).resolve().parent  # deploy/modelscope

# 与 deploy.sh 的 rsync --exclude 等价
BACKEND_EXCLUDE = {".venv", "venv", "__pycache__", ".pytest_cache", ".env"}
BACKEND_EXCLUDE |= {f".env.{x}" for x in ("local", "prod", "dev", "example")}
BACKEND_EXCLUDE |= {"*.pyc"}
FRONTEND_EXCLUDE = {"node_modules", "dist"}
FRONTEND_EXCLUDE |= {f".env.{x}" for x in ("local", "prod", "dev", "example")}
FRONTEND_EXCLUDE |= {".env"}

POLL_INTERVAL = 20  # 轮询间隔秒
POLL_MAX = 40  # 最多轮询次数
FETCH_RETRIES = 3
PUSH_RETRIES = 3
CREATE_SETTLE = 20  # 新建空间后等待秒


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def fail(msg: str, code: int = 1) -> NoReturn:
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def redact(text: str, token: str) -> str:
    if token:
        text = text.replace(token, "***")
    return text


# ---------------------------------------------------------------------------
# HTTP 辅助 (OpenAPI: Bearer 官方认证 + X-Auth-Token 网关兼容)
# ---------------------------------------------------------------------------
class API:
    def __init__(self, token: str):
        self.token = token

    def _headers(self, with_json: bool = False) -> dict:
        h = {
            "User-Agent": UA,
            "Authorization": f"Bearer {self.token}",
            "X-Auth-Token": self.token,
            "Accept": "application/json",
        }
        if with_json:
            h["Content-Type"] = "application/json"
        return h

    def request(
        self, method: str, url: str, data: dict | None = None, out: Path | None = None
    ) -> tuple[int, dict | str]:
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url, data=body, headers=self._headers(data is not None), method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read().decode("utf-8", errors="replace")
                if out:
                    out.write_text(content, encoding="utf-8")
                try:
                    return resp.getcode(), json.loads(content)
                except json.JSONDecodeError:
                    return resp.getcode(), content
        except urllib.error.HTTPError as e:
            content = e.read().decode("utf-8", errors="replace")
            if out:
                out.write_text(content, encoding="utf-8")
            try:
                return e.code, json.loads(content)
            except json.JSONDecodeError:
                return e.code, content
        except urllib.error.URLError as e:
            fail(f"网络错误 {url}: {e.reason}")

    def get_studio(self, owner: str, name: str) -> tuple[int, dict | str]:
        return self.request("GET", f"{MS_ENDPOINT}/openapi/v1/studios/{owner}/{name}")

    def create_studio(
        self, owner: str, name: str, display_name: str
    ) -> tuple[int, dict | str]:
        payload = {
            "owner": owner,
            "repo_name": name,
            "sdk_type": "docker",
            "visibility": "public",
            "hardware": "platform/2v-cpu-16g-mem",
            "display_name": display_name,
        }
        return self.request("POST", f"{MS_ENDPOINT}/openapi/v1/studios", data=payload)

    def deploy(self, owner: str, name: str) -> tuple[int, dict | str]:
        return self.request(
            "POST", f"{MS_ENDPOINT}/openapi/v1/studios/{owner}/{name}/deploy"
        )


def first_key(d: dict, *keys, default: str = "") -> str:
    """兼容大写/小写字段名。"""
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return str(v)
    return default


def studio_field(doc: dict | str, *keys, default: str = "") -> str:
    if not isinstance(doc, dict):
        return default
    data = doc.get("data") or doc.get("Data") or {}
    if isinstance(data, dict):
        v = first_key(data, *keys, default=default)
        if v:
            return v
    return first_key(doc, *keys, default=default)


# ---------------------------------------------------------------------------
# 载荷组装 (等价 deploy.sh 的 rsync 集合)
# ---------------------------------------------------------------------------
def copytree_exclude(src: Path, dst: Path, excludes: set) -> None:
    def ignore(dirname, names):
        out = set()
        for n in names:
            p = Path(dirname) / n
            if n in excludes or any(
                part in excludes and part.endswith((".pyc",)) for part in []
            ):
                out.add(n)
            elif p.is_dir() and p.name in excludes:
                out.add(n)
            elif p.name.endswith(".pyc") and "*.pyc" in excludes:
                out.add(n)
            elif any(e in p.name for e in excludes if e.startswith(".env")):
                out.add(n)
        return out

    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def assemble_payload(pkg: Path) -> int:
    log("Assembling payload...")
    (pkg / "backend").mkdir(parents=True, exist_ok=True)
    (pkg / "frontend").mkdir(parents=True, exist_ok=True)
    (pkg / "data" / "offline").mkdir(parents=True, exist_ok=True)

    copytree_exclude(ROOT / "backend", pkg / "backend", BACKEND_EXCLUDE)
    copytree_exclude(ROOT / "frontend", pkg / "frontend", FRONTEND_EXCLUDE)
    shutil.copytree(
        ROOT / "data" / "offline", pkg / "data" / "offline", dirs_exist_ok=True
    )

    for name, target in [
        ("Dockerfile", "Dockerfile"),
        ("ms_deploy.json", "ms_deploy.json"),
        (".dockerignore", ".dockerignore"),
        ("STUDIO_README.md", "README.md"),
    ]:
        shutil.copy2(DEPLOY_DIR / name, pkg / target)

    total = sum(f.stat().st_size for f in pkg.rglob("*") if f.is_file())
    n_files = sum(1 for f in pkg.rglob("*") if f.is_file())
    log(f"Payload ready: {n_files} files, {total / 1024 / 1024:.1f} MB -> {pkg}")
    return total


# ---------------------------------------------------------------------------
# Git 推送 (非强推, 合并远端历史, 自动重试)
# ---------------------------------------------------------------------------
def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def push_payload(pkg: Path, git_url: str, commit_msg: str, token: str) -> None:
    log("Initializing git repo for payload...")
    git(pkg, "init", "-q", "-b", "master")
    git(pkg, "config", "user.name", "github-actions[bot]")
    git(pkg, "config", "user.email", "github-actions[bot]@users.noreply.github.com")
    git(pkg, "add", "-A")
    git(pkg, "commit", "-q", "-m", commit_msg)
    r = git(pkg, "remote", "add", "origin", git_url, check=False)
    if r.returncode != 0:
        log(f"(remote origin 已存在: {r.stderr.strip()[:80]})")

    log("Fetching ModelScope master (no force push)...")
    fetched = False
    for i in range(1, FETCH_RETRIES + 1):
        if git(pkg, "fetch", "origin", "master", check=False).returncode == 0:
            fetched = True
            break
        log(f"WARN: fetch attempt {i} failed, retry...")
        time.sleep(5)
    if fetched:
        mr = git(
            pkg,
            "merge",
            "origin/master",
            "--allow-unrelated-histories",
            "-X",
            "ours",
            "--no-edit",
            "-q",
            check=False,
        )
        if mr.returncode != 0:
            git(pkg, "checkout", "--ours", ".", check=False)
            git(pkg, "add", "-A")
            git(pkg, "commit", "-q", "-m", "merge remote history (ours)", check=False)

    pushed = False
    for i in range(1, PUSH_RETRIES + 1):
        pr = git(pkg, "push", "origin", "HEAD:master", check=False)
        if pr.returncode == 0:
            pushed = True
            break
        log(f"WARN: push attempt {i} failed — {redact(pr.stderr.strip()[:300], token)}")
        time.sleep(5)
        git(pkg, "fetch", "origin", "master", check=False)
        git(
            pkg,
            "merge",
            "origin/master",
            "--allow-unrelated-histories",
            "-X",
            "ours",
            "--no-edit",
            "-q",
            check=False,
        )
    if not pushed:
        fail("git push to ModelScope failed")
    log("Pushed to ModelScope master")


# ---------------------------------------------------------------------------
# 轮询部署状态
# ---------------------------------------------------------------------------
def poll_status(api: API, owner: str, name: str, timeout: int) -> None:
    log("Triggering deploy...")
    code, doc = api.deploy(owner, name)
    if code not in (200, 201):
        fail(
            f"deploy trigger failed HTTP {code}: {json.dumps(doc, ensure_ascii=False)[:300]}"
        )
    log(f"POST deploy -> HTTP {code}")

    demo_url = f"https://{owner}-{name}.ms.show"
    deadline = time.time() + timeout
    n = 0
    while time.time() < deadline:
        n += 1
        code, doc = api.get_studio(owner, name)
        status = studio_field(doc, "status", "Status")
        url = studio_field(doc, "independent_url", "IndependentUrl")
        failed_msg = studio_field(doc, "failed_message", "FailedMessage")
        log(f"  [{n}] Status: {status or 'unknown'}")
        if status == "Running":
            log(f"Deploy succeeded. Demo: {url or demo_url}")
            return
        if status in ("Failed", "Error"):
            fail(f"deploy failed — {failed_msg or 'see studio logs'}")
        time.sleep(POLL_INTERVAL)
    fail(
        f"timed out waiting for Running (re-run workflow if build still going, public URL: {demo_url})"
    )


# ---------------------------------------------------------------------------
# 本地 Docker 构建校验 (可选 --build)
# ---------------------------------------------------------------------------
def docker_build_check() -> None:
    if shutil.which("docker") is None:
        log("WARN: docker not found, skip local build check")
        return
    log("Local docker build check (could take minutes)...")
    ctx = ROOT
    p = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(DEPLOY_DIR / "Dockerfile"),
            "--progress=plain",
            str(ctx),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if p.returncode != 0:
        fail(
            f"local docker build failed:\n{redact(p.stdout[-1500:], '')}\n{p.stderr[-1500:]}"
        )
    log("Local docker build OK")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description="ModelScope Studio Docker 部署脚本 (Python 版)"
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="只组装载荷到临时目录，不推送不部署"
    )
    ap.add_argument(
        "--build", action="store_true", help="部署前先本地 docker build 校验"
    )
    ap.add_argument(
        "--poll-timeout",
        type=int,
        default=POLL_INTERVAL * POLL_MAX,
        help=f"轮询上限秒数(默认 {POLL_INTERVAL * POLL_MAX})",
    )
    ap.add_argument(
        "--owner",
        default=os.environ.get("MS_STUDIO_OWNER", ""),
        help="空间属主(env: MS_STUDIO_OWNER)",
    )
    ap.add_argument(
        "--name",
        default=os.environ.get("MS_STUDIO_NAME", ""),
        help="空间名(env: MS_STUDIO_NAME)",
    )
    args = ap.parse_args()

    token = os.environ.get("MODELSCOPE_API_TOKEN", "")
    if not token:
        fail("MODELSCOPE_API_TOKEN is required", code=2)
    if not args.owner or not args.name:
        fail(
            "MS_STUDIO_OWNER / MS_STUDIO_NAME (或 --owner/--name) are required", code=2
        )
    owner, name = args.owner, args.name

    display_name = os.environ.get("MS_DISPLAY_NAME", "AlphaQuant")
    commit_msg = os.environ.get(
        "DEPLOY_COMMIT_MSG", f"deploy: {os.environ.get('GITHUB_SHA', 'manual')}"
    )
    git_url = f"https://oauth2:{token}@www.modelscope.cn/studios/{owner}/{name}.git"

    with tempfile.TemporaryDirectory(prefix="ms-deploy-") as tmp:
        pkg = Path(tmp) / "pkg"
        pkg.mkdir(parents=True, exist_ok=True)

        if args.dry_run:
            assemble_payload(pkg)
            log(
                "DRY-RUN: 载荷已组装，未做任何网络/推送/部署操作（去掉 --dry-run 重跑执行完整部署）"
            )
            return 0

        api = API(token)

        log(f"Checking studio {owner}/{name}...")
        get_code, doc = api.get_studio(owner, name)
        log(f"GET studio -> HTTP {get_code}")
        if get_code == 404:
            log("Studio not found, creating Docker/CPU/public...")
            create_code, cdoc = api.create_studio(owner, name, display_name)
            log(f"POST studios -> HTTP {create_code}")
            if create_code not in (200, 201):
                msg = studio_field(cdoc, "message", "Message", "code", "Code")
                fail(f"create studio failed HTTP {create_code}: {msg}")
            log(f"Created, waiting {CREATE_SETTLE}s...")
            time.sleep(CREATE_SETTLE)
        elif get_code != 200:
            msg = studio_field(doc, "message", "Message", "code", "Code")
            fail(f"unexpected GET studio HTTP {get_code}: {msg}")
        else:
            st = studio_field(doc, "status", "Status")
            log(f"Studio status: {st or 'unknown'}")

        assemble_payload(pkg)

        if args.build:
            docker_build_check()

        push_payload(pkg, git_url, commit_msg, token)
        poll_status(api, owner, name, args.poll_timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
