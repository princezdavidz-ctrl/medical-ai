import uuid
from datetime import datetime
from sqlalchemy import (
    JSON, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index,
    Integer, String, Text, UniqueConstraint, Uuid, func, text,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class PatientRecordDocument(Base):
    __tablename__ = "patient_record_documents"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_record_document_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_record_document_encounter_patient"),
        ForeignKeyConstraint(["hospital_id", "supersedes_document_id", "patient_id"], ["patient_record_documents.hospital_id", "patient_record_documents.id", "patient_record_documents.patient_id"], name="fk_record_document_supersedes"),
        UniqueConstraint("hospital_id", "id", "patient_id", name="uq_record_document_hospital_id_patient"),
        UniqueConstraint("hospital_id", "vault_reference", name="uq_record_document_vault_reference"),
        UniqueConstraint("hospital_id", "patient_id", "source_module", "source_record_id", "version_number", name="uq_record_document_source_version"),
        CheckConstraint("source_module IN ('opd', 'nursing', 'inpatient', 'emergency', 'icu', 'surgery', 'maternity', 'pediatrics', 'laboratory', 'radiology', 'pharmacy', 'billing', 'insurance', 'external', 'other')", name="ck_record_document_source"),
        CheckConstraint("record_type IN ('clinical_note', 'discharge_summary', 'lab_report', 'imaging_report', 'prescription', 'referral', 'consent', 'identity_document', 'administrative', 'external_record', 'other')", name="ck_record_document_type"),
        CheckConstraint("status IN ('pending_review', 'verified', 'rejected', 'superseded')", name="ck_record_document_status"),
        CheckConstraint("version_number >= 1", name="ck_record_document_version"),
        CheckConstraint("length(trim(title)) >= 2", name="ck_record_document_title"),
        CheckConstraint("vault_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_document_vault_ref"),
        CheckConstraint("sha256_checksum ~ '^[0-9a-fA-F]{64}$'", name="ck_record_document_checksum"),
        CheckConstraint("mime_type IN ('application/pdf', 'image/jpeg', 'image/png', 'application/dicom', 'text/plain', 'application/octet-stream')", name="ck_record_document_mime"),
        CheckConstraint("(status = 'pending_review' AND verified_by_user_id IS NULL AND verified_at IS NULL AND rejection_reason IS NULL) OR (status = 'verified' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND rejection_reason IS NULL) OR (status = 'rejected' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND rejection_reason IS NOT NULL) OR status = 'superseded'", name="ck_record_document_review_state"),
        CheckConstraint("supersedes_document_id IS NULL OR supersedes_document_id != id", name="ck_record_document_no_self_supersede"),
        Index("ix_record_document_patient_date", "hospital_id", "patient_id", "document_date"),
        Index("ix_record_document_patient_type", "hospital_id", "patient_id", "record_type", "status"),
        Index("ix_record_document_encounter", "hospital_id", "encounter_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    source_module: Mapped[str] = mapped_column(String(24), nullable=False)
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    document_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    vault_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_review")
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatientRecordReleaseRequest(Base):
    __tablename__ = "patient_record_release_requests"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_record_release_patient"),
        ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_record_release_consent"),
        UniqueConstraint("hospital_id", "id", "patient_id", name="uq_record_release_hospital_id_patient"),
        CheckConstraint("requester_type IN ('patient', 'legal_representative', 'treating_provider', 'insurer', 'court', 'regulator', 'other')", name="ck_record_release_requester_type"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'released', 'cancelled')", name="ck_record_release_status"),
        CheckConstraint("purpose IN ('record_sharing', 'care_coordination', 'referral', 'patient_portal', 'insurance_claim', 'legal_requirement', 'other')", name="ck_record_release_purpose"),
        CheckConstraint("recipient_type IN ('hospital', 'clinic', 'provider', 'insurer', 'patient', 'court', 'regulator', 'other')", name="ck_record_release_recipient_type"),
        CheckConstraint("json_typeof(data_categories) = 'array' AND json_array_length(data_categories) > 0", name="ck_record_release_categories"),
        CheckConstraint("period_end IS NULL OR period_start IS NULL OR period_end >= period_start", name="ck_record_release_period"),
        CheckConstraint("length(trim(recipient_name)) >= 2 AND length(trim(request_reason)) >= 5", name="ck_record_release_text"),
        CheckConstraint("(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND decision_reason IS NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'approved' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'rejected' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NOT NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'released' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL AND release_vault_reference IS NOT NULL) OR (status = 'cancelled' AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL)", name="ck_record_release_state"),
        CheckConstraint("release_vault_reference IS NULL OR release_vault_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_release_vault_ref"),
        Index("ix_record_release_patient_status", "hospital_id", "patient_id", "status", "created_at"),
        Index("ix_record_release_review_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    consent_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    requester_type: Mapped[str] = mapped_column(String(32), nullable=False)
    requester_name: Mapped[str] = mapped_column(String(180), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(180), nullable=False)
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)
    recipient_contact: Mapped[str | None] = mapped_column(String(320))
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    data_categories: Mapped[list] = mapped_column(JSON, nullable=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_vault_reference: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatientRecordAmendmentRequest(Base):
    __tablename__ = "patient_record_amendment_requests"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_record_amendment_patient"),
        ForeignKeyConstraint(["hospital_id", "document_id", "patient_id"], ["patient_record_documents.hospital_id", "patient_record_documents.id", "patient_record_documents.patient_id"], name="fk_record_amendment_document"),
        UniqueConstraint("hospital_id", "id", "patient_id", name="uq_record_amendment_hospital_id_patient"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'fulfilled', 'cancelled')", name="ck_record_amendment_status"),
        CheckConstraint("amendment_type IN ('demographic', 'clinical_content', 'metadata', 'identity')", name="ck_record_amendment_type"),
        CheckConstraint("length(trim(reason)) >= 5", name="ck_record_amendment_reason"),
        CheckConstraint("(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND decision_reason IS NULL AND amendment_vault_reference IS NULL) OR (status = 'approved' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NULL AND amendment_vault_reference IS NULL) OR (status = 'rejected' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NOT NULL AND amendment_vault_reference IS NULL) OR (status = 'fulfilled' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND fulfilled_by_user_id IS NOT NULL AND fulfilled_at IS NOT NULL AND amendment_vault_reference IS NOT NULL) OR (status = 'cancelled' AND amendment_vault_reference IS NULL)", name="ck_record_amendment_state"),
        CheckConstraint("amendment_vault_reference IS NULL OR amendment_vault_reference ~ '^vault://[0-9a-fA-F-]{36}
        Index("ix_record_amendment_patient_status", "hospital_id", "patient_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amendment_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    supporting_evidence_reference: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    fulfilled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amendment_vault_reference: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatientRecordEvent(Base):
    __tablename__ = "patient_record_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_patient_record_event_patient"),
        UniqueConstraint("hospital_id", "id", name="uq_patient_record_event_hospital_id"),
        CheckConstraint("event_type IN ('document_registered', 'document_verified', 'document_rejected', 'document_superseded', 'release_requested', 'release_approved', 'release_rejected', 'release_cancelled', 'records_released', 'amendment_requested', 'amendment_approved', 'amendment_rejected', 'amendment_fulfilled', 'amendment_cancelled')", name="ck_patient_record_event_type"),
        Index("ix_patient_record_event_history", "hospital_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_record_amendment_vault_ref"),
        CheckConstraint("supporting_evidence_reference IS NULL OR supporting_evidence_reference ~ '^vault://[0-9a-fA-F-]{36}
        Index("ix_record_amendment_patient_status", "hospital_id", "patient_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amendment_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    supporting_evidence_reference: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    fulfilled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amendment_vault_reference: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatientRecordEvent(Base):
    __tablename__ = "patient_record_events"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_patient_record_event_hospital_id"),
        CheckConstraint("event_type IN ('document_registered', 'document_verified', 'document_rejected', 'document_superseded', 'release_requested', 'release_approved', 'release_rejected', 'release_cancelled', 'records_released', 'amendment_requested', 'amendment_approved', 'amendment_rejected', 'amendment_fulfilled', 'amendment_cancelled')", name="ck_patient_record_event_type"),
        Index("ix_patient_record_event_history", "hospital_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_record_amendment_evidence_ref"),
        Index("ix_record_amendment_patient_status", "hospital_id", "patient_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amendment_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    supporting_evidence_reference: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(String(1000))
    fulfilled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amendment_vault_reference: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatientRecordEvent(Base):
    __tablename__ = "patient_record_events"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_patient_record_event_hospital_id"),
        CheckConstraint("event_type IN ('document_registered', 'document_verified', 'document_rejected', 'document_superseded', 'release_requested', 'release_approved', 'release_rejected', 'release_cancelled', 'records_released', 'amendment_requested', 'amendment_approved', 'amendment_rejected', 'amendment_fulfilled', 'amendment_cancelled')", name="ck_patient_record_event_type"),
        Index("ix_patient_record_event_history", "hospital_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(48), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
