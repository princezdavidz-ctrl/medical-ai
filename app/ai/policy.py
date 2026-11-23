from dataclasses import dataclass
from app.ai.contracts import AICapability, OperatingMode
from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason_code: str
    provider_class: str | None = None


class AIPolicyEngine:
    """Fail-closed routing policy; capability approvals are explicit configuration."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self, *, capability: AICapability, has_patient_context: bool
    ) -> PolicyDecision:
        if capability.value not in self.settings.ai_enabled_capabilities:
            return PolicyDecision(False, "capability_not_approved")

        try:
            mode = OperatingMode(self.settings.ai_operating_mode.lower())
        except ValueError:
            return PolicyDecision(False, "invalid_operating_mode")

        if mode in {OperatingMode.OFFLINE, OperatingMode.DEGRADED}:
            if not self.settings.ai_local_model_enabled:
                return PolicyDecision(False, "local_runtime_unavailable")
            return PolicyDecision(True, "approved_local", "local")

        # Patient-context tasks may never fall back to an external provider.
        if self.settings.ai_local_model_enabled:
            return PolicyDecision(True, "approved_local", "local")
        if has_patient_context:
            return PolicyDecision(False, "patient_context_requires_local_model")
        if self.settings.ai_allow_hosted:
            return PolicyDecision(True, "approved_hosted_public_input", "hosted")
        return PolicyDecision(False, "no_approved_model_route")
