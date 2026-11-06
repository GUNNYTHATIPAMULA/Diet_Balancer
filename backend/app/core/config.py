"""Application settings, loaded from environment variables (and backend/.env)."""
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_INSECURE_DEFAULT_SECRET = "change-me-to-a-long-random-string-before-production-use"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Diet Balancer API"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://diet:diet@localhost:5432/diet_balancer"

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 720

    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    DEVICE_ONLINE_TIMEOUT_SECONDS: int = 30
    COMMAND_PENDING_TTL_SECONDS: int = 60
    COMMAND_RESULT_GRACE_SECONDS: int = 90
    DISPENSE_MIN_G: float = 5
    DISPENSE_MAX_G: float = 500

    RATE_LIMIT_ENABLED: bool = True

    # Optional verified nutrition database: USDA FoodData Central (free key at
    # https://fdc.nal.usda.gov/api-key-signup). Empty = local catalogue only.
    USDA_API_KEY: str | None = None
    NUTRITION_API_TIMEOUT_SECONDS: float = 6.0

    # Approximate dispensing defaults
    DISPENSE_TOLERANCE_PERCENT: float = 10.0

    # Pairing ("connect like AirPods")
    PAIRING_CODE_TTL_SECONDS: int = 600
    PAIRING_NEARBY_WINDOW_SECONDS: int = 30

    # Advertise the API on the local network (mDNS / Bonjour) so dispensers find it
    # without typing an address. Multicast does not leave Docker's bridge network, so
    # in Docker either use network_mode: host or type the address in the device setup page.
    MDNS_ENABLED: bool = True
    MDNS_PORT: int = 8000
    MDNS_ADVERTISE_IP: str | None = None   # auto-detected when empty

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def check_production_secret(self):
        if self.ENVIRONMENT == "production" and (
            self.JWT_SECRET_KEY == _INSECURE_DEFAULT_SECRET or len(self.JWT_SECRET_KEY) < 32
        ):
            raise ValueError("JWT_SECRET_KEY must be a random string of at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
