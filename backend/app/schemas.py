import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer, field_validator

# Stored times are naive UTC. Adding the "Z" lets the browser convert them to the viewer's own time zone.
UtcTime = Annotated[datetime, PlainSerializer(lambda d: d.isoformat() + "Z", return_type=str)]

HANDLE = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")
RESERVED = {"admin", "api", "login", "register", "expert", "experts", "dashboard", "me", "e", "explore", "settings", "about", "help", "sessio"}
Kind = Literal["call", "document", "dm"]


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=8, max_length=128)


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    token: str


class MeOut(BaseModel):
    id: int
    name: str
    email: str
    handle: str | None = None  # set once the person has created an expert page


class ExpertIn(BaseModel):
    handle: str
    headline: str = Field(default="", max_length=120)
    bio: str = Field(default="", max_length=2000)
    timezone: str = "Asia/Kolkata"

    @field_validator("handle")
    @classmethod
    def clean_handle(cls, value: str) -> str:
        value = value.strip().lower()
        if not HANDLE.match(value) or value in RESERVED:
            raise ValueError("Use 3 to 30 letters, numbers or hyphens, starting with a letter or number")
        return value


class ExpertUpdate(BaseModel):
    headline: str = Field(default="", max_length=120)
    bio: str = Field(default="", max_length=2000)
    timezone: str = "Asia/Kolkata"


class ServiceIn(BaseModel):
    kind: Kind
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)
    price_rupees: int = Field(ge=0, le=50_000)
    duration_min: int | None = Field(default=None, ge=10, le=240)
    reply_hours: int | None = Field(default=None, ge=1, le=168)
    is_active: bool = True


class ServiceOut(BaseModel):
    id: int
    kind: str
    title: str
    description: str
    price_paise: int
    duration_min: int | None
    reply_hours: int | None
    is_active: bool
    file_name: str | None = None
    file_size: int | None = None


class ExpertPublic(BaseModel):
    handle: str
    name: str
    headline: str
    bio: str
    timezone: str
    services: list[ServiceOut]


class ExpertCard(BaseModel):
    handle: str
    name: str
    headline: str
    from_paise: int | None
    services: int


class WindowIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_min: int = Field(ge=0, le=1440)
    end_min: int = Field(ge=0, le=1440)


class SlotsOut(BaseModel):
    timezone: str
    duration_min: int
    slots: list[UtcTime]


class BookingIn(BaseModel):
    service_id: int
    slot_start: datetime | None = None  # UTC, for calls
    note: str = Field(default="", max_length=2000)


class PayIn(BaseModel):
    razorpay_payment_id: str | None = Field(default=None, max_length=80)
    razorpay_signature: str | None = Field(default=None, max_length=200)


class AnswerIn(BaseModel):
    answer: str = Field(min_length=5, max_length=4000)


class BookingOut(BaseModel):
    id: int
    kind: str
    status: str
    amount_paise: int
    slot_start: UtcTime | None
    slot_end: UtcTime | None
    note: str
    answer: str | None
    meeting_link: str | None
    created_at: UtcTime
    paid_at: UtcTime | None
    answered_at: UtcTime | None
    service_title: str
    expert_name: str
    expert_handle: str
    seeker_name: str | None = None
    has_file: bool = False
    file_name: str | None = None
    file_size: int | None = None


class PaymentInfo(BaseModel):
    mode: Literal["razorpay", "mock"]
    order_id: str
    key_id: str | None
    amount_paise: int
    currency: str = "INR"


class BookingCreated(BaseModel):
    booking: BookingOut
    payment: PaymentInfo | None  # None when the service is free


class Summary(BaseModel):
    orders: int
    gross_paise: int
    fee_paise: int
    net_paise: int
    fee_percent: int
    by_kind: dict[str, int]
    pending_dms: int
    upcoming_calls: int
