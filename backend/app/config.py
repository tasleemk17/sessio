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


def _flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# "production" turns the safety checks below from warnings into refusals to start. The Docker image and the
# Render blueprint set it; a laptop run is "development".
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
PRODUCTION = ENVIRONMENT == "production"

# SQLite works with zero setup. For Postgres (Neon, Supabase...) set DATABASE_URL to the URL as the host gives it.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sessio.db")

DEV_JWT_SECRET = "dev-only-secret-change-me-before-deploying-1234567890"
JWT_SECRET = os.getenv("JWT_SECRET", DEV_JWT_SECRET)
# OWASP's guidance for PBKDF2-HMAC-SHA256. Tests lower it to stay fast; hashes remember their own count, so the
# number can be raised later and old passwords are upgraded the next time their owner signs in.
PBKDF2_ITERATIONS = int(os.getenv("PBKDF2_ITERATIONS", "600000"))
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "24"))

# Exact origins only, never "*". The site's own address is the only one that should be listed.
CORS_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "http://localhost:5190").split(",") if o.strip()]

# Razorpay test keys (rzp_test_...). With both set, payments go through Razorpay Checkout.
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "").strip()
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
# Razorpay calls the server on this address when a payment succeeds, even if the buyer closed the tab. The secret
# is the one typed into the webhook form in the Razorpay dashboard; it is not the API secret.
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()

# Without keys the app can run in "mock" mode: a Pay button that confirms any booking. That is only safe on a
# laptop or a clearly labelled demo, because anybody can then get anything for free. In production it must be
# switched on on purpose.
ALLOW_MOCK_PAYMENTS = _flag("ALLOW_MOCK_PAYMENTS", not PRODUCTION)

PLATFORM_FEE_PERCENT = int(os.getenv("PLATFORM_FEE_PERCENT", "10"))  # shown in the expert's earnings
HOLD_MINUTES = int(os.getenv("HOLD_MINUTES", "15"))  # how long an unpaid booking keeps its slot
MAX_PENDING_HOLDS = int(os.getenv("MAX_PENDING_HOLDS", "3"))  # unpaid bookings one person may hold at once
MAX_SERVICES = int(os.getenv("MAX_SERVICES", "20"))  # per expert
MIN_NOTICE_HOURS = int(os.getenv("MIN_NOTICE_HOURS", "2"))  # a slot cannot be booked closer than this
MAX_FILE_MB = int(os.getenv("MAX_FILE_MB", "5"))
MEETING_BASE = os.getenv("MEETING_BASE", "https://meet.jit.si")  # free video rooms, no account needed

RATE_LIMITS_ENABLED = _flag("RATE_LIMITS_ENABLED", True)
# Set to true only behind a proxy you trust (Render, nginx): the client address is then read from X-Forwarded-For.
TRUST_PROXY = _flag("TRUST_PROXY", False)


def payment_mode() -> str:
    if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
        return "razorpay"
    return "mock" if ALLOW_MOCK_PAYMENTS else "off"


def startup_problems() -> list[str]:
    """Things that make a production server unsafe. Empty when the settings are fine."""
    problems = []
    if JWT_SECRET == DEV_JWT_SECRET or len(JWT_SECRET) < 32:
        problems.append("JWT_SECRET must be set to a random value of at least 32 characters")
    if "*" in CORS_ORIGINS:
        problems.append("CORS_ORIGINS must list the site's exact address, not *")
    if any(o.startswith("http://") and "localhost" not in o and "127.0.0.1" not in o for o in CORS_ORIGINS):
        problems.append("CORS_ORIGINS must use https")
    if bool(RAZORPAY_KEY_ID) != bool(RAZORPAY_KEY_SECRET):
        problems.append("Set both RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET, or neither")
    if payment_mode() == "off":
        problems.append("No payment method: add Razorpay keys, or set ALLOW_MOCK_PAYMENTS=true for a labelled demo")
    if DATABASE_URL.startswith("sqlite") and PRODUCTION:
        problems.append("Use Postgres (DATABASE_URL) in production: a SQLite file is lost when the container restarts")
    return problems
