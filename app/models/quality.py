import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    JSON, String, Text, UniqueConstraint, Uuid, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SafetyIncident(Base):
    __tablename__ = "safety_incidents"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_safety_incident_department"),
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_safety_incident_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_safety_incident_encounter"),
        ForeignKeyConstraint(["hospital_id", "reporter_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_incident_reporter_membership"),
        UniqueConstraint("hospital_id", "id", name="uq_safety_incident_hospital_id"),
        CheckConstraint("category IN ('medication', 'patient_fall', 'diagnostic', 'procedure', 'infection', 'equipment', 'transfusion', 'documentation', 'communication', 'security', 'other')", name="ck_safety_incident_category"),
        CheckConstraint("severity IN ('low', 'moderate', 'high', 'critical', 'unclassified')", name="ck_safety_incident_severity"),
        CheckConstraint("harm_level IN ('none', 'mild', 'moderate', 'severe', 'death', 'unknown')", name="ck_safety_incident_harm"),
        CheckConstraint("status IN ('reported', 'triaged', 'investigating', 'capa_open', 'pending_review', 'closed', 'reopened')", name="ck_safety_incident_status"),
        CheckConstraint("length(trim(summary)) BETWEEN 10 AND 4000", name="ck_safety_incident_summary"),
        CheckConstraint("(patient_id IS NULL AND encounter_id IS NULL) OR patient_id IS NOT NULL", name="ck_safety_incident_patient_encounter_pair"),
        Index("ix_safety_incident_department_status", "hospital_id", "department_id", "status", "reported_at"),
        Index("ix_safety_incident_severity_time", "hospital_id", "severity", "reported_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    reporter_confidential: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="unclassified")
    harm_level: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="reported")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    immediate_actions: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SafetyIncidentEvent(Base):
    __tablename__ = "safety_incident_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "incident_id"], ["safety_incidents.hospital_id", "safety_incidents.id"], name="fk_safety_incident_event_incident"),
        CheckConstraint("event_type IN ('reported', 'triaged', 'assigned', 'investigation_started', 'investigation_completed', 'capa_created', 'status_changed', 'reopened', 'closed')", name="ck_safety_incident_event_type"),
        Index("ix_safety_incident_event_history", "hospital_id", "incident_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SafetyInvestigation(Base):
    __tablename__ = "safety_investigations"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "incident_id"], ["safety_incidents.hospital_id", "safety_incidents.id"], name="fk_safety_investigation_incident"),
        ForeignKeyConstraint(["hospital_id", "assigned_to_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_investigation_assignee"),
        ForeignKeyConstraint(["hospital_id", "reviewed_by_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_investigation_reviewer"),
        UniqueConstraint("hospital_id", "incident_id", name="uq_safety_investigation_incident"),
        CheckConstraint("status IN ('assigned', 'in_progress', 'pending_review', 'approved', 'rejected')", name="ck_safety_investigation_status"),
        CheckConstraint("reviewed_at IS NULL OR reviewed_by_user_id IS NOT NULL", name="ck_safety_investigation_review_state"),
        Index("ix_safety_investigation_assignee", "hospital_id", "assigned_to_user_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    assigned_to_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="assigned")
    findings: Mapped[str | None] = mapped_column(Text)
    contributing_factors: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CAPAAction(Base):
    __tablename__ = "safety_capa_actions"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "incident_id"], ["safety_incidents.hospital_id", "safety_incidents.id"], name="fk_safety_capa_incident"),
        ForeignKeyConstraint(["hospital_id", "owner_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_capa_owner"),
        ForeignKeyConstraint(["hospital_id", "effectiveness_reviewer_user_id"], ["hospital_memberships.hospital_id", "hospital_memberships.user_id"], name="fk_safety_capa_reviewer"),
        CheckConstraint("status IN ('open', 'in_progress', 'pending_effectiveness_review', 'completed', 'cancelled')", name="ck_safety_capa_status"),
        CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_safety_capa_evidence_reference"),
        CheckConstraint("(status = 'completed' AND effectiveness_reviewer_user_id IS NOT NULL AND effectiveness_reviewed_at IS NOT NULL) OR (status != 'completed' AND effectiveness_reviewer_user_id IS NULL AND effectiveness_reviewed_at IS NULL)", name="ck_safety_capa_completion_review"),
        Index("ix_safety_capa_owner_due", "hospital_id", "owner_user_id", "status", "due_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    evidence_reference: Mapped[str | None] = mapped_column(String(80))
    effectiveness_review: Mapped[str | None] = mapped_column(Text)
    effectiveness_reviewer_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    effectiveness_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
