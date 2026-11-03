import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer, field_validator

# Stored times are naive UTC. Adding the "Z" lets the browser convert them to the viewer's own time zone.
UtcTime = Annotated[datetime, PlainSerializer(lambda d: d.isoformat() + "Z", return_type=str)]

HANDLE = re.compile(r"^[a-z0-9][a-z0-9-]{2,29}$")
RESERVED = {"admin", "api", "login", "register", "expert", "experts", "dashboard", "me", "e", "explore", "settings", "about", "help", "sessio", "categories"}
Kind = Literal["call", "document", "dm", "webinar", "package", "membership"]
CategoryName = Literal["career", "tech", "interview", "finance", "design", "marketing", "health", "education", "other"]


# The passwords people reach for first. A short list stops the worst; length does the rest.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "123456789", "1234567890", "12345678910", "qwertyuiop", "qwerty123",
    "iloveyou123", "welcome123", "admin12345", "letmein123", "abcd123456", "india123456", "sessio12345", "1q2w3e4r5t",
}


class Register(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("password")
    @classmethod
    def _not_guessable(cls, value: str) -> str:
        return check_password_strength(value)


def check_password_strength(value: str) -> str:
    if value.lower() in COMMON_PASSWORDS or len(set(value)) < 5:
        raise ValueError("That password is too easy to guess. Try a longer phrase.")
    return value


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _not_guessable(cls, value: str) -> str:
        return check_password_strength(value)


class EmailChange(BaseModel):
    new_email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    current_password: str = Field(max_length=128)


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


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
    category: CategoryName = "other"

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
    category: CategoryName = "other"


class ServiceIn(BaseModel):
    kind: Kind
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=2000)
    price_rupees: int = Field(ge=0, le=50_000)
    duration_min: int | None = Field(default=None, ge=10, le=240)
    reply_hours: int | None = Field(default=None, ge=1, le=168)
    is_active: bool = True
    capacity: int | None = Field(default=None, ge=1, le=500)  # webinar seats
    sessions: list[datetime] = Field(default_factory=list, max_length=12)  # webinar dates (UTC); several make a cohort
    call_service_id: int | None = None  # package: the call it is a bundle of
    credits: int | None = Field(default=None, ge=2, le=20)
    valid_days: int | None = Field(default=None, ge=7, le=365)


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
    capacity: int | None = None
    spots_left: int | None = None
    sessions: list[UtcTime] = []
    call_service_id: int | None = None
    call_service_title: str | None = None
    credits: int | None = None
    valid_days: int | None = None
    documents_included: int | None = None  # membership: how many documents it unlocks


class ExpertPublic(BaseModel):
    handle: str
    name: str
    headline: str
    bio: str
    timezone: str
    category: str = "other"
    services: list[ServiceOut]


class ExpertCard(BaseModel):
    handle: str
    name: str
    headline: str
    category: str = "other"
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
    package_booking_id: int | None = None  # pay for a call with a credit from a package the person already bought
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
    service_id: int = 0
    reference: str = ""
    sessions: list[UtcTime] = []  # webinars and cohorts
    package_total: int | None = None
    package_used: int | None = None
    package_call_service_id: int | None = None
    valid_until: UtcTime | None = None
    via_package: bool = False


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


class SubscriptionIn(BaseModel):
    service_id: int


class SubscriptionOut(BaseModel):
    id: int
    status: str  # pending | active | cancelling | cancelled | expired
    service_id: int
    service_title: str
    expert_name: str
    expert_handle: str
    amount_paise: int
    payments: int
    created_at: UtcTime
    current_period_end: UtcTime | None
    cancel_at_period_end: bool
    has_access: bool
    documents_included: int


class SubscriptionPayment(BaseModel):
    mode: Literal["razorpay", "mock"]
    subscription_id: str
    key_id: str | None
    amount_paise: int
    currency: str = "INR"


class SubscriptionCreated(BaseModel):
    subscription: SubscriptionOut
    payment: SubscriptionPayment


class CategoryOut(BaseModel):
    key: str
    label: str
    experts: int


class RewardLine(BaseModel):
    title: str
    points: int
    at: UtcTime


class RewardsOut(BaseModel):
    points: int
    spent_paise: int
    tier: str
    next_tier: str | None
    points_to_next: int | None
    recent: list[RewardLine]


class HomeOut(BaseModel):
    name: str
    upcoming_calls: int
    upcoming_webinars: int
    documents: int
    pending_replies: int
    active_memberships: int
    active_packages: int
    next_session: BookingOut | None
