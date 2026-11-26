import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON,
    String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CompliancePolicy(Base):
    __tablename__ = "compliance_policies"
    __table_args__ = (
        UniqueConstraint("hospital_id", "policy_code", "version", name="uq_compliance_policy_version"),
        UniqueConstraint("hospital_id", "id", name="uq_compliance_policy_hospital_id"),
        CheckConstraint("status IN ('draft', 'published', 'retired')", name="ck_compliance_policy_status"),
        CheckConstraint("version >= 1", name="ck_compliance_policy_version"),
        CheckConstraint("length(trim(policy_code)) BETWEEN 2 AND 80", name="ck_compliance_policy_code"),
        CheckConstraint("length(trim(title)) BETWEEN 3 AND 180", name="ck_compliance_policy_title"),
        CheckConstraint("document_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_compliance_policy_document_ref"),
        CheckConstraint("(status = 'published' AND published_by_user_id IS NOT NULL AND published_at IS NOT NULL AND effective_at IS NOT NULL) OR (status != 'published' AND published_by_user_id IS NULL AND published_at IS NULL)", name="ck_compliance_policy_publish_state"),
        Index("ix_compliance_policy_status", "hospital_id", "status", "policy_code"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    policy_code: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    document_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PolicyAcknowledgement(Base):
    __tablename__ = "policy_acknowledgements"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "policy_id"], ["compliance_policies.hospital_id", "compliance_policies.id"], name="fk_policy_acknowledgement_policy"),
        ForeignKeyConstraint(["hospital_id", "user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_policy_acknowledgement_member"),
        UniqueConstraint("hospital_id", "policy_id", "user_id", name="uq_policy_acknowledgement_user"),
        CheckConstraint("acknowledgement_method IN ('electronic', 'written', 'in_person')", name="ck_policy_acknowledgement_method"),
        Index("ix_policy_acknowledgement_user", "hospital_id", "user_id", "acknowledged_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    acknowledgement_method: Mapped[str] = mapped_column(String(16), nullable=False, default="electronic")
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SecurityIncident(Base):
    __tablename__ = "security_incidents"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "reporter_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_security_incident_reporter"),
        ForeignKeyConstraint(["hospital_id", "assigned_to_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_security_incident_assignee"),
        UniqueConstraint("hospital_id", "id", name="uq_security_incident_hospital_id"),
        CheckConstraint("category IN ('data_breach', 'unauthorized_access', 'malware', 'loss_or_theft', 'service_disruption', 'insider_threat', 'phishing', 'other')", name="ck_security_incident_category"),
        CheckConstraint("severity IN ('low', 'moderate', 'high', 'critical', 'unclassified')", name="ck_security_incident_severity"),
        CheckConstraint("status IN ('reported', 'triaged', 'investigating', 'contained', 'resolved', 'closed')", name="ck_security_incident_status"),
        CheckConstraint("breach_assessment IN ('pending', 'confirmed', 'not_confirmed', 'not_required')", name="ck_security_incident_breach_assessment"),
        CheckConstraint("length(trim(summary)) BETWEEN 10 AND 5000", name="ck_security_incident_summary"),
        Index("ix_security_incident_queue", "hospital_id", "status", "severity", "reported_at"),
        Index("ix_security_incident_assignee", "hospital_id", "assigned_to_user_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reporter_confidential: Mapped[bool] = mapped_column(nullable=False, default=True)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="unclassified")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="reported")
    breach_assessment: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    affected_system: Mapped[str | None] = mapped_column(String(180))
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    immediate_actions: Mapped[str | None] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SecurityIncidentEvent(Base):
    __tablename__ = "security_incident_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "incident_id"], ["security_incidents.hospital_id", "security_incidents.id"], name="fk_security_incident_event_incident"),
        CheckConstraint("event_type IN ('reported', 'triaged', 'assigned', 'investigation_started', 'contained', 'breach_assessed', 'resolved', 'closed')", name="ck_security_incident_event_type"),
        Index("ix_security_incident_event_history", "hospital_id", "incident_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ComplianceRisk(Base):
    __tablename__ = "compliance_risks"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "owner_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_compliance_risk_owner"),
        UniqueConstraint("hospital_id", "id", name="uq_compliance_risk_hospital_id"),
        CheckConstraint("category IN ('clinical', 'privacy', 'cybersecurity', 'operational', 'financial', 'regulatory', 'third_party', 'other')", name="ck_compliance_risk_category"),
        CheckConstraint("status IN ('open', 'mitigating', 'accepted', 'closed')", name="ck_compliance_risk_status"),
        CheckConstraint("likelihood BETWEEN 1 AND 5 AND impact BETWEEN 1 AND 5", name="ck_compliance_risk_inherent"),
        CheckConstraint("residual_likelihood BETWEEN 1 AND 5 AND residual_impact BETWEEN 1 AND 5", name="ck_compliance_risk_residual"),
        CheckConstraint("inherent_score = likelihood * impact AND residual_score = residual_likelihood * residual_impact", name="ck_compliance_risk_scores"),
        Index("ix_compliance_risk_status_score", "hospital_id", "status", "inherent_score"),
        Index("ix_compliance_risk_owner_due", "hospital_id", "owner_user_id", "due_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    likelihood: Mapped[int] = mapped_column(nullable=False)
    impact: Mapped[int] = mapped_column(nullable=False)
    inherent_score: Mapped[int] = mapped_column(nullable=False)
    residual_likelihood: Mapped[int] = mapped_column(nullable=False)
    residual_impact: Mapped[int] = mapped_column(nullable=False)
    residual_score: Mapped[int] = mapped_column(nullable=False)
    mitigation_plan: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
