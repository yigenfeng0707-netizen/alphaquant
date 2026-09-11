#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# 三层验证法 - 通用脚本模板 (Deploy Triple-Layer Verification Template, Python 版)
# ----------------------------------------------------------------------------
# 用途：判定一次部署是否真正上线。必须三层证据全部通过才能宣布"上线"：
#   第1层 GitHub Actions 构建结果   -> 构建通过（代码/镜像链路 OK）
#   第2层 平台空间实例状态          -> 实例在线（运行平台 OK）
#   第3层 公网 Demo 端到端         -> 公网可用（用户可访问 OK）
#
# 特点：
#   - 纯 Python 标准库（urllib），无第三方依赖；Python 3.7+ 可跑
#   - 所有参数支持"环境变量"与"命令行参数"两种方式，见下方可配置区
#   - 三层可整体跑，也可按 --layer 只跑指定层
#   - 退出码：全部通过=0；任一失败=1；参数错误=2
#
# 用法：
#   python verify_3layer.py                                # 全量验证
#   python verify_3layer.py --layer 1                      # 只验第1层
#   python verify_3layer.py --layer 1,3                    # 验第1+3层
#   GH_TOKEN=ghp_xxx python verify_3layer.py               # 用环境变量给 token
#
# 通用示例（魔搭 + GitHub Actions）：
#   GH_REPO=myorg/myapp \
#   STUDIO_URL=https://modelscope.cn/studios/owner/myapp \
#   PUBLIC_BASE_URL=https://<uid>-myapp.ms.show \
#   python verify_3layer.py
# ============================================================================

import os
import re
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime

# Windows 控制台兼容：强制 UTF-8 输出（无 reconfigure 的旧解释器跳过）
for _s in (sys.stdout, sys.stderr):
    _rec = getattr(_s, "reconfigure", None)
    if _rec is not None:
        try:
            _rec(encoding="utf-8")
        except Exception:
            pass

# ---------------------------------------------------------------------------
# 0. 可配置区：按目标项目修改，或通过同名环境变量覆盖
# ---------------------------------------------------------------------------
GH_REPO = os.environ.get("GH_REPO", "")  # GitHub 仓库 owner/repo；空则跳过第1层
GH_TOKEN = os.environ.get("GH_TOKEN", "")  # GitHub token（ghp_ 开头 40 位）
GH_TOKEN_FILE = os.environ.get(
    "GH_TOKEN_FILE", ""
)  # 或从文件读 token（自动提取 ghp_ 开头 40 位）
EXPECT_SHA = os.environ.get(
    "EXPECT_SHA", ""
)  # 期望 commit 前7位（留空=只看是否 success）
WORKFLOW_KEY = os.environ.get("WORKFLOW_KEY", "Deploy")  # 第1层筛选的 workflow 名关键字

STUDIO_URL = os.environ.get("STUDIO_URL", "")  # 平台空间页 URL；空则跳过第2层
STATUS_PATTERN = os.environ.get(
    "STATUS_PATTERN", r"Status[^,]{0,25}"
)  # 提取状态的扫描模式
STATUS_EXPECT = os.environ.get("STATUS_EXPECT", "Running")  # 期望状态值（含即通过）

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")  # 公网根地址；空则跳过第3层
HEALTH_PATH = os.environ.get("HEALTH_PATH", "/health")  # 健康检查路径
HEALTH_EXPECT = os.environ.get(
    "HEALTH_EXPECT", '"ok":true'
)  # 健康响应需包含的文本（键带引号）
# 抽查的业务只读接口（逗号分隔可传多个；默认基于目标其实业务端点，可按项目覆盖）。
# 判据升级：仅 HTTP 200 不够——SPA fallback 会让任意未知路径也返回 200 + index.html，
# 必须同时校验 Content-Type 为 application/json 且响应体含 "ok":true 才算业务接口存活。
API_SAMPLE_PATH = os.environ.get(
    "API_SAMPLE_PATH",
    "/api/screen,/api/backtest/walk-forward,/api/suitability,/api/optimize",
)
API_JSON_KEY = os.environ.get(
    "API_JSON_KEY", '"ok":true'
)  # 响应体必须包含的 JSON 键（含引号）
API_CTYPE = os.environ.get(
    "API_CTYPE", "application/json"
)  # 期望的 Content-Type（含即通过）

UA = os.environ.get(
    "UA",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
)
TIMEOUT = int(os.environ.get("TIMEOUT", "20"))  # 请求超时秒数
# ---------------------------------------------------------------------------

