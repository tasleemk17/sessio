from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

KINDS = ("call", "document", "dm", "webinar", "package", "membership")
CATEGORIES = ("career", "tech", "interview", "finance", "design", "marketing", "health", "education", "other")


def utcnow() -> datetime:
    # Naive UTC keeps SQLite and Postgres behaving the same. Every stored time is UTC.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Sessions started before this moment stop working: set when the password is changed
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Expert(Base):
    """A user who sells sessions and documents. The handle is the address of the public page."""

    __tablename__ = "experts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    handle: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    headline: Mapped[str] = mapped_column(String(120), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Kolkata")
    category: Mapped[str] = mapped_column(String(20), default="other", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts.user_id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # call | document | dm | webinar | package | membership
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price_paise: Mapped[int] = mapped_column(Integer, default=0)  # money is kept in paise, never as a float
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)  # calls, and each webinar session
    reply_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)  # priority DMs only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # webinars: seats
    call_service_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # packages: which call it is a bundle of
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)  # packages: how many calls
    valid_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # packages: how long the credits last
    meeting_link: Mapped[str | None] = mapped_column(String(200), nullable=True)  # webinars: one room for every session
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(60), nullable=True)  # memberships: created on first subscribe


class ServiceSession(Base):
    """One date of a webinar. A cohort is simply a webinar with several of them."""

    __tablename__ = "service_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime)


class ServiceFile(Base):
    """The file behind a document service. It lives in the database so it survives restarts on hosts with a
    throwaway disk. Fine for small files; object storage (S3) is the next step for large ones."""

    __tablename__ = "service_files"

    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), primary_key=True)
    filename: Mapped[str] = mapped_column(String(200))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)


class Availability(Base):
    """A weekly window in the expert's own time zone, in minutes from midnight. Monday is 0."""

    __tablename__ = "availability"

    id: Mapped[int] = mapped_column(primary_key=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts.user_id", ondelete="CASCADE"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_min: Mapped[int] = mapped_column(Integer)
    end_min: Mapped[int] = mapped_column(Integer)


class Booking(Base):
    """One purchase: a call slot, a document, or a priority DM.

    status: pending (waiting for payment), paid, cancelled, expired.
    slot_lock is "<expert>:<start>" while a call slot is held and NULL otherwise. Its unique constraint is what
    stops two people from taking the same slot at the same moment, whatever the application code does."""

    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("slot_lock", name="uq_booking_slot_lock"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    seeker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts.user_id", ondelete="CASCADE"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, default=0)
    slot_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    slot_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    slot_lock: Mapped[str | None] = mapped_column(String(60), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")  # the seeker's message or question
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)  # the expert's reply to a priority DM
    meeting_link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_order_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    package_booking_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)  # a call paid for with a package credit
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # packages: when the credits run out


class Subscription(Base):
    """A membership: paid access to an expert's documents for as long as the subscription runs.

    status: pending (waiting for the first payment), active, cancelled, expired.
    Access lasts until current_period_end even after cancelling, because the buyer has already paid for it."""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    seeker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts.user_id", ondelete="CASCADE"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)  # per month
    payments: Mapped[int] = mapped_column(Integer, default=0)  # how many months have been paid
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_id: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True, index=True)  # Razorpay subscription id, or mock_sub_...
    payment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
