from tests.conftest import PASSWORD, add_service, new_expert, new_user, open_every_day


def test_register_login_and_duplicate(client):
    body = {"name": "Asha Rao", "email": "Asha@Example.com", "password": PASSWORD}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": PASSWORD}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong-password"}).status_code == 401


def test_validation_and_auth_required(client):
    assert client.post("/api/auth/register", json={"name": "A", "email": "nope", "password": PASSWORD}).status_code == 422
    assert client.post("/api/auth/register", json={"name": "Asha", "email": "a@b.co", "password": "short"}).status_code == 422
    assert client.get("/api/me/bookings").status_code == 401
    assert client.get("/api/expert/services").status_code == 401


def test_me_shows_the_handle_once_there_is_an_expert_page(client):
    headers, handle = new_expert(client)
    assert client.get("/api/auth/me", headers=headers).json()["handle"] == handle
    assert client.get("/api/auth/me", headers=new_user(client)).json()["handle"] is None


def test_expert_page_names_are_checked(client):
    headers = new_user(client)
    for bad in ("ab", "Has Space", "-start", "x" * 31, "admin", "api"):
        assert client.post("/api/expert", headers=headers, json={"handle": bad}).status_code == 422, bad
    assert client.post("/api/expert", headers=headers, json={"handle": "Mixed-Case-1"}).status_code == 201  # lower-cased
    assert client.get("/api/experts/mixed-case-1").json()["handle"] == "mixed-case-1"
    assert client.post("/api/expert", headers=headers, json={"handle": "another-one"}).status_code == 409  # one page per person
    other = new_user(client)
    assert client.post("/api/expert", headers=other, json={"handle": "mixed-case-1"}).status_code == 409  # name taken


def test_only_active_services_are_public_and_prices_are_in_paise(client):
    headers, handle = new_expert(client)
    assert client.get(f"/api/experts/{handle}").json()["services"] == []
    visible = add_service(client, headers, title="Visible call", price_rupees=499)
    hidden = add_service(client, headers, title="Hidden call", is_active=False)
    page = client.get(f"/api/experts/{handle}").json()
    assert [s["id"] for s in page["services"]] == [visible["id"]]
    assert page["services"][0]["price_paise"] == 49900
    assert hidden["is_active"] is False
    assert "email" not in str(page).lower()  # the public page never shows contact details


def test_service_rules(client):
    headers, _ = new_expert(client)
    assert client.post("/api/expert/services", headers=headers, json={"kind": "call", "title": "No length", "price_rupees": 100}).status_code == 422
    dm = add_service(client, headers, kind="dm", title="Ask me", duration_min=None, reply_hours=None)
    assert dm["reply_hours"] == 48 and dm["duration_min"] is None
    doc = add_service(client, headers, kind="document", title="Resume template", price_rupees=0, duration_min=None)
    assert doc["duration_min"] is None
    # the type cannot be switched afterwards
    assert client.put(f"/api/expert/services/{doc['id']}", headers=headers, json={"kind": "call", "title": "Now a call", "price_rupees": 0, "duration_min": 30}).status_code == 422


def test_nobody_edits_someone_elses_service(client):
    owner, _ = new_expert(client)
    service = add_service(client, owner)
    intruder, _ = new_expert(client)
    body = {"kind": "call", "title": "Hijacked", "price_rupees": 1, "duration_min": 30}
    assert client.put(f"/api/expert/services/{service['id']}", headers=intruder, json=body).status_code == 404
    assert client.delete(f"/api/expert/services/{service['id']}", headers=intruder).status_code == 404


def test_availability_rules(client):
    headers, _ = new_expert(client)
    window = lambda day, a, b: {"weekday": day, "start_min": a, "end_min": b}  # noqa: E731
    assert client.put("/api/expert/availability", headers=headers, json=[window(0, 600, 600)]).status_code == 422  # ends when it starts
    assert client.put("/api/expert/availability", headers=headers, json=[window(0, 600, 720), window(0, 700, 800)]).status_code == 422  # overlap
    assert client.put("/api/expert/availability", headers=headers, json=[window(0, 600, 720), window(1, 700, 800)]).status_code == 200
    assert len(client.get("/api/expert/availability", headers=headers).json()) == 2
    open_every_day(client, headers)  # replaces, not adds
    assert len(client.get("/api/expert/availability", headers=headers).json()) == 7


def test_explore_lists_experts_with_a_service_and_searches(client):
    headers, handle = new_expert(client, "searchable")
    assert handle not in [e["handle"] for e in client.get("/api/experts").json()]  # no service yet
    add_service(client, headers, price_rupees=250)
    add_service(client, headers, kind="dm", title="Quick question", price_rupees=99, duration_min=None)
    cards = {e["handle"]: e for e in client.get("/api/experts", params={"q": "searchable"}).json()}
    assert cards[handle]["from_paise"] == 9900 and cards[handle]["services"] == 2
    assert client.get("/api/experts", params={"q": "zzz-nobody-zzz"}).json() == []
