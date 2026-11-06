import enum

from sqlalchemy import Enum as SAEnum


def db_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Store enums as VARCHAR + CHECK constraint (easier to migrate than native PG enums)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )


class Sex(str, enum.Enum):
    male = "male"
    female = "female"


class ActivityLevel(str, enum.Enum):
    sedentary = "sedentary"
    lightly_active = "lightly_active"
    moderately_active = "moderately_active"
    very_active = "very_active"
    extra_active = "extra_active"


class GoalType(str, enum.Enum):
    maintain = "maintain"
    lose = "lose"
    gain = "gain"


class GoalPace(str, enum.Enum):
    gentle = "gentle"
    moderate = "moderate"


class DietaryPreference(str, enum.Enum):
    none = "none"
    vegetarian = "vegetarian"
    eggetarian = "eggetarian"
    vegan = "vegan"
    non_vegetarian = "non_vegetarian"


class DietType(str, enum.Enum):
    """What kind of diet a food item fits into."""
    unknown = "unknown"            # imported from a nutrition API; the user hasn't confirmed it
    vegan = "vegan"
    vegetarian = "vegetarian"      # contains dairy, no egg/meat
    eggetarian = "eggetarian"      # contains egg
    non_vegetarian = "non_vegetarian"


class MealType(str, enum.Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snacks = "snacks"


class EntrySource(str, enum.Enum):
    manual = "manual"
    dispenser = "dispenser"


class CommandType(str, enum.Enum):
    dispense = "dispense"
    tare = "tare"


class CommandStatus(str, enum.Enum):
    queued = "queued"              # later step of a meal; becomes pending when its turn comes
    pending = "pending"            # created, waiting for the device to pick it up
    acknowledged = "acknowledged"  # device accepted it
    dispensing = "dispensing"      # device reported progress
    completed = "completed"        # load cell confirmed the result
    failed = "failed"
    cancelled = "cancelled"
    expired = "expired"            # device never picked it up in time


class MealPlanStatus(str, enum.Enum):
    proposed = "proposed"    # generated, not served yet
    serving = "serving"      # dispensing commands queued/running
    completed = "completed"  # every item dispensed and measured
    partial = "partial"      # some items dispensed, some failed or were stopped
    failed = "failed"        # nothing was dispensed
    cancelled = "cancelled"


# Nutrition categories a food can belong to (several at once).
NUTRITION_CATEGORIES = ("protein", "carbohydrates", "fat", "fiber", "mixed")

ACTIVE_COMMAND_STATUSES = (CommandStatus.pending, CommandStatus.acknowledged, CommandStatus.dispensing)
TERMINAL_COMMAND_STATUSES = (
    CommandStatus.completed, CommandStatus.failed, CommandStatus.cancelled, CommandStatus.expired,
)

# Controlled allergen vocabulary used by food items and user profiles.
ALLERGENS = ("dairy", "egg", "gluten", "peanut", "tree_nut", "soy", "sesame", "fish", "shellfish")
