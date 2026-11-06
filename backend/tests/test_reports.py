from datetime import date, timedelta

from tests.conftest import find_food


def test_weekly_report_averages_logged_days(client, profiled):
    rice = find_food(client, profiled, "White rice, cooked")
    today = date.today()
    for offset, grams in ((0, 1000), (1, 2000)):
        client.post("/api/v1/meals", headers=profiled, json={
            "food_item_id": rice["id"], "meal_type": "lunch", "quantity_g": grams,
            "consumed_on": str(today - timedelta(days=offset))})
    r = client.get("/api/v1/reports/weekly", headers=profiled).json()
    assert len(r["days"]) == 7 and r["days_logged"] == 2
    assert r["average_calories"] == (1300 + 2600) / 2
    assert r["days_on_target"] == 1  # 2600 kcal is within 10 % of the 2560 kcal target
    assert r["top_foods"][0]["food_name"] == "White rice, cooked"


def test_monthly_report_shape(client, profiled):
    r = client.get("/api/v1/reports/monthly", params={"year": 2026, "month": 2}, headers=profiled).json()
    assert r["start_date"] == "2026-02-01" and r["end_date"] == "2026-02-28" and len(r["days"]) == 28


def test_summary_without_profile(client, auth):
    r = client.get("/api/v1/nutrition/summary", headers=auth).json()
    assert r["has_profile"] is False and r["targets"] is None and len(r["meals"]) == 4
