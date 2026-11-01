"""Fills a local Sessio with demo people so the dashboard has something to show. Local use only."""
import datetime as dt
import sys

import httpx

BASE = "http://127.0.0.1:8010/api"
PASSWORD = "demo-pass-phrase-1"
c = httpx.Client(base_url=BASE, timeout=30)


def user(name, email):
    r = c.post("/auth/register", json={"name": name, "email": email, "password": PASSWORD})
    if r.status_code == 409:
        r = c.post("/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["token"]}


def expert(name, email, handle, headline, category, services):
    h = user(name, email)
    r = c.post("/expert", headers=h, json={"handle": handle, "headline": headline, "bio": headline, "timezone": "Asia/Kolkata", "category": category})
    if r.status_code not in (201, 409):
        r.raise_for_status()
    c.put("/expert/availability", headers=h, json=[{"weekday": d, "start_min": 540, "end_min": 1080} for d in range(7)]).raise_for_status()
    made = {}
    for key, body in services.items():
        if body.get("call_ref"):
            body = {**body, "call_service_id": made[body["call_ref"]]["id"]}
            body.pop("call_ref")
        r = c.post("/expert/services", headers=h, json=body)
        r.raise_for_status()
        made[key] = r.json()
    doc = made.get("doc")
    if doc:
        files = {"file": ("aws-study-plan.pdf", b"%PDF-1.4 demo study plan", "application/pdf")}
        c.post(f"/expert/services/{doc['id']}/file", headers=h, files=files, data={"declaration": "true"}).raise_for_status()
    return h, made


def when(days, hour=19):
    d = (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return d.isoformat() + "Z"


asha_h, asha = expert(
    "Asha Verma", "asha@example.test", "asha", "Cloud engineer. I help freshers land their first AWS role.", "tech",
    {
        "call": {"kind": "call", "title": "Resume review and AWS career advice", "price_rupees": 500, "duration_min": 30},
        "doc": {"kind": "document", "title": "AWS Cloud Practitioner 4-week study plan", "price_rupees": 199},
        "dm": {"kind": "dm", "title": "Ask me anything about AWS", "price_rupees": 99, "reply_hours": 48},
        "webinar": {"kind": "webinar", "title": "Cloud careers for freshers (4-week cohort)", "price_rupees": 499, "duration_min": 60, "capacity": 25,
                    "sessions": [when(4), when(11), when(18), when(25)]},
        "package": {"kind": "package", "title": "3 mock interviews", "price_rupees": 1200, "credits": 3, "valid_days": 60, "call_ref": "call"},
        "club": {"kind": "membership", "title": "Asha's monthly club", "price_rupees": 299, "description": "Every guide and template I write, as long as you are a member."},
    },
)
expert("Rahul Nair", "rahul@example.test", "rahul-nair", "Product designer. Portfolio reviews that get interviews.", "design",
       {"call": {"kind": "call", "title": "Portfolio review", "price_rupees": 400, "duration_min": 45}})
expert("Meera Iyer", "meera@example.test", "meera", "CA. Taxes and first-job money questions, answered plainly.", "finance",
       {"dm": {"kind": "dm", "title": "One money question", "price_rupees": 149, "reply_hours": 24}})

ravi = user("Ravi Kumar", "ravi@example.test")
svc = c.get("/experts/asha").json()["services"]
by = {s["kind"]: s for s in svc}


def buy(s, **extra):
    r = c.post("/bookings", headers=ravi, json={"service_id": s["id"], "note": "How should I start learning AWS as a fresher?", **extra})
    r.raise_for_status()
    created = r.json()
    if created["payment"]:
        c.post(f"/bookings/{created['booking']['id']}/pay", headers=ravi, json={}).raise_for_status()
    return created["booking"]["id"]


buy(by["document"])
dm_id = buy(by["dm"])
buy(by["webinar"])
pkg = buy(by["package"])
day = (dt.date.today() + dt.timedelta(days=2)).isoformat()
slot = c.get("/experts/asha/slots", params={"service_id": by["call"]["id"], "days": 1, "from_date": day}).json()["slots"][0]
buy(by["call"], slot_start=slot, package_booking_id=pkg)
c.post(f"/expert/bookings/{dm_id}/answer", headers=asha_h, json={"answer": "Start with the Cloud Practitioner guide, then build one small S3 + EC2 project."}).raise_for_status()
sub = c.post("/subscriptions", headers=ravi, json={"service_id": by["membership"]["id"]}).json()
c.post(f"/subscriptions/{sub['subscription']['id']}/pay", headers=ravi, json={}).raise_for_status()
print("seeded", file=sys.stderr)
