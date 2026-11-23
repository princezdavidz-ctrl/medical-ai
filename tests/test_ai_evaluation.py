from datetime import datetime, timedelta, timezone

import pytest

from app.ai.contracts import AICapability, OperatingMode
from app.ai.evaluation import (
    REQUIRED_METRICS,
    ClinicalRelease,
    EvaluationManifest,
    EvaluationMetric,
    EvaluationRun,
    EvaluationThresholds,
    ReleaseApproval,
    evaluate_release,
    evaluate_run,
)

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64


def build_run(*, score: float = 0.99, approved_dataset: bool = True) -> EvaluationRun:
    manifest = EvaluationManifest(
        capability=AICapability.MEDICAL_INFORMATION,
        operating_mode=OperatingMode.OFFLINE,
        provider_id="local-runtime",
        model_id="test-model",
        model_version="1.0.0",
        model_digest=DIGEST,
        prompt_version="prompt-v1",
        prompt_digest="d" * 64,
        dataset_id="synthetic-suite",
        dataset_version="v1",
        dataset_digest="b" * 64,
        synthetic_or_deidentified=approved_dataset,
        dataset_approval_id="dataset-approval-1",
    )
    return EvaluationRun(
        run_id="eval-001",
        manifest=manifest,
        metrics={metric: score for metric in REQUIRED_METRICS},
        executed_at=NOW,
        evaluator_version="eval-harness-v1",
        evaluator_digest="c" * 64,
    )


def thresholds() -> EvaluationThresholds:
    return EvaluationThresholds({metric: 0.95 for metric in REQUIRED_METRICS})


def build_release(*, safety_actor: str = "safety-1", clinical_actor: str = "reviewer-1"):
    return ClinicalRelease(
        release_id="release-001",
        evaluation_run=build_run(),
        thresholds_version="thresholds-v1",
        safety_owner_approval=ReleaseApproval(
            actor_id=safety_actor, role="clinical_safety_owner", credential_verified=True,
            approved_at=NOW, expires_at=NOW + timedelta(days=30),
        ),
        clinical_reviewer_approval=ReleaseApproval(
            actor_id=clinical_actor, role="clinical_reviewer", credential_verified=True,
            approved_at=NOW, expires_at=NOW + timedelta(days=30),
        ),
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
    )


def test_evaluation_passes_only_with_complete_thresholds():
    result = evaluate_run(build_run(), thresholds())
    assert result.passed
    assert result.failures == ()


def test_below_threshold_fails_closed():
    result = evaluate_run(build_run(score=0.94), thresholds())
    assert not result.passed
    assert "threshold_failed:factual_support" in result.failures


def test_unapproved_dataset_fails_even_with_high_scores():
    result = evaluate_run(build_run(approved_dataset=False), thresholds())
    assert not result.passed
    assert "dataset_not_approved_for_safe_evaluation" in result.failures


def test_threshold_configuration_must_be_complete():
    with pytest.raises(ValueError):
        EvaluationThresholds({EvaluationMetric.FACTUAL_SUPPORT: 0.9})


def test_release_requires_two_distinct_verified_approvers():
    assert evaluate_release(build_release(), thresholds(), now=NOW).approved


def test_same_person_cannot_approve_both_roles():
    result = evaluate_release(
        build_release(safety_actor="same-person", clinical_actor="same-person"),
        thresholds(), now=NOW,
    )
    assert not result.approved
    assert "separation_of_duties_violated" in result.failures


def test_expired_and_revoked_release_fails():
    original = build_release()
    release = ClinicalRelease(
        release_id=original.release_id, evaluation_run=original.evaluation_run,
        thresholds_version=original.thresholds_version,
        safety_owner_approval=original.safety_owner_approval,
        clinical_reviewer_approval=original.clinical_reviewer_approval,
        created_at=original.created_at, expires_at=NOW - timedelta(seconds=1),
        revoked_at=NOW,
    )
    result = evaluate_release(release, thresholds(), now=NOW)
    assert not result.approved
    assert "release_revoked" in result.failures
    assert "release_expired" in result.failures


def test_unverified_reviewer_fails():
    original = build_release()
    reviewer = ReleaseApproval(
        actor_id="reviewer-1", role="clinical_reviewer", credential_verified=False,
        approved_at=NOW, expires_at=NOW + timedelta(days=30),
    )
    release = ClinicalRelease(
        release_id=original.release_id, evaluation_run=original.evaluation_run,
        thresholds_version=original.thresholds_version,
        safety_owner_approval=original.safety_owner_approval,
        clinical_reviewer_approval=reviewer, created_at=original.created_at,
        expires_at=original.expires_at,
    )
    result = evaluate_release(release, thresholds(), now=NOW)
    assert not result.approved
    assert "clinical_reviewer_approval_invalid" in result.failures
