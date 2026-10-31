import hmac
import hashlib

import httpx
import pytest

from app import config, payments
from tests.conftest import add_service, new_expert, new_user

PDF = b"%PDF-1.4 a pretend resume template"


def upload(client, headers, service_id, name="template.pdf", data=PDF, declaration="true"):
    return client.post(
        f"/api/expert/services/{service_id}/file", headers=headers,
        files={"file": (name, data, "application/pdf")}, data={"declaration": declaration},
    )


def document_shop(client, price=199, with_file=True):
    headers, handle = new_expert(client)
    service = add_service(client, headers, kind="document", title="Resume template", price_rupees=price, duration_min=None)
    if with_file:
        assert upload(client, headers, service["id"]).status_code == 200
    return headers, handle, service


def buy(client, seeker, service_id):
    created = client.post("/api/bookings", headers=seeker, json={"service_id": service_id})
    assert created.status_code == 201, created.text
    booking = created.json()["booking"]
    if created.json()["payment"]:
        assert client.post(f"/api/bookings/{booking['id']}/pay", headers=seeker, json={}).status_code == 200
    return booking


# ------------------------------------------------------------------ documents

def test_buying_a_document_and_downloading_it(client, seeker):
    _, _, service = document_shop(client)
    booking = buy(client, seeker, service["id"])
    docs = client.get("/api/me/bookings", headers=seeker, params={"tab": "documents"}).json()
    assert [d["id"] for d in docs] == [booking["id"]] and docs[0]["has_file"] and docs[0]["file_name"] == "template.pdf"

    res = client.get(f"/api/me/bookings/{booking['id']}/download", headers=seeker)
    assert res.status_code == 200 and res.content == PDF
    assert res.headers["content-disposition"].startswith("attachment") and res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-type"] == "application/octet-stream"  # never shown as a web page


def test_only_the_buyer_can_download(client, seeker):
    expert, _, service = document_shop(client)
    booking = buy(client, seeker, service["id"])
    assert client.get(f"/api/me/bookings/{booking['id']}/download", headers=new_user(client, "seeker")).status_code == 404
    assert client.get(f"/api/me/bookings/{booking['id']}/download").status_code == 401
    assert client.get(f"/api/expert/services/{service['id']}/file", headers=expert).content == PDF  # the author can fetch their own
    assert client.get(f"/api/expert/services/{service['id']}/file", headers=new_expert(client)[0]).status_code == 404


def test_an_unpaid_order_gives_no_file(client, seeker):
    _, _, service = document_shop(client)
    created = client.post("/api/bookings", headers=seeker, json={"service_id": service["id"]}).json()["booking"]
    assert created["status"] == "pending"
    assert client.get(f"/api/me/bookings/{created['id']}/download", headers=seeker).status_code == 404


def test_a_document_cannot_be_sold_before_its_file_exists_or_bought_twice(client, seeker):
    _, _, empty = document_shop(client, with_file=False)
    assert client.post("/api/bookings", headers=seeker, json={"service_id": empty["id"]}).status_code == 409
    _, _, service = document_shop(client)
    buy(client, seeker, service["id"])
    again = client.post("/api/bookings", headers=seeker, json={"service_id": service["id"]})
    assert again.status_code == 409 and "already own" in again.json()["detail"]


def test_a_free_document_is_delivered_immediately(client, seeker):
    _, _, service = document_shop(client, price=0)
    created = client.post("/api/bookings", headers=seeker, json={"service_id": service["id"]}).json()
    assert created["payment"] is None and created["booking"]["status"] == "paid"
    assert client.get(f"/api/me/bookings/{created['booking']['id']}/download", headers=seeker).content == PDF


def test_upload_rules(client, monkeypatch):
    headers, _ = new_expert(client)
    doc = add_service(client, headers, kind="document", title="Guide", price_rupees=50, duration_min=None)
    call = add_service(client, headers, title="A call")
    assert upload(client, headers, doc["id"], declaration="false").status_code == 422  # the seller must confirm
    assert upload(client, headers, doc["id"], name="run.exe").status_code == 415
    assert upload(client, headers, doc["id"], data=b"").status_code == 422
    assert upload(client, headers, call["id"]).status_code == 422  # a call has no file
    monkeypatch.setattr(config, "MAX_FILE_MB", 1)
    assert upload(client, headers, doc["id"], data=b"x" * (1024 * 1024 + 1)).status_code == 413
    assert upload(client, new_expert(client)[0], doc["id"]).status_code == 404  # not their service


def test_file_names_are_cleaned(client):
    headers, _ = new_expert(client)
    doc = add_service(client, headers, kind="document", title="Guide", price_rupees=50, duration_min=None)
    res = upload(client, headers, doc["id"], name="../../etc/<script>passwd.pdf")
    assert res.status_code == 200 and "/" not in res.json()["file_name"] and "<" not in res.json()["file_name"]
    assert upload(client, headers, doc["id"], name="v2.pdf", data=b"newer").json()["file_name"] == "v2.pdf"  # replaced, not added


# ------------------------------------------------------------------ priority DMs

