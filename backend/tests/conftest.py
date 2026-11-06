"""Tests run against a real PostgreSQL database (partial indexes, row locks and
JSONB behave differently on SQLite). Set TEST_DATABASE_URL to override."""
import os
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://diet:diet@localhost:5432/diet_balancer_test")
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256-signing"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["MDNS_ENABLED"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.seed import seed_foods  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_foods(db)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    with engine.begin() as conn:
        # DELETE (not TRUNCATE ... CASCADE) so the shared, seeded food catalogue survives;
        # ON DELETE CASCADE removes each user's devices, commands, meals and custom foods.
        conn.execute(text("DELETE FROM users"))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def register_user(client, email=None, name="Asha Rao", password="greenleaf42"):
    email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/api/v1/auth/register", json={
        "full_name": name, "email": email, "password": password, "confirm_password": password})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]


PROFILE = {
    "age": 30, "sex": "male", "height_cm": 175, "weight_kg": 70, "activity_level": "moderately_active",
    "goal_type": "maintain", "goal_pace": "gentle", "dietary_preference": "none", "allergies": [],
    "restrictions": [], "meals_per_day": 3,
}


@pytest.fixture
def auth(client):
    headers, _ = register_user(client)
    return headers


@pytest.fixture
def profiled(client, auth):
    r = client.put("/api/v1/profile", json=PROFILE, headers=auth)
    assert r.status_code == 200, r.text
    return auth


def find_food(client, headers, name):
    r = client.get("/api/v1/foods/search", params={"q": name}, headers=headers)
    assert r.status_code == 200
    return next(f for f in r.json()["items"] if f["name"] == name)
