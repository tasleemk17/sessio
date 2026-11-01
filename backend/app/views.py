"""Turns database rows into the shapes the API returns, loading related rows in a few queries, not one per row."""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Booking, Expert, Service, ServiceFile, ServiceSession, Subscription, User, utcnow
from .schemas import BookingOut, ServiceOut, SubscriptionOut
from .slots import holding


def seats_taken(db: Session, service_ids: list[int]) -> dict[int, int]:
    """Bookings that currently occupy a seat of a webinar: paid, or unpaid but still inside the hold time."""
    if not service_ids:
        return {}
    rows = db.execute(
        select(Booking.service_id, func.count()).where(Booking.service_id.in_(service_ids), holding(utcnow())).group_by(Booking.service_id)
    )
    return {sid: n for sid, n in rows}


def session_times(db: Session, service_ids: list[int]) -> dict[int, list]:
    out: dict[int, list] = defaultdict(list)
    if service_ids:
        for sid, at in db.execute(select(ServiceSession.service_id, ServiceSession.starts_at).where(ServiceSession.service_id.in_(service_ids)).order_by(ServiceSession.starts_at)):
            out[sid].append(at)
    return out


def services_out(db: Session, services: list[Service]) -> list[ServiceOut]:
    ids = [s.id for s in services]
    files = {}
    if ids:
        for sid, name, size in db.execute(select(ServiceFile.service_id, ServiceFile.filename, ServiceFile.size).where(ServiceFile.service_id.in_(ids))):
            files[sid] = (name, size)
    sessions = session_times(db, [s.id for s in services if s.kind == "webinar"])
    taken = seats_taken(db, [s.id for s in services if s.kind == "webinar"])
    call_ids = {s.call_service_id for s in services if s.call_service_id}
    call_titles = {sid: title for sid, title in db.execute(select(Service.id, Service.title).where(Service.id.in_(call_ids)))} if call_ids else {}
    included: dict[int, int] = {}
    for expert_id in {s.expert_id for s in services if s.kind == "membership"}:
        included[expert_id] = db.scalar(
            select(func.count()).select_from(Service).join(ServiceFile, ServiceFile.service_id == Service.id)
            .where(Service.expert_id == expert_id, Service.kind == "document", Service.is_active.is_(True))
        ) or 0
    return [
        ServiceOut(
            id=s.id, kind=s.kind, title=s.title, description=s.description, price_paise=s.price_paise,
            duration_min=s.duration_min, reply_hours=s.reply_hours, is_active=s.is_active,
            file_name=files.get(s.id, (None, None))[0], file_size=files.get(s.id, (None, None))[1],
            capacity=s.capacity, spots_left=max(0, s.capacity - taken.get(s.id, 0)) if s.kind == "webinar" and s.capacity else None,
            sessions=sessions.get(s.id, []), call_service_id=s.call_service_id, call_service_title=call_titles.get(s.call_service_id),
            credits=s.credits, valid_days=s.valid_days,
            documents_included=included.get(s.expert_id) if s.kind == "membership" else None,
        )
        for s in services
    ]


def bookings_out(db: Session, bookings: list[Booking], with_seeker: bool = False) -> list[BookingOut]:
    if not bookings:
        return []
    services = {s.id: s for s in db.scalars(select(Service).where(Service.id.in_({b.service_id for b in bookings})))}
    expert_ids = {b.expert_id for b in bookings}
    experts = {e.user_id: e for e in db.scalars(select(Expert).where(Expert.user_id.in_(expert_ids)))}
    user_ids = set(expert_ids) | ({b.seeker_id for b in bookings} if with_seeker else set())
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(user_ids)))}
    files = {
        sid: (name, size)
        for sid, name, size in db.execute(
            select(ServiceFile.service_id, ServiceFile.filename, ServiceFile.size).where(ServiceFile.service_id.in_(list(services)))
        )
    }
    sessions = session_times(db, [b.service_id for b in bookings if b.kind == "webinar"])
    package_ids = [b.id for b in bookings if b.kind == "package"]
    used: dict[int, int] = {}
    if package_ids:
        used = {
            pid: n for pid, n in db.execute(
                select(Booking.package_booking_id, func.count()).where(Booking.package_booking_id.in_(package_ids), holding(utcnow())).group_by(Booking.package_booking_id)
            )
        }
    out = []
    for b in bookings:
        has_file = b.kind == "document" and b.service_id in files
        service = services[b.service_id]
        is_package = b.kind == "package"
        out.append(
            BookingOut(
                id=b.id, kind=b.kind, status=b.status, amount_paise=b.amount_paise, slot_start=b.slot_start, slot_end=b.slot_end,
                note=b.note, answer=b.answer, meeting_link=b.meeting_link, created_at=b.created_at, paid_at=b.paid_at,
                answered_at=b.answered_at, service_title=service.title,
                expert_name=names.get(b.expert_id, "Expert"), expert_handle=experts[b.expert_id].handle,
                seeker_name=names.get(b.seeker_id) if with_seeker else None,
                has_file=has_file, file_name=files[b.service_id][0] if has_file else None,
                file_size=files[b.service_id][1] if has_file else None,
                service_id=b.service_id, reference=f"SES-{b.id:06d}",
                sessions=sessions.get(b.service_id, []) if b.kind == "webinar" else [],
                package_total=service.credits if is_package else None,
                package_used=used.get(b.id, 0) if is_package else None,
                package_call_service_id=service.call_service_id if is_package else None,
                valid_until=b.valid_until if is_package else None,
                via_package=b.package_booking_id is not None,
            )
        )
    return out


def has_access(sub: Subscription, now=None) -> bool:
    """A membership gives access while it is paid up, even after the person has cancelled the renewal."""
    now = now or utcnow()
    return sub.status in ("active", "cancelled") and sub.current_period_end is not None and sub.current_period_end >= now


def subscription_state(sub: Subscription, now=None) -> str:
    now = now or utcnow()
    if sub.status == "pending":
        return "pending"
    if sub.current_period_end is not None and sub.current_period_end < now:
        return "expired"
    if sub.status == "cancelled":
        return "cancelled"
    return "cancelling" if sub.cancel_at_period_end else "active"


def subscriptions_out(db: Session, subs: list[Subscription]) -> list[SubscriptionOut]:
    if not subs:
        return []
    services = {s.id: s for s in db.scalars(select(Service).where(Service.id.in_({x.service_id for x in subs})))}
    experts = {e.user_id: e for e in db.scalars(select(Expert).where(Expert.user_id.in_({x.expert_id for x in subs})))}
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(list(experts))))}
    included = {
        eid: db.scalar(
            select(func.count()).select_from(Service).join(ServiceFile, ServiceFile.service_id == Service.id)
            .where(Service.expert_id == eid, Service.kind == "document", Service.is_active.is_(True))
        ) or 0
        for eid in experts
    }
    return [
        SubscriptionOut(
            id=x.id, status=subscription_state(x), service_id=x.service_id, service_title=services[x.service_id].title,
            expert_name=names.get(x.expert_id, "Expert"), expert_handle=experts[x.expert_id].handle, amount_paise=x.amount_paise,
            payments=x.payments, created_at=x.created_at, current_period_end=x.current_period_end,
            cancel_at_period_end=x.cancel_at_period_end, has_access=has_access(x), documents_included=included[x.expert_id],
        )
        for x in subs
    ]
