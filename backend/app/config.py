from pathlib import Path

APP_NAME = "AlphaQuant"
APP_VERSION = "0.2.0-p1"
DISCLAIMER = "演示系统：非实盘交易、非真实持仓、非收益承诺。"

ROOT = Path(__file__).resolve().parents[2]
OFFLINE_DIR = ROOT / "data" / "offline"
AUDIT_DIR = ROOT / "data" / "audit"
REPORTS_DIR = ROOT / "data" / "reports"
AKSHARE_TIMEOUT_SEC = 8.0
AKSHARE_OVERALL_SEC = 20.0
TRADING_DAYS = 252
DEFAULT_COST = 0.0015
DEFAULT_CAPITAL = 100_000.0
CASE2_NOTIONAL = 100_000_000.0
CASE1_TOP_N = 10
RNG_SEED = 20260909
