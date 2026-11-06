"""Identify a food from the name a user types ("Rice", "anda", "oats").

1. Local catalogue: name and alias matches (sources recorded, flagged approximate).
2. USDA FoodData Central, when USDA_API_KEY is configured (verified reference data).
The user picks one candidate and confirms it. Nutrition values always come from these
databases; nothing is generated."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ValidationFailedError
from app.models.enums import ALLERGENS, DietType
from app.models.food import FoodItem
from app.models.user import User
from app.repositories import foods as food_repo
from app.schemas.food import FoodOut
from app.schemas.lookup import FoodCandidate, IdentifyOut, ImportFoodIn
from app.services import usda_client
from app.services.nutrition_classifier import classify, classify_food

DRY_HINTS = ("(dry)", "raw", "roasted")
DISPENSABLE_CATEGORIES = {"Nuts & seeds"}


def _dispenser_friendly(food: FoodItem) -> bool:
    name = food.name.lower()
    return any(h in name for h in DRY_HINTS) or food.category in DISPENSABLE_CATEGORIES


def _local_candidate(food: FoodItem, match: str) -> FoodCandidate:
    c = classify_food(food)
    return FoodCandidate(
        source="catalogue", food_id=food.id, external_id=None, name=food.name, category=food.category,
        calories_per_100g=float(food.calories_per_100g), protein_per_100g=float(food.protein_per_100g),
        carbs_per_100g=float(food.carbs_per_100g), fat_per_100g=float(food.fat_per_100g),
        fiber_per_100g=float(food.fiber_per_100g), categories=c.categories, primary_category=c.primary,
        classification_reasons=c.reasons, diet_type=food.diet_type.value, allergens=list(food.allergens or []),
        data_source=food.source, is_approximate=food.is_approximate, dispenser_friendly=_dispenser_friendly(food),
        match=match, is_custom=food.created_by_user_id is not None,
    )


def identify(db: Session, user: User, query: str, limit: int = 8) -> IdentifyOut:
    q = " ".join(query.lower().split())
    if len(q) < 2:
        raise ValidationFailedError("Type at least 2 letters of the food name.")
    foods = db.scalars(select(FoodItem).where(food_repo.visible_to(user.id))).all()
    scored = []
    for f in foods:
        name = f.name.lower()
        aliases = [a.lower() for a in (f.aliases or [])]
        if name == q or q in aliases:
            rank, match = 0, "exact"
        elif name.startswith(q) or any(a.startswith(q) for a in aliases):
            rank, match = 1, "starts_with"
        elif q in name or any(q in a for a in aliases) or all(w in name for w in q.split()):
            rank, match = 2, "contains"
        else:
            continue
        # Dispensers usually hold dry/raw food, so those come first among equal matches.
        scored.append((rank, 0 if _dispenser_friendly(f) else 1, f.name, f, match))
    scored.sort(key=lambda t: t[:3])
    candidates = [_local_candidate(f, m) for *_, f, m in scored[:limit]]

    external_error = None
    if usda_client.enabled():
        try:
            for u in usda_client.search(q, limit=5):
                c = classify(protein=u.protein, carbs=u.carbs, fat=u.fat, fiber=u.fiber)
                candidates.append(FoodCandidate(
                    source="usda_fdc", food_id=None, external_id=u.fdc_id, name=u.name, category="Imported",
                    calories_per_100g=u.calories, protein_per_100g=u.protein, carbs_per_100g=u.carbs,
                    fat_per_100g=u.fat, fiber_per_100g=u.fiber, categories=c.categories, primary_category=c.primary,
                    classification_reasons=c.reasons, diet_type=DietType.unknown.value, allergens=[],
                    data_source=u.source, is_approximate=False,
                    dispenser_friendly=any(h in u.name.lower() for h in DRY_HINTS), match="external",
                    is_custom=False))
        except usda_client.UsdaError as exc:
            external_error = str(exc)
    return IdentifyOut(query=query, candidates=candidates,
                       external_provider="usda_fdc" if usda_client.enabled() else None,
                       external_error=external_error)


def import_external(db: Session, user: User, data: ImportFoodIn) -> FoodOut:
    """Import a USDA record as the user's private food. Values are re-fetched from USDA by id
    on the server, so nothing the browser sends can change the nutrition data."""
    if data.source != "usda_fdc" or not usda_client.enabled():
        raise ValidationFailedError("This nutrition source is not available.")
    existing = db.scalar(select(FoodItem).where(FoodItem.created_by_user_id == user.id,
                                                FoodItem.external_source == "usda_fdc",
                                                FoodItem.external_id == data.external_id))
    if existing:
        return FoodOut.model_validate(existing)
    try:
        u = usda_client.get(data.external_id)
    except usda_client.UsdaError as exc:
        raise ValidationFailedError(str(exc), code="nutrition_source_error")
    bad = [a for a in data.allergens if a not in ALLERGENS]
    if bad:
        raise ValidationFailedError(f"Unknown allergen: {bad[0]}")
    name = u.name
    if db.scalar(select(FoodItem.id).where(FoodItem.created_by_user_id == user.id, FoodItem.name.ilike(name))):
        name = f"{u.name[:100]} (FDC {u.fdc_id})"
    food = FoodItem(
        name=name, category="Imported", calories_per_100g=u.calories, protein_per_100g=u.protein,
        carbs_per_100g=u.carbs, fat_per_100g=u.fat, fiber_per_100g=u.fiber, serving_unit="100 g",
        serving_size_g=100, diet_type=data.diet_type, allergens=list(dict.fromkeys(data.allergens)), source=u.source,
        is_approximate=False, external_source="usda_fdc", external_id=u.fdc_id, created_by_user_id=user.id,
        categories=classify(protein=u.protein, carbs=u.carbs, fat=u.fat, fiber=u.fiber).categories, aliases=[])
    db.add(food)
    db.commit()
    db.refresh(food)
    return FoodOut.model_validate(food)
