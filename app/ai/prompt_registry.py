"""Versioned, capability-specific instructions and workflow contracts.

Registry entries are source-controlled and immutable by version. Any edit requires a
new version and a new evaluation run; no capability has tool permissions by default.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from app.ai.contracts import AICapability


@dataclass(frozen=True, slots=True)
class CapabilityPrompt:
    capability: AICapability
    version: str
    system_prompt: str
    tool_permissions: tuple[str, ...]
    output_schema: dict[str, object]
    workflow_contract: dict[str, object]

    @property
    def digest(self) -> str:
        payload = {
            "capability": self.capability.value,
            "version": self.version,
            "system_prompt": self.system_prompt,
            "tool_permissions": self.tool_permissions,
            "output_schema": self.output_schema,
            "workflow_contract": self.workflow_contract,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()


_COMMON = (
    "You are a clinical information support system, not a licensed clinician. "
    "Do not claim to diagnose, prescribe, order tests, or independently decide treatment. "
    "Use only the supplied approved evidence; cite its exact citation tokens. "
    "Clearly state uncertainty, missing information, conflicting evidence and limitations. "
    "If evidence is insufficient, say so and abstain rather than inventing facts. "
    "Escalate urgent or potentially life-threatening findings to a qualified clinician "
    "or emergency service. Patient care decisions remain with authorized clinicians."
)

_WORKFLOW = {
    "clinical_use_enabled": False,
    "requires_clinician_review": True,
    "autonomous_orders_permitted": False,
    "autonomous_diagnosis_permitted": False,
    "autonomous_prescribing_permitted": False,
    "must_cite_approved_evidence": True,
    "must_state_uncertainty": True,
    "must_abstain_without_sufficient_evidence": True,
}

_OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "content", "provider", "model", "model_version", "prompt_version",
        "citations", "clinical_use_enabled", "requires_clinician_review",
    ],
    "properties": {
        "content": {"type": "string"},
        "provider": {"type": "string"},
        "model": {"type": "string"},
        "model_version": {"type": "string"},
        "prompt_version": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "object"}},
        "clinical_use_enabled": {"const": False},
        "requires_clinician_review": {"const": True},
    },
}

_REGISTRY = {
    AICapability.MEDICAL_INFORMATION: CapabilityPrompt(
        capability=AICapability.MEDICAL_INFORMATION,
        version="medical-information.v1",
        system_prompt=_COMMON + " Explain medical concepts in clear, neutral language.",
        tool_permissions=(),
        output_schema=_OUTPUT_SCHEMA,
        workflow_contract={**_WORKFLOW, "purpose": "general_medical_information"},
    ),
    AICapability.CLINICAL_DECISION_SUPPORT: CapabilityPrompt(
        capability=AICapability.CLINICAL_DECISION_SUPPORT,
        version="clinical-decision-support.v1",
        system_prompt=_COMMON + " Present relevant considerations and differential possibilities "
        "only as clinician-facing decision support; do not rank a definitive diagnosis.",
        tool_permissions=(),
        output_schema=_OUTPUT_SCHEMA,
        workflow_contract={**_WORKFLOW, "purpose": "clinician_reviewed_decision_support"},
    ),
    AICapability.LAB_INTERPRETATION: CapabilityPrompt(
        capability=AICapability.LAB_INTERPRETATION,
        version="lab-interpretation.v1",
        system_prompt=_COMMON + " Interpret laboratory information only with the supplied "
        "specimen-, method-, population- and unit-specific reference context. Do not infer "
        "missing units or apply another laboratory's reference interval.",
        tool_permissions=(),
        output_schema=_OUTPUT_SCHEMA,
        workflow_contract={**_WORKFLOW, "purpose": "clinician_reviewed_lab_interpretation"},
    ),
    AICapability.MEDICATION_SAFETY: CapabilityPrompt(
        capability=AICapability.MEDICATION_SAFETY,
        version="medication-safety.v1",
        system_prompt=_COMMON + " Identify evidence-backed safety concerns and missing details. "
        "Never calculate or recommend an individualized dose unless an approved workflow "
        "explicitly supplies validated rules and a clinician reviews the result.",
        tool_permissions=(),
        output_schema=_OUTPUT_SCHEMA,
        workflow_contract={**_WORKFLOW, "purpose": "clinician_reviewed_medication_safety"},
    ),
    AICapability.RADIOLOGY_SUPPORT: CapabilityPrompt(
        capability=AICapability.RADIOLOGY_SUPPORT,
        version="radiology-support.v1",
        system_prompt=_COMMON + " Provide text-only imaging information support from supplied "
        "approved evidence. Do not claim to inspect images unless a separately validated "
        "imaging model and image workflow are explicitly provided.",
        tool_permissions=(),
        output_schema=_OUTPUT_SCHEMA,
        workflow_contract={**_WORKFLOW, "purpose": "clinician_reviewed_radiology_information"},
    ),
}


def get_capability_prompt(capability: AICapability) -> CapabilityPrompt:
    """Return the immutable source-controlled prompt for an enabled capability."""
    try:
        return _REGISTRY[capability]
    except KeyError:
        raise ValueError("capability_prompt_not_registered") from None
