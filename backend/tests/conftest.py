import itertools
import os
import tempfile

# Must be set before the app is imported: a throwaway database, mock payments, no real keys
_dir = tempfile.mkdtemp()
# Normally a throwaway SQLite file. Set TEST_DATABASE_URL to a Postgres URL to run the same tests on Postgres.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_dir}/test.db"
os.environ["RAZORPAY_KEY_ID"] = ""
os.environ["RAZORPAY_KEY_SECRET"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

_counter = itertools.count(1)
PASSWORD = "correct-horse-1"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def new_user(client, prefix="user") -> dict:
    """A fresh account, returned as request headers."""
    n = next(_counter)
    token = client.post("/api/auth/register", json={"name": f"{prefix.title()} {n}", "email": f"{prefix}{n}@example.com", "password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def new_expert(client, prefix="expert") -> tuple[dict, str]:
    """A fresh expert with a page, returned as (headers, handle)."""
    headers = new_user(client, prefix)
    handle = f"{prefix}-{next(_counter)}"
    res = client.post("/api/expert", headers=headers, json={"handle": handle, "headline": "Helps with careers", "bio": "Ten years in tech."})
    assert res.status_code == 201, res.text
    return headers, handle


def open_every_day(client, headers, start=18 * 60, end=21 * 60):
    """Availability on all seven days, so slot tests do not depend on the weekday the test runs on."""
    res = client.put("/api/expert/availability", headers=headers, json=[{"weekday": d, "start_min": start, "end_min": end} for d in range(7)])
    assert res.status_code == 200, res.text


def add_service(client, headers, **fields) -> dict:
    body = {"kind": "call", "title": "Career chat", "description": "", "price_rupees": 500, "duration_min": 30, **fields}
    res = client.post("/api/expert/services", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture()
def seeker(client):
    return new_user(client, "seeker")


@pytest.fixture()
def expert(client):
    return new_expert(client)
