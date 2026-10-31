"""Turns database rows into the shapes the API returns, loading related rows in a few queries, not one per row."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Booking, Expert, Service, ServiceFile, User
from .schemas import BookingOut, ServiceOut


def services_out(db: Session, services: list[Service]) -> list[ServiceOut]:
    ids = [s.id for s in services]
    files = {}
    if ids:
        for sid, name, size in db.execute(select(ServiceFile.service_id, ServiceFile.filename, ServiceFile.size).where(ServiceFile.service_id.in_(ids))):
            files[sid] = (name, size)
    return [
        ServiceOut(
            id=s.id, kind=s.kind, title=s.title, description=s.description, price_paise=s.price_paise,
            duration_min=s.duration_min, reply_hours=s.reply_hours, is_active=s.is_active,
            file_name=files.get(s.id, (None, None))[0], file_size=files.get(s.id, (None, None))[1],
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
    out = []
    for b in bookings:
        has_file = b.kind == "document" and b.service_id in files
        out.append(
            BookingOut(
                id=b.id, kind=b.kind, status=b.status, amount_paise=b.amount_paise, slot_start=b.slot_start, slot_end=b.slot_end,
                note=b.note, answer=b.answer, meeting_link=b.meeting_link, created_at=b.created_at, paid_at=b.paid_at,
                answered_at=b.answered_at, service_title=services[b.service_id].title,
                expert_name=names.get(b.expert_id, "Expert"), expert_handle=experts[b.expert_id].handle,
                seeker_name=names.get(b.seeker_id) if with_seeker else None,
                has_file=has_file, file_name=files[b.service_id][0] if has_file else None,
                file_size=files[b.service_id][1] if has_file else None,
            )
        )
    return out
