"""Import every model so Base.metadata is complete (used by Alembic)."""
from app.models.device import Device, DeviceContainer, DeviceEvent, DispensingCommand, DispensingLog, PairingSession  # noqa: F401
from app.models.food import FoodItem  # noqa: F401
from app.models.meal import MealEntry  # noqa: F401
from app.models.profile import FitnessGoal, UserProfile  # noqa: F401
from app.models.user import User  # noqa: F401
