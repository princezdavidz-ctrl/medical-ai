"""Frozen Phase 1 baseline schema for a new, empty database.

Do not import live application metadata here: later application models must be
introduced only by their explicit Alembic revisions.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

metadata = sa.MetaData()

organizations = sa.Table(
    "organizations", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("legal_name", sa.String(240), nullable=False),
    sa.Column("registration_number", sa.String(100), unique=True),
    sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)

hospitals = sa.Table(
    "hospitals", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
    sa.Column("name", sa.String(240), nullable=False),
    sa.Column("facility_code", sa.String(80), unique=True, nullable=False),
    sa.Column("ownership_type", sa.String(24), nullable=False),
    sa.Column("country_code", sa.String(2), nullable=False, server_default="KE"),
    sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
sa.Index("ix_hospitals_organization_id", hospitals.c.organization_id)

departments = sa.Table(
    "departments", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
    sa.Column("name", sa.String(160), nullable=False),
    sa.Column("code", sa.String(40), nullable=False),
    sa.Column("status", sa.String(24), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("hospital_id", "code", name="uq_department_hospital_code"),
)
sa.Index("ix_departments_hospital_id", departments.c.hospital_id)

users = sa.Table(
    "users", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("email", sa.String(320), nullable=False),
    sa.Column("password_hash", sa.String(255), nullable=False),
    sa.Column("full_name", sa.String(200), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
sa.Index("ix_users_email", users.c.email, unique=True)

roles = sa.Table(
    "roles", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
    sa.Column("name", sa.String(80), nullable=False),
    sa.Column("description", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("hospital_id", "name", name="uq_role_hospital_name"),
)
sa.Index("ix_roles_hospital_id", roles.c.hospital_id)

hospital_memberships = sa.Table(
    "hospital_memberships", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
    sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id")),
    sa.Column("role_id", sa.Uuid(), sa.ForeignKey("roles.id"), nullable=False),
    sa.Column("professional_registration", sa.String(120)),
    sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("hospital_id", "user_id", name="uq_membership_hospital_user"),
)
sa.Index("ix_hospital_memberships_hospital_id", hospital_memberships.c.hospital_id)
sa.Index("ix_hospital_memberships_user_id", hospital_memberships.c.user_id)

patients = sa.Table(
    "patients", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
    sa.Column("medical_record_number", sa.String(80), nullable=False),
    sa.Column("given_name", sa.String(120), nullable=False),
    sa.Column("family_name", sa.String(120), nullable=False),
    sa.Column("date_of_birth", sa.Date()),
    sa.Column("administrative_sex", sa.String(24)),
    sa.Column("phone_number", sa.String(40)),
    sa.Column("status", sa.String(24), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.UniqueConstraint("hospital_id", "medical_record_number", name="uq_patient_hospital_mrn"),
)
sa.Index("ix_patients_hospital_id", patients.c.hospital_id)
sa.Index(
    "ix_patient_hospital_name_dob",
    patients.c.hospital_id, patients.c.family_name, patients.c.date_of_birth,
)

encounters = sa.Table(
    "encounters", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
    sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
    sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id")),
    sa.Column("encounter_type", sa.String(40), nullable=False),
    sa.Column("status", sa.String(24), nullable=False, server_default="in_progress"),
    sa.Column("chief_complaint", sa.Text()),
    sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("ended_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
sa.Index("ix_encounters_hospital_id", encounters.c.hospital_id)
sa.Index("ix_encounters_patient_id", encounters.c.patient_id)
sa.Index("ix_encounter_hospital_patient", encounters.c.hospital_id, encounters.c.patient_id)

patient_consents = sa.Table(
    "patient_consents", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
    sa.Column("patient_id", sa.Uuid(), sa.ForeignKey("patients.id"), nullable=False),
    sa.Column("purpose", sa.String(240), nullable=False),
    sa.Column("scope", sa.JSON(), nullable=False),
    sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
    sa.Column("granted_at", sa.DateTime(timezone=True)),
    sa.Column("expires_at", sa.DateTime(timezone=True)),
    sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
sa.Index("ix_patient_consents_hospital_id", patient_consents.c.hospital_id)
sa.Index("ix_patient_consents_patient_id", patient_consents.c.patient_id)
sa.Index(
    "ix_consent_hospital_patient_status",
    patient_consents.c.hospital_id, patient_consents.c.patient_id, patient_consents.c.status,
)

audit_events = sa.Table(
    "audit_events", metadata,
    sa.Column("id", sa.Uuid(), primary_key=True),
    sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
    sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
    sa.Column("action", sa.String(100), nullable=False),
    sa.Column("resource_type", sa.String(100), nullable=False),
    sa.Column("resource_id", sa.String(80)),
    sa.Column("outcome", sa.String(24), nullable=False),
    sa.Column("reason", sa.Text()),
    sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
)
sa.Index("ix_audit_events_hospital_id", audit_events.c.hospital_id)
sa.Index("ix_audit_hospital_time", audit_events.c.hospital_id, audit_events.c.occurred_at)


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())
