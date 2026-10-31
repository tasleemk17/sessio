from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Booking, utcnow
from tests.conftest import add_service, new_expert, new_user, open_every_day


def day_after_tomorrow():
    return (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()


def slots_for(client, handle, service_id, days=1):
    res = client.get(f"/api/experts/{handle}/slots", params={"service_id": service_id, "days": days, "from_date": day_after_tomorrow()})
    assert res.status_code == 200, res.text
    return res.json()["slots"]


def call_setup(client, price=500, duration=30):
    headers, handle = new_expert(client)
    open_every_day(client, headers)
    service = add_service(client, headers, price_rupees=price, duration_min=duration)
    return headers, handle, service


def book(client, seeker, service_id, slot, note=""):
    return client.post("/api/bookings", headers=seeker, json={"service_id": service_id, "slot_start": slot, "note": note})


def expire(booking_id):
    """Pretend the booking was made an hour ago, so its hold has run out."""
    with SessionLocal() as db:
        row = db.get(Booking, booking_id)
        row.created_at = utcnow() - timedelta(hours=1)
        db.commit()


def test_a_call_from_choosing_a_slot_to_the_meeting_link(client, seeker):
    expert, handle, service = call_setup(client)
    free = slots_for(client, handle, service["id"])
    assert len(free) == 6  # 18:00-21:00 in 30 minute steps

    created = book(client, seeker, service["id"], free[0], "Resume review")
    assert created.status_code == 201
    body = created.json()
    assert body["booking"]["status"] == "pending" and body["booking"]["amount_paise"] == 50000 and body["booking"]["meeting_link"] is None
    assert body["payment"]["mode"] == "mock" and body["payment"]["order_id"].startswith("mock_") and body["payment"]["key_id"] is None
    assert free[0] not in slots_for(client, handle, service["id"])  # held while the payment is open

    paid = client.post(f"/api/bookings/{body['booking']['id']}/pay", headers=seeker, json={})
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    link = paid.json()["meeting_link"]
    assert link.startswith("https://meet.jit.si/Sessio-")
    assert client.post(f"/api/bookings/{body['booking']['id']}/pay", headers=seeker, json={}).json()["meeting_link"] == link  # idempotent

    upcoming = client.get("/api/me/bookings", headers=seeker, params={"tab": "upcoming"}).json()
    assert [b["id"] for b in upcoming] == [body["booking"]["id"]] and upcoming[0]["note"] == "Resume review"
    assert client.get("/api/me/bookings", headers=seeker, params={"tab": "past"}).json() == []

    sales = client.get("/api/expert/bookings", headers=expert).json()
    assert sales[0]["seeker_name"].startswith("Seeker") and sales[0]["meeting_link"] == link


def test_earnings_summary_shows_the_platform_fee(client, seeker):
    expert, handle, service = call_setup(client, price=1000)
    slot = slots_for(client, handle, service["id"])[0]
    booking = book(client, seeker, service["id"], slot).json()["booking"]
    client.post(f"/api/bookings/{booking['id']}/pay", headers=seeker, json={})
    s = client.get("/api/expert/summary", headers=expert).json()
    assert (s["orders"], s["gross_paise"], s["fee_paise"], s["net_paise"], s["fee_percent"]) == (1, 100000, 10000, 90000, 10)
    assert s["upcoming_calls"] == 1 and s["by_kind"] == {"call": 1}


def test_two_people_cannot_take_the_same_time(client):
    _, handle, service = call_setup(client)
    slot = slots_for(client, handle, service["id"])[0]
    first, second = new_user(client, "seeker"), new_user(client, "seeker")
    assert book(client, first, service["id"], slot).status_code == 201
    assert book(client, second, service["id"], slot).status_code == 409


def test_a_longer_call_cannot_overlap_a_booked_one(client):
    headers, handle = new_expert(client)
    open_every_day(client, headers)
    short = add_service(client, headers, title="Short", duration_min=30)
    long = add_service(client, headers, title="Long", duration_min=60)
    a, b = new_user(client, "seeker"), new_user(client, "seeker")
    eighteen = slots_for(client, handle, long["id"])[0]  # 18:00 local, a 60 minute call that runs until 19:00
    start = slots_for(client, handle, short["id"])[1]  # 18:30 local, a 30 minute call
    assert book(client, a, short["id"], start).status_code == 201
    # the 18:00 call would run into the 18:30 booking, so it is no longer offered and is refused if sent anyway
    assert eighteen not in slots_for(client, handle, long["id"])
    assert book(client, b, long["id"], eighteen).status_code == 409


def test_times_that_are_not_real_slots_are_refused(client, seeker):
    _, handle, service = call_setup(client)
    slot = datetime.fromisoformat(slots_for(client, handle, service["id"])[0].replace("Z", "+00:00"))
    off_grid = (slot + timedelta(minutes=7)).isoformat()
    in_the_past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    outside_hours = (slot - timedelta(hours=10)).isoformat()
    for bad in (off_grid, in_the_past, outside_hours):
        assert book(client, seeker, service["id"], bad).status_code == 409, bad
    assert client.post("/api/bookings", headers=seeker, json={"service_id": service["id"]}).status_code == 422  # no time chosen


def test_nobody_books_their_own_service(client):
    expert, handle, service = call_setup(client)
    slot = slots_for(client, handle, service["id"])[0]
    assert book(client, expert, service["id"], slot).status_code == 400


def test_an_unpaid_hold_runs_out_and_the_slot_returns(client):
    _, handle, service = call_setup(client)
    slot = slots_for(client, handle, service["id"])[0]
    a, b = new_user(client, "seeker"), new_user(client, "seeker")
    first = book(client, a, service["id"], slot).json()["booking"]
    expire(first["id"])
    assert slot in slots_for(client, handle, service["id"])
    assert book(client, b, service["id"], slot).status_code == 201  # b can have it now
    # a late payment for the lost slot is refused with an explanation, not silently accepted
    late = client.post(f"/api/bookings/{first['id']}/pay", headers=a, json={})
    assert late.status_code == 409 and "went through" in late.json()["detail"]


def test_a_payment_that_arrives_after_the_hold_still_works_if_the_slot_is_free(client, seeker):
    _, handle, service = call_setup(client)
    slot = slots_for(client, handle, service["id"])[0]
    booking = book(client, seeker, service["id"], slot).json()["booking"]
    expire(booking["id"])
    slots_for(client, handle, service["id"])  # looking at the slots releases the stale hold
    assert client.post(f"/api/bookings/{booking['id']}/pay", headers=seeker, json={}).json()["status"] == "paid"


def test_cancelling_an_unpaid_booking_frees_the_slot(client, seeker):
    _, handle, service = call_setup(client)
    slot = slots_for(client, handle, service["id"])[0]
    booking = book(client, seeker, service["id"], slot).json()["booking"]
    assert client.post(f"/api/bookings/{booking['id']}/cancel", headers=seeker).json()["status"] == "cancelled"
    assert slot in slots_for(client, handle, service["id"])
    assert client.post(f"/api/bookings/{booking['id']}/pay", headers=seeker, json={}).status_code == 409  # cancelled stays cancelled


def test_a_paid_booking_cannot_be_cancelled_here(client, seeker):
    _, handle, service = call_setup(client)
    booking = book(client, seeker, service["id"], slots_for(client, handle, service["id"])[0]).json()["booking"]
    client.post(f"/api/bookings/{booking['id']}/pay", headers=seeker, json={})
    assert client.post(f"/api/bookings/{booking['id']}/cancel", headers=seeker).status_code == 409


def test_bookings_belong_to_one_person(client, seeker):
    _, handle, service = call_setup(client)
    booking = book(client, seeker, service["id"], slots_for(client, handle, service["id"])[0]).json()["booking"]
    stranger = new_user(client, "seeker")
    assert client.post(f"/api/bookings/{booking['id']}/pay", headers=stranger, json={}).status_code == 404
    assert client.post(f"/api/bookings/{booking['id']}/cancel", headers=stranger).status_code == 404
    assert client.get("/api/me/bookings", headers=stranger, params={"tab": "upcoming"}).json() == []


def test_a_free_call_is_confirmed_at_once(client, seeker):
    _, handle, service = call_setup(client, price=0)
    created = book(client, seeker, service["id"], slots_for(client, handle, service["id"])[0]).json()
    assert created["payment"] is None and created["booking"]["status"] == "paid" and created["booking"]["meeting_link"]


def test_deleting_a_service_that_was_bought_is_refused(client, seeker):
    expert, handle, service = call_setup(client)
    booking = book(client, seeker, service["id"], slots_for(client, handle, service["id"])[0]).json()["booking"]
    client.post(f"/api/bookings/{booking['id']}/pay", headers=seeker, json={})
    assert client.delete(f"/api/expert/services/{service['id']}", headers=expert).status_code == 409
    other = add_service(client, expert, title="Unsold")
    assert client.delete(f"/api/expert/services/{other['id']}", headers=expert).status_code == 204


def test_the_database_itself_refuses_a_double_booking(client):
    """Even if two requests got past the checks together, the unique slot_lock stops the second one."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    _, handle, service = call_setup(client)
    slot = datetime.fromisoformat(slots_for(client, handle, service["id"])[0].replace("Z", "+00:00")).replace(tzinfo=None)
    first = book(client, new_user(client, "seeker"), service["id"], slot.isoformat() + "Z").json()["booking"]
    with SessionLocal() as db:
        original = db.get(Booking, first["id"])
        db.add(Booking(seeker_id=original.seeker_id, expert_id=original.expert_id, service_id=original.service_id, kind="call",
                       slot_start=slot, slot_end=original.slot_end, slot_lock=original.slot_lock))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(Booking.id).where(Booking.id == first["id"])) == first["id"]
