r"""Local-only: set a new password (and optionally a new email) for an account in YOUR OWN laptop database.

Sessio has no "forgot password" email yet, so this is the way back in on a local run. It refuses to run against a
production setup or any database other than a local SQLite file, so it cannot be pointed at a live site by accident.

Run from the backend folder:  .venv\Scripts\python scripts\reset_account.py
The password you type is visible in this window (pasting into a hidden prompt fails in some Windows consoles).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app import config  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import User, utcnow  # noqa: E402
from app.schemas import check_password_strength  # noqa: E402
from app.security import hash_password  # noqa: E402

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def main() -> int:
    if config.PRODUCTION or not config.DATABASE_URL.startswith("sqlite"):
        print("Stopped: this tool only works on a local SQLite database, never on a live site.")
        return 1
    with SessionLocal() as db:
        users = list(db.scalars(select(User).order_by(User.id)))
        if not users:
            print("There are no accounts in this database yet. Create one with Get started on the site.")
            return 1
        print("Accounts in this local database:\n")
        for i, u in enumerate(users, 1):
            print(f"  {i}. {u.name}  <{u.email}>")
        choice = input("\nWhich account (number)? ").strip()
        if not choice.isdigit() or not 1 <= int(choice) <= len(users):
            print("Stopped: that is not one of the numbers above.")
            return 1
        user = users[int(choice) - 1]

        new_email = input(f"New email (press Enter to keep {user.email}): ").strip().lower()
        if new_email:
            if not EMAIL.match(new_email) or len(new_email) > 254:
                print("Stopped: that does not look like an email address.")
                return 1
            taken = db.scalar(select(User.id).where(User.email == new_email, User.id != user.id))
            if taken:
                print("Stopped: another account already uses that email.")
                return 1

        password = input("New password (at least 10 characters, visible as you type): ").strip()
        try:
            if len(password) < 10 or len(password) > 128:
                raise ValueError("The password must be 10 to 128 characters.")
            check_password_strength(password)
        except ValueError as exc:
            print(f"Stopped: {exc}")
            return 1

        user.password_hash = hash_password(password)
        user.password_changed_at = utcnow()  # signs out every old session, including the open browser tab
        if new_email:
            user.email = new_email
        db.commit()
        print(f"\nDone. Sign in as {user.email} with the new password. Old sessions were signed out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
