from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker"
    test_database_url: str = "postgresql+psycopg://moneytracker:moneytracker@localhost:5433/moneytracker_test"
    supabase_jwt_secret: str = "dev-only-change-me"
    supabase_jwt_aud: str = "authenticated"


@lru_cache
def get_settings() -> Settings:
    return Settings()
