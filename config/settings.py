"""
settings.py — Central config loader from environment variables.
All other modules import from here; never read os.environ directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- AI Analysts (Custom Waterfall) ---
import os
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY")


# ── Queue ──────────────────────────────────────────────────────────
QUEUE_PROVIDER     = os.getenv("QUEUE_PROVIDER", "supabase")
SUPABASE_URL       = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY       = os.getenv("SUPABASE_KEY", "")
SUPABASE_TABLE     = os.getenv("SUPABASE_TABLE", "signals")
SQS_QUEUE_URL      = os.getenv("SQS_QUEUE_URL", "")
AWS_REGION         = os.getenv("AWS_REGION", "us-east-1")

# ── Google Sheets ──────────────────────────────────────────────────
SHEETS_SPREADSHEET_ID      = os.environ["SHEETS_SPREADSHEET_ID"]
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

# ── MT5 ───────────────────────────────────────────────────────────
MT5_LOGIN    = int(os.environ["MT5_LOGIN"])
MT5_PASSWORD = os.environ["MT5_PASSWORD"]
MT5_SERVER   = os.environ["MT5_SERVER"]

# ── Risk Controls ──────────────────────────────────────────────────
LIVE_TRADING          = os.getenv("LIVE_TRADING", "False").lower() == "true"
RISK_PCT_PER_TRADE    = float(os.getenv("RISK_PCT_PER_TRADE", "1.0"))
SOFT_LOSS_LIMIT_PCT   = float(os.getenv("SOFT_LOSS_LIMIT_PCT", "-2.0"))
HARD_LOSS_LIMIT_PCT   = float(os.getenv("HARD_LOSS_LIMIT_PCT", "-4.0"))
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "2"))
POLL_INTERVAL_SEC     = int(os.getenv("POLL_INTERVAL_SEC", "4"))

# ── Screener ───────────────────────────────────────────────────────
SCREENER_SYMBOLS              = os.getenv(
    "SCREENER_SYMBOLS",
    "XAUUSD,NAS100,EURUSD,GBPJPY,USDJPY"
).split(",")
SCREENER_ANOMALY_THRESHOLD_MULT = float(os.getenv("SCREENER_ANOMALY_THRESHOLD_MULT", "2.0"))
SCREENER_COOLDOWN_SEC           = int(os.getenv("SCREENER_COOLDOWN_SEC", "1800"))
SCREENER_POLL_SEC               = int(os.getenv("SCREENER_POLL_SEC", "5"))
SCREENER_ATR_PERIOD             = int(os.getenv("SCREENER_ATR_PERIOD", "14"))

# ── System ─────────────────────────────────────────────────────────
APP_MAGIC_NUMBER = 20260425   # MT5 magic number to tag our orders
MAX_RETRIES      = 2
RETRY_WAIT_SEC   = 3
