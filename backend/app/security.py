import hashlib
import hmac
import os
import time

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import Expert, User

_bearer = HTTPBearer(auto_error=False)
_LEGACY_ITERATIONS = 200_000  # the first format, "salt$digest", before the count was stored with the hash


def hash_password(password: str) -> str:
    """Stored as pbkdf2$<iterations>$<salt>$<digest>, so the work factor can be raised without breaking old hashes."""
    iterations = config.PBKDF2_ITERATIONS
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


def _parse(stored: str) -> tuple[int, bytes, str]:
    parts = stored.split("$")
    if len(parts) == 4 and parts[0] == "pbkdf2":
        return int(parts[1]), bytes.fromhex(parts[2]), parts[3]
    if len(parts) == 2:
        return _LEGACY_ITERATIONS, bytes.fromhex(parts[0]), parts[1]
    raise ValueError("unknown hash format")


def verify_password(password: str, stored: str) -> bool:
    try:
        iterations, salt, expected = _parse(stored)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return hmac.compare_digest(digest.hex(), expected)
    except ValueError:
        return False


def needs_rehash(stored: str) -> bool:
    try:
        return _parse(stored)[0] < config.PBKDF2_ITERATIONS
    except ValueError:
        return True


# Checked when the email is unknown, so "no such account" takes as long as "wrong password" and the response
# time does not reveal which emails are registered.
_DUMMY_HASH = hash_password("not-a-real-password")


def spend_time_like_a_login(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def create_token(user_id: int) -> str:
    now = int(time.time())
    payload = {"sub": str(user_id), "iat": now, "exp": now + config.TOKEN_HOURS * 3600}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(401, "Not signed in")
    try:
        # The algorithm is pinned (a token cannot pick "none"), and a token without an expiry is refused
        payload = jwt.decode(creds.credentials, config.JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Session expired, please sign in again")
    if user is None:
        raise HTTPException(401, "Account not found")
    return user


def current_expert(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Expert:
    expert = db.get(Expert, user.id)
    if expert is None:
        raise HTTPException(403, "Create your expert page first")
    return expert
