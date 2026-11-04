"""Security behaviour: passwords, sessions, limits, payments that must not be free, uploads, and webhooks."""

import hashlib
import hmac
import json
import time

import jwt
import pytest
from sqlalchemy import select

from app import config, payments, ratelimit
from app.db import SessionLocal
from app.models import Booking, User
from app.security import hash_password, needs_rehash, verify_password
from tests.conftest import PASSWORD, add_service, new_expert, new_user
from tests.test_bookings import book, call_setup, slots_for
from tests.test_documents_dm_payments import PDF, document_shop, upload


@pytest.fixture()
def limits_on(monkeypatch):
    monkeypatch.setattr(config, "RATE_LIMITS_ENABLED", True)
    ratelimit.reset_all()
    yield
    ratelimit.reset_all()


def register(client, email, password=PASSWORD, name="Test Person"):
    return client.post("/api/auth/register", json={"name": name, "email": email, "password": password})


# ---------------------------------------------------------------- passwords

def test_weak_passwords_are_refused(client):
    assert register(client, "w1@example.com", "short1").status_code == 422
    assert register(client, "w2@example.com", "password123").status_code == 422  # on the common list
    assert register(client, "w3@example.com", "aaaaaaaaaaaa").status_code == 422  # one repeated letter
    assert register(client, "robertson@example.com", "robertson-2024-x").status_code == 422  # contains the email name
    assert register(client, "w5@example.com", "a-long-sentence-works").status_code == 201


def test_hashes_are_salted_and_remember_their_work_factor():
    a, b = hash_password("same-password-1"), hash_password("same-password-1")
    assert a != b  # a random salt each time
    assert a.startswith("pbkdf2$") and verify_password("same-password-1", a) and not verify_password("other", a)
    assert not verify_password("x", "garbage")


def test_an_old_hash_still_works_and_is_upgraded_on_login(client, monkeypatch):
    monkeypatch.setattr(config, "PBKDF2_ITERATIONS", 300_000)  # the real setting is higher than the old format's count
    old_digest = hashlib.pbkdf2_hmac("sha256", b"legacy-password-1", bytes.fromhex("00" * 16), 200_000).hex()
    legacy = f"{'00' * 16}${old_digest}"  # the first format, before the work factor was stored
    assert verify_password("legacy-password-1", legacy) and needs_rehash(legacy)
    with SessionLocal() as db:
        db.add(User(email="legacy@example.com", name="Legacy", password_hash=legacy))
        db.commit()
    assert client.post("/api/auth/login", json={"email": "legacy@example.com", "password": "legacy-password-1"}).status_code == 200
    with SessionLocal() as db:
        stored = db.scalar(select(User.password_hash).where(User.email == "legacy@example.com"))
    assert stored.startswith("pbkdf2$")


def test_login_does_not_reveal_which_emails_exist(client):
    new_user(client, "known")
    wrong_password = client.post("/api/auth/login", json={"email": "known1@example.com", "password": "nope-nope-nope"})
    no_account = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "nope-nope-nope"})
    assert wrong_password.status_code == no_account.status_code == 401
    assert wrong_password.json() == no_account.json()


# ---------------------------------------------------------------- brute force

def test_repeated_wrong_passwords_lock_that_account_for_a_while(client, limits_on):
    register(client, "victim@example.com", "a-long-sentence-works")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "victim@example.com", "password": "wrong-wrong-1"}).status_code == 401
    blocked = client.post("/api/auth/login", json={"email": "victim@example.com", "password": "a-long-sentence-works"})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0  # even the right password waits


def test_a_stranger_cannot_lock_you_out_from_another_address(client, limits_on):
    register(client, "owner@example.com", "a-long-sentence-works")
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong-wrong-1"}, headers={"x-forwarded-for": "6.6.6.6"})
    # The attacker's failures are counted against the attacker's address, not the owner's
    ratelimit.LOGIN_ACCOUNT.clear("owner@example.com|testclient")
    assert client.post("/api/auth/login", json={"email": "owner@example.com", "password": "a-long-sentence-works"}).status_code == 200


def test_registration_is_rate_limited(client, limits_on):
    codes = [register(client, f"bulk{i}@example.com", f"a-long-sentence-{i}x").status_code for i in range(12)]
    assert codes[:10] == [201] * 10 and 429 in codes[10:]


def test_forwarded_header_is_ignored_unless_the_proxy_is_trusted(monkeypatch):
    class Req:
        headers = {"x-forwarded-for": "1.1.1.1, 9.9.9.9"}
        client = type("C", (), {"host": "10.0.0.5"})()

    assert ratelimit.client_ip(Req()) == "10.0.0.5"  # a caller cannot pick their own address
    monkeypatch.setattr(config, "TRUST_PROXY", True)
    assert ratelimit.client_ip(Req()) == "9.9.9.9"  # the last entry is the one our proxy added


# ---------------------------------------------------------------- tokens

