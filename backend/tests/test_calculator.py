import pytest

from app.models.enums import ActivityLevel, GoalPace, GoalType, Sex
from app.services.nutrition_calculator import (ACTIVITY_FACTORS, calculate_bmr, calculate_targets, calculate_tdee,
                                               scale_nutrition)


def test_bmr_male_matches_formula():
    # 10*70 + 6.25*175 - 5*30 + 5 = 1648.75
    assert calculate_bmr(70, 175, 30, Sex.male) == pytest.approx(1648.75)


def test_bmr_female_matches_formula():
    # 10*60 + 6.25*165 - 5*28 - 161 = 1330.25
    assert calculate_bmr(60, 165, 28, Sex.female) == pytest.approx(1330.25)


@pytest.mark.parametrize("level,factor", [
    (ActivityLevel.sedentary, 1.2), (ActivityLevel.lightly_active, 1.375),
    (ActivityLevel.moderately_active, 1.55), (ActivityLevel.very_active, 1.725),
    (ActivityLevel.extra_active, 1.9)])
def test_tdee_factors(level, factor):
    assert ACTIVITY_FACTORS[level] == factor
    assert calculate_tdee(1500, level) == pytest.approx(1500 * factor)


def test_maintain_target_equals_tdee_rounded():
    t = calculate_targets(weight_kg=70, height_cm=175, age=30, sex=Sex.male,
                          activity_level=ActivityLevel.moderately_active, goal_type=GoalType.maintain)
    assert t.tdee == 2556
    assert t.calorie_target == 2560
    assert t.goal_adjustment == 0


def test_loss_deficit_is_capped_at_500():
    t = calculate_targets(weight_kg=110, height_cm=185, age=35, sex=Sex.male,
                          activity_level=ActivityLevel.very_active, goal_type=GoalType.lose,
                          goal_pace=GoalPace.moderate)
    assert t.goal_adjustment == -500


def test_gain_surplus_is_capped():
    t = calculate_targets(weight_kg=90, height_cm=190, age=25, sex=Sex.male,
                          activity_level=ActivityLevel.extra_active, goal_type=GoalType.gain,
                          goal_pace=GoalPace.moderate)
    assert 0 < t.goal_adjustment <= 350


def test_calorie_floor_prevents_extreme_deficit():
    t = calculate_targets(weight_kg=45, height_cm=150, age=60, sex=Sex.female,
                          activity_level=ActivityLevel.sedentary, goal_type=GoalType.lose,
                          goal_pace=GoalPace.moderate)
    assert t.floor_applied
    assert t.calorie_target >= 1200


def test_macros_add_up_to_target():
    t = calculate_targets(weight_kg=65, height_cm=168, age=40, sex=Sex.female,
                          activity_level=ActivityLevel.lightly_active, goal_type=GoalType.lose)
    kcal = t.protein_g * 4 + t.carbs_g * 4 + t.fat_g * 9
    assert abs(kcal - t.calorie_target) < 15


def test_scale_nutrition_example_from_spec():
    values = scale_nutrition({"calories": 130, "protein": 2.7, "carbs": 28.2, "fat": 0.3, "fiber": 0.4}, 150)
    assert values["calories"] == 195.0
    assert values["protein_g"] == pytest.approx(4.05)
    assert values["carbs_g"] == pytest.approx(42.3)
