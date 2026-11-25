"""Create mortuary custody and pathology case workflows."""
from alembic import op
import sqlalchemy as sa

revision = "0037_mortuary_pathology"
down_revision = "0036_ambulance_transport"
branch_labels = None
depends_on = None

TABLES = (
    "mortuary_cases", "mortuary_authorizations", "mortuary_movements",
    "mortuary_property_items", "pathology_cases", "pathology_specimens",
    "pathology_reports", "pathology_events",
)


def upgrade() -> None:
    op.create_table(
        "mortuary_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid()),
        sa.Column("case_number", sa.String(80), nullable=False),
        sa.Column("body_reference", sa.String(100), nullable=False),
        sa.Column("death_occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("death_certification_reference", sa.String(160)),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("received_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("storage_location", sa.String(180), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("released_to_name", sa.String(180)),
        sa.Column("released_to_identity_reference", sa.String(160)),
        sa.Column("released_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_mortuary_case_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_mortuary_case_encounter_patient"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_mortuary_case_hospital_id"),
        sa.UniqueConstraint("hospital_id", "case_number", name="uq_mortuary_case_number"),
        sa.UniqueConstraint("hospital_id", "body_reference", name="uq_mortuary_body_reference"),
        sa.CheckConstraint("status IN ('received', 'stored', 'release_pending', 'released', 'transferred', 'retained_by_authority')", name="ck_mortuary_case_status"),
        sa.CheckConstraint("length(trim(storage_location)) >= 2", name="ck_mortuary_storage_location"),
        sa.CheckConstraint("(status = 'released' AND released_to_name IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL) OR (status != 'released' AND released_to_name IS NULL AND released_by_user_id IS NULL AND released_at IS NULL)", name="ck_mortuary_release_state"),
        sa.CheckConstraint("legal_hold = false OR status NOT IN ('release_pending', 'released', 'transferred')", name="ck_mortuary_legal_hold"),
    )
    op.create_index("ix_mortuary_case_queue", "mortuary_cases", ["hospital_id", "status", "received_at"])
    op.create_table(
        "mortuary_authorizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("mortuary_case_id", sa.Uuid(), nullable=False),
        sa.Column("authority_type", sa.String(32), nullable=False),
        sa.Column("authority_reference", sa.String(160), nullable=False),
        sa.Column("evidence_reference", sa.String(100)),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("submitted_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_authorization_case"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_mortuary_authorization_hospital_id"),
        sa.CheckConstraint("authority_type IN ('next_of_kin_consent', 'court_order', 'coroner_directive', 'public_health_order', 'other_lawful_basis')", name="ck_mortuary_authority_type"),
        sa.CheckConstraint("status IN ('pending', 'verified', 'rejected', 'revoked')", name="ck_mortuary_authorization_status"),
        sa.CheckConstraint("(status = 'verified' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND evidence_reference IS NOT NULL) OR (status != 'verified' AND verified_by_user_id IS NULL AND verified_at IS NULL)", name="ck_mortuary_authorization_verification"),
        sa.CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_mortuary_authorization_evidence"),
    )
    op.create_index("ix_mortuary_authorization_case", "mortuary_authorizations", ["hospital_id", "mortuary_case_id", "status"])
    op.create_table(
        "mortuary_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("mortuary_case_id", sa.Uuid(), nullable=False),
        sa.Column("movement_type", sa.String(32), nullable=False),
        sa.Column("from_location", sa.String(180)),
        sa.Column("to_location", sa.String(180), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_movement_case"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_mortuary_movement_hospital_id"),
        sa.CheckConstraint("movement_type IN ('received', 'stored', 'relocated', 'release_pending', 'released', 'transferred', 'retained')", name="ck_mortuary_movement_type"),
        sa.CheckConstraint("length(trim(to_location)) >= 2", name="ck_mortuary_movement_location"),
    )
    op.create_index("ix_mortuary_movement_case_time", "mortuary_movements", ["hospital_id", "mortuary_case_id", "created_at"])
    op.create_table(
        "mortuary_property_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("mortuary_case_id", sa.Uuid(), nullable=False),
        sa.Column("property_description", sa.String(500), nullable=False),
        sa.Column("property_reference", sa.String(120)),
        sa.Column("sealed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(24), nullable=False, server_default="received"),
        sa.Column("released_to_name", sa.String(180)),
        sa.Column("released_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("received_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "mortuary_case_id"], ["mortuary_cases.hospital_id", "mortuary_cases.id"], name="fk_mortuary_property_case"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_mortuary_property_hospital_id"),
        sa.CheckConstraint("status IN ('received', 'sealed', 'released', 'retained')", name="ck_mortuary_property_status"),
        sa.CheckConstraint("(status = 'released' AND released_to_name IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL) OR (status != 'released' AND released_to_name IS NULL AND released_by_user_id IS NULL AND released_at IS NULL)", name="ck_mortuary_property_release_state"),
    )
    op.create_index("ix_mortuary_property_case", "mortuary_property_items", ["hospital_id", "mortuary_case_id", "status"])
    op.create_table(
        "pathology_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid()),
        sa.Column("case_number", sa.String(80), nullable=False),
        sa.Column("case_type", sa.String(24), nullable=False),
        sa.Column("clinical_indication", sa.Text(), nullable=False),
        sa.Column("order_reference", sa.String(160)),
        sa.Column("authority_type", sa.String(32)),
        sa.Column("authority_reference", sa.String(160)),
        sa.Column("authority_evidence_reference", sa.String(100)),
        sa.Column("authority_verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("authority_verified_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="opened"),
        sa.Column("assigned_pathologist_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("opened_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_pathology_case_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_pathology_case_encounter_patient"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_pathology_case_hospital_id"),
        sa.UniqueConstraint("hospital_id", "case_number", name="uq_pathology_case_number"),
        sa.CheckConstraint("case_type IN ('biopsy', 'surgical', 'autopsy', 'forensic')", name="ck_pathology_case_type"),
        sa.CheckConstraint("status IN ('opened', 'specimens_received', 'in_progress', 'report_draft', 'finalized', 'closed', 'cancelled')", name="ck_pathology_case_status"),
        sa.CheckConstraint("(case_type NOT IN ('autopsy', 'forensic')) OR (authority_type IS NOT NULL AND authority_reference IS NOT NULL)", name="ck_pathology_authority_required"),
        sa.CheckConstraint("authority_type IS NULL OR authority_type IN ('patient_consent', 'next_of_kin_consent', 'court_order', 'coroner_directive', 'public_health_order', 'other_lawful_basis')", name="ck_pathology_authority_type"),
        sa.CheckConstraint("(authority_verified_by_user_id IS NULL AND authority_verified_at IS NULL) OR (authority_verified_by_user_id IS NOT NULL AND authority_verified_at IS NOT NULL)", name="ck_pathology_authority_verification"),
        sa.CheckConstraint("authority_evidence_reference IS NULL OR authority_evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_pathology_authority_evidence"),
    )
    op.create_index("ix_pathology_case_queue", "pathology_cases", ["hospital_id", "status", "created_at"])
    op.create_table(
        "pathology_specimens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("pathology_case_id", sa.Uuid(), nullable=False),
        sa.Column("accession_number", sa.String(100), nullable=False),
        sa.Column("specimen_type", sa.String(120), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("specimen_condition", sa.String(24), nullable=False, server_default="acceptable"),
        sa.Column("status", sa.String(24), nullable=False, server_default="collected"),
        sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("received_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_specimen_case"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_pathology_specimen_hospital_id"),
        sa.UniqueConstraint("hospital_id", "accession_number", name="uq_pathology_specimen_accession"),
        sa.CheckConstraint("status IN ('collected', 'received', 'processing', 'processed', 'archived', 'rejected')", name="ck_pathology_specimen_status"),
        sa.CheckConstraint("specimen_condition IN ('acceptable', 'damaged', 'leaking', 'unlabelled', 'other')", name="ck_pathology_specimen_condition"),
        sa.CheckConstraint("status NOT IN ('received', 'processing', 'processed', 'archived') OR (received_at IS NOT NULL AND received_by_user_id IS NOT NULL)", name="ck_pathology_specimen_receipt_state"),
    )
    op.create_index("ix_pathology_specimen_case", "pathology_specimens", ["hospital_id", "pathology_case_id", "status"])
    op.create_table(
        "pathology_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("pathology_case_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("interpretation", sa.Text()),
        sa.Column("conclusion", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("authored_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("signed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("signed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_report_case"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_pathology_report_hospital_id"),
        sa.UniqueConstraint("hospital_id", "pathology_case_id", "version", name="uq_pathology_report_version"),
        sa.CheckConstraint("version >= 1", name="ck_pathology_report_version"),
        sa.CheckConstraint("status IN ('draft', 'final')", name="ck_pathology_report_status"),
        sa.CheckConstraint("(status = 'final' AND signed_by_user_id IS NOT NULL AND signed_at IS NOT NULL) OR (status = 'draft' AND signed_by_user_id IS NULL AND signed_at IS NULL)", name="ck_pathology_report_signing"),
    )
    op.create_index("ix_pathology_report_case", "pathology_reports", ["hospital_id", "pathology_case_id", "version"])
    op.create_table(
        "pathology_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("pathology_case_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("note", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "pathology_case_id"], ["pathology_cases.hospital_id", "pathology_cases.id"], name="fk_pathology_event_case"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_pathology_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('case_opened', 'authority_verified', 'specimen_added', 'specimen_received', 'specimen_status_changed', 'report_drafted', 'report_finalized', 'case_closed', 'case_cancelled')", name="ck_pathology_event_type"),
    )
    op.create_index("ix_pathology_event_case_time", "pathology_events", ["hospital_id", "pathology_case_id", "created_at"])
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))
    op.execute("""
        CREATE FUNCTION prevent_mortuary_movement_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'mortuary movement records are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_mortuary_movements_immutable BEFORE UPDATE OR DELETE ON mortuary_movements FOR EACH ROW EXECUTE FUNCTION prevent_mortuary_movement_mutation()")
    op.execute("""
        CREATE FUNCTION prevent_pathology_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'pathology events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_pathology_events_immutable BEFORE UPDATE OR DELETE ON pathology_events FOR EACH ROW EXECUTE FUNCTION prevent_pathology_event_mutation()")
    op.execute("""
        CREATE FUNCTION prevent_final_pathology_report_mutation() RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'final' THEN
                RAISE EXCEPTION 'final pathology reports are immutable; create a new version';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_pathology_reports_immutable BEFORE UPDATE OR DELETE ON pathology_reports FOR EACH ROW EXECUTE FUNCTION prevent_final_pathology_report_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_pathology_reports_immutable ON pathology_reports")
    op.execute("DROP FUNCTION IF EXISTS prevent_final_pathology_report_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_pathology_events_immutable ON pathology_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_pathology_event_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_mortuary_movements_immutable ON mortuary_movements")
    op.execute("DROP FUNCTION IF EXISTS prevent_mortuary_movement_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
