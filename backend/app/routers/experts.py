import re
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config, slots
from ..db import get_db
from ..models import Availability, Booking, Expert, Service, ServiceFile, User, utcnow
from ..schemas import (
    AnswerIn, BookingOut, ExpertCard, ExpertIn, ExpertPublic, ExpertUpdate, ServiceIn, ServiceOut, SlotsOut, Summary, WindowIn,
)
from ..security import current_expert, current_user
from ..views import bookings_out, services_out

public = APIRouter(prefix="/api/experts", tags=["experts"])
manage = APIRouter(prefix="/api/expert", tags=["expert"])

ALLOWED_FILES = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".zip"}


# ---------------------------------------------------------------- public pages

@public.get("", response_model=list[ExpertCard])
def explore(q: str = "", db: Session = Depends(get_db)):
    """Experts who have at least one active service, newest first."""
    stmt = (
        select(Expert, User.name, func.min(Service.price_paise), func.count(Service.id))
        .join(User, User.id == Expert.user_id)
        .join(Service, Service.expert_id == Expert.user_id)
        .where(Service.is_active.is_(True))
        .group_by(Expert.user_id, User.name)
        .order_by(Expert.created_at.desc())
        .limit(60)
    )
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.name.ilike(like), Expert.handle.ilike(like), Expert.headline.ilike(like), Expert.bio.ilike(like)))
    return [
        ExpertCard(handle=e.handle, name=name, headline=e.headline, from_paise=cheapest, services=count)
        for e, name, cheapest, count in db.execute(stmt).all()
    ]


def _expert_by_handle(db: Session, handle: str) -> tuple[Expert, User]:
    expert = db.scalar(select(Expert).where(Expert.handle == handle.lower()))
    if expert is None:
        raise HTTPException(404, "No expert with this name")
    return expert, db.get(User, expert.user_id)


@public.get("/{handle}", response_model=ExpertPublic)
def expert_page(handle: str, db: Session = Depends(get_db)):
    expert, user = _expert_by_handle(db, handle)
    active = db.scalars(select(Service).where(Service.expert_id == expert.user_id, Service.is_active.is_(True)).order_by(Service.id)).all()
    return ExpertPublic(handle=expert.handle, name=user.name, headline=expert.headline, bio=expert.bio, timezone=expert.timezone, services=services_out(db, list(active)))


@public.get("/{handle}/slots", response_model=SlotsOut)
def expert_slots(handle: str, service_id: int, days: int = Query(7, ge=1, le=14), from_date: date | None = None, db: Session = Depends(get_db)):
    expert, _ = _expert_by_handle(db, handle)
    service = db.get(Service, service_id)
    if service is None or service.expert_id != expert.user_id or not service.is_active or service.kind != "call":
        raise HTTPException(404, "This is not a bookable call")
    slots.expire_stale_holds(db)
    found = slots.available_slots(db, expert, service, from_date, days)
    return SlotsOut(timezone=expert.timezone, duration_min=service.duration_min or 30, slots=found)


# ---------------------------------------------------------------- the expert's own area

@manage.post("", status_code=201)
def become_expert(body: ExpertIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if db.get(Expert, user.id):
        raise HTTPException(409, "You already have an expert page")
    if not slots.valid_timezone(body.timezone):
        raise HTTPException(422, "Unknown time zone")
    db.add(Expert(user_id=user.id, handle=body.handle, headline=body.headline.strip(), bio=body.bio.strip(), timezone=body.timezone))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "That page name is taken, try another")
    return {"handle": body.handle}


@manage.get("/me")
def my_expert(expert: Expert = Depends(current_expert)):
    return {"handle": expert.handle, "headline": expert.headline, "bio": expert.bio, "timezone": expert.timezone}


