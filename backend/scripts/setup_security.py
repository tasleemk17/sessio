r"""Creates the two secrets Sessio needs, as long random values, and saves them in backend\.env.

  JWT_SECRET               signs the login tokens. Without a strong one anybody could forge a sign-in.
  RAZORPAY_WEBHOOK_SECRET  lets the server trust Razorpay's payment messages. You paste it into Razorpay's webhook form.

Neither value is printed. The webhook secret is copied to the clipboard so you can paste it into Razorpay.
Existing good values are kept. Run from the backend folder:  .venv\Scripts\python scripts\setup_security.py
Replacing JWT_SECRET signs everybody out once (they sign in again). That is expected the first time.
"""

import secrets
import subprocess
import sys
from pathlib import Path

DEFAULT_ENV = Path(__file__).resolve().parent.parent / ".env"
DEV_SECRET = "dev-only-secret-change-me-before-deploying-1234567890"


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig").splitlines() if path.is_file() else []


def get(lines: list[str], key: str) -> str:
    for line in lines:
        if line.startswith(f"{key}="):
            return line.partition("=")[2].strip().strip("\"'")
    return ""


def put(lines: list[str], key: str, value: str) -> list[str]:
    out, done = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            if not done:
                out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    return out


def copy_to_clipboard(text: str) -> bool:
    try:
        subprocess.run(["clip"], input=text.encode("utf-16le"), check=True, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def main(path: Path) -> int:
    lines = read_lines(path)
    changed: list[str] = []

    jwt_secret = get(lines, "JWT_SECRET")
    if len(jwt_secret) < 32 or jwt_secret == DEV_SECRET:
        lines = put(lines, "JWT_SECRET", secrets.token_urlsafe(48))
        changed.append("JWT_SECRET created (48 random bytes). Everyone is signed out once.")
    else:
        changed.append("JWT_SECRET already strong: kept.")

    webhook = get(lines, "RAZORPAY_WEBHOOK_SECRET")
    if len(webhook) < 16:
        webhook = secrets.token_urlsafe(32)
        lines = put(lines, "RAZORPAY_WEBHOOK_SECRET", webhook)
        changed.append("RAZORPAY_WEBHOOK_SECRET created.")
    else:
        changed.append("RAZORPAY_WEBHOOK_SECRET already set: kept.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(f"- {c}" for c in changed))
    print(f"\nSaved in {path}")
    if copy_to_clipboard(webhook):
        print("The webhook secret is now on your clipboard: paste it into Razorpay's 'Secret' box. Do not paste it anywhere else.")
    else:
        print("Could not use the clipboard. Open backend\\.env in Notepad and copy the RAZORPAY_WEBHOOK_SECRET value yourself.")
    print("Restart the API so the new secrets are used.")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[sys.argv.index("--env-file") + 1]) if "--env-file" in sys.argv else DEFAULT_ENV
    sys.exit(main(target))
