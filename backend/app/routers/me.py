"""The signed-in person's own overview: home summary and rewards."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Booking, Service, Subscription, User, utcnow
from ..schemas import HomeOut, RewardLine, RewardsOut
from ..security import current_user
from ..views import bookings_out, has_access

router = APIRouter(prefix="/api/me", tags=["me"])

PAISE_PER_POINT = 1000  # 1 point for every 10 rupees spent
TIERS = (("Starter", 0), ("Silver", 100), ("Gold", 500), ("Platinum", 1500))


@router.get("/home", response_model=HomeOut)
def home(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = utcnow()
    paid = select(Booking).where(Booking.seeker_id == user.id, Booking.status == "paid")

    def count(*conditions) -> int:
        return db.scalar(select(func.count()).select_from(paid.where(*conditions).subquery())) or 0

    next_row = db.scalar(paid.where(Booking.kind.in_(["call", "webinar"]), Booking.slot_end >= now).order_by(Booking.slot_start).limit(1))
    packages = bookings_out(db, list(db.scalars(paid.where(Booking.kind == "package").limit(200))))
    members = db.scalars(select(Subscription).where(Subscription.seeker_id == user.id, Subscription.status.in_(["active", "cancelled"])))
    return HomeOut(
        name=user.name,
        upcoming_calls=count(Booking.kind == "call", Booking.slot_end >= now),
        upcoming_webinars=count(Booking.kind == "webinar", Booking.slot_end >= now),
        documents=count(Booking.kind == "document"),
        pending_replies=count(Booking.kind == "dm", Booking.answer.is_(None)),
        active_memberships=sum(1 for s in members if has_access(s)),
        active_packages=sum(1 for p in packages if p.valid_until and p.valid_until >= now and (p.package_used or 0) < (p.package_total or 0)),
        next_session=bookings_out(db, [next_row])[0] if next_row else None,
    )


@router.get("/rewards", response_model=RewardsOut)
def rewards(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Booking.amount_paise, Booking.paid_at, Service.title)
        .join(Service, Service.id == Booking.service_id)
        .where(Booking.seeker_id == user.id, Booking.status == "paid", Booking.amount_paise > 0)
        .order_by(Booking.paid_at.desc())
    ).all()
    subs = db.execute(
        select(Subscription.amount_paise, Subscription.payments, Subscription.created_at, Service.title)
        .join(Service, Service.id == Subscription.service_id)
        .where(Subscription.seeker_id == user.id, Subscription.payments > 0)
    ).all()
    lines = [(paise, at, title) for paise, at, title in rows] + [(paise * n, at, f"{title} (membership)") for paise, n, at, title in subs]
    spent = sum(p for p, _, _ in lines)
    points = spent // PAISE_PER_POINT
    tier = max((t for t in TIERS if points >= t[1]), key=lambda t: t[1])
    upcoming = next((t for t in TIERS if t[1] > points), None)
    recent = sorted(lines, key=lambda x: x[1], reverse=True)[:10]
    return RewardsOut(
        points=points, spent_paise=spent, tier=tier[0],
        next_tier=upcoming[0] if upcoming else None, points_to_next=upcoming[1] - points if upcoming else None,
        recent=[RewardLine(title=title, points=paise // PAISE_PER_POINT, at=at) for paise, at, title in recent],
    )
