import json
import logging
import secrets
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config, payments, ratelimit, slots
from ..db import get_db
from ..models import Booking, Expert, Service, ServiceFile, ServiceSession, User, utcnow
from ..schemas import BookingCreated, BookingIn, BookingOut, PayIn, PaymentInfo
from ..security import current_user
from ..views import bookings_out, seats_taken
from . import subscriptions
from .experts import file_response

router = APIRouter(tags=["bookings"])
log = logging.getLogger("sessio.bookings")


def _mark_paid(db: Session, booking: Booking, payment_id: str | None = None) -> None:
    booking.status, booking.paid_at = "paid", utcnow()
    if payment_id:
        booking.payment_id = payment_id
    if booking.kind == "call" and not booking.meeting_link:
        booking.meeting_link = f"{config.MEETING_BASE}/Sessio-{secrets.token_hex(6)}"
    elif booking.kind == "webinar":
        booking.meeting_link = db.get(Service, booking.service_id).meeting_link  # every date of a webinar shares one room
    elif booking.kind == "package":
        booking.valid_until = booking.paid_at + timedelta(days=db.get(Service, booking.service_id).valid_days or 30)


def _own_booking(db: Session, user: User, booking_id: int) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or booking.seeker_id != user.id:  # 404 for other people's rows too, never confirm they exist
        raise HTTPException(404, "Booking not found")
    return booking


@router.post("/api/bookings", response_model=BookingCreated, status_code=201)
def create_booking(body: BookingIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service = db.get(Service, body.service_id)
    if service is None or not service.is_active:
        raise HTTPException(404, "This service is not available")
    if service.expert_id == user.id:
        raise HTTPException(400, "You cannot book your own service")
    if service.kind == "membership":
        raise HTTPException(400, "A membership is started with Subscribe, not Book")
    expert = db.get(Expert, service.expert_id)
    ratelimit.BOOKING.check(f"u{user.id}")
    slots.expire_stale_holds(db)
    # Without a cap, one person could hold every free time of an expert by never paying
    holds = db.scalar(select(func.count()).select_from(Booking).where(Booking.seeker_id == user.id, Booking.status == "pending"))
    if holds >= config.MAX_PENDING_HOLDS:
        raise HTTPException(429, "You have bookings waiting for payment. Finish or cancel them first.")

    start = end = lock = None
    note = body.note.strip()
    credit: Booking | None = None
    if body.package_booking_id is not None and service.kind != "call":
        raise HTTPException(422, "A package credit pays for a 1:1 call only")
    if service.kind == "call":
        if body.slot_start is None:
            raise HTTPException(422, "Choose a time for the call")
        start = body.slot_start
        if start.tzinfo is not None:
            start = start.astimezone(timezone.utc).replace(tzinfo=None)
        local_day = start.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(expert.timezone)).date()
        # The only valid times are the ones the slot list would offer right now: inside a window, not too soon, not taken
        if start not in slots.available_slots(db, expert, service, local_day, 1):
            raise HTTPException(409, "That time is no longer available. Please pick another.")
        end = start + timedelta(minutes=service.duration_min or 30)
        lock = f"{expert.user_id}:{start:%Y%m%d%H%M}"
        if body.package_booking_id is not None:
            credit = _usable_package(db, user, service, body.package_booking_id, start)
    elif service.kind == "webinar":
        # Seats are counted while the webinar row is locked, so two people cannot take the last seat together
        db.execute(select(Service.id).where(Service.id == service.id).with_for_update())
        first, last = db.execute(select(func.min(ServiceSession.starts_at), func.max(ServiceSession.starts_at)).where(ServiceSession.service_id == service.id)).one()
        if first is None or first <= utcnow():
            raise HTTPException(409, "This webinar has already started")
        if service.capacity and seats_taken(db, [service.id]).get(service.id, 0) >= service.capacity:
            raise HTTPException(409, "This webinar is full")
        if db.scalar(select(Booking.id).where(Booking.seeker_id == user.id, Booking.service_id == service.id, slots.holding(utcnow()))):
            raise HTTPException(409, "You already have a seat in this webinar")
        start, end = first, last + timedelta(minutes=service.duration_min or 60)
    elif service.kind == "package":
        call = db.get(Service, service.call_service_id) if service.call_service_id else None
        if call is None or not call.is_active:
            raise HTTPException(409, "The call this package is for is not offered right now")
    elif service.kind == "document":
        if db.get(ServiceFile, service.id) is None:
            raise HTTPException(409, "The file for this document has not been uploaded yet")
        if db.scalar(select(Booking.id).where(Booking.seeker_id == user.id, Booking.service_id == service.id, Booking.status == "paid")):
            raise HTTPException(409, "You already own this. Find it under Documents in your dashboard.")
    elif len(note) < 10:
        raise HTTPException(422, "Write your question (at least 10 characters)")

    price = 0 if credit else service.price_paise  # a credit was paid for when the package was bought
    booking = Booking(
        seeker_id=user.id, expert_id=service.expert_id, service_id=service.id, kind=service.kind, amount_paise=price,
        slot_start=start, slot_end=end, slot_lock=lock, note=note, package_booking_id=credit.id if credit else None,
    )
    free = price == 0
    if free:
        _mark_paid(db, booking)
    db.add(booking)
    try:
        db.commit()
    except IntegrityError:  # someone took the slot in the same instant
        db.rollback()
        raise HTTPException(409, "Someone just booked that time. Please pick another.")

    payment = None
    if not free:
        try:
            order = payments.create_order(price, f"sessio_{booking.id}")
        except HTTPException:
            booking.status, booking.slot_lock = "expired", None  # give the slot back at once
            db.commit()
            raise
        booking.payment_order_id = order["order_id"]
        db.commit()
        payment = PaymentInfo(mode=order["mode"], order_id=order["order_id"], key_id=order["key_id"], amount_paise=price)
    return BookingCreated(booking=bookings_out(db, [booking])[0], payment=payment)


