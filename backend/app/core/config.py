from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker"
    test_database_url: str = "postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker_test"
    supabase_url: str = ""
    supabase_jwt_secret: str  # no default — fail fast if unset
    supabase_jwt_aud: str = "authenticated"
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5000",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
