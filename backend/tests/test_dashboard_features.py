"""Categories, webinars and cohorts, packages with credits, memberships, rewards, and account settings."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import timedelta

import pytest

from app import config, payments
from app.db import SessionLocal
from app.models import Subscription, utcnow
from tests.conftest import PASSWORD, add_service, new_expert, new_user, open_every_day
from tests.test_bookings import book, call_setup, slots_for
from tests.test_documents_dm_payments import PDF, upload


def iso(days=0, hours=0):
    return ((utcnow() + timedelta(days=days, hours=hours)).replace(microsecond=0)).isoformat() + "Z"


def pay(client, headers, booking_id):
    res = client.post(f"/api/bookings/{booking_id}/pay", headers=headers, json={})
    assert res.status_code == 200, res.text
    return res.json()


def buy(client, headers, service_id, **extra):
    res = client.post("/api/bookings", headers=headers, json={"service_id": service_id, "note": "", **extra})
    assert res.status_code == 201, res.text
    created = res.json()
    return pay(client, headers, created["booking"]["id"]) if created["payment"] else created["booking"]


def tab(client, headers, name):
    res = client.get("/api/me/bookings", headers=headers, params={"tab": name})
    assert res.status_code == 200, res.text
    return res.json()


def webinar(client, headers, price=300, seats=2, dates=None, **extra):
    body = {"kind": "webinar", "title": "Resume workshop", "price_rupees": price, "duration_min": 60, "capacity": seats,
            "sessions": dates or [iso(days=3)], **extra}
    res = client.post("/api/expert/services", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------- categories

def test_experts_can_be_found_by_category(client):
    headers, handle = new_expert(client, "catty")
    assert client.put("/api/expert/me", headers=headers, json={"headline": "x", "bio": "", "timezone": "Asia/Kolkata", "category": "finance"}).status_code == 200
    add_service(client, headers)
    found = client.get("/api/experts", params={"category": "finance"}).json()
    assert handle in [e["handle"] for e in found] and all(e["category"] == "finance" for e in found)
    assert handle not in [e["handle"] for e in client.get("/api/experts", params={"category": "design"}).json()]
    assert client.get("/api/experts", params={"category": "nonsense"}).status_code == 422
    listing = {c["key"]: c["experts"] for c in client.get("/api/experts/categories").json()}
    assert listing["finance"] >= 1 and "other" in listing
    assert client.put("/api/expert/me", headers=headers, json={"headline": "", "bio": "", "timezone": "Asia/Kolkata", "category": "hacking"}).status_code == 422


# ---------------------------------------------------------------- webinars and cohorts

def test_webinar_rules(client):
    headers, _ = new_expert(client)
    base = {"kind": "webinar", "title": "Resume workshop", "price_rupees": 100, "duration_min": 60, "capacity": 5, "sessions": [iso(days=2)]}
    post = lambda **o: client.post("/api/expert/services", headers=headers, json={**base, **o}).status_code
    assert post() == 201
    assert post(sessions=[]) == 422  # at least one date
    assert post(sessions=[iso(days=-1)]) == 422  # the past
    assert post(sessions=[iso(days=2), iso(days=2)]) == 422  # a date twice
    assert post(capacity=None) == 422
    assert post(duration_min=None) == 422
    cohort = webinar(client, headers, dates=[iso(days=2), iso(days=9), iso(days=16)])
    assert len(cohort["sessions"]) == 3 and cohort["spots_left"] == 2


def test_webinar_seats_are_limited_and_one_per_person(client):
    headers, handle = new_expert(client)
    service = webinar(client, headers, seats=2)
    a, b, c = new_user(client), new_user(client), new_user(client)
    made = client.post("/api/bookings", headers=a, json={"service_id": service["id"]})
    assert made.status_code == 201
    assert client.post("/api/bookings", headers=a, json={"service_id": service["id"]}).status_code == 409  # a second seat for the same person
    pay(client, a, made.json()["booking"]["id"])
    buy(client, b, service["id"])
    assert client.get(f"/api/experts/{handle}").json()["services"][0]["spots_left"] == 0
    assert client.post("/api/bookings", headers=c, json={"service_id": service["id"]}).status_code == 409  # full


def test_webinar_shows_in_upcoming_with_one_shared_room(client):
    headers, _ = new_expert(client)
    service = webinar(client, headers, dates=[iso(days=2), iso(days=9)], seats=5)
    a, b = new_user(client), new_user(client)
    one, two = buy(client, a, service["id"]), buy(client, b, service["id"])
    assert one["meeting_link"] and one["meeting_link"] == two["meeting_link"]
    assert len(one["sessions"]) == 2 and one["reference"].startswith("SES-")
    assert [x["id"] for x in tab(client, a, "webinar-upcoming")] == [one["id"]]
    assert tab(client, a, "webinar-past") == []


def test_a_webinar_with_buyers_cannot_change_its_promise(client):
    headers, _ = new_expert(client)
    service = webinar(client, headers, seats=5)
    buy(client, new_user(client), service["id"])
    body = {"kind": "webinar", "title": "Renamed", "description": "", "price_rupees": 300, "duration_min": 60, "capacity": 5, "sessions": service["sessions"]}
    put = lambda **o: client.put(f"/api/expert/services/{service['id']}", headers=headers, json={**body, **o})
    assert put().status_code == 200  # the text can change
    assert put(price_rupees=1).status_code == 409
    assert put(sessions=[iso(days=30)]).status_code == 409
    assert put(capacity=0).status_code == 422
    assert client.delete(f"/api/expert/services/{service['id']}", headers=headers).status_code == 409


# ---------------------------------------------------------------- packages

def package_shop(client, credits=3, price=1200, valid_days=30):
    headers, handle, call = call_setup(client, price=500)
    body = {"kind": "package", "title": "3 sessions", "price_rupees": price, "call_service_id": call["id"], "credits": credits, "valid_days": valid_days}
    res = client.post("/api/expert/services", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return headers, handle, call, res.json()


def test_package_rules(client):
    headers, handle, call = call_setup(client)
    other_headers, _, other_call = call_setup(client)
    post = lambda **o: client.post("/api/expert/services", headers=headers, json={"kind": "package", "title": "Bundle", "price_rupees": 900, "call_service_id": call["id"], "credits": 3, "valid_days": 30, **o}).status_code
    assert post() == 201
    assert post(call_service_id=other_call["id"]) == 422  # somebody else's call
    assert post(call_service_id=None) == 422
    assert post(credits=1) == 422 and post(valid_days=1) == 422
    assert client.delete(f"/api/expert/services/{call['id']}", headers=headers).status_code == 409  # a package stands on it


def test_credits_pay_for_calls_until_they_run_out(client):
    headers, handle, call, package = package_shop(client, credits=2)
    buyer = new_user(client)
    bought = buy(client, buyer, package["id"])
    assert bought["valid_until"] and bought["package_total"] == 2 and bought["package_used"] == 0
    slots = slots_for(client, handle, call["id"], days=1)
    first = client.post("/api/bookings", headers=buyer, json={"service_id": call["id"], "slot_start": slots[0], "package_booking_id": bought["id"]})
    assert first.status_code == 201 and first.json()["payment"] is None  # no payment: the credit pays
    assert first.json()["booking"]["status"] == "paid" and first.json()["booking"]["amount_paise"] == 0 and first.json()["booking"]["via_package"]
    assert first.json()["booking"]["meeting_link"]
    second = client.post("/api/bookings", headers=buyer, json={"service_id": call["id"], "slot_start": slots[1], "package_booking_id": bought["id"]})
    assert second.status_code == 201
    third = client.post("/api/bookings", headers=buyer, json={"service_id": call["id"], "slot_start": slots[2], "package_booking_id": bought["id"]})
    assert third.status_code == 409  # both credits are used
    assert tab(client, buyer, "package-active") == [] and [p["id"] for p in tab(client, buyer, "package-past")] == [bought["id"]]


def test_a_package_belongs_to_one_buyer_and_one_call(client):
    headers, handle, call, package = package_shop(client)
    other_call = add_service(client, headers, title="A different call", price_rupees=700)
    buyer, stranger = new_user(client), new_user(client)
    bought = buy(client, buyer, package["id"])
    assert [p["id"] for p in tab(client, buyer, "package-active")] == [bought["id"]]
    slot = slots_for(client, handle, call["id"])[0]
    steal = client.post("/api/bookings", headers=stranger, json={"service_id": call["id"], "slot_start": slot, "package_booking_id": bought["id"]})
    assert steal.status_code == 404  # not their package
    wrong = client.post("/api/bookings", headers=buyer, json={"service_id": other_call["id"], "slot_start": slot, "package_booking_id": bought["id"]})
    assert wrong.status_code == 422  # the package is for another call
    not_a_call = client.post("/api/bookings", headers=buyer, json={"service_id": package["id"], "package_booking_id": bought["id"]})
    assert not_a_call.status_code == 422


def test_credits_expire(client):
    headers, handle, call, package = package_shop(client, valid_days=7)
    buyer = new_user(client)
    bought = buy(client, buyer, package["id"])
    day = (utcnow() + timedelta(days=9)).date().isoformat()
    late = client.get(f"/api/experts/{handle}/slots", params={"service_id": call["id"], "days": 1, "from_date": day}).json()["slots"][0]
    res = client.post("/api/bookings", headers=buyer, json={"service_id": call["id"], "slot_start": late, "package_booking_id": bought["id"]})
    assert res.status_code == 409 and "run out" in res.json()["detail"]  # the credits are gone by then


# ---------------------------------------------------------------- memberships

def member_shop(client, price=299):
    headers, handle = new_expert(client, "club")
    doc = add_service(client, headers, kind="document", title="Notes", duration_min=None, price_rupees=999)
    assert upload(client, headers, doc["id"], data=PDF).status_code == 200
    res = client.post("/api/expert/services", headers=headers, json={"kind": "membership", "title": "Monthly club", "price_rupees": price})
    assert res.status_code == 201, res.text
    return headers, handle, doc, res.json()


def join(client, headers, service_id):
    made = client.post("/api/subscriptions", headers=headers, json={"service_id": service_id})
    assert made.status_code == 201, made.text
    sub = made.json()["subscription"]
    paid = client.post(f"/api/subscriptions/{sub['id']}/pay", headers=headers, json={})
    assert paid.status_code == 200, paid.text
    return paid.json()


def test_membership_price_floor_and_no_booking_route(client):
    headers, _ = new_expert(client)
    assert client.post("/api/expert/services", headers=headers, json={"kind": "membership", "title": "Cheap club", "price_rupees": 5}).status_code == 422
    plan = client.post("/api/expert/services", headers=headers, json={"kind": "membership", "title": "Club", "price_rupees": 99}).json()
    assert client.post("/api/bookings", headers=new_user(client), json={"service_id": plan["id"]}).status_code == 400


def test_a_member_gets_the_documents_and_a_stranger_does_not(client):
    headers, handle, doc, plan = member_shop(client)
    member, stranger = new_user(client), new_user(client)
    sub = join(client, member, plan["id"])
    assert sub["status"] == "active" and sub["has_access"] and sub["documents_included"] == 1 and sub["payments"] == 1
    listing = client.get(f"/api/me/subscriptions/{sub['id']}/documents", headers=member)
    assert [d["id"] for d in listing.json()] == [doc["id"]]
    download = client.get(f"/api/me/subscriptions/{sub['id']}/documents/{doc['id']}/download", headers=member)
    assert download.status_code == 200 and download.content == PDF and download.headers["content-type"] == "application/octet-stream"
    assert client.get(f"/api/me/subscriptions/{sub['id']}/documents", headers=stranger).status_code == 404
    assert client.get(f"/api/me/subscriptions/{sub['id']}/documents/{doc['id']}/download", headers=stranger).status_code == 404
    assert client.post(f"/api/subscriptions/{sub['id']}/cancel", headers=stranger).status_code == 404
    assert client.get(f"/api/me/subscriptions/{sub['id']}/documents/9999/download", headers=member).status_code == 404
    assert client.post("/api/subscriptions", headers=member, json={"service_id": plan["id"]}).status_code == 409  # already a member


def test_cancelling_keeps_the_month_that_was_paid_for(client):
    headers, handle, doc, plan = member_shop(client)
    member = new_user(client)
    sub = join(client, member, plan["id"])
    cancelled = client.post(f"/api/subscriptions/{sub['id']}/cancel", headers=member).json()
    assert cancelled["status"] == "cancelling" and cancelled["has_access"] and cancelled["cancel_at_period_end"]
    assert client.get(f"/api/me/subscriptions/{sub['id']}/documents", headers=member).status_code == 200


def test_an_ended_membership_loses_access_and_can_be_renewed(client):
    headers, handle, doc, plan = member_shop(client)
    member = new_user(client)
    sub = join(client, member, plan["id"])
    with SessionLocal() as db:
        row = db.get(Subscription, sub["id"])
        row.current_period_end = utcnow() - timedelta(days=1)
        db.commit()
    assert client.get(f"/api/me/subscriptions/{sub['id']}/documents", headers=member).status_code == 403
    assert client.get("/api/me/subscriptions", headers=member).json()[0]["status"] == "expired"
    assert join(client, member, plan["id"])["status"] == "active"  # renewing works


def test_the_membership_demo_button_does_not_work_when_payments_are_off(client, monkeypatch):
    headers, handle, doc, plan = member_shop(client)
    buyer = new_user(client)
    made = client.post("/api/subscriptions", headers=buyer, json={"service_id": plan["id"]}).json()
    monkeypatch.setattr(config, "ALLOW_MOCK_PAYMENTS", False)
    assert client.post(f"/api/subscriptions/{made['subscription']['id']}/pay", headers=buyer, json={}).status_code == 400
    assert client.post("/api/subscriptions", headers=new_user(client), json={"service_id": plan["id"]}).status_code == 503


WEBHOOK = "whsec_dashboard_tests"


@pytest.fixture()
def live_membership(client, monkeypatch):
    """A membership bought through (faked) Razorpay: the network call is replaced, everything else is real code."""
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "api-secret")
    monkeypatch.setattr(config, "RAZORPAY_WEBHOOK_SECRET", WEBHOOK)
    monkeypatch.setattr(payments, "create_subscription", lambda plan, title, amount: {"mode": "razorpay", "subscription_id": f"sub_live_{uuid.uuid4().hex[:12]}", "key_id": "rzp_test_key", "plan_id": "plan_1"})
    stopped = []
    monkeypatch.setattr(payments, "cancel_subscription", lambda sid: stopped.append(sid))
    headers, handle, doc, plan = member_shop(client, price=299)
    member = new_user(client)
    made = client.post("/api/subscriptions", headers=member, json={"service_id": plan["id"]}).json()
    return member, made["subscription"]["id"], made["payment"]["subscription_id"], stopped


def test_a_real_subscription_needs_razorpays_signature(client, live_membership):
    member, sub_id, provider_id, _ = live_membership
    assert client.post(f"/api/subscriptions/{sub_id}/pay", headers=member, json={}).status_code == 400
    forged = {"razorpay_payment_id": "pay_1", "razorpay_signature": "f" * 64}
    assert client.post(f"/api/subscriptions/{sub_id}/pay", headers=member, json=forged).status_code == 400
    order_style = hmac.new(b"api-secret", f"{provider_id}|pay_1".encode(), hashlib.sha256).hexdigest()  # the wrong way round
    assert client.post(f"/api/subscriptions/{sub_id}/pay", headers=member, json={"razorpay_payment_id": "pay_1", "razorpay_signature": order_style}).status_code == 400
    good = hmac.new(b"api-secret", f"pay_1|{provider_id}".encode(), hashlib.sha256).hexdigest()
    assert client.post(f"/api/subscriptions/{sub_id}/pay", headers=member, json={"razorpay_payment_id": "pay_1", "razorpay_signature": good}).json()["status"] == "active"


def _event(name, provider_id, amount=29900, payment_id="pay_m2", end=None):
    entity = {"id": provider_id, "current_end": end or int(time.time()) + 60 * 86400}
    payload = {"subscription": {"entity": entity}}
    if name == "subscription.charged":
        payload["payment"] = {"entity": {"id": payment_id, "amount": amount, "currency": "INR"}}
    raw = json.dumps({"event": name, "payload": payload}).encode()
    return raw, hmac.new(WEBHOOK.encode(), raw, hashlib.sha256).hexdigest()


def test_the_monthly_charge_extends_the_membership(client, live_membership):
    member, sub_id, provider_id, _ = live_membership
    end = int(time.time()) + 45 * 86400
    raw, sig = _event("subscription.charged", provider_id, end=end)
    assert client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": sig}).status_code == 200
    sub = client.get("/api/me/subscriptions", headers=member).json()[0]
    assert sub["status"] == "active" and sub["payments"] == 1  # the first charge also activates it
    assert abs(time.mktime(time.strptime(sub["current_period_end"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone - end) < 90000
    client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": sig})  # Razorpay retries: nothing doubles
    assert client.get("/api/me/subscriptions", headers=member).json()[0]["payments"] == 1
    again, sig2 = _event("subscription.charged", provider_id, payment_id="pay_m3", end=end + 30 * 86400)
    client.post("/api/payments/webhook", content=again, headers={"x-razorpay-signature": sig2})
    assert client.get("/api/me/subscriptions", headers=member).json()[0]["payments"] == 2


def test_membership_webhook_ignores_forgeries_and_wrong_amounts(client, live_membership):
    member, sub_id, provider_id, _ = live_membership
    raw, _ = _event("subscription.charged", provider_id)
    assert client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": "0" * 64}).status_code == 400
    cheap, sig = _event("subscription.charged", provider_id, amount=100)
    assert client.post("/api/payments/webhook", content=cheap, headers={"x-razorpay-signature": sig}).status_code == 200
    assert client.get("/api/me/subscriptions", headers=member).json() == []  # still pending, so not listed


def test_cancelling_a_live_subscription_stops_razorpay_and_a_halt_ends_renewal(client, live_membership):
    member, sub_id, provider_id, stopped = live_membership
    raw, sig = _event("subscription.charged", provider_id)
    client.post("/api/payments/webhook", content=raw, headers={"x-razorpay-signature": sig})
    assert client.post(f"/api/subscriptions/{sub_id}/cancel", headers=member).json()["status"] == "cancelling"
    assert stopped == [provider_id]
    halted, sig = _event("subscription.halted", provider_id)
    client.post("/api/payments/webhook", content=halted, headers={"x-razorpay-signature": sig})
    sub = client.get("/api/me/subscriptions", headers=member).json()[0]
    assert sub["status"] == "cancelled" and sub["has_access"]  # the paid time still counts


# ---------------------------------------------------------------- rewards and home

def test_rewards_count_what_was_spent(client):
    headers, handle, doc, plan = member_shop(client)
    buyer = new_user(client)
    assert client.get("/api/me/rewards", headers=buyer).json()["points"] == 0
    buy(client, buyer, doc["id"])  # 999 rupees
    join(client, buyer, plan["id"])  # 299 rupees
    rewards = client.get("/api/me/rewards", headers=buyer).json()
    assert rewards["spent_paise"] == 129800 and rewards["points"] == 129 and rewards["tier"] == "Silver"
    assert rewards["next_tier"] == "Gold" and rewards["points_to_next"] == 371 and len(rewards["recent"]) == 2


def test_home_summary(client):
    headers, handle, call = call_setup(client)
    doc = add_service(client, headers, kind="document", title="Guide", duration_min=None, price_rupees=100)
    upload(client, headers, doc["id"], data=PDF)
    dm = add_service(client, headers, kind="dm", title="Ask", duration_min=None, price_rupees=50)
    seeker = new_user(client)
    buy(client, seeker, doc["id"])
    asked = client.post("/api/bookings", headers=seeker, json={"service_id": dm["id"], "note": "How do I start in cloud?"}).json()
    pay(client, seeker, asked["booking"]["id"])
    buy(client, seeker, call["id"], slot_start=slots_for(client, handle, call["id"])[0])
    home = client.get("/api/me/home", headers=seeker).json()
    assert home["documents"] == 1 and home["upcoming_calls"] == 1 and home["pending_replies"] == 1
    assert home["next_session"]["kind"] == "call"
    assert client.get("/api/me/home").status_code == 401


# ---------------------------------------------------------------- account settings

def test_profile_name_can_change(client):
    headers = new_user(client)
    assert client.put("/api/auth/me", headers=headers, json={"name": "A. Better Name"}).json()["name"] == "A. Better Name"
    assert client.put("/api/auth/me", headers=headers, json={"name": "x"}).status_code == 422


def test_changing_the_password_signs_other_sessions_out(client):
    email = "changer@example.com"
    old = client.post("/api/auth/register", json={"name": "Changer Person", "email": email, "password": PASSWORD}).json()["token"]
    time.sleep(1.1)  # tokens are timestamped to the second
    headers = {"Authorization": f"Bearer {old}"}
    assert client.post("/api/auth/password", headers=headers, json={"current_password": "not-the-password", "new_password": "a-brand-new-phrase-1"}).status_code == 400
    assert client.post("/api/auth/password", headers=headers, json={"current_password": PASSWORD, "new_password": "password123"}).status_code == 422  # too weak
    assert client.post("/api/auth/password", headers=headers, json={"current_password": PASSWORD, "new_password": PASSWORD}).status_code == 422  # the same
    changed = client.post("/api/auth/password", headers=headers, json={"current_password": PASSWORD, "new_password": "a-brand-new-phrase-1"})
    assert changed.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401  # the old session is gone
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {changed.json()['token']}"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": "a-brand-new-phrase-1"}).status_code == 200


def test_membership_money_counts_in_the_experts_earnings(client):
    headers, handle, doc, plan = member_shop(client, price=300)
    join(client, new_user(client), plan["id"])
    join(client, new_user(client), plan["id"])
    summary = client.get("/api/expert/summary", headers=headers).json()
    assert summary["gross_paise"] == 60000 and summary["by_kind"]["membership"] == 2 and summary["orders"] == 2
    assert summary["net_paise"] == 54000  # after the 10% fee


def test_changing_the_email_needs_the_password_and_signs_other_sessions_out(client):
    old_email, new_email = "before@example.com", "after@example.com"
    old = client.post("/api/auth/register", json={"name": "Mail Changer", "email": old_email, "password": PASSWORD}).json()["token"]
    other = new_user(client)
    time.sleep(1.1)  # tokens are timestamped to the second
    headers = {"Authorization": f"Bearer {old}"}
    post = lambda **b: client.post("/api/auth/email", headers=headers, json={"new_email": new_email, "current_password": PASSWORD, **b})
    assert post(current_password="not-the-password").status_code == 400
    assert post(new_email="not-an-email").status_code == 422
    assert post(new_email=old_email).status_code == 422  # the same one
    taken = client.get("/api/auth/me", headers=other).json()["email"]
    assert post(new_email=taken).status_code == 409  # somebody else's
    changed = post()
    assert changed.status_code == 200
    assert client.get("/api/auth/me", headers=headers).status_code == 401  # the old session is gone
    fresh = {"Authorization": f"Bearer {changed.json()['token']}"}
    assert client.get("/api/auth/me", headers=fresh).json()["email"] == new_email
    assert client.post("/api/auth/login", json={"email": old_email, "password": PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": new_email, "password": PASSWORD}).status_code == 200
