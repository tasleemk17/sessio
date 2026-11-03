import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config, ratelimit
from ..db import get_db
from ..models import Expert, User
from ..models import utcnow
from ..schemas import EmailChange, Login, MeOut, PasswordChange, ProfileUpdate, Register, TokenOut
from ..security import create_token, current_user, hash_password, needs_rehash, spend_time_like_a_login, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("sessio.auth")  # events only: never a password, a token or a full email


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: Register, request: Request, db: Session = Depends(get_db)):
    ratelimit.REGISTER.check(ratelimit.client_ip(request))
    email = body.email.strip().lower()
    if body.password.lower() == email or email.split("@")[0] in body.password.lower() and len(email.split("@")[0]) >= 4:
        raise HTTPException(422, "The password must not contain your email")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists")
    return TokenOut(token=create_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(body: Login, request: Request, db: Session = Depends(get_db)):
    ip = ratelimit.client_ip(request)
    ratelimit.LOGIN_IP.check(ip)
    email = body.email.strip().lower()
    # Failed tries are counted per email AND address, so a stranger cannot lock somebody else out of their account
    account_key = f"{email}|{ip}"
    wait = ratelimit.LOGIN_ACCOUNT.retry_after(account_key) if config.RATE_LIMITS_ENABLED else 0
    if wait:
        log.warning("Login blocked for repeated failures from %s", ip)
        raise HTTPException(429, "Too many wrong passwords. Try again in a few minutes.", headers={"Retry-After": str(wait)})

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        spend_time_like_a_login(body.password)
        ok = False
    else:
        ok = verify_password(body.password, user.password_hash)
    # One message for "no such user" and "wrong password", so emails cannot be probed
    if not ok:
        if config.RATE_LIMITS_ENABLED:
            ratelimit.LOGIN_ACCOUNT.hit(account_key)
        log.info("Failed login from %s", ip)
        raise HTTPException(401, "Wrong email or password")

    ratelimit.LOGIN_ACCOUNT.clear(account_key)
    if needs_rehash(user.password_hash):  # upgrade an older hash now that the real password is in hand
        user.password_hash = hash_password(body.password)
        db.commit()
    return TokenOut(token=create_token(user.id))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    expert = db.get(Expert, user.id)
    return MeOut(id=user.id, name=user.name, email=user.email, handle=expert.handle if expert else None)


@router.put("/me", response_model=MeOut)
def update_profile(body: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name = body.name.strip()
    db.commit()
    return me(user, db)


@router.post("/password", response_model=TokenOut)
def change_password(body: PasswordChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Needs the current password even though the person is signed in, so a borrowed phone cannot lock them out."""
    key = f"u{user.id}"
    wait = ratelimit.LOGIN_ACCOUNT.retry_after(key) if config.RATE_LIMITS_ENABLED else 0
    if wait:
        raise HTTPException(429, "Too many wrong passwords. Try again in a few minutes.", headers={"Retry-After": str(wait)})
    if not verify_password(body.current_password, user.password_hash):
        if config.RATE_LIMITS_ENABLED:
            ratelimit.LOGIN_ACCOUNT.hit(key)
        raise HTTPException(400, "The current password is wrong")
    if body.new_password == body.current_password:
        raise HTTPException(422, "Choose a different password from the current one")
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    db.commit()
    log.info("Password changed for user %s", user.id)
    return TokenOut(token=create_token(user.id))  # this session carries on; every older one is signed out


@router.post("/email", response_model=TokenOut)
def change_email(body: EmailChange, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Needs the password, like a password change: a borrowed phone must not be able to take over the account.
    Every other session is signed out, because the sign-in address is part of who can get in."""
    key = f"u{user.id}"
    wait = ratelimit.LOGIN_ACCOUNT.retry_after(key) if config.RATE_LIMITS_ENABLED else 0
    if wait:
        raise HTTPException(429, "Too many wrong passwords. Try again in a few minutes.", headers={"Retry-After": str(wait)})
    if not verify_password(body.current_password, user.password_hash):
        if config.RATE_LIMITS_ENABLED:
            ratelimit.LOGIN_ACCOUNT.hit(key)
        raise HTTPException(400, "The current password is wrong")
    new_email = body.new_email.strip().lower()
    if new_email == user.email:
        raise HTTPException(422, "That is already your email")
    if db.scalar(select(User.id).where(User.email == new_email)):
        raise HTTPException(409, "An account with this email already exists")
    user.email = new_email
    user.password_changed_at = utcnow()
    try:
        db.commit()
    except IntegrityError:  # someone registered it in the same instant
        db.rollback()
        raise HTTPException(409, "An account with this email already exists")
    log.info("Email changed for user %s", user.id)
    return TokenOut(token=create_token(user.id))
