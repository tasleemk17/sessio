from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

KINDS = ("call", "document", "dm")


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


class Expert(Base):
    """A user who sells sessions and documents. The handle is the address of the public page."""

    __tablename__ = "experts"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    handle: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    headline: Mapped[str] = mapped_column(String(120), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    expert_id: Mapped[int] = mapped_column(ForeignKey("experts.user_id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # call | document | dm
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    price_paise: Mapped[int] = mapped_column(Integer, default=0)  # money is kept in paise, never as a float
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)  # calls only
    reply_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)  # priority DMs only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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
