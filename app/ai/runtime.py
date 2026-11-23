from app.ai.gateway import ModelGateway
from app.ai.local_provider import LocalOpenAICompatibleProvider
from app.core.config import Settings


def build_model_gateway(settings: Settings) -> ModelGateway:
    """Register only explicitly configured providers; no implicit hosted fallback."""
    gateway = ModelGateway()
    if settings.ai_local_model_enabled:
        if not settings.ai_local_model_base_url or not settings.ai_local_model_name:
            raise ValueError("local_model_runtime_configuration_incomplete")
        api_key = (
            settings.ai_local_model_api_key.get_secret_value()
            if settings.ai_local_model_api_key is not None
            and settings.ai_local_model_api_key.get_secret_value()
            else None
        )
        gateway.register(LocalOpenAICompatibleProvider(
            base_url=settings.ai_local_model_base_url,
            model_name=settings.ai_local_model_name,
            model_version=settings.ai_local_model_version,
            model_digest=settings.ai_local_model_digest,
            timeout_seconds=settings.ai_local_model_timeout_seconds,
            max_tokens=settings.ai_local_model_max_tokens,
            api_key=api_key,
        ))
    return gateway
