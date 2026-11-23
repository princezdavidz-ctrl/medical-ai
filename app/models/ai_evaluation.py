import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Index, JSON, String, Text,
    UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import TimestampMixin


class AIEvaluationDataset(TimestampMixin, Base):
    """Registry metadata for approved synthetic/de-identified evaluation datasets."""

    __tablename__ = "ai_evaluation_datasets"
    __table_args__ = (
        UniqueConstraint("dataset_key", "version", name="uq_ai_eval_dataset_key_version"),
        CheckConstraint(
            "classification IN ('synthetic', 'deidentified')",
            name="ck_ai_eval_dataset_classification",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'revoked', 'retired')",
            name="ck_ai_eval_dataset_status",
        ),
        CheckConstraint("length(content_sha256) = 64", name="ck_ai_eval_dataset_sha256_length"),
        Index("ix_ai_eval_dataset_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    license_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")


class AIEvaluationThresholdSet(TimestampMixin, Base):
    """Versioned, complete threshold set; clinical thresholds require governance approval."""

    __tablename__ = "ai_evaluation_threshold_sets"
    __table_args__ = (
        UniqueConstraint("capability", "operating_mode", "version", name="uq_ai_eval_threshold_version"),
        CheckConstraint(
            "operating_mode IN ('hybrid', 'offline', 'degraded')",
            name="ck_ai_eval_threshold_mode",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'retired', 'revoked')",
            name="ck_ai_eval_threshold_status",
        ),
        Index("ix_ai_eval_threshold_lookup", "capability", "operating_mode", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    operating_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    minimums_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    hard_stop_rules_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")


class AIEvaluationRunRecord(Base):
    """Immutable evaluation result record bound to exact model, dataset and thresholds."""

    __tablename__ = "ai_evaluation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'passed', 'failed', 'aborted')",
            name="ck_ai_eval_run_status",
        ),
        Index("ix_ai_eval_run_capability_mode_created", "capability", "operating_mode", "created_at"),
        Index("ix_ai_eval_run_dataset", "dataset_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    operating_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    model_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_sha256: Mapped[str | None] = mapped_column(String(64))
    evaluator_version: Mapped[str] = mapped_column(String(120), nullable=False)
    evaluator_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_evaluation_datasets.id"), nullable=False)
    threshold_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_evaluation_threshold_sets.id"), nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    failures_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    result_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AIModelRelease(TimestampMixin, Base):
    """Release envelope; activation is intentionally controlled outside the API app."""

    __tablename__ = "ai_model_releases"
    __table_args__ = (
        UniqueConstraint("release_key", name="uq_ai_model_release_key"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'active', 'revoked', 'expired', 'rolled_back')",
            name="ck_ai_model_release_status",
        ),
        Index("ix_ai_model_release_status_expiry", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_key: Mapped[str] = mapped_column(String(120), nullable=False)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_evaluation_runs.id"), nullable=False)
    threshold_set_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_evaluation_threshold_sets.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    previous_approved_release_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_model_releases.id"))


class AIReleaseApproval(Base):
    """Two-person release approvals; writes reserved for the governance worker role."""

    __tablename__ = "ai_release_approvals"
    __table_args__ = (
        UniqueConstraint("release_id", "approval_role", name="uq_ai_release_approval_role"),
        CheckConstraint(
            "approval_role IN ('clinical_safety_owner', 'clinical_reviewer')",
            name="ck_ai_release_approval_role",
        ),
        Index("ix_ai_release_approval_actor", "actor_user_id", "release_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    release_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_model_releases.id"), nullable=False)
    approval_role: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    credential_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    credential_verified_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIGovernanceEvent(Base):
    """Append-only record of dataset, evaluation, approval and release decisions."""

    __tablename__ = "ai_governance_events"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('accepted', 'rejected', 'revoked', 'activated', 'rolled_back')",
            name="ck_ai_governance_event_outcome",
        ),
        Index("ix_ai_governance_event_resource_time", "resource_type", "resource_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(80), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
