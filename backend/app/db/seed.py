"""Idempotent seeding of the shared food catalogue.

Run from the backend directory:  python -m app.db.seed
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.seed_data import ALIASES, FOODS, SOURCES
from app.services.nutrition_classifier import classify
from app.db.session import SessionLocal
from app.models.enums import DietType
from app.models.food import FoodItem


def seed_foods(db: Session) -> tuple[int, int]:
    created = updated = 0
    for (name, category, kcal, protein, carbs, fat, fiber, unit, serving_g, diet, allergens, source) in FOODS:
        existing = db.scalar(
            select(FoodItem).where(func.lower(FoodItem.name) == name.lower(), FoodItem.created_by_user_id.is_(None))
        )
        values = dict(
            name=name, category=category, calories_per_100g=kcal, protein_per_100g=protein,
            carbs_per_100g=carbs, fat_per_100g=fat, fiber_per_100g=fiber, serving_unit=unit,
            serving_size_g=serving_g, diet_type=DietType(diet), allergens=list(allergens),
            source=SOURCES[source], is_approximate=True,
            aliases=ALIASES.get(name, []),
            categories=classify(protein=protein, carbs=carbs, fat=fat, fiber=fiber).categories,
        )
        if existing is None:
            db.add(FoodItem(**values))
            created += 1
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            updated += 1
    # Backfill categories for foods created before classification existed (custom foods).
    for food in db.scalars(select(FoodItem).where(FoodItem.created_by_user_id.is_not(None))):
        if not food.categories:
            food.categories = classify(protein=food.protein_per_100g, carbs=food.carbs_per_100g,
                                       fat=food.fat_per_100g, fiber=food.fiber_per_100g).categories
    db.commit()
    return created, updated


def main() -> None:
    with SessionLocal() as db:
        created, updated = seed_foods(db)
    print(f"Food catalogue seeded: {created} created, {updated} updated.")


if __name__ == "__main__":
    main()
