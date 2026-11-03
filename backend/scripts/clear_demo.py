r"""Removes the demo people made by seed_demo.py, and everything that belongs to them, from the local database.

Only accounts whose email ends in @example.test are touched. Real accounts stay as they are, except that
purchases they made from a demo expert go with that expert.

Run from the backend folder:  .venv\Scripts\python scripts\clear_demo.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, or_, select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Availability, Booking, Expert, Service, ServiceFile, ServiceSession, Subscription, User  # noqa: E402


def main() -> None:
    with SessionLocal() as db:
        ids = list(db.scalars(select(User.id).where(User.email.like("%@example.test"))))
        if not ids:
            print("No demo accounts found. Nothing to remove.")
            return
        services = list(db.scalars(select(Service.id).where(Service.expert_id.in_(ids))))
        db.execute(delete(Booking).where(or_(Booking.seeker_id.in_(ids), Booking.expert_id.in_(ids))))
        db.execute(delete(Subscription).where(or_(Subscription.seeker_id.in_(ids), Subscription.expert_id.in_(ids))))
        if services:
            db.execute(delete(ServiceSession).where(ServiceSession.service_id.in_(services)))
            db.execute(delete(ServiceFile).where(ServiceFile.service_id.in_(services)))
        db.execute(delete(Service).where(Service.expert_id.in_(ids)))
        db.execute(delete(Availability).where(Availability.expert_id.in_(ids)))
        db.execute(delete(Expert).where(Expert.user_id.in_(ids)))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.commit()
        print(f"Removed {len(ids)} demo accounts and their pages, services, files and orders.")


if __name__ == "__main__":
    main()
