from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Expert, User
from ..schemas import Login, MeOut, Register, TokenOut
from ..security import create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: Register, db: Session = Depends(get_db)):
    user = User(email=body.email.strip().lower(), name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists")
    return TokenOut(token=create_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(body: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    # One message for "no such user" and "wrong password", so emails cannot be probed
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return TokenOut(token=create_token(user.id))


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    expert = db.get(Expert, user.id)
    return MeOut(id=user.id, name=user.name, email=user.email, handle=expert.handle if expert else None)
