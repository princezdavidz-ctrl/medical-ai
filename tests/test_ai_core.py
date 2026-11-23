from uuid import uuid4
import pytest
from app.ai.contracts import AICapability, AIModelResponse
from app.ai.gateway import ModelGateway, ModelUnavailable
from app.ai.policy import AIPolicyEngine
from app.core.config import Settings


def test_capabilities_are_disabled_by_default() -> None:
    settings = Settings(_env_file=None, secret_key="unit-test-secret-key-long-enough-123456")
    decision = AIPolicyEngine(settings).evaluate(
        capability=AICapability.MEDICAL_INFORMATION, has_patient_context=False
    )
    assert not decision.allowed
    assert decision.reason_code == "capability_not_approved"


def test_offline_mode_never_selects_hosted_provider() -> None:
    settings = Settings(
        _env_file=None, secret_key="unit-test-secret-key-long-enough-123456",
        ai_operating_mode="offline", ai_enabled_capabilities=["medical_information"],
        ai_allow_hosted=True, ai_local_model_enabled=False,
    )
    decision = AIPolicyEngine(settings).evaluate(
        capability=AICapability.MEDICAL_INFORMATION, has_patient_context=False
    )
    assert not decision.allowed
    assert decision.reason_code == "local_runtime_unavailable"


def test_patient_context_cannot_route_to_hosted_model() -> None:
    settings = Settings(
        _env_file=None, secret_key="unit-test-secret-key-long-enough-123456",
        ai_operating_mode="hybrid", ai_enabled_capabilities=["medical_information"],
        ai_allow_hosted=True, ai_local_model_enabled=False,
    )
    decision = AIPolicyEngine(settings).evaluate(
        capability=AICapability.MEDICAL_INFORMATION, has_patient_context=True
    )
    assert not decision.allowed
    assert decision.reason_code == "patient_context_requires_local_model"


def test_gateway_fails_closed_without_registered_provider() -> None:
    gateway = ModelGateway()
    with pytest.raises(ModelUnavailable):
        gateway.generate(provider_class="local", request=None)  # type: ignore[arg-type]


def test_gateway_rejects_unknown_provider_class() -> None:
    gateway = ModelGateway()
    class InvalidProvider:
        provider_id = "invalid"
        provider_class = "third_party"
    with pytest.raises(ValueError):
        gateway.register(InvalidProvider())  # type: ignore[arg-type]
