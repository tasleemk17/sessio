"""The slot arithmetic, checked on fixed dates with its own empty database."""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import slots
from app.db import Base
from app.models import Availability, Booking, Expert, Service, User

MONDAY = date(2026, 11, 2)  # a Monday
NOW = datetime(2026, 11, 2, 0, 0)  # 05:30 in Kolkata, far before the evening windows


@pytest.fixture()
def world():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine, expire_on_commit=False)() as db:
        db.add_all([User(id=1, email="e@x.co", name="Expert", password_hash="x"), User(id=2, email="s@x.co", name="Seeker", password_hash="x")])
        expert = Expert(user_id=1, handle="expert-one", timezone="Asia/Kolkata")
        service = Service(id=1, expert_id=1, kind="call", title="Chat", price_paise=0, duration_min=30)
        db.add_all([expert, service, Availability(expert_id=1, weekday=0, start_min=18 * 60, end_min=20 * 60)])  # Mon 18:00-20:00 IST
        db.commit()
        yield db, expert, service


def utc(h, m=0, day=2):
    return datetime(2026, 11, day, h, m)


def test_a_window_becomes_slots_in_utc(world):
    db, expert, service = world
    # 18:00 IST is 12:30 UTC
    assert slots.available_slots(db, expert, service, MONDAY, 1, now=NOW) == [utc(12, 30), utc(13, 0), utc(13, 30), utc(14, 0)]


def test_other_weekdays_have_no_slots(world):
    db, expert, service = world
    assert slots.available_slots(db, expert, service, date(2026, 11, 3), 1, now=NOW) == []  # Tuesday


def test_slot_length_follows_the_service(world):
    db, expert, service = world
    service.duration_min = 60
    assert slots.available_slots(db, expert, service, MONDAY, 1, now=NOW) == [utc(12, 30), utc(13, 30)]
    service.duration_min = 45  # 120 minutes hold two 45 minute slots, not three
    assert len(slots.available_slots(db, expert, service, MONDAY, 1, now=NOW)) == 2


def test_slots_too_soon_are_removed(world):
    db, expert, service = world
    # at 12:00 UTC with a 2 hour notice, only 14:00 UTC (and later) can still be booked
    assert slots.available_slots(db, expert, service, MONDAY, 1, now=utc(12, 0)) == [utc(14, 0)]
    assert slots.available_slots(db, expert, service, MONDAY, 1, now=utc(15, 0)) == []


def test_a_window_after_midnight_in_india_lands_on_the_previous_utc_day(world):
    db, expert, service = world
    db.add(Availability(expert_id=1, weekday=0, start_min=0, end_min=60))  # Monday 00:00-01:00 IST
    db.commit()
    first = slots.available_slots(db, expert, service, MONDAY, 1, now=datetime(2026, 11, 1, 0, 0))[0]
    assert first == datetime(2026, 11, 1, 18, 30)  # Sunday 18:30 UTC


def _booking(status, start, minutes=30, age_minutes=0):
    return Booking(seeker_id=2, expert_id=1, service_id=1, kind="call", status=status, slot_start=start,
                   slot_end=start + timedelta(minutes=minutes), created_at=NOW - timedelta(minutes=age_minutes))


def test_paid_bookings_block_their_slot_and_neighbours_that_overlap(world):
    db, expert, service = world
    db.add(_booking("paid", utc(13, 0)))
    db.commit()
    assert slots.available_slots(db, expert, service, MONDAY, 1, now=NOW) == [utc(12, 30), utc(13, 30), utc(14, 0)]
    # a longer booking that starts earlier also covers the next slot
    db.add(_booking("paid", utc(13, 30), minutes=60))
    db.commit()
    assert slots.available_slots(db, expert, service, MONDAY, 1, now=NOW) == [utc(12, 30)]


def test_unpaid_bookings_hold_a_slot_only_for_a_while(world):
    db, expert, service = world
    db.add_all([_booking("pending", utc(12, 30), age_minutes=1), _booking("pending", utc(13, 0), age_minutes=60)])
    db.commit()
    free = slots.available_slots(db, expert, service, MONDAY, 1, now=NOW)
    assert utc(12, 30) not in free and utc(13, 0) in free  # the fresh hold blocks, the stale one does not


def test_cancelled_and_expired_bookings_do_not_block(world):
    db, expert, service = world
    db.add_all([_booking("cancelled", utc(12, 30)), _booking("expired", utc(13, 0))])
    db.commit()
    assert len(slots.available_slots(db, expert, service, MONDAY, 1, now=NOW)) == 4


def test_expiring_stale_holds_releases_the_lock(world):
    db, expert, service = world
    old = _booking("pending", utc(13, 0), age_minutes=120)
    old.slot_lock = "1:202611021300"
    db.add(old)
    db.commit()
    slots.expire_stale_holds(db, now=NOW)
    db.refresh(old)
    assert old.status == "expired" and old.slot_lock is None


def test_timezone_names_are_checked():
    assert slots.valid_timezone("Asia/Kolkata") and slots.valid_timezone("America/New_York")
    assert not slots.valid_timezone("Mars/Olympus") and not slots.valid_timezone("")
