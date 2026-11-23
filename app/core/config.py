from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEVELOPMENT_SECRET = "local-development-only-secret-change-before-deploy-123456"
_EXAMPLE_SECRET = "replace-with-a-long-random-secret-before-running"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_name: str = "Medical AI Hospital System API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = _DEVELOPMENT_SECRET
    access_token_expire_minutes: int = 20
    database_url: str = "postgresql+psycopg://medical:medical_dev_only@localhost:5432/medical_ai"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    ai_operating_mode: str = "hybrid"
    ai_enabled_capabilities: list[str] = []
    ai_allow_hosted: bool = False
    ai_local_model_enabled: bool = False

    @model_validator(mode="after")
    def validate_security_settings(self):
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if self.environment.lower() == "production" and self.secret_key in {_DEVELOPMENT_SECRET, _EXAMPLE_SECRET}:
            raise ValueError("A unique production SECRET_KEY must be configured")
        return self

@lru_cache
def get_settings() -> Settings:
    return Settings()