def _usable_package(db: Session, user: User, call: Service, package_id: int, start) -> Booking:
    """The package a call may be paid with. Locks the package row so the last credit cannot be spent twice."""
    package = db.get(Booking, package_id)
    if package is None or package.seeker_id != user.id or package.kind != "package" or package.status != "paid":
        raise HTTPException(404, "Package not found")
    db.execute(select(Booking.id).where(Booking.id == package.id).with_for_update())
    bundle = db.get(Service, package.service_id)
    if bundle.call_service_id != call.id:
        raise HTTPException(422, "This package is for a different call")
    if package.valid_until is None or package.valid_until < start:
        raise HTTPException(409, "Your package credits run out before that time")
    used = db.scalar(select(func.count()).select_from(Booking).where(Booking.package_booking_id == package.id, slots.holding(utcnow())))
    if used >= (bundle.credits or 0):
        raise HTTPException(409, "There are no credits left in this package")
    return package


def _settle(db: Session, booking: Booking, payment_id: str | None) -> None:
    """Marks a genuinely paid booking as paid. Shared by the buyer's browser and Razorpay's own webhook, so both
    end the same way, and doing it twice changes nothing. Raises IntegrityError when the slot was taken meanwhile."""
    if booking.status == "paid":
        return
    if booking.status == "expired" and booking.slot_start is not None:
        # The hold ran out while the person was paying. Take the slot back if nobody else has it.
        expert = db.get(Expert, booking.expert_id)
        booking.slot_lock = f"{expert.user_id}:{booking.slot_start:%Y%m%d%H%M}"
        db.flush()
    _mark_paid(db, booking, payment_id)
    db.commit()


