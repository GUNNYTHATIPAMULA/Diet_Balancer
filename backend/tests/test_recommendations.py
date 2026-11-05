from tests.conftest import PROFILE, find_food


def _names(client, headers):
    r = client.get("/api/v1/nutrition/recommendations", params={"limit": 20}, headers=headers)
    assert r.status_code == 200
    return r.json(), {i["food_name"] for i in r.json()["items"]}


def test_respects_diet_and_allergies(client, auth):
    client.put("/api/v1/profile", json={**PROFILE, "dietary_preference": "vegan",
                                        "allergies": ["peanut", "soy"]}, headers=auth)
    body, names = _names(client, auth)
    assert names
    forbidden = {"Paneer", "Egg, whole, boiled", "Chicken breast, cooked (skinless)", "Peanuts, raw",
                 "Tofu, firm", "Curd / dahi (whole milk)", "Milk, toned (about 3% fat)"}
    assert not names & forbidden
    assert body["excluded_count"] > 0
    assert all(item["reasons"] for item in body["items"])


def test_restriction_keywords_exclude_foods(client, auth):
    client.put("/api/v1/profile", json={**PROFILE, "restrictions": ["rice", "dal"]}, headers=auth)
    _, names = _names(client, auth)
    assert not any("rice" in n.lower() or "dal" in n.lower() for n in names)


def test_fat_focus_when_fat_gap_is_largest(client, profiled):
    rice = find_food(client, profiled, "White rice, cooked")
    client.post("/api/v1/meals", json={"food_item_id": rice["id"], "meal_type": "lunch", "quantity_g": 600},
                headers=profiled)
    body, _ = _names(client, profiled)
    assert body["focus"] == "fat"  # 600 g rice is nearly fat-free


def test_protein_focus_when_protein_gap_is_largest(client, profiled):
    rice = find_food(client, profiled, "White rice, cooked")
    ghee = find_food(client, profiled, "Ghee")
    for food, grams in ((rice, 500), (ghee, 30)):
        client.post("/api/v1/meals", json={"food_item_id": food["id"], "meal_type": "lunch", "quantity_g": grams},
                    headers=profiled)
    body, _ = _names(client, profiled)
    assert body["focus"] == "protein"
    top = body["items"][0]
    assert top["protein_g"] >= 5


def test_light_mode_after_target_reached(client, profiled):
    ghee = find_food(client, profiled, "Ghee")
    client.post("/api/v1/meals", json={"food_item_id": ghee["id"], "meal_type": "lunch", "quantity_g": 300},
                headers=profiled)
    body, _ = _names(client, profiled)
    assert body["focus"] == "light"
    assert all(i["calories"] <= 80 for i in body["items"])
