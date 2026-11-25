import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, JSON, String, Text, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ClinicalStaffProfile(Base):
    __tablename__ = "clinical_staff_profiles"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "employee_profile_id"], ["employee_profiles.hospital_id", "employee_profiles.id"], name="fk_clinical_staff_employee"),
        UniqueConstraint("hospital_id", "id", name="uq_clinical_staff_profile_hospital_id"),
        UniqueConstraint("hospital_id", "user_id", name="uq_clinical_staff_profile_user"),
        UniqueConstraint("hospital_id", "registration_number", name="uq_clinical_staff_registration_number"),
        CheckConstraint("clinical_role IN ('physician', 'nurse', 'midwife', 'pharmacist', 'clinical_officer', 'dentist', 'therapist', 'radiographer', 'laboratory_scientist', 'other')", name="ck_clinical_staff_role"),
        CheckConstraint("status IN ('pending', 'verified', 'rejected', 'suspended')", name="ck_clinical_staff_status"),
        CheckConstraint("(status IN ('verified', 'suspended') AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND evidence_reference IS NOT NULL) OR (status IN ('pending', 'rejected') AND verified_by_user_id IS NULL AND verified_at IS NULL)", name="ck_clinical_staff_verification"),
        CheckConstraint("status != 'rejected' OR rejection_reason IS NOT NULL", name="ck_clinical_staff_rejection_reason"),
        CheckConstraint("status != 'suspended' OR suspension_reason IS NOT NULL", name="ck_clinical_staff_suspension_reason"),
        CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_clinical_staff_evidence_reference"),
        Index("ix_clinical_staff_status_role", "hospital_id", "status", "clinical_role"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    employee_profile_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    clinical_role: Mapped[str] = mapped_column(String(32), nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(160))
    professional_title: Mapped[str] = mapped_column(String(160), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(120), nullable=False)
    licensing_body: Mapped[str] = mapped_column(String(160), nullable=False)
    license_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    evidence_reference: Mapped[str | None] = mapped_column(String(100))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))
    suspension_reason: Mapped[str | None] = mapped_column(String(1000))
    submitted_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PatientCareTeamAssignment(Base):
    __tablename__ = "patient_care_team_assignments"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_care_team_patient"),
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_care_team_department"),
        UniqueConstraint("hospital_id", "id", name="uq_care_team_assignment_hospital_id"),
        CheckConstraint("care_role IN ('attending_physician', 'consultant', 'primary_nurse', 'midwife', 'pharmacist', 'case_manager', 'allied_health', 'other')", name="ck_care_team_role"),
        CheckConstraint("status IN ('active', 'ended', 'revoked')", name="ck_care_team_status"),
        CheckConstraint("json_typeof(access_scope) = 'array'", name="ck_care_team_access_scope_array"),
        CheckConstraint("assigned_by_user_id != staff_user_id", name="ck_care_team_no_self_assignment"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="ck_care_team_time_range"),
        CheckConstraint("(status = 'active' AND ended_by_user_id IS NULL AND ended_at IS NULL AND end_reason IS NULL) OR (status IN ('ended', 'revoked') AND ended_by_user_id IS NOT NULL AND ended_at IS NOT NULL AND end_reason IS NOT NULL)", name="ck_care_team_end_state"),
        Index("uq_care_team_active_member", "hospital_id", "patient_id", "staff_user_id", "care_role", unique=True, postgresql_where=text("status = 'active'")),
        Index("ix_care_team_staff_status", "hospital_id", "staff_user_id", "status"),
        Index("ix_care_team_patient_status", "hospital_id", "patient_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    staff_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    care_role: Mapped[str] = mapped_column(String(32), nullable=False)
    access_scope: Mapped[list] = mapped_column(JSON, nullable=False, default=lambda: ["profile", "encounters"])
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ended_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class StaffWorkQueueTask(Base):
    __tablename__ = "staff_work_queue_tasks"
    __table_args__ = (
        ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_staff_task_patient"),
        ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_staff_task_encounter_patient"),
        ForeignKeyConstraint(["hospital_id", "department_id"], ["departments.hospital_id", "departments.id"], name="fk_staff_task_department"),
        UniqueConstraint("hospital_id", "id", name="uq_staff_task_hospital_id"),
        CheckConstraint("task_type IN ('review_lab_result', 'sign_note', 'medication_review', 'discharge_planning', 'follow_up', 'referral', 'care_coordination', 'other')", name="ck_staff_task_type"),
        CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_staff_task_priority"),
        CheckConstraint("status IN ('open', 'in_progress', 'completed', 'cancelled')", name="ck_staff_task_status"),
        CheckConstraint("encounter_id IS NULL OR patient_id IS NOT NULL", name="ck_staff_task_encounter_patient_required"),
        CheckConstraint("(status = 'completed' AND completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL) OR (status != 'completed' AND completed_by_user_id IS NULL AND completed_at IS NULL)", name="ck_staff_task_completion_state"),
        Index("ix_staff_task_assignee_queue", "hospital_id", "assigned_to_user_id", "status", "priority", "due_at"),
        Index("ix_staff_task_patient", "hospital_id", "patient_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    assigned_to_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StaffPortalEvent(Base):
    __tablename__ = "staff_portal_events"
    __table_args__ = (
        UniqueConstraint("hospital_id", "id", name="uq_staff_portal_event_hospital_id"),
        CheckConstraint("event_type IN ('clinical_profile_submitted', 'clinical_profile_verified', 'clinical_profile_rejected', 'clinical_profile_suspended', 'care_team_assigned', 'care_team_ended', 'task_created', 'task_status_changed', 'patient_overview_viewed')", name="ck_staff_portal_event_type"),
        Index("ix_staff_portal_event_history", "hospital_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hospital_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("hospitals.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    event_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