@router.post("/api/bookings/{booking_id}/pay", response_model=BookingOut)
def confirm_payment(booking_id: int, body: PayIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    booking = _own_booking(db, user, booking_id)
    if booking.status == "paid":
        return bookings_out(db, [booking])[0]  # confirming twice changes nothing
    if booking.status == "cancelled" or not booking.payment_order_id:
        raise HTTPException(409, "This booking can no longer be paid")
    if not payments.verify(booking.payment_order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(400, "The payment could not be verified")
    try:
        _settle(db, booking, body.razorpay_payment_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Your payment went through but the time was taken meanwhile. Contact support with your booking number.")
    return bookings_out(db, [booking])[0]


@router.post("/api/payments/webhook", include_in_schema=False)
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay tells the server a payment succeeded, even when the buyer closed the tab before the browser could.
    Nothing in the body is trusted until the signature over the raw bytes checks out."""
    raw = await request.body()
    if not payments.verify_webhook(raw, request.headers.get("x-razorpay-signature")):
        log.warning("Webhook with a bad signature from %s", ratelimit.client_ip(request))
        raise HTTPException(400, "Invalid signature")
    try:
        event = json.loads(raw)
        if str(event.get("event", "")).startswith("subscription."):
            subscriptions.handle_event(db, event)
            return {"ok": True}
        if event.get("event") not in {"payment.captured", "order.paid"}:
            return {"ok": True}
        payment = event["payload"]["payment"]["entity"]
        order_id, payment_id = payment["order_id"], payment["id"]
        amount, currency = int(payment["amount"]), payment["currency"]
    except (ValueError, KeyError, TypeError):
        return {"ok": True}  # a shape we do not use; answering 200 stops Razorpay from retrying it
    booking = db.scalar(select(Booking).where(Booking.payment_order_id == order_id))
    if booking is None or booking.status == "paid":
        return {"ok": True}
    # The amount actually paid must match what this booking costs, whatever the order said
    if amount != booking.amount_paise or currency != "INR":
        log.error("Webhook amount mismatch for booking %s", booking.id)
        return {"ok": True}
    try:
        _settle(db, booking, payment_id)
    except IntegrityError:
        db.rollback()
        log.error("Booking %s was paid but its time was taken: refund needed", booking.id)
    return {"ok": True}


@router.post("/api/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_unpaid(booking_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    booking = _own_booking(db, user, booking_id)
    if booking.status != "pending":
        raise HTTPException(409, "Only a booking that is still waiting for payment can be cancelled here")
    booking.status, booking.slot_lock = "cancelled", None
    db.commit()
    return bookings_out(db, [booking])[0]


TABS = "^(upcoming|past|documents|messages|webinar-upcoming|webinar-past|package-active|package-past)$"


@router.get("/api/me/bookings", response_model=list[BookingOut])
def my_bookings(tab: str = Query("upcoming", pattern=TABS), user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = utcnow()
    stmt = select(Booking).where(Booking.seeker_id == user.id, Booking.status == "paid")
    if tab == "upcoming":
        stmt = stmt.where(Booking.kind == "call", Booking.slot_end >= now).order_by(Booking.slot_start)
    elif tab == "past":
        stmt = stmt.where(Booking.kind == "call", Booking.slot_end < now).order_by(Booking.slot_start.desc())
    elif tab == "documents":
        stmt = stmt.where(Booking.kind == "document").order_by(Booking.paid_at.desc())
    elif tab == "messages":
        stmt = stmt.where(Booking.kind == "dm").order_by(Booking.paid_at.desc())
    elif tab == "webinar-upcoming":
        stmt = stmt.where(Booking.kind == "webinar", Booking.slot_end >= now).order_by(Booking.slot_start)
    elif tab == "webinar-past":
        stmt = stmt.where(Booking.kind == "webinar", Booking.slot_end < now).order_by(Booking.slot_start.desc())
    else:
        packages = bookings_out(db, list(db.scalars(stmt.where(Booking.kind == "package").order_by(Booking.paid_at.desc()).limit(200))))
        live = [b for b in packages if b.valid_until and b.valid_until.replace(tzinfo=None) >= now and (b.package_used or 0) < (b.package_total or 0)]
        return live if tab == "package-active" else [b for b in packages if b not in live]
    return bookings_out(db, list(db.scalars(stmt.limit(200))))


@router.get("/api/me/bookings/{booking_id}", response_model=BookingOut)
def booking_details(booking_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return bookings_out(db, [_own_booking(db, user, booking_id)])[0]


@router.get("/api/me/bookings/{booking_id}/download")
def download_document(booking_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    booking = _own_booking(db, user, booking_id)
    if booking.kind != "document" or booking.status != "paid":
        raise HTTPException(404, "Nothing to download")
    row = db.get(ServiceFile, booking.service_id)
    if row is None:
        raise HTTPException(404, "The file is not available")
    return file_response(row)