def test_priority_dm_question_and_answer(client, seeker):
    expert, handle = new_expert(client)
    dm = add_service(client, expert, kind="dm", title="Ask me anything", price_rupees=99, duration_min=None, reply_hours=24)
    short = client.post("/api/bookings", headers=seeker, json={"service_id": dm["id"], "note": "hi"})
    assert short.status_code == 422  # a real question is needed

    created = client.post("/api/bookings", headers=seeker, json={"service_id": dm["id"], "note": "Which AWS certificate should I take first?"}).json()
    client.post(f"/api/bookings/{created['booking']['id']}/pay", headers=seeker, json={})
    assert client.get("/api/expert/summary", headers=expert).json()["pending_dms"] == 1

    assert client.post(f"/api/expert/bookings/{created['booking']['id']}/answer", headers=new_expert(client)[0], json={"answer": "Not yours to answer"}).status_code == 404
    answered = client.post(f"/api/expert/bookings/{created['booking']['id']}/answer", headers=expert, json={"answer": "Start with Cloud Practitioner."})
    assert answered.status_code == 200 and answered.json()["answered_at"]

    mine = client.get("/api/me/bookings", headers=seeker, params={"tab": "messages"}).json()
    assert mine[0]["answer"] == "Start with Cloud Practitioner." and mine[0]["note"].startswith("Which AWS")
    assert client.get("/api/expert/summary", headers=expert).json()["pending_dms"] == 0


# ------------------------------------------------------------------ payment signatures

def test_the_signature_matches_razorpays_formula():
    expected = hmac.new(b"topsecret", b"order_ABC|pay_XYZ", hashlib.sha256).hexdigest()
    assert payments.signature_for("order_ABC", "pay_XYZ", "topsecret") == expected


def real_keys(monkeypatch):
    monkeypatch.setattr(config, "RAZORPAY_KEY_ID", "rzp_test_publicid")
    monkeypatch.setattr(config, "RAZORPAY_KEY_SECRET", "rzp_secret_value")


def fake_razorpay(monkeypatch, order_id="order_TEST1"):
    sent = {}

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {"id": order_id}

    def post(url, auth=None, json=None, timeout=None):
        sent.update(url=url, auth=auth, json=json)
        return Reply()

    monkeypatch.setattr(payments.httpx, "post", post)
    return sent


def test_a_real_payment_must_carry_a_valid_signature(client, seeker, monkeypatch):
    real_keys(monkeypatch)
    sent = fake_razorpay(monkeypatch)
    _, _, service = document_shop(client, price=299)
    created = client.post("/api/bookings", headers=seeker, json={"service_id": service["id"]}).json()
    assert created["payment"] == {"mode": "razorpay", "order_id": "order_TEST1", "key_id": "rzp_test_publicid", "amount_paise": 29900, "currency": "INR"}
    assert sent["json"]["amount"] == 29900 and sent["json"]["currency"] == "INR" and sent["auth"] == ("rzp_test_publicid", "rzp_secret_value")
    assert "rzp_secret_value" not in str(created)  # the secret never goes to the browser

    bid = created["booking"]["id"]
    forged = {"razorpay_payment_id": "pay_FAKE", "razorpay_signature": "0" * 64}
    assert client.post(f"/api/bookings/{bid}/pay", headers=seeker, json=forged).status_code == 400
    assert client.post(f"/api/bookings/{bid}/pay", headers=seeker, json={}).status_code == 400  # the mock button does not work on a real order
    assert client.get(f"/api/me/bookings/{bid}/download", headers=seeker).status_code == 404  # still nothing delivered

    good = {"razorpay_payment_id": "pay_REAL", "razorpay_signature": payments.signature_for("order_TEST1", "pay_REAL", "rzp_secret_value")}
    paid = client.post(f"/api/bookings/{bid}/pay", headers=seeker, json=good)
    assert paid.status_code == 200 and paid.json()["status"] == "paid"
    assert client.get(f"/api/me/bookings/{bid}/download", headers=seeker).content == PDF


def test_a_signature_for_another_order_is_rejected(monkeypatch):
    real_keys(monkeypatch)
    sig = payments.signature_for("order_A", "pay_1", "rzp_secret_value")
    assert payments.verify("order_A", "pay_1", sig) is True
    assert payments.verify("order_B", "pay_1", sig) is False  # same payment, different order
    assert payments.verify("order_A", "pay_2", sig) is False
    assert payments.verify("order_A", None, sig) is False and payments.verify("order_A", "pay_1", None) is False
    assert payments.verify("mock_abc", None, None) is False  # mock orders do not exist in real mode


def test_a_real_order_cannot_be_paid_with_the_mock_button():
    assert config.payment_mode() == "mock"
    assert payments.verify("order_REAL123", "pay_1", "anything") is False
    assert payments.verify("mock_abc", None, None) is True


def test_when_razorpay_is_down_the_slot_is_given_back(client, seeker, monkeypatch):
    from tests.test_bookings import book, call_setup, slots_for

    real_keys(monkeypatch)
    _, handle, service = call_setup(client)
    slot = slots_for(client, handle, service["id"])[0]

    def down(*args, **kwargs):
        raise httpx.ConnectError("could not connect to https://api.razorpay.com?key=rzp_secret_value")

    monkeypatch.setattr(payments.httpx, "post", down)
    res = book(client, seeker, service["id"], slot)
    assert res.status_code == 502 and "rzp_secret_value" not in res.text  # no secret in the error either
    assert slot in slots_for(client, handle, service["id"])  # nobody is left holding it
