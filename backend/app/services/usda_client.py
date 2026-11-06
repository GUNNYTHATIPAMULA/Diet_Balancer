"""USDA FoodData Central client (Foundation + SR Legacy data: values per 100 g).

Only used when USDA_API_KEY is set. Responses are parsed defensively and rejected if
they are incomplete or physically impossible; nothing is ever estimated or invented."""
import logging
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

logger = logging.getLogger("diet_balancer.usda")
BASE = "https://api.nal.usda.gov/fdc/v1"
DATA_TYPES = ["Foundation", "SR Legacy"]  # per-100 g reference data (not branded per-serving data)

# nutrientId (current API) and nutrientNumber (legacy) for each value we need
ENERGY_IDS = {1008: "208", 2047: "957", 2048: "958"}  # kcal; Atwater general/specific for Foundation foods
PROTEIN, FAT, CARBS, FIBER = (1003, "203"), (1004, "204"), (1005, "205"), (1079, "291")


class UsdaError(Exception):
    pass


@dataclass
class UsdaFood:
    fdc_id: str
    name: str
    data_type: str
    calories: float
    protein: float
    carbs: float
    fat: float
    fiber: float

    @property
    def source(self) -> str:
        return f"USDA FoodData Central ({self.data_type}), FDC ID {self.fdc_id}"


def _nutrient(nutrients: list, nid: int, number: str) -> float | None:
    for n in nutrients:
        n_id = n.get("nutrientId") or (n.get("nutrient") or {}).get("id")
        n_num = str(n.get("nutrientNumber") or (n.get("nutrient") or {}).get("number") or "")
        if n_id == nid or n_num == number:
            value = n.get("value", n.get("amount"))
            unit = (n.get("unitName") or (n.get("nutrient") or {}).get("unitName") or "").lower()
            if value is None:
                return None
            if nid in ENERGY_IDS and unit and unit not in ("kcal",):
                continue  # skip kJ entries
            return float(value)
    return None


def parse_food(item: dict) -> UsdaFood | None:
    """Turn one FDC record into a UsdaFood, or None if it is incomplete or implausible."""
    nutrients = item.get("foodNutrients") or []
    energy = None
    for nid, num in ENERGY_IDS.items():
        energy = _nutrient(nutrients, nid, num)
        if energy is not None:
            break
    protein, fat, carbs = (_nutrient(nutrients, *PROTEIN), _nutrient(nutrients, *FAT), _nutrient(nutrients, *CARBS))
    fiber = _nutrient(nutrients, *FIBER) or 0.0
    if None in (energy, protein, fat, carbs):
        return None
    if min(energy, protein, fat, carbs, fiber) < 0 or energy > 950 or protein + fat + carbs > 101:
        return None
    # Atwater sanity check: reported energy should roughly agree with 4/4/9 kcal per gram.
    atwater = protein * 4 + carbs * 4 + fat * 9
    if atwater > 20 and not (0.6 <= energy / atwater <= 1.4):
        return None
    name = (item.get("description") or "").strip()
    if not name:
        return None
    return UsdaFood(fdc_id=str(item.get("fdcId")), name=name[:120].capitalize(), data_type=item.get("dataType", ""),
                    calories=round(energy, 2), protein=round(protein, 2), carbs=round(carbs, 2), fat=round(fat, 2),
                    fiber=round(fiber, 2))


def enabled() -> bool:
    return bool(get_settings().USDA_API_KEY)


def search(query: str, limit: int = 5) -> list[UsdaFood]:
    settings = get_settings()
    try:
        r = httpx.get(f"{BASE}/foods/search", timeout=settings.NUTRITION_API_TIMEOUT_SECONDS,
                      params={"api_key": settings.USDA_API_KEY, "query": query, "dataType": DATA_TYPES,
                              "pageSize": limit * 3})
        r.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("USDA search failed: %s", exc)
        raise UsdaError("The USDA nutrition database is not reachable right now.") from exc
    foods = [f for f in (parse_food(i) for i in r.json().get("foods", [])) if f]
    return foods[:limit]


def get(fdc_id: str) -> UsdaFood:
    settings = get_settings()
    if not fdc_id.isdigit():
        raise UsdaError("Invalid FoodData Central id.")
    try:
        r = httpx.get(f"{BASE}/food/{fdc_id}", timeout=settings.NUTRITION_API_TIMEOUT_SECONDS,
                      params={"api_key": settings.USDA_API_KEY})
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise UsdaError("The USDA nutrition database is not reachable right now.") from exc
    food = parse_food(r.json())
    if food is None:
        raise UsdaError("That USDA record is missing calories or macronutrients, so it can't be used.")
    return food
