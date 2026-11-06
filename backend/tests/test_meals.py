from datetime import date, timedelta

from tests.conftest import find_food, register_user


def test_food_search_ranks_prefix_first(client, auth):
    items = client.get("/api/v1/foods/search", params={"q": "rice"}, headers=auth).json()["items"]
    assert items and items[0]["name"].lower().startswith(("white rice", "brown rice"))
    assert all(i["is_approximate"] and i["source"] for i in items)


def test_create_meal_scales_nutrition(client, auth):
    rice = find_food(client, auth, "White rice, cooked")
    r = client.post("/api/v1/meals", json={"food_item_id": rice["id"], "meal_type": "lunch", "quantity_g": 150},
                    headers=auth)
    assert r.status_code == 201
    body = r.json()
    assert body["calories"] == 195.0 and body["source"] == "manual"


def test_update_and_delete_meal(client, auth):
    rice = find_food(client, auth, "White rice, cooked")
    entry = client.post("/api/v1/meals", json={"food_item_id": rice["id"], "meal_type": "lunch",
                                               "quantity_g": 100}, headers=auth).json()
    upd = client.patch(f"/api/v1/meals/{entry['id']}", json={"quantity_g": 200, "meal_type": "dinner"},
                       headers=auth)
    assert upd.status_code == 200 and upd.json()["calories"] == 260.0 and upd.json()["meal_type"] == "dinner"
    assert client.delete(f"/api/v1/meals/{entry['id']}", headers=auth).status_code == 204
    assert client.get("/api/v1/meals/daily", headers=auth).json()["totals"]["calories"] == 0


def test_daily_groups_and_weekly_totals(client, auth):
    egg = find_food(client, auth, "Egg, whole, boiled")
    today = date.today()
    client.post("/api/v1/meals", json={"food_item_id": egg["id"], "meal_type": "breakfast", "quantity_g": 100},
                headers=auth)
    client.post("/api/v1/meals", json={"food_item_id": egg["id"], "meal_type": "snacks", "quantity_g": 50,
                                       "consumed_on": str(today - timedelta(days=2))}, headers=auth)
    daily = client.get("/api/v1/meals/daily", headers=auth).json()
    assert [g["meal_type"] for g in daily["meals"]] == ["breakfast", "lunch", "dinner", "snacks"]
    assert daily["meals"][0]["totals"]["protein_g"] == 12.6
    weekly = client.get("/api/v1/meals/weekly", headers=auth).json()
    assert len(weekly["days"]) == 7
    assert sum(d["calories"] for d in weekly["days"]) == 155 + 77.5


def test_users_cannot_touch_each_others_meals(client, auth):
    rice = find_food(client, auth, "White rice, cooked")
    entry = client.post("/api/v1/meals", json={"food_item_id": rice["id"], "meal_type": "lunch",
                                               "quantity_g": 100}, headers=auth).json()
    other, _ = register_user(client)
    assert client.patch(f"/api/v1/meals/{entry['id']}", json={"quantity_g": 1}, headers=other).status_code == 404
    assert client.delete(f"/api/v1/meals/{entry['id']}", headers=other).status_code == 404
    assert client.get("/api/v1/meals/daily", headers=other).json()["totals"]["calories"] == 0


def test_custom_foods_are_private(client, auth):
    r = client.post("/api/v1/foods", headers=auth, json={
        "name": "Grandma's upma", "category": "Breakfast", "calories_per_100g": 150, "protein_per_100g": 4,
        "carbs_per_100g": 22, "fat_per_100g": 5, "diet_type": "vegan"})
    assert r.status_code == 201 and r.json()["is_custom"] is True
    other, _ = register_user(client)
    assert client.get(f"/api/v1/foods/{r.json()['id']}", headers=other).status_code == 404
    assert client.get("/api/v1/foods/search", params={"q": "upma"}, headers=other).json()["items"] == []


def test_invalid_food_macros_rejected(client, auth):
    r = client.post("/api/v1/foods", headers=auth, json={
        "name": "Impossible", "category": "Test", "calories_per_100g": 100, "protein_per_100g": 60,
        "carbs_per_100g": 60, "fat_per_100g": 0, "diet_type": "vegan"})
    assert r.status_code == 422
