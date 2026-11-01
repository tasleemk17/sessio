"""Payments through Razorpay Checkout, with a mock mode for offline use.

The flow Razorpay asks for:
  1. the server creates an order for the amount (in paise) and keeps the order id,
  2. the browser opens Checkout with that order id and the PUBLIC key id,
  3. Checkout hands back the payment id and a signature,
  4. the server recomputes HMAC-SHA256("<order_id>|<payment_id>") with the SECRET key and compares.
The secret never leaves the server, and a browser cannot fake step 4."""

import hashlib
import hmac
import logging
import uuid

import httpx
from fastapi import HTTPException

from . import config

log = logging.getLogger("sessio.payments")
ORDERS_URL = "https://api.razorpay.com/v1/orders"


def create_order(amount_paise: int, receipt: str) -> dict:
    """Returns {"mode", "order_id", "key_id"}. key_id is the public key, safe to send to the browser."""
    if config.payment_mode() == "off":
        raise HTTPException(503, "Payments are not switched on for this site")
    if config.payment_mode() == "mock":
        return {"mode": "mock", "order_id": f"mock_{uuid.uuid4().hex[:16]}", "key_id": None}
    try:
        response = httpx.post(
            ORDERS_URL,
            auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET),
            json={"amount": amount_paise, "currency": "INR", "receipt": receipt[:40]},
            timeout=20,
        )
        response.raise_for_status()
        return {"mode": "razorpay", "order_id": response.json()["id"], "key_id": config.RAZORPAY_KEY_ID}
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        # Log the kind of failure only: never the response or the request, they can carry the key
        log.warning("Razorpay order failed: %s", type(exc).__name__)
        raise HTTPException(502, "The payment provider is not answering. Please try again in a moment.")


def signature_for(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def verify(order_id: str, payment_id: str | None, signature: str | None) -> bool:
    """True when the payment is genuine. In mock mode only mock orders are accepted, and a real order id can
    never be paid with the mock button."""
    if order_id.startswith("mock_"):
        return config.payment_mode() == "mock"
    if config.payment_mode() != "razorpay" or not payment_id or not signature:
        return False
    return hmac.compare_digest(signature_for(order_id, payment_id, config.RAZORPAY_KEY_SECRET), signature)


def verify_webhook(raw_body: bytes, signature: str | None) -> bool:
    """Razorpay signs the exact bytes it sends with HMAC-SHA256 and the webhook secret. The raw body is checked, not
    a re-encoded copy of the JSON, because any difference in spacing would change the signature."""
    if not config.RAZORPAY_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(config.RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------- memberships (Razorpay Subscriptions)

API = "https://api.razorpay.com/v1"


def _razorpay(path: str, payload: dict) -> dict:
    try:
        response = httpx.post(f"{API}{path}", auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET), json=payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("Razorpay %s failed: %s", path.split("/")[1], type(exc).__name__)  # the kind only, never the body
        raise HTTPException(502, "The payment provider is not answering. Please try again in a moment.")


def create_subscription(plan_id: str | None, title: str, amount_paise: int) -> dict:
    """Returns {"mode", "subscription_id", "key_id", "plan_id"}. A Razorpay plan is made once per membership."""
    if config.payment_mode() == "off":
        raise HTTPException(503, "Payments are not switched on for this site")
    if config.payment_mode() == "mock":
        return {"mode": "mock", "subscription_id": f"mock_sub_{uuid.uuid4().hex[:16]}", "key_id": None, "plan_id": plan_id}
    if not plan_id:
        plan_id = _razorpay("/plans", {"period": "monthly", "interval": 1, "item": {"name": title[:60], "amount": amount_paise, "currency": "INR"}})["id"]
    sub = _razorpay("/subscriptions", {"plan_id": plan_id, "total_count": 12, "customer_notify": 0})
    return {"mode": "razorpay", "subscription_id": sub["id"], "key_id": config.RAZORPAY_KEY_ID, "plan_id": plan_id}


def verify_subscription(subscription_id: str, payment_id: str | None, signature: str | None) -> bool:
    """For subscriptions Razorpay signs "<payment_id>|<subscription_id>", the other way round from an order."""
    if subscription_id.startswith("mock_sub_"):
        return config.payment_mode() == "mock"
    if config.payment_mode() != "razorpay" or not payment_id or not signature:
        return False
    expected = hmac.new(config.RAZORPAY_KEY_SECRET.encode(), f"{payment_id}|{subscription_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def cancel_subscription(subscription_id: str) -> None:
    """Stops the next monthly charge. The month already paid for stays usable."""
    if subscription_id.startswith("mock_sub_"):
        return
    _razorpay(f"/subscriptions/{subscription_id}/cancel", {"cancel_at_cycle_end": 1})