FAIL = [False]  # 用列表以便闭包内修改


def now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{now()}] {msg}")


def pass_(msg: str) -> None:
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    FAIL[0] = True


def http_get(
    url: str, headers: dict | None = None, timeout: int = TIMEOUT
) -> tuple[int, str, str]:
    """GET 请求，返回 (HTTP状态码, 响应文本, Content-Type)。无法连接时返回 (-1, '', '')。"""
    h = {
        "User-Agent": UA,
        "Accept": "application/vnd.github+json, text/html, */*",
    }
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            body = resp.read().decode("utf-8", errors="replace")
            ctype = resp.headers.get("Content-Type", "")
            return code, body, ctype
    except urllib.error.HTTPError as e:
        return e.code, "", e.headers.get("Content-Type", "") if e.headers else ""
    except urllib.error.URLError as e:
        print(f"  请求失败 {url}: {e.reason}")
        return -1, "", ""


def usage() -> None:
    help_text = """三层验证法 - 通用脚本模板 (Python 版)

用途：判定一次部署是否真正上线，必须三层证据全部通过：
  第1层 GitHub Actions 构建结果   -> 构建通过（代码/镜像链路 OK）
  第2层 平台空间实例状态          -> 实例在线（运行平台 OK）
  第3层 公网 Demo 端到端         -> 公网可用（用户可访问 OK）

用法：
  python verify_3layer.py                                # 全量验证
  python verify_3layer.py --layer 1                      # 只验第1层
  python verify_3layer.py --layer 1,3                    # 验第1+3层
  GH_TOKEN=ghp_xxx python verify_3layer.py               # 用环境变量给 token

通用示例（魔搭 + GitHub Actions）：
  GH_REPO=myorg/myapp \\
  STUDIO_URL=https://modelscope.cn/studios/owner/myapp \\
  PUBLIC_BASE_URL=https://<uid>-myapp.ms.show \\
  python verify_3layer.py

全部参数均可通过同名环境变量覆盖，见脚本顶部"可配置区"。"""
    print(help_text)
    sys.exit(0)


def parse_args(argv: list[str]) -> str:
    layers = "1,2,3"
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--layer":
            if i + 1 >= len(argv) or not argv[i + 1]:
                print("错误: --layer 需要一个值，如 1 或 1,3")
                sys.exit(2)
            layers = argv[i + 1]
            i += 2
        elif a in ("-h", "--help"):
            usage()
        else:
            print(f"未知参数: {a} (用 --help 查看用法)")
            sys.exit(2)
    return layers


def want(layer: int, layers: str) -> bool:
    return f",{layers},".find(f",{layer},") >= 0


# ---------------------------------------------------------------------------
# 第1层：GitHub Actions 构建结果
# ---------------------------------------------------------------------------
def layer1(layers: str) -> None:
    print("===== 第1层: GitHub Actions 构建结果 =====")
    global GH_TOKEN
    if not GH_REPO:
        print("  未配置 GH_REPO，跳过第1层")
        return

    if not GH_TOKEN and GH_TOKEN_FILE and os.path.isfile(GH_TOKEN_FILE):
        try:
            content = open(GH_TOKEN_FILE, encoding="utf-8", errors="replace").read()
            m = re.search(r"ghp_[A-Za-z0-9]*", content)
            if m:
                GH_TOKEN = m.group(0)
        except OSError as e:
            print(f"  token 文件读取失败: {e}")

    headers = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        headers["Authorization"] = f"token {GH_TOKEN}"
    else:
        print(
            "  警告: 无 GH_TOKEN/GH_TOKEN_FILE，只能看最新一次 run 结论，无法核对 commit"
        )

    code, body, _ = http_get(
        f"https://api.github.com/repos/{GH_REPO}/actions/runs?per_page=8", headers
    )
    if code != 200 or not body:
        fail(f"GitHub API 无响应/异常 (HTTP {code})")
        return

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        fail("GitHub API 返回非 JSON（token 无效或仓库不存在？）")
        return

    runs = [
        r
        for r in data.get("workflow_runs", [])
        if WORKFLOW_KEY.lower() in r.get("name", "").lower()
    ]
    if not runs:
        fail(f"未找到名称含 [{WORKFLOW_KEY}] 的 run")
        return

    r = runs[0]
    name = r.get("name", "")[:40]
    sha = r.get("head_sha", "")[:7]
    conc = f"{r.get('status')}/{r.get('conclusion')}"
    print(f"  最新匹配 run: {name} | {sha} | {conc}")

    if conc != "completed/success":
        fail("最新 run 结论非 success")
        return
    if EXPECT_SHA and sha != EXPECT_SHA:
        fail(f"HEAD 不匹配: 期望 {EXPECT_SHA}, 实际 {sha} (构建的是旧提交?)")
        return
    pass_(f"构建结论 success 且 HEAD={sha}" if EXPECT_SHA else "构建结论 success")


