from conftest import PASSWORD


def test_api_requires_session(client):
    from fastapi.testclient import TestClient
    import app.main as m

    anon = TestClient(m.app)
    r = anon.get("/api/conversations")
    assert r.status_code == 401 and r.json()["auth"] is True
    assert anon.get("/").status_code == 200            # l'interface reste accessible (écran de connexion)
    assert anon.get("/api/auth/status").json()["setup_needed"] is False


def test_csrf_header_required(client):
    r = client.post("/api/backups", headers={"X-Atom": ""})
    assert r.status_code == 403


def test_login_and_lockout():
    from fastapi.testclient import TestClient
    import app.main as m
    from app import auth

    c = TestClient(m.app)
    assert c.post("/api/auth/login", json={"password": "faux"}).status_code == 401
    assert c.post("/api/auth/login", json={"password": PASSWORD}).status_code == 200
    assert c.get("/api/conversations").status_code == 200
    for _ in range(5):
        c.post("/api/auth/login", json={"password": "faux"})
    assert c.post("/api/auth/login", json={"password": PASSWORD}).status_code == 429
    auth.record_success("testclient")   # débloque pour les autres tests


def test_password_change_revokes_others(client):
    from fastapi.testclient import TestClient
    import app.main as m

    other = TestClient(m.app)
    assert other.post("/api/auth/login", json={"password": PASSWORD}).status_code == 200
    r = client.post("/api/security/password", json={"current": PASSWORD, "new": PASSWORD + "2"})
    assert r.status_code == 200
    assert other.get("/api/conversations").status_code == 401
    assert client.get("/api/conversations").status_code == 200
    client.post("/api/security/password", json={"current": PASSWORD + "2", "new": PASSWORD})


def test_password_min_length(client):
    r = client.post("/api/security/password", json={"current": PASSWORD, "new": "court"})
    assert r.status_code == 400
