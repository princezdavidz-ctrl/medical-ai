"""Create insurer coverage and manual insurance claim workflows."""

from alembic import op
import sqlalchemy as sa

revision = "0031_insurance"
down_revision = "0030_billing"
branch_labels = None
depends_on = None

TABLES = ("insurer_definitions", "patient_coverages", "insurance_claims", "insurance_claim_events")


def upgrade() -> None:
    op.create_table(
        "insurer_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("insurer_type", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("retired_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.Column("retirement_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "id", name="uq_insurer_definition_hospital_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_insurer_definition_code"),
        sa.CheckConstraint("insurer_type IN ('kenya_sha', 'private', 'employer', 'other')", name="ck_insurer_definition_type"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_insurer_definition_status"),
        sa.CheckConstraint("approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id", name="ck_insurer_definition_two_person"),
        sa.CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_insurer_definition_lifecycle",
        ),
    )
    op.create_index("ix_insurer_definition_status", "insurer_definitions", ["hospital_id", "status"])

    op.create_table(
        "patient_coverages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("insurer_definition_id", sa.Uuid(), nullable=False),
        sa.Column("member_number", sa.String(120), nullable=False),
        sa.Column("policy_number", sa.String(120)),
        sa.Column("principal_member_name", sa.String(180)),
        sa.Column("relationship_to_principal", sa.String(40)),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="reported"),
        sa.Column("verification_reference", sa.String(160)),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_patient_coverage_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "insurer_definition_id"], ["insurer_definitions.hospital_id", "insurer_definitions.id"], name="fk_patient_coverage_insurer"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_patient_coverage_hospital_id"),
        sa.CheckConstraint("status IN ('reported', 'verified', 'suspended', 'expired', 'cancelled')", name="ck_patient_coverage_status"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_patient_coverage_dates"),
        sa.CheckConstraint("(status = 'verified' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL) OR (status != 'verified')", name="ck_patient_coverage_verification"),
    )
    op.create_index("ix_patient_coverage_patient", "patient_coverages", ["hospital_id", "patient_id", "status"])

    op.create_table(
        "insurance_claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("coverage_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("claim_number", sa.String(80), nullable=False),
        sa.Column("external_claim_reference", sa.String(160)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("claimed_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("submission_note", sa.Text()),
        sa.Column("adjudication_note", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("adjudicated_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True)),
        sa.Column("last_payment_recorded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("last_payment_recorded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_insurance_claim_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_insurance_claim_encounter"),
        sa.ForeignKeyConstraint(["hospital_id", "coverage_id"], ["patient_coverages.hospital_id", "patient_coverages.id"], name="fk_insurance_claim_coverage"),
        sa.ForeignKeyConstraint(["hospital_id", "invoice_id"], ["invoices.hospital_id", "invoices.id"], name="fk_insurance_claim_invoice"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_insurance_claim_hospital_id"),
        sa.UniqueConstraint("hospital_id", "claim_number", name="uq_insurance_claim_number"),
        sa.UniqueConstraint("hospital_id", "external_claim_reference", name="uq_insurance_claim_external_reference"),
        sa.CheckConstraint("status IN ('draft', 'submitted', 'accepted', 'partially_approved', 'rejected', 'partially_paid', 'paid', 'closed')", name="ck_insurance_claim_status"),
        sa.CheckConstraint("claimed_amount > 0 AND approved_amount >= 0 AND paid_amount >= 0 AND approved_amount <= claimed_amount AND paid_amount <= approved_amount", name="ck_insurance_claim_amounts"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_insurance_claim_currency"),
        sa.CheckConstraint("status != 'draft' OR (submitted_at IS NULL AND adjudicated_at IS NULL)", name="ck_insurance_claim_draft_state"),
    )
    op.create_index("ix_insurance_claim_queue", "insurance_claims", ["hospital_id", "status", "created_at"])
    op.create_index("ix_insurance_claim_patient", "insurance_claims", ["hospital_id", "patient_id", "created_at"])

    op.create_table(
        "insurance_claim_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(24)),
        sa.Column("to_status", sa.String(24), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "claim_id"], ["insurance_claims.hospital_id", "insurance_claims.id"], name="fk_insurance_claim_event_claim"),
    )
    op.create_index("ix_insurance_claim_event_time", "insurance_claim_events", ["hospital_id", "claim_id", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(
            f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" '
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        ))
    op.execute("""
        CREATE FUNCTION prevent_insurance_claim_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'insurance claim events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_insurance_claim_events_immutable
        BEFORE UPDATE OR DELETE ON insurance_claim_events
        FOR EACH ROW EXECUTE FUNCTION prevent_insurance_claim_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_insurance_claim_events_immutable ON insurance_claim_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_insurance_claim_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
