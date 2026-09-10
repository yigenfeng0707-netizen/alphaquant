from pathlib import Path
import os

APP_NAME = "AlphaQuant"
APP_VERSION = "0.2.0-p1"
DISCLAIMER = "演示系统：非实盘交易、非真实持仓、非收益承诺。"

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_DIR = ROOT / "data" / "offline"
AUDIT_DIR = ROOT / "data" / "audit"
REPORTS_DIR = ROOT / "data" / "reports"
AKSHARE_TIMEOUT_SEC = 8.0
AKSHARE_OVERALL_SEC = 20.0
AKSHARE_FUND_SEC = 45.0
TRADING_DAYS = 252
DEFAULT_COST = 0.0015
DEFAULT_CAPITAL = 100_000.0
CASE2_NOTIONAL = 100_000_000.0
CASE1_TOP_N = 10
RNG_SEED = 20260909
SLIPPAGE_COEF = 0.001  # sqrt-impact coefficient: slippage = coef * sqrt(turnover_ratio)

# ---------------------------------------------------------------------------
# LLM / 多模态 API 配置（非策略用途：报告摘要 / FAQ 辅助 / 配图 / 语音合成）
# SCOPE.md 红线：禁止 LLM 生成交易策略、禁止支付计费、禁止实盘交易。
# 凭据从 .env 读取，不硬编码；.env 已被 .gitignore 忽略。
# ---------------------------------------------------------------------------

# 阶跃星辰
STEP_API_KEY = os.environ.get("STEP_API_KEY", "")
STEP_BASE_URL = os.environ.get("STEP_BASE_URL", "https://api.stepfun.com/step_plan/v1")
STEP_MODEL_PRIMARY = os.environ.get("STEP_MODEL_PRIMARY", "step-3.7-flash")
STEP_MODEL_VISION = os.environ.get("STEP_MODEL_VISION", "step-router-v1")
STEP_MODEL_VOICE = os.environ.get("STEP_MODEL_VOICE", "stepaudio-2.5-tts")
STEP_MODEL_FALLBACK1 = os.environ.get("STEP_MODEL_FALLBACK1", "step-3.5-flash-2603")

# 商汤 SenseNova（文本）
SENSENOVA_API_KEY = os.environ.get("SENSENOVA_API_KEY", "")
SENSENOVA_BASE_URL = os.environ.get(
    "SENSENOVA_BASE_URL", "https://token.sensenova.cn/v1"
)
SENSENOVA_MODEL_ID = os.environ.get("SENSENOVA_MODEL_ID", "sensenova-6.8-flash-lite")

# 商汤 SenseNova（图像）
SENSENOVA_IMAGE_API_KEY = os.environ.get("SENSENOVA_IMAGE_API_KEY", "")
SENSENOVA_IMAGE_BASE_URL = os.environ.get(
    "SENSENOVA_IMAGE_BASE_URL", "https://token.sensenova.cn/v1"
)
SENSENOVA_IMAGE_MODEL_ID = os.environ.get(
    "SENSENOVA_IMAGE_MODEL_ID", "sensenova-u1.5-lite"
)

# 奇绩算力（OpenAI 协议兼容中转）— 按量文本/对话
QIJI_API_KEY = os.environ.get("QIJI_API_KEY", "")
QIJI_BASE_URL = os.environ.get("QIJI_BASE_URL", "https://api.openai-next.com/v1")
QIJI_MODEL_TEXT = os.environ.get("QIJI_MODEL_TEXT", "gpt-5.6-sol")

# 奇绩算力 — 按次图像生成
QIJI_IMAGE_API_KEY = os.environ.get("QIJI_IMAGE_API_KEY", "")
QIJI_IMAGE_BASE_URL = os.environ.get(
    "QIJI_IMAGE_BASE_URL", "https://draw.openai-next.com/v1"
)
QIJI_IMAGE_MODEL_ID = os.environ.get("QIJI_IMAGE_MODEL_ID", "gpt-image-2-vip")

# LLM 请求超时（秒）
LLM_TIMEOUT_SEC = float(os.environ.get("LLM_TIMEOUT_SEC", "30.0"))

# LLM 是否启用（未配置 API_KEY 时自动降级为本地回退）
LLM_ENABLED = bool(
    STEP_API_KEY
    or SENSENOVA_API_KEY
    or SENSENOVA_IMAGE_API_KEY
    or QIJI_API_KEY
    or QIJI_IMAGE_API_KEY
)
