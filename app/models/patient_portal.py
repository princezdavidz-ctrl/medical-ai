import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, String, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class PatientPortalLink(Base):
    __tablename__ = "patient_portal_links"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_patient_portal_link_patient"),
        UniqueConstraint("hospital_id", "id", "patient_id", name="uq_patient_portal_link_hospital_patient"),
        UniqueConstraint("hospital_id", "patient_id", "portal_user_id", name="uq_patient_portal_link_user_patient"),
        CheckConstraint("relationship_type IN ('self', 'parent_guardian', 'caregiver', 'legal_representative')", name="ck_patient_portal_relationship"),
        CheckConstraint("status IN ('pending', 'active', 'revoked')", name="ck_patient_portal_link_status"),
        CheckConstraint("json_typeof(access_scope) = 'array'", name="ck_patient_portal_access_scope_array"),
        CheckConstraint("verification_method IS NULL OR verification_method IN ('in_person', 'identity_document', 'verified_email', 'verified_phone', 'guardian_document', 'court_order')", name="ck_patient_portal_verification_method"),
        CheckConstraint("relationship_type = 'self' OR (authority_reference IS NOT NULL AND expires_at IS NOT NULL)", name="ck_patient_portal_proxy_authority"),
        CheckConstraint("(status = 'active' AND verification_method IS NOT NULL AND evidence_reference IS NOT NULL AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL) OR (status != 'active' AND verified_by_user_id IS NULL AND verified_at IS NULL)", name="ck_patient_portal_verification_state"),
        CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_patient_portal_evidence_reference"),
        CheckConstraint("(status = 'revoked' AND revoked_by_user_id IS NOT NULL AND revoked_at IS NOT NULL AND revocation_reason IS NOT NULL) OR (status != 'revoked' AND revoked_by_user_id IS NULL AND revoked_at IS NULL AND revocation_reason IS NULL)", name="ck_patient_portal_revocation_state"),
        Index("ix_patient_portal_user_status", "hospital_id", "portal_user_id", "status"),
        Index("ix_patient_portal_patient_status", "hospital_id", "patient_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    portal_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(24), nullable=False, default="self")
    access_scope: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: ["profile", "encounters"])
    authority_reference: Mapped[str | None] = mapped_column(String(160))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    verification_method: Mapped[str | None] = mapped_column(String(32))
    evidence_reference: Mapped[str | None] = mapped_column(String(100))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatientPortalAccessEvent(Base):
    __tablename__ = "patient_portal_access_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "portal_link_id", "patient_id"], ["patient_portal_links.hospital_id", "patient_portal_links.id", "patient_portal_links.patient_id"], name="fk_patient_portal_event_link"),
        UniqueConstraint("hospital_id", "id", name="uq_patient_portal_event_hospital_id"),
        CheckConstraint("action IN ('viewed_profile', 'viewed_encounters', 'viewed_lab_results', 'viewed_medications', 'viewed_invoices', 'viewed_consents')", name="ck_patient_portal_event_action"),
        CheckConstraint("resource_count >= 0", name="ck_patient_portal_event_resource_count"),
        Index("ix_patient_portal_access_history", "hospital_id", "patient_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    portal_link_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    portal_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