@manage.put("/me")
def update_expert(body: ExpertUpdate, expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    if not slots.valid_timezone(body.timezone):
        raise HTTPException(422, "Unknown time zone")
    expert.headline, expert.bio, expert.timezone = body.headline.strip(), body.bio.strip(), body.timezone
    db.commit()
    return my_expert(expert)


def _check_service(body: ServiceIn) -> dict:
    if body.kind == "call" and not body.duration_min:
        raise HTTPException(422, "A call needs a length in minutes")
    return {
        "kind": body.kind, "title": body.title.strip(), "description": body.description.strip(),
        "price_paise": body.price_rupees * 100,
        "duration_min": body.duration_min if body.kind == "call" else None,
        "reply_hours": (body.reply_hours or 48) if body.kind == "dm" else None,
        "is_active": body.is_active,
    }


def _own_service(db: Session, expert: Expert, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if service is None or service.expert_id != expert.user_id:
        raise HTTPException(404, "Service not found")
    return service


@manage.get("/services", response_model=list[ServiceOut])
def my_services(expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    return services_out(db, list(db.scalars(select(Service).where(Service.expert_id == expert.user_id).order_by(Service.id))))


@manage.post("/services", response_model=ServiceOut, status_code=201)
def add_service(body: ServiceIn, expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    service = Service(expert_id=expert.user_id, **_check_service(body))
    db.add(service)
    db.commit()
    return services_out(db, [service])[0]


@manage.put("/services/{service_id}", response_model=ServiceOut)
def edit_service(service_id: int, body: ServiceIn, expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    service = _own_service(db, expert, service_id)
    if body.kind != service.kind:
        raise HTTPException(422, "The type of a service cannot be changed. Add a new one instead.")
    for key, value in _check_service(body).items():
        setattr(service, key, value)
    db.commit()
    return services_out(db, [service])[0]


@manage.delete("/services/{service_id}", status_code=204)
def remove_service(service_id: int, expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    service = _own_service(db, expert, service_id)
    if db.scalar(select(func.count()).select_from(Booking).where(Booking.service_id == service.id, Booking.status == "paid")):
        raise HTTPException(409, "People have already bought this. Hide it instead of deleting it.")
    db.query(Booking).filter(Booking.service_id == service.id).delete()
    db.query(ServiceFile).filter(ServiceFile.service_id == service.id).delete()
    db.delete(service)
    db.commit()


def _safe_name(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", (name or "file").replace("\\", "/").split("/")[-1]).strip(" .")
    return (base or "file")[:150]


@manage.post("/services/{service_id}/file", response_model=ServiceOut)
async def upload_file(
    service_id: int,
    file: UploadFile = File(...),
    declaration: bool = Form(...),
    expert: Expert = Depends(current_expert),
    db: Session = Depends(get_db),
):
    service = _own_service(db, expert, service_id)
    if service.kind != "document":
        raise HTTPException(422, "Only a document service has a file")
    if not declaration:
        raise HTTPException(422, "Please confirm that the file does not contain anyone else's personal contact details")
    name = _safe_name(file.filename or "")
    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_FILES:
        raise HTTPException(415, "Allowed files: " + ", ".join(sorted(ALLOWED_FILES)))
    limit = config.MAX_FILE_MB * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"The file is larger than {config.MAX_FILE_MB} MB")
    if not data:
        raise HTTPException(422, "The file is empty")
    row = db.get(ServiceFile, service.id)
    if row:
        row.filename, row.size, row.data = name, len(data), data
    else:
        db.add(ServiceFile(service_id=service.id, filename=name, size=len(data), data=data))
    db.commit()
    return services_out(db, [service])[0]


def file_response(row: ServiceFile) -> Response:
    # Always a download, never rendered by the browser, so an uploaded file can never run as a web page
    return Response(
        content=row.data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{row.filename}"', "X-Content-Type-Options": "nosniff"},
    )


@manage.get("/services/{service_id}/file")
def own_file(service_id: int, expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    service = _own_service(db, expert, service_id)
    row = db.get(ServiceFile, service.id)
    if row is None:
        raise HTTPException(404, "No file uploaded yet")
    return file_response(row)


@manage.get("/availability")
def get_availability(expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    rows = db.scalars(select(Availability).where(Availability.expert_id == expert.user_id).order_by(Availability.weekday, Availability.start_min))
    return [{"weekday": r.weekday, "start_min": r.start_min, "end_min": r.end_min} for r in rows]


@manage.put("/availability")
def set_availability(windows: list[WindowIn], expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    if len(windows) > 28:
        raise HTTPException(422, "Too many windows")
    by_day: dict[int, list[WindowIn]] = {}
    for w in windows:
        if w.start_min >= w.end_min:
            raise HTTPException(422, "Each window must end after it starts")
        by_day.setdefault(w.weekday, []).append(w)
    for day_windows in by_day.values():
        ordered = sorted(day_windows, key=lambda x: x.start_min)
        if any(a.end_min > b.start_min for a, b in zip(ordered, ordered[1:])):
            raise HTTPException(422, "Two windows on the same day overlap")
    db.query(Availability).filter(Availability.expert_id == expert.user_id).delete()
    db.add_all([Availability(expert_id=expert.user_id, weekday=w.weekday, start_min=w.start_min, end_min=w.end_min) for w in windows])
    db.commit()
    return get_availability(expert, db)


@manage.get("/bookings", response_model=list[BookingOut])
def my_sales(expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    rows = db.scalars(select(Booking).where(Booking.expert_id == expert.user_id, Booking.status == "paid").order_by(Booking.paid_at.desc()).limit(300)).all()
    return bookings_out(db, list(rows), with_seeker=True)


@manage.get("/summary", response_model=Summary)
def summary(expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    paid = db.scalars(select(Booking).where(Booking.expert_id == expert.user_id, Booking.status == "paid")).all()
    gross = sum(b.amount_paise for b in paid)
    fee = gross * config.PLATFORM_FEE_PERCENT // 100
    now = utcnow()
    by_kind: dict[str, int] = {}
    for b in paid:
        by_kind[b.kind] = by_kind.get(b.kind, 0) + 1
    return Summary(
        orders=len(paid), gross_paise=gross, fee_paise=fee, net_paise=gross - fee, fee_percent=config.PLATFORM_FEE_PERCENT, by_kind=by_kind,
        pending_dms=sum(1 for b in paid if b.kind == "dm" and b.answer is None),
        upcoming_calls=sum(1 for b in paid if b.kind == "call" and b.slot_end and b.slot_end >= now),
    )


@manage.post("/bookings/{booking_id}/answer", response_model=BookingOut)
def answer_dm(booking_id: int, body: AnswerIn, expert: Expert = Depends(current_expert), db: Session = Depends(get_db)):
    booking = db.get(Booking, booking_id)
    if booking is None or booking.expert_id != expert.user_id or booking.kind != "dm" or booking.status != "paid":
        raise HTTPException(404, "Message not found")
    booking.answer, booking.answered_at = body.answer.strip(), utcnow()
    db.commit()
    return bookings_out(db, [booking], with_seeker=True)[0]
