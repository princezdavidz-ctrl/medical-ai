import json
from uuid import uuid4

import httpx
import pytest

from app.ai.contracts import AICapability, AIModelRequest, OperatingMode
from app.ai.gateway import ModelGateway, ModelUnavailable
from app.ai.local_provider import LocalModelUnavailable, LocalOpenAICompatibleProvider
from app.core.config import Settings


def _request() -> AIModelRequest:
    return AIModelRequest(
        capability=AICapability.MEDICAL_INFORMATION,
        prompt="Synthetic test question",
        evidence=(),
        evidence_context="Synthetic evidence context [K-0123456789-abcdef0123]",
        hospital_id=uuid4(),
        actor_user_id=uuid4(),
        operating_mode=OperatingMode.OFFLINE,
    )


def test_local_provider_sends_only_configured_local_chat_request_and_returns_identity():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "ollama"
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer fixture-key"
        payload = json.loads(request.content)
        assert payload["model"] == "fixture-model"
        assert payload["stream"] is False
        assert "Synthetic evidence context" in payload["messages"][0]["content"]
        return httpx.Response(200, json={
            "model": "fixture-model",
            "choices": [{"message": {"content": "Synthetic answer [K-0123456789-abcdef0123]"}}],
        })

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = LocalOpenAICompatibleProvider(
        base_url="http://ollama:11434",
        model_name="fixture-model",
        model_version="fixture-v1",
        model_digest="a" * 64,
        api_key="fixture-key",
        client=client,
    )
    response = provider.generate(_request())
    assert response.provider == "local-openai-compatible"
    assert response.model == "fixture-model"
    assert response.model_version == f"fixture-v1+sha256:{'a' * 12}"
    client.close()


def test_local_provider_rejects_unexpected_model_identity():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={
            "model": "unexpected-model",
            "choices": [{"message": {"content": "Synthetic output"}}],
        })
    ))
    provider = LocalOpenAICompatibleProvider(
        base_url="http://ollama:11434",
        model_name="fixture-model",
        model_version="fixture-v1",
        client=client,
    )
    with pytest.raises(LocalModelUnavailable):
        provider.generate(_request())
    client.close()


def test_local_provider_health_check_requires_exact_model_id():
    client = httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={
            "data": [{"id": "fixture-model"}, {"id": "other-model"}]
        })
    ))
    provider = LocalOpenAICompatibleProvider(
        base_url="http://ollama:11434",
        model_name="fixture-model",
        model_version="fixture-v1",
        client=client,
    )
    assert provider.health_check()
    client.close()


def test_gateway_never_falls_back_from_local_to_hosted():
    gateway = ModelGateway()
    provider = LocalOpenAICompatibleProvider(
        base_url="http://ollama:11434",
        model_name="fixture-model",
        model_version="fixture-v1",
        client=httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(503)
        )),
    )
    gateway.register(provider)
    with pytest.raises(ModelUnavailable):
        gateway.generate(provider_class="hosted", request=_request())


def test_local_runtime_requires_explicit_safe_configuration():
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            secret_key="unit-test-secret-key-long-enough-123456",
            ai_local_model_enabled=True,
        )
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            secret_key="unit-test-secret-key-long-enough-123456",
            ai_local_model_enabled=True,
            ai_local_model_base_url="http://example.com:11434",
            ai_local_model_name="fixture-model",
        )
