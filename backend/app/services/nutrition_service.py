from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import DietaryPreference
from app.models.user import User
from app.repositories import foods as food_repo
from app.repositories import users as user_repo
from app.schemas.meal import NutritionTotals
from app.schemas.nutrition import RecommendationOut, RecommendationsOut, SummaryOut
from app.schemas.profile import TargetsOut
from app.services import meal_service, profile_service
from app.services.recommendation_service import DEFAULT_ENGINE, ENGINES, RecommendationContext


def summary(db: Session, user: User, day: date) -> SummaryOut:
    daily = meal_service.daily_meals(db, user, day)
    targets = profile_service.get_targets_or_none(db, user)
    consumed = daily.totals
    remaining = None
    if targets:
        remaining = NutritionTotals(
            calories=round(targets.calorie_target - consumed.calories, 1),
            protein_g=round(targets.protein_g - consumed.protein_g, 1),
            carbs_g=round(targets.carbs_g - consumed.carbs_g, 1),
            fat_g=round(targets.fat_g - consumed.fat_g, 1),
            fiber_g=round(targets.fiber_g - consumed.fiber_g, 1),
        )
    macro_kcal = consumed.protein_g * 4 + consumed.carbs_g * 4 + consumed.fat_g * 9
    split = {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
    if macro_kcal > 0:
        split = {
            "protein": round(consumed.protein_g * 4 / macro_kcal * 100, 1),
            "carbs": round(consumed.carbs_g * 4 / macro_kcal * 100, 1),
            "fat": round(consumed.fat_g * 9 / macro_kcal * 100, 1),
        }
    return SummaryOut(date=day, has_profile=targets is not None,
                      targets=TargetsOut(**targets.__dict__) if targets else None,
                      consumed=consumed, remaining=remaining, meals=daily.meals, macro_split_percent=split)


def recommendations(db: Session, user: User, day: date, limit: int = 8) -> RecommendationsOut:
    daily = meal_service.daily_meals(db, user, day)
    profile = user_repo.get_profile(db, user.id)
    engine = ENGINES[DEFAULT_ENGINE]
    ctx = RecommendationContext(
        targets=profile_service.get_targets_or_none(db, user),
        consumed=daily.totals,
        dietary_preference=profile.dietary_preference if profile else DietaryPreference.none,
        allergies=list(profile.allergies or []) if profile else [],
        restrictions=list(profile.restrictions or []) if profile else [],
        meals_per_day=profile.meals_per_day if profile else 3,
        meals_logged_today=sum(1 for g in daily.meals if g.entries),
        foods=food_repo.list_visible(db, user.id),
        limit=limit,
    )
    result = engine.recommend(ctx)
    return RecommendationsOut(
        date=day, engine=engine.name, focus=result.focus, message=result.message, remaining=result.remaining,
        excluded_count=result.excluded_count,
        items=[RecommendationOut(
            food_id=r.food.id, food_name=r.food.name, category=r.food.category, suggested_quantity_g=r.quantity_g,
            serving_hint=f"{r.food.serving_unit} is about {float(r.food.serving_size_g):g} g",
            calories=r.calories, protein_g=r.protein_g, carbs_g=r.carbs_g, fat_g=r.fat_g, score=r.score,
            reasons=r.reasons, is_approximate=r.food.is_approximate,
        ) for r in result.items],
    )
