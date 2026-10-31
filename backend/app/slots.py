"""Which times a call can be booked.

An expert sets weekly windows in their own time zone ("Mon 18:00-21:00"). A 30 minute service turns that
into 18:00, 18:30, ... 20:30. Slots that are too soon, or that overlap a paid booking or a booking still
waiting for payment, are removed. Everything is returned in UTC, and the browser shows it in the viewer's
own time zone."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from . import config
from .models import Availability, Booking, Expert, Service, utcnow


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return False


def holding(now: datetime):
    """SQL condition for bookings that currently occupy a slot: paid, or unpaid but still inside the hold time."""
    return or_(
        Booking.status == "paid",
        and_(Booking.status == "pending", Booking.created_at > now - timedelta(minutes=config.HOLD_MINUTES)),
    )


def expire_stale_holds(db: Session, now: datetime | None = None) -> None:
    """Unpaid bookings older than the hold time give their slot back. Done lazily, whenever slots are looked at."""
    now = now or utcnow()
    stale = db.scalars(
        select(Booking).where(Booking.status == "pending", Booking.created_at <= now - timedelta(minutes=config.HOLD_MINUTES))
    ).all()
    for booking in stale:
        booking.status = "expired"
        booking.slot_lock = None
    if stale:
        db.commit()


def available_slots(db: Session, expert: Expert, service: Service, first_day: date | None = None, days: int = 7,
                    now: datetime | None = None) -> list[datetime]:
    """Naive UTC start times, oldest first."""
    now = now or utcnow()
    duration = service.duration_min or 30
    tz = ZoneInfo(expert.timezone)
    first_day = first_day or datetime.now(timezone.utc).astimezone(tz).date()

    windows: dict[int, list[Availability]] = {}
    for w in db.scalars(select(Availability).where(Availability.expert_id == expert.user_id)):
        windows.setdefault(w.weekday, []).append(w)

    def to_utc(day: date, minute: int) -> datetime:
        local = datetime(day.year, day.month, day.day, tzinfo=tz) + timedelta(minutes=minute)
        return local.astimezone(timezone.utc).replace(tzinfo=None)

    earliest = now + timedelta(hours=config.MIN_NOTICE_HOURS)
    candidates = []
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        for w in sorted(windows.get(day.weekday(), []), key=lambda x: x.start_min):
            minute = w.start_min
            while minute + duration <= w.end_min:
                start = to_utc(day, minute)
                if start >= earliest:
                    candidates.append(start)
                minute += duration
    if not candidates:
        return []

    window_end = candidates[-1] + timedelta(minutes=duration)
    taken = db.scalars(
        select(Booking).where(
            Booking.expert_id == expert.user_id,
            Booking.kind == "call",
            holding(now),
            Booking.slot_start < window_end,
            Booking.slot_end > candidates[0],
        )
    ).all()
    free = []
    for start in candidates:
        end = start + timedelta(minutes=duration)
        if not any(b.slot_start < end and b.slot_end > start for b in taken):
            free.append(start)
    return free
