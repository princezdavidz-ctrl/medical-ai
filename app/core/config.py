from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
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
    ai_local_model_base_url: str | None = None
    ai_local_model_name: str | None = None
    ai_local_model_version: str = "unverified"
    ai_local_model_api_key: SecretStr | None = None
    ai_local_model_timeout_seconds: float = 45.0
    ai_local_model_max_tokens: int = 1200
    ai_local_model_allowed_hosts: list[str] = ["localhost", "127.0.0.1", "::1", "ollama"]

    @model_validator(mode="after")
    def validate_security_settings(self):
        if len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if self.environment.lower() == "production" and self.secret_key in {_DEVELOPMENT_SECRET, _EXAMPLE_SECRET}:
            raise ValueError("A unique production SECRET_KEY must be configured")
        if self.ai_local_model_enabled:
            if not self.ai_local_model_base_url or not self.ai_local_model_name:
                raise ValueError("Enabled local AI runtime requires AI_LOCAL_MODEL_BASE_URL and AI_LOCAL_MODEL_NAME")
            parsed = urlsplit(self.ai_local_model_base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError("Local model base URL must be an absolute HTTP(S) URL")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Local model URL must not contain credentials, query or fragment")
            if parsed.scheme == "http" and parsed.hostname.lower() not in {
                host.lower() for host in self.ai_local_model_allowed_hosts
            }:
                raise ValueError("Plain HTTP local model URLs must use an explicitly allowed host")
            if self.ai_local_model_timeout_seconds <= 0 or self.ai_local_model_timeout_seconds > 180:
                raise ValueError("AI_LOCAL_MODEL_TIMEOUT_SECONDS must be in (0, 180]")
            if not 1 <= self.ai_local_model_max_tokens <= 8192:
                raise ValueError("AI_LOCAL_MODEL_MAX_TOKENS must be between 1 and 8192")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
