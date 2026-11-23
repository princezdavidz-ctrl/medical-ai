"""Version-pinned AI evaluation and clinical release gates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import re
from collections.abc import Mapping

from app.ai.contracts import AICapability, OperatingMode


class EvaluationMetric(StrEnum):
    FACTUAL_SUPPORT = "factual_support"
    CITATION_INTEGRITY = "citation_integrity"
    OMISSION_SENSITIVITY = "omission_sensitivity"
    UNCERTAINTY_CALIBRATION = "uncertainty_calibration"
    RED_FLAG_SENSITIVITY = "red_flag_sensitivity"
    FALSE_ALARM_CONTROL = "false_alarm_control"
    SUBGROUP_PARITY = "subgroup_parity"
    PROMPT_INJECTION_RESISTANCE = "prompt_injection_resistance"
    TENANT_ISOLATION = "tenant_isolation"
    ROLE_CONSENT_BOUNDARIES = "role_consent_boundaries"
    AUDIT_COMPLETENESS = "audit_completeness"


REQUIRED_METRICS = frozenset(EvaluationMetric)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class EvaluationManifest:
    capability: AICapability
    operating_mode: OperatingMode
    provider_id: str
    model_id: str
    model_version: str
    model_digest: str
    prompt_version: str
    prompt_digest: str
    dataset_id: str
    dataset_version: str
    dataset_digest: str
    synthetic_or_deidentified: bool
    dataset_approval_id: str


@dataclass(frozen=True, slots=True)
class EvaluationThresholds:
    minimums: Mapping[EvaluationMetric, float]

    def __post_init__(self) -> None:
        if set(self.minimums) != REQUIRED_METRICS:
            raise ValueError("Thresholds must define every required evaluation metric")
        if any(not 0.0 <= value <= 1.0 for value in self.minimums.values()):
            raise ValueError("Evaluation thresholds must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    run_id: str
    manifest: EvaluationManifest
    metrics: Mapping[EvaluationMetric, float]
    executed_at: datetime
    evaluator_version: str
    evaluator_digest: str

    def __post_init__(self) -> None:
        if set(self.metrics) != REQUIRED_METRICS:
            raise ValueError("Evaluation run must report every required evaluation metric")
        if any(not 0.0 <= value <= 1.0 for value in self.metrics.values()):
            raise ValueError("Evaluation metric values must be between 0 and 1")
        for value in (
            self.manifest.model_digest, self.manifest.prompt_digest,
            self.manifest.dataset_digest, self.evaluator_digest,
        ):
            if not _SHA256.fullmatch(value):
                raise ValueError("Model, dataset and evaluator digests must be SHA-256 hex")


@dataclass(frozen=True, slots=True)
class EvaluationDecision:
    passed: bool
    failures: tuple[str, ...]


def evaluate_run(run: EvaluationRun, thresholds: EvaluationThresholds) -> EvaluationDecision:
    """Compare a complete, pinned evaluation run against all configured thresholds."""
    failures: list[str] = []
    if not run.manifest.synthetic_or_deidentified:
        failures.append("dataset_not_approved_for_safe_evaluation")
    if not run.manifest.dataset_approval_id.strip():
        failures.append("dataset_approval_missing")
    for metric in sorted(REQUIRED_METRICS, key=lambda item: item.value):
        if run.metrics[metric] < thresholds.minimums[metric]:
            failures.append(f"threshold_failed:{metric.value}")
    return EvaluationDecision(passed=not failures, failures=tuple(failures))


@dataclass(frozen=True, slots=True)
class ReleaseApproval:
    actor_id: str
    role: str
    credential_verified: bool
    approved_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ClinicalRelease:
    release_id: str
    evaluation_run: EvaluationRun
    thresholds_version: str
    safety_owner_approval: ReleaseApproval
    clinical_reviewer_approval: ReleaseApproval
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    approved: bool
    failures: tuple[str, ...]


def evaluate_release(
    release: ClinicalRelease,
    thresholds: EvaluationThresholds,
    *,
    now: datetime | None = None,
) -> ReleaseDecision:
    """Fail closed unless evaluation and independent, current approvals are valid."""
    current = now or datetime.now(timezone.utc)
    failures = list(evaluate_run(release.evaluation_run, thresholds).failures)

    if current.tzinfo is None or release.created_at.tzinfo is None:
        failures.append("timezone_required")
    if release.revoked_at is not None:
        failures.append("release_revoked")
    if release.expires_at <= current:
        failures.append("release_expired")
    if not release.thresholds_version.strip():
        failures.append("thresholds_version_missing")

    safety = release.safety_owner_approval
    clinical = release.clinical_reviewer_approval
    if safety.actor_id == clinical.actor_id:
        failures.append("separation_of_duties_violated")
    if safety.role != "clinical_safety_owner" or not safety.credential_verified:
        failures.append("safety_owner_approval_invalid")
    if clinical.role != "clinical_reviewer" or not clinical.credential_verified:
        failures.append("clinical_reviewer_approval_invalid")

    for label, approval in (("safety_owner", safety), ("clinical_reviewer", clinical)):
        if approval.revoked_at is not None:
            failures.append(f"{label}_approval_revoked")
        if approval.expires_at <= current:
            failures.append(f"{label}_approval_expired")
        if approval.approved_at > current:
            failures.append(f"{label}_approval_from_future")
        if approval.approved_at < release.created_at:
            failures.append(f"{label}_approval_predates_release")

    if not release.release_id.strip() or not release.evaluation_run.run_id.strip():
        failures.append("release_or_evaluation_id_missing")

    return ReleaseDecision(approved=not failures, failures=tuple(dict.fromkeys(failures)))
