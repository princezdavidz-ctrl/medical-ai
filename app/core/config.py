import base64
import json
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
    ai_requests_enabled: bool = False
    ai_local_model_enabled: bool = False
    ai_local_model_base_url: str | None = None
    ai_local_model_name: str | None = None
    ai_local_model_version: str = "unverified"
    ai_local_model_digest: str | None = None
    ai_local_model_api_key: SecretStr | None = None
    ai_local_model_timeout_seconds: float = 45.0
    ai_local_model_max_tokens: int = 1200
    ai_local_model_allowed_hosts: list[str] = ["localhost", "127.0.0.1", "::1", "ollama"]
    ai_hosted_model_enabled: bool = False
    ai_hosted_data_transfer_approved: bool = False
    ai_hosted_model_base_url: str | None = None
    ai_hosted_model_name: str | None = None
    ai_hosted_model_version: str = "unverified"
    ai_hosted_model_api_key: SecretStr | None = None
    ai_hosted_model_timeout_seconds: float = 45.0
    ai_hosted_model_max_tokens: int = 1200
    ai_hosted_model_allowed_hosts: list[str] = []
    ai_sessions_enabled: bool = False
    ai_session_encryption_keys: SecretStr | None = None
    ai_session_active_key_version: str = "unset"
    ai_session_retention_days: int = 30
    ai_model_pricing_json: str = "{}"

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
            if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
                raise ValueError("Local model URL must not contain credentials, path, query or fragment")
            if parsed.hostname.lower() not in {
                host.lower() for host in self.ai_local_model_allowed_hosts
            }:
                raise ValueError("Local model host must be explicitly allow-listed")
            if self.ai_local_model_timeout_seconds <= 0 or self.ai_local_model_timeout_seconds > 180:
                raise ValueError("AI_LOCAL_MODEL_TIMEOUT_SECONDS must be in (0, 180]")
            if not 1 <= self.ai_local_model_max_tokens <= 8192:
                raise ValueError("AI_LOCAL_MODEL_MAX_TOKENS must be between 1 and 8192")
            if (
                self.environment.lower() == "production"
                and (self.ai_local_model_version == "unverified" or not self.ai_local_model_digest)
            ):
                raise ValueError("Production local AI requires a pinned model version and SHA-256 digest")
            if self.ai_local_model_digest and (
                len(self.ai_local_model_digest) != 64
                or any(ch not in "0123456789abcdefABCDEF" for ch in self.ai_local_model_digest)
            ):
                raise ValueError("AI_LOCAL_MODEL_DIGEST must be a SHA-256 hex digest")
        if self.ai_hosted_model_enabled:
            if not self.ai_hosted_data_transfer_approved:
                raise ValueError("Hosted model requires explicit data-transfer approval")
            if (
                not self.ai_hosted_model_base_url
                or not self.ai_hosted_model_name
                or not self.ai_hosted_model_version.strip()
                or not self.ai_hosted_model_api_key
                or not self.ai_hosted_model_api_key.get_secret_value()
            ):
                raise ValueError("Hosted model requires endpoint, model name and API key")
            parsed_hosted = urlsplit(self.ai_hosted_model_base_url)
            if (
                parsed_hosted.scheme != "https"
                or not parsed_hosted.hostname
                or parsed_hosted.username
                or parsed_hosted.password
                or parsed_hosted.query
                or parsed_hosted.fragment
                or parsed_hosted.path not in {"", "/"}
                or parsed_hosted.port not in {None, 443}
            ):
                raise ValueError("Hosted model endpoint must be a clean HTTPS origin")
            if parsed_hosted.hostname.lower() not in {
                host.lower() for host in self.ai_hosted_model_allowed_hosts
            }:
                raise ValueError("Hosted model host must be explicitly allow-listed")
            if not 0 < self.ai_hosted_model_timeout_seconds <= 180:
                raise ValueError("AI_HOSTED_MODEL_TIMEOUT_SECONDS must be in (0, 180]")
            if not 1 <= self.ai_hosted_model_max_tokens <= 8192:
                raise ValueError("AI_HOSTED_MODEL_MAX_TOKENS must be between 1 and 8192")
            if self.environment.lower() == "production" and self.ai_hosted_model_version == "unverified":
                raise ValueError("Production hosted AI requires a pinned provider model version")
        try:
            pricing = json.loads(self.ai_model_pricing_json)
        except (TypeError, ValueError):
            raise ValueError("AI_MODEL_PRICING_JSON must be valid JSON") from None
        if not isinstance(pricing, dict):
            raise ValueError("AI_MODEL_PRICING_JSON must be an object")
        for pricing_key, price in pricing.items():
            if not isinstance(pricing_key, str) or not isinstance(price, dict):
                raise ValueError("AI model pricing entries must be keyed objects")
            for field in ("input_micros_per_million_tokens", "output_micros_per_million_tokens"):
                amount = price.get(field)
                if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
                    raise ValueError(f"AI model pricing {field} must be a non-negative integer")
            currency = price.get("currency")
            if not isinstance(currency, str) or len(currency) != 3:
                raise ValueError("AI model pricing currency must be a three-letter code")
        if self.ai_sessions_enabled:
            if self.ai_session_encryption_keys is None:
                raise ValueError("AI sessions require an encryption keyring")
            if not 1 <= self.ai_session_retention_days <= 3650:
                raise ValueError("AI_SESSION_RETENTION_DAYS must be between 1 and 3650")
            try:
                keyring = json.loads(self.ai_session_encryption_keys.get_secret_value())
            except (TypeError, ValueError):
                raise ValueError("AI session encryption keyring must be valid JSON") from None
            if not isinstance(keyring, dict) or self.ai_session_active_key_version not in keyring:
                raise ValueError("AI session active key version must exist in the keyring")
            for version, encoded_key in keyring.items():
                if not isinstance(version, str) or not isinstance(encoded_key, str):
                    raise ValueError("AI session keyring entries must be string versions and base64 keys")
                try:
                    raw_key = base64.b64decode(encoded_key, validate=True)
                except ValueError:
                    raise ValueError("AI session keys must be valid base64") from None
                if len(raw_key) != 32:
                    raise ValueError("AI session keys must decode to exactly 32 bytes")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
