import os
from pathlib import Path


def _load_env_files() -> None:
    """Reads KEY=VALUE lines from backend/.env and the project .env, so local runs need no exported variables.
    Variables that are already set (Docker, the shell, tests) always win."""
    here = Path(__file__).resolve().parent.parent
    for path in (here / ".env", here.parent / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_files()

# SQLite works with zero setup. For Postgres (Neon, Supabase...) set DATABASE_URL to the URL as the host gives it.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sessio.db")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-deploying-1234567890")
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "72"))

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5190").split(",") if o.strip()]

# Razorpay test keys (rzp_test_...). With both set, payments go through Razorpay Checkout. Without them the
# app runs in "mock" mode: a Pay button that behaves like a successful payment, so everything works offline.
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()

PLATFORM_FEE_PERCENT = int(os.getenv("PLATFORM_FEE_PERCENT", "10"))  # shown in the expert's earnings
HOLD_MINUTES = int(os.getenv("HOLD_MINUTES", "15"))  # how long an unpaid booking keeps its slot
MIN_NOTICE_HOURS = int(os.getenv("MIN_NOTICE_HOURS", "2"))  # a slot cannot be booked closer than this
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "5"))
MEETING_BASE = os.getenv("MEETING_BASE", "https://meet.jit.si")  # free video rooms, no account needed


def payment_mode() -> str:
    return "razorpay" if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET else "mock"
