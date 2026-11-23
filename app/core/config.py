import os
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "Medical AI Hospital System API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str
    access_token_expire_minutes: int = 20
    database_url: str = "postgresql+psycopg://medical:medical_dev_only@localhost:5432/medical_ai"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 32 and value != "replace-with-a-long-random-secret-before-running":
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if value == "replace-with-a-long-random-secret-before-running" and os.getenv("ENVIRONMENT") == "production":
            raise ValueError("A production SECRET_KEY must be configured")
        return value

@lru_cache
def get_settings() -> Settings:
    return Settings()
