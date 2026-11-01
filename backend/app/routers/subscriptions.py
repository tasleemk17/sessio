"""Memberships: a monthly subscription that unlocks all of an expert's documents while it is paid up.

With Razorpay keys this uses Razorpay Subscriptions (a plan per membership, a subscription per buyer, the
monthly charge made by Razorpay, and webhooks that tell this server about every charge). Without keys it runs
in demo mode: one paid month, no automatic renewal."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import config, payments, ratelimit
from ..db import get_db
from ..models import Service, ServiceFile, Subscription, User, utcnow
from ..schemas import PayIn, ServiceOut, SubscriptionCreated, SubscriptionIn, SubscriptionOut, SubscriptionPayment
from ..security import current_user
from ..views import has_access, services_out, subscription_state, subscriptions_out
from .experts import file_response

router = APIRouter(tags=["memberships"])
log = logging.getLogger("sessio.subscriptions")
MONTH = timedelta(days=30)


def _own(db: Session, user: User, sub_id: int) -> Subscription:
    sub = db.get(Subscription, sub_id)
    if sub is None or sub.seeker_id != user.id:  # other people's rows answer 404, never confirm they exist
        raise HTTPException(404, "Membership not found")
    return sub


@router.post("/api/subscriptions", response_model=SubscriptionCreated, status_code=201)
def subscribe(body: SubscriptionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    service = db.get(Service, body.service_id)
    if service is None or not service.is_active or service.kind != "membership":
        raise HTTPException(404, "This membership is not available")
    if service.expert_id == user.id:
        raise HTTPException(400, "You cannot join your own membership")
    ratelimit.BOOKING.check(f"u{user.id}")
    mine = list(db.scalars(select(Subscription).where(Subscription.seeker_id == user.id, Subscription.service_id == service.id)))
    if any(subscription_state(s) in ("active", "cancelling", "cancelled") for s in mine):
        raise HTTPException(409, "You are already a member. You can renew once the current month ends.")
    stale = [s for s in mine if s.status == "pending"]
    for s in stale:
        s.status = "expired"  # an abandoned attempt; the new one replaces it
    others = db.scalar(select(func.count()).select_from(Subscription).where(Subscription.seeker_id == user.id, Subscription.status == "pending"))
    if others >= config.MAX_PENDING_HOLDS:
        raise HTTPException(429, "You have memberships waiting for payment. Finish or cancel them first.")

    made = payments.create_subscription(service.razorpay_plan_id, service.title, service.price_paise)
    service.razorpay_plan_id = made["plan_id"]
    sub = Subscription(seeker_id=user.id, expert_id=service.expert_id, service_id=service.id, amount_paise=service.price_paise, provider_id=made["subscription_id"])
    db.add(sub)
    db.commit()
    return SubscriptionCreated(
        subscription=subscriptions_out(db, [sub])[0],
        payment=SubscriptionPayment(mode=made["mode"], subscription_id=made["subscription_id"], key_id=made["key_id"], amount_paise=service.price_paise),
    )


@router.post("/api/subscriptions/{sub_id}/pay", response_model=SubscriptionOut)
def confirm(sub_id: int, body: PayIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = _own(db, user, sub_id)
    if sub.status != "pending":
        return subscriptions_out(db, [sub])[0]  # confirming twice changes nothing
    if not sub.provider_id or not payments.verify_subscription(sub.provider_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(400, "The payment could not be verified")
    _first_payment(sub, body.razorpay_payment_id)
    db.commit()
    return subscriptions_out(db, [sub])[0]


def _first_payment(sub: Subscription, payment_id: str | None) -> None:
    sub.status, sub.payments, sub.payment_id = "active", 1, payment_id
    sub.current_period_end = utcnow() + MONTH  # Razorpay's webhook later replaces this with its own billing date


@router.post("/api/subscriptions/{sub_id}/cancel", response_model=SubscriptionOut)
def cancel(sub_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = _own(db, user, sub_id)
    if sub.status == "pending":
        sub.status = "cancelled"
    elif subscription_state(sub) == "active":
        if sub.provider_id:
            payments.cancel_subscription(sub.provider_id)  # raises 502 if the provider could not stop it, so we never lie
        sub.cancel_at_period_end = True
    db.commit()
    return subscriptions_out(db, [sub])[0]


@router.get("/api/me/subscriptions", response_model=list[SubscriptionOut])
def my_subscriptions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    subs = db.scalars(select(Subscription).where(Subscription.seeker_id == user.id, Subscription.status.in_(["active", "cancelled"])).order_by(Subscription.created_at.desc()).limit(100))
    return subscriptions_out(db, list(subs))


def _documents_of(db: Session, sub: Subscription) -> list[Service]:
    return list(db.scalars(
        select(Service).join(ServiceFile, ServiceFile.service_id == Service.id)
        .where(Service.expert_id == sub.expert_id, Service.kind == "document", Service.is_active.is_(True)).order_by(Service.id)
    ))


def _member_access(db: Session, user: User, sub_id: int) -> Subscription:
    sub = _own(db, user, sub_id)
    if not has_access(sub):
        raise HTTPException(403, "This membership is not active. Renew it to get the documents.")
    return sub


@router.get("/api/me/subscriptions/{sub_id}/documents", response_model=list[ServiceOut])
def member_documents(sub_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return services_out(db, _documents_of(db, _member_access(db, user, sub_id)))


@router.get("/api/me/subscriptions/{sub_id}/documents/{service_id}/download")
def member_download(sub_id: int, service_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = _member_access(db, user, sub_id)
    if service_id not in {s.id for s in _documents_of(db, sub)}:
        raise HTTPException(404, "That document is not part of this membership")
    return file_response(db.get(ServiceFile, service_id))


# ---------------------------------------------------------------- Razorpay's own messages

def handle_event(db: Session, event: dict) -> None:
    """Called by the signed webhook. A monthly charge extends the membership; a cancellation stops the renewal."""
    name = event.get("event", "")
    try:
        entity = event["payload"]["subscription"]["entity"]
        provider_id = entity["id"]
    except (KeyError, TypeError):
        return
    sub = db.scalar(select(Subscription).where(Subscription.provider_id == provider_id))
    if sub is None:
        return
    if name in {"subscription.charged", "subscription.activated"}:
        payment = (event.get("payload", {}).get("payment") or {}).get("entity") or {}
        payment_id = payment.get("id")
        if name == "subscription.charged" and (int(payment.get("amount", -1)) != sub.amount_paise or payment.get("currency") != "INR"):
            log.error("Subscription %s charge with the wrong amount", sub.id)
            return
        if payment_id and sub.payment_id == payment_id:
            return  # a repeat of a message already handled
        end = entity.get("current_end")
        new_end = datetime.fromtimestamp(int(end), timezone.utc).replace(tzinfo=None) if end else (utcnow() + MONTH)
        if sub.status == "pending":
            sub.status = "active"
        if name == "subscription.charged":
            sub.payments += 1
        sub.current_period_end = max(new_end, sub.current_period_end or new_end)
        sub.payment_id = payment_id or sub.payment_id
    elif name in {"subscription.cancelled", "subscription.completed", "subscription.halted"}:
        if sub.status != "pending":
            sub.status = "cancelled"  # paid time stays usable until current_period_end
    db.commit()