# ---------------------------------------------------------------------------
# 第2层：平台空间实例状态
# ---------------------------------------------------------------------------
def layer2(layers: str) -> None:
    print("===== 第2层: 平台实例状态 =====")
    if not STUDIO_URL:
        print("  未配置 STUDIO_URL，跳过第2层")
        return

    code, page, _ = http_get(
        STUDIO_URL, {"Accept": "text/html,application/xhtml+xml,*/*"}
    )
    if code != 200 or not page:
        fail(f"空间页无响应: {STUDIO_URL} (HTTP {code})")
        return

    try:
        compiled = re.compile(STATUS_PATTERN)
        values = sorted(set(compiled.findall(page)))
    except re.error as e:
        fail(f"STATUS_PATTERN 正则无效: {e}")
        return

    hits = [v for v in values if STATUS_EXPECT in v]
    if hits:
        pass_(f"实例状态命中 [{STATUS_EXPECT}]（命中值: {hits[0]}）")
    else:
        fail(
            f"未找到状态 [{STATUS_EXPECT}]；页面 {len(page)} 字节，可能未运行/构建失败/页面结构变化"
        )


# ---------------------------------------------------------------------------
# 第3层：公网 Demo 端到端
# ---------------------------------------------------------------------------
def layer3(layers: str) -> None:
    print("===== 第3层: 公网 Demo 端到端 =====")
    if not PUBLIC_BASE_URL:
        print("  未配置 PUBLIC_BASE_URL，跳过第3层")
        return

    code, _, _ = http_get(f"{PUBLIC_BASE_URL}/")
    print(f"  主页 HTTP {code}")
    if code == 200:
        pass_("主页 200")
    else:
        fail(f"主页非 200 (实际 {code})")

    code, health, _ = http_get(f"{PUBLIC_BASE_URL}{HEALTH_PATH}")
    print(f"  {HEALTH_PATH}: {health[:200]}")
    if HEALTH_EXPECT in health:
        pass_(f"{HEALTH_PATH} 含 [{HEALTH_EXPECT}]")
    else:
        fail(f"{HEALTH_PATH} 未含 [{HEALTH_EXPECT}]")

    # 业务接口抽查：支持逗号分隔多个路径；判据 = HTTP 200
    # + Content-Type 含 application/json + 响应体含 "ok":true
    # （防 SPA fallback：未知路径也返回 200+HTML，仅看状态码会误报）
    if API_SAMPLE_PATH:
        for _p in [p.strip() for p in API_SAMPLE_PATH.split(",") if p.strip()]:
            apicode, abody, actype = http_get(f"{PUBLIC_BASE_URL}{_p}")
            ctype_ok = API_CTYPE.lower() in actype.lower()
            json_ok = abody.strip() and API_JSON_KEY in abody
            ok = apicode == 200 and ctype_ok and json_ok
            print(
                f"  业务接口 {_p} HTTP {apicode} | Content-Type: {actype or '(空)'} "
                f"| JSON[{API_JSON_KEY}]: {'是' if json_ok else '否'}"
            )
            if ok:
                pass_(f"业务接口 {_p} 存活：200 + {API_CTYPE} + 含 {API_JSON_KEY}")
            else:
                fail(
                    f"业务接口 {_p} 校验失败（须 200 + {API_CTYPE} + 含 {API_JSON_KEY}；"
                    f"实际 {apicode}/{actype or '无CT'}/{'有key' if json_ok else '无key'}）"
                )


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    layers = parse_args(argv)
    if want(1, layers):
        layer1(layers)
    if want(2, layers):
        layer2(layers)
    if want(3, layers):
        layer3(layers)

    print("")
    if not FAIL[0]:
        print("★★ 所选层全部通过：构建成功 + 实例在线 + 公网可用 ★★")
        return 0
    print("!! 存在失败项：按部署排障流程定位对应层，别跨层猜。")
    print("   (403/网关提示先检查是否带 UA / 是否用错 token 类型)")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
