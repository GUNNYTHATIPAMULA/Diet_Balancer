from tests.conftest import register_user


def test_register_returns_token_and_user(client):
    headers, user = register_user(client, email="Asha@Example.com")
    assert user["email"] == "asha@example.com"
    assert user["has_profile"] is False
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200 and me.json()["full_name"] == "Asha Rao"


def test_duplicate_email_rejected(client):
    register_user(client, email="dup@example.com")
    r = client.post("/api/v1/auth/register", json={"full_name": "Other", "email": "DUP@example.com",
                                                   "password": "abcdef12", "confirm_password": "abcdef12"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "email_taken"


def test_password_rules_and_confirmation(client):
    weak = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": "w@example.com",
                                                      "password": "short", "confirm_password": "short"})
    assert weak.status_code == 422
    mismatch = client.post("/api/v1/auth/register", json={"full_name": "A B", "email": "m@example.com",
                                                          "password": "abcdef12", "confirm_password": "abcdef13"})
    assert mismatch.status_code == 422
    assert "do not match" in mismatch.json()["error"]["message"]


def test_password_is_hashed(client, db):
    from app.models.user import User
    register_user(client, email="hash@example.com", password="plainpass9")
    user = db.query(User).filter_by(email="hash@example.com").one()
    assert "plainpass9" not in user.password_hash and user.password_hash.startswith("$argon2")


def test_login_success_and_failure(client):
    register_user(client, email="login@example.com", password="correct1pass")
    ok = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "correct1pass"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "wrong1pass"})
    assert bad.status_code == 401
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong1pass"})
    assert unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_protected_routes_need_valid_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/meals/daily").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_logout_all_invalidates_old_tokens(client):
    headers, _ = register_user(client)
    assert client.post("/api/v1/auth/logout-all", headers=headers).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_change_password(client):
    headers, user = register_user(client, password="oldpass123")
    r = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "oldpass123", "new_password": "newpass456", "confirm_password": "newpass456"})
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401  # old token revoked
    login = client.post("/api/v1/auth/login", json={"email": user["email"], "password": "newpass456"})
    assert login.status_code == 200
