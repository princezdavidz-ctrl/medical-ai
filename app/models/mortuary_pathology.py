import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class MortuaryCase(Base):
    __tablename__ = "mortuary_cases"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_mortuary_case_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_mortuary_case_encounter_patient"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_case_hospital_id"),
        UniqueConstraint("hospital_id", "case_number", name="uq_mortuary_case_number"),
        UniqueConstraint("hospital_id", "body_reference", name="uq_mortuary_body_reference"),
        CheckConstraint("status IN ('received', 'stored', 'release_pending', 'released', 'transferred', 'retained_by_authority')", name="ck_mortuary_case_status"),
        CheckConstraint("length(trim(storage_location)) >= 2", name="ck_mortuary_storage_location"),
        CheckConstraint("(status = 'released' AND released_to_name IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL) OR (status != 'released' AND released_to_name IS NULL AND released_by_user_id IS NULL AND released_at IS NULL)", name="ck_mortuary_release_state"),
        CheckConstraint("legal_hold = false OR status NOT IN ('release_pending', 'released', 'transferred')", name="ck_mortuary_legal_hold"),
        Index("ix_mortuary_case_queue", "hospital_id", "status", "received_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    case_number: Mapped[str] = mapped_column(String(80), nullable=False)
    body_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    death_occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    death_certification_reference: Mapped[str | None] = mapped_column(String(160))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    storage_location: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    released_to_name: Mapped[str | None] = mapped_column(String(180))
    released_to_identity_reference: Mapped[str | None] = mapped_column(String(160))
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MortuaryAuthorization(Base):
    __tablename__ = "mortuary_authorizations"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_authorization_case"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_authorization_hospital_id"),
        CheckConstraint("authority_type IN ('next_of_kin_consent', 'court_order', 'coroner_directive', 'public_health_order', 'other_lawful_basis')", name="ck_mortuary_authority_type"),
        CheckConstraint("status IN ('pending', 'verified', 'rejected', 'revoked')", name="ck_mortuary_authorization_status"),
        CheckConstraint("(status = 'verified' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND evidence_reference IS NOT NULL) OR (status != 'verified' AND verified_by_user_id IS NULL AND verified_at IS NULL)", name="ck_mortuary_authorization_verification"),
        CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}
        Index("ix_mortuary_authorization_case", "hospital_id", "mortuary_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    authority_type: Mapped[str] = mapped_column(String(32), nullable=False)
    authority_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MortuaryMovement(Base):
    __tablename__ = "mortuary_movements"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_movement_case"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_movement_hospital_id"),
        CheckConstraint("movement_type IN ('received', 'stored', 'relocated', 'release_pending', 'released', 'transferred', 'retained')", name="ck_mortuary_movement_type"),
        CheckConstraint("length(trim(to_location)) >= 2", name="ck_mortuary_movement_location"),
        Index("ix_mortuary_movement_case_time", "hospital_id", "mortuary_case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_location: Mapped[str | None] = mapped_column(String(180))
    to_location: Mapped[str] = mapped_column(String(180), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MortuaryPropertyItem(Base):
    __tablename__ = "mortuary_property_items"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_property_case"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_property_hospital_id"),
        CheckConstraint("status IN ('received', 'sealed', 'released', 'retained')", name="ck_mortuary_property_status"),
        CheckConstraint("(status = 'released' AND released_to_name IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL) OR (status != 'released' AND released_to_name IS NULL AND released_by_user_id IS NULL AND released_at IS NULL)", name="ck_mortuary_property_release_state"),
        Index("ix_mortuary_property_case", "hospital_id", "mortuary_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    property_description: Mapped[str] = mapped_column(String(500), nullable=False)
    property_reference: Mapped[str | None] = mapped_column(String(120))
    sealed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")
    released_to_name: Mapped[str | None] = mapped_column(String(180))
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyCase(Base):
    __tablename__ = "pathology_cases"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_pathology_case_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_pathology_case_encounter_patient"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_case_hospital_id"),
        UniqueConstraint("hospital_id", "case_number", name="uq_pathology_case_number"),
        CheckConstraint("case_type IN ('biopsy', 'surgical', 'autopsy', 'forensic')", name="ck_pathology_case_type"),
        CheckConstraint("status IN ('opened', 'specimens_received', 'in_progress', 'report_draft', 'finalized', 'closed', 'cancelled')", name="ck_pathology_case_status"),
        CheckConstraint("(case_type NOT IN ('autopsy', 'forensic')) OR (authority_type IS NOT NULL AND authority_reference IS NOT NULL)", name="ck_pathology_authority_required"),
        CheckConstraint("authority_type IS NULL OR authority_type IN ('patient_consent', 'next_of_kin_consent', 'court_order', 'coroner_directive', 'public_health_order', 'other_lawful_basis')", name="ck_pathology_authority_type"),
        CheckConstraint("case_type != 'forensic' OR authority_type IN ('court_order', 'coroner_directive', 'public_health_order')", name="ck_pathology_forensic_authority"),
        CheckConstraint("authority_evidence_reference IS NULL OR authority_evidence_reference ~ '^vault://[0-9a-fA-F-]{36}
        CheckConstraint("(authority_verified_by_user_id IS NULL AND authority_verified_at IS NULL AND authority_evidence_reference IS NULL) OR (authority_verified_by_user_id IS NOT NULL AND authority_verified_at IS NOT NULL AND authority_evidence_reference IS NOT NULL)", name="ck_pathology_authority_verification"),
        CheckConstraint("authority_verified_by_user_id IS NULL OR case_type IN ('autopsy', 'forensic')", name="ck_pathology_authority_verification_scope"),
        Index("ix_pathology_case_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    case_number: Mapped[str] = mapped_column(String(80), nullable=False)
    case_type: Mapped[str] = mapped_column(String(24), nullable=False)
    clinical_indication: Mapped[str] = mapped_column(Text, nullable=False)
    order_reference: Mapped[str | None] = mapped_column(String(160))
    authority_type: Mapped[str | None] = mapped_column(String(32))
    authority_reference: Mapped[str | None] = mapped_column(String(160))
    authority_evidence_reference: Mapped[str | None] = mapped_column(String(100))
    authority_verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    authority_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="opened")
    assigned_pathologist_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologySpecimen(Base):
    __tablename__ = "pathology_specimens"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_specimen_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_specimen_hospital_id"),
        UniqueConstraint("hospital_id", "accession_number", name="uq_pathology_specimen_accession"),
        CheckConstraint("status IN ('collected', 'received', 'processing', 'processed', 'archived', 'rejected')", name="ck_pathology_specimen_status"),
        CheckConstraint("specimen_condition IN ('acceptable', 'damaged', 'leaking', 'unlabelled', 'other')", name="ck_pathology_specimen_condition"),
        CheckConstraint("status NOT IN ('received', 'processing', 'processed', 'archived') OR (received_at IS NOT NULL AND received_by_user_id IS NOT NULL)", name="ck_pathology_specimen_receipt_state"),
        Index("ix_pathology_specimen_case", "hospital_id", "pathology_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(100), nullable=False)
    specimen_type: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    specimen_condition: Mapped[str] = mapped_column(String(24), nullable=False, default="acceptable")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="collected")
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyReport(Base):
    __tablename__ = "pathology_reports"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_report_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_report_hospital_id"),
        UniqueConstraint("hospital_id", "pathology_case_id", "version", name="uq_pathology_report_version"),
        CheckConstraint("version >= 1", name="ck_pathology_report_version"),
        CheckConstraint("status IN ('draft', 'final')", name="ck_pathology_report_status"),
        CheckConstraint("(status = 'final' AND signed_by_user_id IS NOT NULL AND signed_at IS NOT NULL) OR (status = 'draft' AND signed_by_user_id IS NULL AND signed_at IS NULL)", name="ck_pathology_report_signing"),
        Index("ix_pathology_report_case", "hospital_id", "pathology_case_id", "version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    authored_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    signed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyEvent(Base):
    __tablename__ = "pathology_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_event_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_event_hospital_id"),
        CheckConstraint("event_type IN ('case_opened', 'authority_verified', 'specimen_added', 'specimen_received', 'specimen_status_changed', 'report_drafted', 'report_finalized', 'case_closed', 'case_cancelled')", name="ck_pathology_event_type"),
        Index("ix_pathology_event_case_time", "hospital_id", "pathology_case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_mortuary_authorization_evidence"),
        Index("ix_mortuary_authorization_case", "hospital_id", "mortuary_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    authority_type: Mapped[str] = mapped_column(String(32), nullable=False)
    authority_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MortuaryMovement(Base):
    __tablename__ = "mortuary_movements"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_movement_case"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_movement_hospital_id"),
        CheckConstraint("movement_type IN ('received', 'stored', 'relocated', 'release_pending', 'released', 'transferred', 'retained')", name="ck_mortuary_movement_type"),
        CheckConstraint("length(trim(to_location)) >= 2", name="ck_mortuary_movement_location"),
        Index("ix_mortuary_movement_case_time", "hospital_id", "mortuary_case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_location: Mapped[str | None] = mapped_column(String(180))
    to_location: Mapped[str] = mapped_column(String(180), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MortuaryPropertyItem(Base):
    __tablename__ = "mortuary_property_items"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_property_case"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_property_hospital_id"),
        CheckConstraint("status IN ('received', 'sealed', 'released', 'retained')", name="ck_mortuary_property_status"),
        CheckConstraint("(status = 'released' AND released_to_name IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL) OR (status != 'released' AND released_to_name IS NULL AND released_by_user_id IS NULL AND released_at IS NULL)", name="ck_mortuary_property_release_state"),
        Index("ix_mortuary_property_case", "hospital_id", "mortuary_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    property_description: Mapped[str] = mapped_column(String(500), nullable=False)
    property_reference: Mapped[str | None] = mapped_column(String(120))
    sealed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")
    released_to_name: Mapped[str | None] = mapped_column(String(180))
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyCase(Base):
    __tablename__ = "pathology_cases"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_pathology_case_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_pathology_case_encounter_patient"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_case_hospital_id"),
        UniqueConstraint("hospital_id", "case_number", name="uq_pathology_case_number"),
        CheckConstraint("case_type IN ('biopsy', 'surgical', 'autopsy', 'forensic')", name="ck_pathology_case_type"),
        CheckConstraint("status IN ('opened', 'specimens_received', 'in_progress', 'report_draft', 'finalized', 'closed', 'cancelled')", name="ck_pathology_case_status"),
        CheckConstraint("(case_type NOT IN ('autopsy', 'forensic')) OR (authority_type IS NOT NULL AND authority_reference IS NOT NULL)", name="ck_pathology_authority_required"),
        CheckConstraint("authority_type IS NULL OR authority_type IN ('patient_consent', 'next_of_kin_consent', 'court_order', 'coroner_directive', 'public_health_order', 'other_lawful_basis')", name="ck_pathology_authority_type"),
        CheckConstraint("(authority_verified_by_user_id IS NULL AND authority_verified_at IS NULL) OR (authority_verified_by_user_id IS NOT NULL AND authority_verified_at IS NOT NULL)", name="ck_pathology_authority_verification"),
        Index("ix_pathology_case_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    case_number: Mapped[str] = mapped_column(String(80), nullable=False)
    case_type: Mapped[str] = mapped_column(String(24), nullable=False)
    clinical_indication: Mapped[str] = mapped_column(Text, nullable=False)
    order_reference: Mapped[str | None] = mapped_column(String(160))
    authority_type: Mapped[str | None] = mapped_column(String(32))
    authority_reference: Mapped[str | None] = mapped_column(String(160))
    authority_evidence_reference: Mapped[str | None] = mapped_column(String(100))
    authority_verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    authority_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="opened")
    assigned_pathologist_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologySpecimen(Base):
    __tablename__ = "pathology_specimens"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_specimen_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_specimen_hospital_id"),
        UniqueConstraint("hospital_id", "accession_number", name="uq_pathology_specimen_accession"),
        CheckConstraint("status IN ('collected', 'received', 'processing', 'processed', 'archived', 'rejected')", name="ck_pathology_specimen_status"),
        CheckConstraint("specimen_condition IN ('acceptable', 'damaged', 'leaking', 'unlabelled', 'other')", name="ck_pathology_specimen_condition"),
        CheckConstraint("status NOT IN ('received', 'processing', 'processed', 'archived') OR (received_at IS NOT NULL AND received_by_user_id IS NOT NULL)", name="ck_pathology_specimen_receipt_state"),
        Index("ix_pathology_specimen_case", "hospital_id", "pathology_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(100), nullable=False)
    specimen_type: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    specimen_condition: Mapped[str] = mapped_column(String(24), nullable=False, default="acceptable")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="collected")
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyReport(Base):
    __tablename__ = "pathology_reports"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_report_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_report_hospital_id"),
        UniqueConstraint("hospital_id", "pathology_case_id", "version", name="uq_pathology_report_version"),
        CheckConstraint("version >= 1", name="ck_pathology_report_version"),
        CheckConstraint("status IN ('draft', 'final')", name="ck_pathology_report_status"),
        CheckConstraint("(status = 'final' AND signed_by_user_id IS NOT NULL AND signed_at IS NOT NULL) OR (status = 'draft' AND signed_by_user_id IS NULL AND signed_at IS NULL)", name="ck_pathology_report_signing"),
        Index("ix_pathology_report_case", "hospital_id", "pathology_case_id", "version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    authored_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    signed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyEvent(Base):
    __tablename__ = "pathology_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_event_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_event_hospital_id"),
        CheckConstraint("event_type IN ('case_opened', 'authority_verified', 'specimen_added', 'specimen_received', 'specimen_status_changed', 'report_drafted', 'report_finalized', 'case_closed', 'case_cancelled')", name="ck_pathology_event_type"),
        Index("ix_pathology_event_case_time", "hospital_id", "pathology_case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_pathology_authority_evidence"),
        CheckConstraint("(authority_verified_by_user_id IS NULL AND authority_verified_at IS NULL) OR (authority_verified_by_user_id IS NOT NULL AND authority_verified_at IS NOT NULL)", name="ck_pathology_authority_verification"),
        Index("ix_pathology_case_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    case_number: Mapped[str] = mapped_column(String(80), nullable=False)
    case_type: Mapped[str] = mapped_column(String(24), nullable=False)
    clinical_indication: Mapped[str] = mapped_column(Text, nullable=False)
    order_reference: Mapped[str | None] = mapped_column(String(160))
    authority_type: Mapped[str | None] = mapped_column(String(32))
    authority_reference: Mapped[str | None] = mapped_column(String(160))
    authority_evidence_reference: Mapped[str | None] = mapped_column(String(100))
    authority_verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    authority_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="opened")
    assigned_pathologist_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologySpecimen(Base):
    __tablename__ = "pathology_specimens"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_specimen_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_specimen_hospital_id"),
        UniqueConstraint("hospital_id", "accession_number", name="uq_pathology_specimen_accession"),
        CheckConstraint("status IN ('collected', 'received', 'processing', 'processed', 'archived', 'rejected')", name="ck_pathology_specimen_status"),
        CheckConstraint("specimen_condition IN ('acceptable', 'damaged', 'leaking', 'unlabelled', 'other')", name="ck_pathology_specimen_condition"),
        CheckConstraint("status NOT IN ('received', 'processing', 'processed', 'archived') OR (received_at IS NOT NULL AND received_by_user_id IS NOT NULL)", name="ck_pathology_specimen_receipt_state"),
        Index("ix_pathology_specimen_case", "hospital_id", "pathology_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(100), nullable=False)
    specimen_type: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    specimen_condition: Mapped[str] = mapped_column(String(24), nullable=False, default="acceptable")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="collected")
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyReport(Base):
    __tablename__ = "pathology_reports"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_report_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_report_hospital_id"),
        UniqueConstraint("hospital_id", "pathology_case_id", "version", name="uq_pathology_report_version"),
        CheckConstraint("version >= 1", name="ck_pathology_report_version"),
        CheckConstraint("status IN ('draft', 'final')", name="ck_pathology_report_status"),
        CheckConstraint("(status = 'final' AND signed_by_user_id IS NOT NULL AND signed_at IS NOT NULL) OR (status = 'draft' AND signed_by_user_id IS NULL AND signed_at IS NULL)", name="ck_pathology_report_signing"),
        Index("ix_pathology_report_case", "hospital_id", "pathology_case_id", "version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    authored_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    signed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyEvent(Base):
    __tablename__ = "pathology_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_event_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_event_hospital_id"),
        CheckConstraint("event_type IN ('case_opened', 'authority_verified', 'specimen_added', 'specimen_received', 'specimen_status_changed', 'report_drafted', 'report_finalized', 'case_closed', 'case_cancelled')", name="ck_pathology_event_type"),
        Index("ix_pathology_event_case_time", "hospital_id", "pathology_case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
", name="ck_mortuary_authorization_evidence"),
        Index("ix_mortuary_authorization_case", "hospital_id", "mortuary_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    authority_type: Mapped[str] = mapped_column(String(32), nullable=False)
    authority_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MortuaryMovement(Base):
    __tablename__ = "mortuary_movements"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_movement_case"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_movement_hospital_id"),
        CheckConstraint("movement_type IN ('received', 'stored', 'relocated', 'release_pending', 'released', 'transferred', 'retained')", name="ck_mortuary_movement_type"),
        CheckConstraint("length(trim(to_location)) >= 2", name="ck_mortuary_movement_location"),
        Index("ix_mortuary_movement_case_time", "hospital_id", "mortuary_case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    movement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_location: Mapped[str | None] = mapped_column(String(180))
    to_location: Mapped[str] = mapped_column(String(180), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MortuaryPropertyItem(Base):
    __tablename__ = "mortuary_property_items"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_property_case"),
        UniqueConstraint("hospital_id", "id", name="uq_mortuary_property_hospital_id"),
        CheckConstraint("status IN ('received', 'sealed', 'released', 'retained')", name="ck_mortuary_property_status"),
        CheckConstraint("(status = 'released' AND released_to_name IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL) OR (status != 'released' AND released_to_name IS NULL AND released_by_user_id IS NULL AND released_at IS NULL)", name="ck_mortuary_property_release_state"),
        Index("ix_mortuary_property_case", "hospital_id", "mortuary_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    mortuary_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    property_description: Mapped[str] = mapped_column(String(500), nullable=False)
    property_reference: Mapped[str | None] = mapped_column(String(120))
    sealed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="received")
    released_to_name: Mapped[str | None] = mapped_column(String(180))
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyCase(Base):
    __tablename__ = "pathology_cases"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_pathology_case_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_pathology_case_encounter_patient"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_case_hospital_id"),
        UniqueConstraint("hospital_id", "case_number", name="uq_pathology_case_number"),
        CheckConstraint("case_type IN ('biopsy', 'surgical', 'autopsy', 'forensic')", name="ck_pathology_case_type"),
        CheckConstraint("status IN ('opened', 'specimens_received', 'in_progress', 'report_draft', 'finalized', 'closed', 'cancelled')", name="ck_pathology_case_status"),
        CheckConstraint("(case_type NOT IN ('autopsy', 'forensic')) OR (authority_type IS NOT NULL AND authority_reference IS NOT NULL)", name="ck_pathology_authority_required"),
        CheckConstraint("authority_type IS NULL OR authority_type IN ('patient_consent', 'next_of_kin_consent', 'court_order', 'coroner_directive', 'public_health_order', 'other_lawful_basis')", name="ck_pathology_authority_type"),
        CheckConstraint("(authority_verified_by_user_id IS NULL AND authority_verified_at IS NULL) OR (authority_verified_by_user_id IS NOT NULL AND authority_verified_at IS NOT NULL)", name="ck_pathology_authority_verification"),
        Index("ix_pathology_case_queue", "hospital_id", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    case_number: Mapped[str] = mapped_column(String(80), nullable=False)
    case_type: Mapped[str] = mapped_column(String(24), nullable=False)
    clinical_indication: Mapped[str] = mapped_column(Text, nullable=False)
    order_reference: Mapped[str | None] = mapped_column(String(160))
    authority_type: Mapped[str | None] = mapped_column(String(32))
    authority_reference: Mapped[str | None] = mapped_column(String(160))
    authority_evidence_reference: Mapped[str | None] = mapped_column(String(100))
    authority_verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    authority_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="opened")
    assigned_pathologist_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    opened_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologySpecimen(Base):
    __tablename__ = "pathology_specimens"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_specimen_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_specimen_hospital_id"),
        UniqueConstraint("hospital_id", "accession_number", name="uq_pathology_specimen_accession"),
        CheckConstraint("status IN ('collected', 'received', 'processing', 'processed', 'archived', 'rejected')", name="ck_pathology_specimen_status"),
        CheckConstraint("specimen_condition IN ('acceptable', 'damaged', 'leaking', 'unlabelled', 'other')", name="ck_pathology_specimen_condition"),
        CheckConstraint("status NOT IN ('received', 'processing', 'processed', 'archived') OR (received_at IS NOT NULL AND received_by_user_id IS NOT NULL)", name="ck_pathology_specimen_receipt_state"),
        Index("ix_pathology_specimen_case", "hospital_id", "pathology_case_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(100), nullable=False)
    specimen_type: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    specimen_condition: Mapped[str] = mapped_column(String(24), nullable=False, default="acceptable")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="collected")
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyReport(Base):
    __tablename__ = "pathology_reports"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_report_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_report_hospital_id"),
        UniqueConstraint("hospital_id", "pathology_case_id", "version", name="uq_pathology_report_version"),
        CheckConstraint("version >= 1", name="ck_pathology_report_version"),
        CheckConstraint("status IN ('draft', 'final')", name="ck_pathology_report_status"),
        CheckConstraint("(status = 'final' AND signed_by_user_id IS NOT NULL AND signed_at IS NOT NULL) OR (status = 'draft' AND signed_by_user_id IS NULL AND signed_at IS NULL)", name="ck_pathology_report_signing"),
        Index("ix_pathology_report_case", "hospital_id", "pathology_case_id", "version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    authored_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    signed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PathologyEvent(Base):
    __tablename__ = "pathology_events"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_event_case"),
        UniqueConstraint("hospital_id", "id", name="uq_pathology_event_hospital_id"),
        CheckConstraint("event_type IN ('case_opened', 'authority_verified', 'specimen_added', 'specimen_received', 'specimen_status_changed', 'report_drafted', 'report_finalized', 'case_closed', 'case_cancelled')", name="ck_pathology_event_type"),
        Index("ix_pathology_event_case_time", "hospital_id", "pathology_case_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    pathology_case_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