def _token(**claims):
    return jwt.encode(claims, config.JWT_SECRET, algorithm="HS256")


def test_forged_and_broken_tokens_are_refused(client):
    uid = client.get("/api/auth/me", headers=new_user(client)).json()["id"]
    good = {"sub": str(uid), "exp": int(time.time()) + 600}
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {_token(**good)}"}).status_code == 200
    expired = _token(sub=str(uid), exp=int(time.time()) - 5)
    no_expiry = _token(sub=str(uid))
    wrong_key = jwt.encode(good, "some-other-secret-some-other-secret-1", algorithm="HS256")
    unsigned = jwt.encode(good, None, algorithm="none")
    for bad in (expired, no_expiry, wrong_key, unsigned, "not.a.token", good["sub"]):
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------- headers, CORS, size

def test_responses_carry_security_headers(client):
    res = client.get("/api/health")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]


def test_only_the_listed_site_may_call_the_api_from_a_browser(client):
    ok = client.get("/api/health", headers={"Origin": "http://localhost:5190"})
    other = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5190"
    assert "access-control-allow-origin" not in other.headers


def test_oversized_bodies_are_refused(client):
    res = client.post("/api/auth/login", content=b"x" * 70_000, headers={"content-type": "application/json"})
    assert res.status_code == 413
    assert res.headers["x-content-type-options"] == "nosniff"  # the refusal still has the safe headers


def test_search_wildcards_are_plain_characters(client):
    headers, _ = new_expert(client, "wild")
    add_service(client, headers)
    assert client.get("/api/experts", params={"q": "%"}).json() == []
    assert client.get("/api/experts", params={"q": "_"}).json() == []
    assert client.get("/api/experts", params={"q": "x" * 81}).status_code == 422


# ---------------------------------------------------------------- production settings

def test_production_refuses_unsafe_settings(monkeypatch):
    monkeypatch.setattr(config, "PRODUCTION", True)
    monkeypatch.setattr(config, "ALLOW_MOCK_PAYMENTS", False)
    monkeypatch.setattr(config, "JWT_SECRET", config.DEV_JWT_SECRET)
    problems = " ".join(config.startup_problems())
    assert "JWT_SECRET" in problems and "payment" in problems.lower()
    monkeypatch.setattr(config, "CORS_ORIGINS", ["*"])
    assert "CORS_ORIGINS" in " ".join(config.startup_problems())


def test_a_site_without_payments_cannot_hand_out_paid_things(client, monkeypatch):
    headers, handle, service = call_setup(client)
    seeker = new_user(client)
    slot = slots_for(client, handle, service["id"])[0]
    pending = book(client, seeker, service["id"], slot)  # made while demo payments were on
    assert pending.status_code == 201
    booking_id = pending.json()["booking"]["id"]

    monkeypatch.setattr(config, "ALLOW_MOCK_PAYMENTS", False)  # what production does by default
    assert client.get("/api/health").json()["payments"] == "off"
    assert client.post(f"/api/bookings/{booking_id}/pay", headers=seeker, json={}).status_code == 400
    again = book(client, new_user(client), service["id"], slots_for(client, handle, service["id"])[1])
    assert again.status_code == 503


# ---------------------------------------------------------------- abuse of holds

def test_one_person_cannot_hold_every_time(client):
    headers, handle, service = call_setup(client)
    seeker = new_user(client)
    slots = slots_for(client, handle, service["id"])
    codes = [book(client, seeker, service["id"], s).status_code for s in slots[: config.MAX_PENDING_HOLDS + 1]]
    assert codes == [201] * config.MAX_PENDING_HOLDS + [429]


def test_nobody_can_touch_someone_elses_booking(client):
    headers, handle, service = call_setup(client)
    owner, stranger = new_user(client), new_user(client)
    booking_id = book(client, owner, service["id"], slots_for(client, handle, service["id"])[0]).json()["booking"]["id"]
    assert client.post(f"/api/bookings/{booking_id}/pay", headers=stranger, json={}).status_code == 404
    assert client.post(f"/api/bookings/{booking_id}/cancel", headers=stranger).status_code == 404
    assert client.get(f"/api/me/bookings/{booking_id}/download", headers=stranger).status_code == 404


# ---------------------------------------------------------------- uploads

def _doc(client):
    headers, _ = new_expert(client, "up")
    doc = add_service(client, headers, kind="document", title="A guide", duration_min=None, price_rupees=100)
    return headers, doc["id"]


def test_a_program_cannot_hide_behind_a_friendly_name(client):
    headers, sid = _doc(client)
    assert upload(client, headers, sid, name="guide.pdf", data=b"MZ\x90\x00 pretend windows program").status_code == 415
    assert upload(client, headers, sid, name="guide.pdf", data=b"#!/bin/sh\nrm -rf /").status_code == 415
    assert upload(client, headers, sid, name="guide.pdf", data=b"just some words").status_code == 415  # not a PDF at all
    assert upload(client, headers, sid, name="notes.txt", data=b"hello\x00world").status_code == 415
    assert upload(client, headers, sid, name="notes.txt", data=b"plain notes").status_code == 200
    assert upload(client, headers, sid, name="guide.pdf", data=PDF).status_code == 200


