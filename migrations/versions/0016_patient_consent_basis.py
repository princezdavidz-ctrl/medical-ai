"""Add purpose-scoped patient consent and declared lawful-basis decisions."""

from alembic import op
import sqlalchemy as sa

revision = "0016_patient_consent_basis"
down_revision = "0015_patient_registration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("patient_consents", sa.Column("basis_code", sa.String(32), nullable=True))
    op.add_column("patient_consents", sa.Column("consent_method", sa.String(24), nullable=True))
    op.add_column("patient_consents", sa.Column("evidence_reference", sa.String(80), nullable=True))
    op.add_column("patient_consents", sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("patient_consents", sa.Column("recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("patient_consents", sa.Column("withdrawn_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("patient_consents", sa.Column("decision_reason_code", sa.String(40), nullable=True))

    op.create_foreign_key(
        "fk_patient_consent_patient_tenant",
        "patient_consents",
        "patients",
        ["hospital_id", "patient_id"],
        ["hospital_id", "id"],
    )
    op.create_check_constraint(
        "ck_patient_consent_basis_code",
        "patient_consents",
        "basis_code IS NULL OR basis_code IN "
        "('patient_consent', 'guardian_consent', 'healthcare_provision', "
        "'vital_interests', 'legal_requirement', 'other_lawful_basis')",
    )
    op.create_check_constraint(
        "ck_patient_consent_method",
        "patient_consents",
        "consent_method IS NULL OR consent_method IN "
        "('written', 'electronic', 'verbal', 'guardian', 'not_applicable')",
    )
    op.create_check_constraint(
        "ck_patient_consent_reason",
        "patient_consents",
        "decision_reason_code IS NULL OR decision_reason_code IN "
        "('evidence_confirmed', 'patient_declined', 'guardian_declined', "
        "'withdrawn_by_patient', 'lawful_basis_ended', 'other')",
    )
    op.create_check_constraint(
        "ck_patient_consent_decision_state",
        "patient_consents",
        "basis_code IS NULL OR "
        "(status = 'pending' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NULL "
        "AND evidence_reference IS NULL AND consent_method IS NULL AND granted_at IS NULL "
        "AND withdrawn_at IS NULL AND withdrawn_by_user_id IS NULL AND decision_reason_code IS NULL) OR "
        "(status = 'granted' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NOT NULL "
        "AND evidence_reference IS NOT NULL AND consent_method IS NOT NULL AND granted_at IS NOT NULL "
        "AND withdrawn_at IS NULL AND withdrawn_by_user_id IS NULL AND decision_reason_code = 'evidence_confirmed') OR "
        "(status = 'rejected' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NOT NULL "
        "AND decision_reason_code IN ('patient_declined', 'guardian_declined', 'other') "
        "AND granted_at IS NULL AND withdrawn_at IS NULL AND withdrawn_by_user_id IS NULL) OR "
        "(status = 'withdrawn' AND requested_by_user_id IS NOT NULL AND recorded_by_user_id IS NOT NULL "
        "AND withdrawn_by_user_id IS NOT NULL AND withdrawn_at IS NOT NULL "
        "AND decision_reason_code IN ('withdrawn_by_patient', 'lawful_basis_ended', 'other'))",
    )
    op.create_index(
        "ix_patient_consent_basis_scope",
        "patient_consents",
        ["hospital_id", "patient_id", "basis_code", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_patient_consent_basis_scope", table_name="patient_consents")
    op.drop_constraint("ck_patient_consent_decision_state", "patient_consents", type_="check")
    op.drop_constraint("ck_patient_consent_reason", "patient_consents", type_="check")
    op.drop_constraint("ck_patient_consent_method", "patient_consents", type_="check")
    op.drop_constraint("ck_patient_consent_basis_code", "patient_consents", type_="check")
    op.drop_constraint("fk_patient_consent_patient_tenant", "patient_consents", type_="foreignkey")
    op.drop_column("patient_consents", "decision_reason_code")
    op.drop_column("patient_consents", "withdrawn_by_user_id")
    op.drop_column("patient_consents", "recorded_by_user_id")
    op.drop_column("patient_consents", "requested_by_user_id")
    op.drop_column("patient_consents", "recorded_by_user_id")
    op.drop_column("patient_consents", "evidence_reference")
    op.drop_column("patient_consents", "consent_method")
    op.drop_column("patient_consents", "basis_code")
