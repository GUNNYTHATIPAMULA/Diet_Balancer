from fastapi import APIRouter

from app.api.v1.endpoints import (auth, devices, dispenser, foods, meal_plans, meals, media, nutrition, pairing,
                                  profile, reports)

api_router = APIRouter()
# pairing is registered before devices so /devices/pairing/... is not taken by /devices/{device_id}
for module in (auth, profile, foods, meals, nutrition, reports, pairing, devices, meal_plans, dispenser, media):
    api_router.include_router(module.router)
