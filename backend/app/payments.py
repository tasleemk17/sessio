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