# ---------------------------------------------------------------- Razorpay webhook

SECRET = "whsec_test_secret_for_unit_tests"


def _signed(body: dict, secret=SECRET):
    raw = json.dumps(body).encode()
    return raw, hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _event(order_id, amount, event="payment.captured", currency="INR"):
    return {"event": event, "payload": {"payment": {"entity": {"id": "pay_test_1", "order_id": order_id, "amount": amount, "currency": currency}}}}


@pytest.fixture()
def razorpay_booking(client, monkeypatch):
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "api-secret")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(payments, "create_order", lambda amount, receipt: {"mode": "razorpay", "order_id": f"order_{receipt}", "key_id": "rzp_test_key"})
    headers, handle, service = call_setup(client, price=500)
    seeker = new_user(client)
    created = book(client, seeker, service["id"], slots_for(client, handle, service["id"])[0]).json()
    return seeker, created["booking"]["id"], created["payment"]["order_id"]


def _status(booking_id):
    with SessionLocal() as db:
        return db.scalar(select(Booking.status).where(Booking.id == booking_id))


def test_webhook_confirms_a_payment_when_the_browser_never_came_back(client, razorpay_booking):
    seeker, booking_id, order_id = razorpay_booking
    raw, sig = _signed(_event(order_id, 50000))
    assert client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": sig}).status_code == 200
    assert _status(booking_id) == "paid"
    assert client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": sig}).status_code == 200  # a retry changes nothing


def test_webhook_rejects_forgeries_and_wrong_amounts(client, razorpay_booking):
    seeker, booking_id, order_id = razorpay_booking
    raw, _ = _signed(_event(order_id, 50000))
    assert client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": "0" * 64}).status_code == 400
    assert client.post("/api/payments/webhook", content=raw).status_code == 400
    forged, sig = _signed(_event(order_id, 50000), secret="someone-elses-secret")
    assert client.post("/api/payments/webhook", content=forged, headers={"x-razorpay-signature": sig}).status_code == 400
    assert _status(booking_id) == "pending"

    cheap, sig = _signed(_event(order_id, 100))  # properly signed, but not the price of this booking
    assert client.post("/api/payments/webhook", content=cheap, headers={"x-razorpay-signature": sig}).status_code == 200
    assert _status(booking_id) == "pending"
    other, sig = _signed(_event(order_id, 50000, event="payment.failed"))
    client.post("/api/payments/webhook", content=other, headers={"x-razorpay-signature": sig})
    assert _status(booking_id) == "pending"


def test_webhook_is_off_when_no_secret_is_configured(client):
    raw, sig = _signed(_event("order_x", 100), secret="")
    assert client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": sig}).status_code == 400


def test_browser_confirmation_needs_a_valid_signature(client, razorpay_booking):
    seeker, booking_id, order_id = razorpay_booking
    assert client.post(f"/api/bookings/{booking_id}/pay", headers=seeker, json={}).status_code == 400
    forged = {"razorpay_payment_id": "pay_1", "razorpay_signature": "f" * 64}
    assert client.post(f"/api/bookings/{booking_id}/pay", headers=seeker, json=forged).status_code == 400
    genuine = {"razorpay_payment_id": "pay_1", "razorpay_signature": payments.signature_for(order_id, "pay_1", "api-secret")}
    assert client.post(f"/api/bookings/{booking_id}/pay", headers=seeker, json=genuine).status_code == 200


def test_a_live_key_is_flagged_outside_production(monkeypatch):
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_live_abc123")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "secret-value-123")
    assert any("LIVE" in p for p in config.startup_problems())


def test_an_empty_line_in_dotenv_counts_as_not_set():
    """JWT_SECRET= copied from .env.example must fall back to the dev default, never become an empty signing key."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    code = "from app import config; print(config.JWT_SECRET == config.DEV_JWT_SECRET, config.DATABASE_URL.startswith('sqlite'), config.CORS_ORIGINS)"
    env = {**os.environ, "JWT_SECRET": "", "DATABASE_URL": "", "CORS_ORIGINS": ""}
    out = subprocess.run([sys.executable, "-c", code], env=env, cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "True True ['http://localhost:5190']", out.stderr


def test_health_says_live_only_for_a_live_razorpay_key(client, monkeypatch):
    """The website hides its "test mode, no real money" notice only when real money really moves."""
    assert client.get("/api/health").json()["live"] is False  # demo payments in tests
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_abc")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "secret")
    assert client.get("/api/health").json() == {"status": "ok", "payments": "razorpay", "live": False}
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_live_abc")
    assert client.get("/api/health").json()["live"] is True
