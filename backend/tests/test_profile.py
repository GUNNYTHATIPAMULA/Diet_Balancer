from tests.conftest import PROFILE


def test_profile_requires_setup(client, auth):
    r = client.get("/api/v1/profile/calorie-target", headers=auth)
    assert r.status_code == 404 and r.json()["error"]["code"] == "profile_incomplete"


def test_profile_saves_and_calculates(client, auth):
    r = client.put("/api/v1/profile", json=PROFILE, headers=auth)
    assert r.status_code == 200
    targets = r.json()["targets"]
    assert targets["bmr"] == 1649 and targets["tdee"] == 2556 and targets["calorie_target"] == 2560
    assert "not medical advice" in targets["disclaimer"]
    assert client.get("/api/v1/auth/me", headers=auth).json()["has_profile"] is True


def test_minors_rejected(client, auth):
    r = client.put("/api/v1/profile", json={**PROFILE, "age": 16}, headers=auth)
    assert r.status_code == 422


def test_target_weight_must_match_goal(client, auth):
    r = client.put("/api/v1/profile", json={**PROFILE, "goal_type": "lose", "target_weight_kg": 80}, headers=auth)
    assert r.status_code == 422
    ok = client.put("/api/v1/profile", json={**PROFILE, "goal_type": "lose", "target_weight_kg": 65}, headers=auth)
    assert ok.status_code == 200 and ok.json()["target_weight_kg"] == 65


def test_weight_update_recalculates(client, profiled):
    before = client.get("/api/v1/profile/calorie-target", headers=profiled).json()
    r = client.patch("/api/v1/profile/weight", json={"weight_kg": 80}, headers=profiled)
    assert r.status_code == 200
    assert r.json()["targets"]["bmr"] == before["bmr"] + 100


def test_goal_change_keeps_single_active_goal(client, profiled, db):
    from app.models.profile import FitnessGoal
    client.put("/api/v1/profile", json={**PROFILE, "goal_type": "gain"}, headers=profiled)
    client.put("/api/v1/profile", json={**PROFILE, "goal_type": "lose"}, headers=profiled)
    goals = db.query(FitnessGoal).all()
    assert len(goals) == 3 and sum(g.is_active for g in goals) == 1


def test_allergy_vocabulary_validated(client, auth):
    r = client.put("/api/v1/profile", json={**PROFILE, "allergies": ["kryptonite"]}, headers=auth)
    assert r.status_code == 422
