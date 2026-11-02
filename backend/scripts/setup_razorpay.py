"""Sets up Razorpay TEST payments for a local run, without the keys ever passing through a chat or a shell history.

It asks for the Key Id and Key Secret with hidden input, refuses anything that is not a test key, checks that
Razorpay accepts them (by creating a 1 rupee test order, which moves no money), and writes backend/.env.

Run from the backend folder:  .venv\\Scripts\\python scripts\\setup_razorpay.py
"""

import getpass
import secrets
import sys
from pathlib import Path

import httpx

ENV = Path(__file__).resolve().parent.parent / ".env"
KEYS = ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "JWT_SECRET", "ALLOW_MOCK_PAYMENTS")


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV.is_file():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def check_keys(key_id: str, key_secret: str) -> str | None:
    """None when Razorpay accepts the keys, otherwise a short reason."""
    try:
        res = httpx.post("https://api.razorpay.com/v1/orders", auth=(key_id, key_secret), json={"amount": 100, "currency": "INR", "receipt": "sessio_setup_check"}, timeout=20)
    except httpx.HTTPError:
        return "Could not reach Razorpay. Check your internet connection."
    if res.status_code == 401:
        return "Razorpay rejected these keys (401). Copy the Key Id and Key Secret again, from Test Mode."
    if res.status_code >= 400:
        return f"Razorpay answered with an error ({res.status_code})."
    return None


def main() -> int:
    print("Razorpay TEST mode setup. Nothing you type here is shown or stored anywhere except backend/.env.\n")
    key_id = input("Key Id (starts with rzp_test_): ").strip()
    if not key_id.startswith("rzp_test_"):
        print("\nStopped: that is not a test key. Use Test Mode in the Razorpay dashboard. Live keys move real money and are refused here.")
        return 1
    key_secret = getpass.getpass("Key Secret (hidden): ").strip()
    if len(key_secret) < 10:
        print("\nStopped: the secret looks too short.")
        return 1

    problem = check_keys(key_id, key_secret)
    if problem:
        print(f"\nStopped: {problem}")
        return 1
    print("Razorpay accepted the keys.")

    values = read_env()
    values["RAZORPAY_KEY_ID"], values["RAZORPAY_KEY_SECRET"] = key_id, key_secret
    values.setdefault("RAZORPAY_WEBHOOK_SECRET", secrets.token_urlsafe(32))
    values.setdefault("JWT_SECRET", secrets.token_urlsafe(48))
    values["ALLOW_MOCK_PAYMENTS"] = "false"  # real checkout only: the demo button is switched off
    ENV.write_text("# Local settings. Never commit this file.\n" + "".join(f"{k}={values[k]}\n" for k in KEYS if k in values) + "".join(f"{k}={v}\n" for k, v in values.items() if k not in KEYS), encoding="utf-8")
    print(f"\nSaved to {ENV}")
    print("Restart the API. Booking will now open the real Razorpay window in test mode.")
    print("Test card: 4111 1111 1111 1111, any future expiry, any 3-digit CVV, any name. OTP/Success on the test bank page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
