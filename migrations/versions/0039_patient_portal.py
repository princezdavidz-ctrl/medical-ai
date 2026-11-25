"""Create verified patient portal links and scoped patient self-service access."""
from alembic import op
import sqlalchemy as sa

revision = "0039_patient_portal"
down_revision = "0038_hospital_admin_console"
branch_labels = None
depends_on = None

TABLES = ("patient_portal_links", "patient_portal_access_events")


def upgrade() -> None:
    op.create_table(
        "patient_portal_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("portal_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("relationship_type", sa.String(24), nullable=False, server_default="self"),
        sa.Column("access_scope", sa.JSON(), nullable=False, server_default=sa.text("""'["profile","encounters"]'::json""")),
        sa.Column("authority_reference", sa.String(160)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("verification_method", sa.String(32)),
        sa.Column("evidence_reference", sa.String(100)),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revocation_reason", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_patient_portal_link_patient"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_patient_portal_link_hospital_patient"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", "portal_user_id", name="uq_patient_portal_link_event_owner"),
        
        sa.CheckConstraint("relationship_type IN ('self', 'parent_guardian', 'caregiver', 'legal_representative')", name="ck_patient_portal_relationship"),
        sa.CheckConstraint("status IN ('pending', 'active', 'revoked')", name="ck_patient_portal_link_status"),
        sa.CheckConstraint("json_typeof(access_scope) = 'array'", name="ck_patient_portal_access_scope_array"),
        sa.CheckConstraint("relationship_type = 'self' OR (authority_reference IS NOT NULL AND expires_at IS NOT NULL)", name="ck_patient_portal_proxy_authority"),
        sa.CheckConstraint("(status = 'active' AND verification_method IS NOT NULL AND evidence_reference IS NOT NULL AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL) OR (status != 'active' AND verified_by_user_id IS NULL AND verified_at IS NULL)", name="ck_patient_portal_verification_state"),
        sa.CheckConstraint("verification_method IS NULL OR verification_method IN ('in_person', 'identity_document', 'verified_email', 'verified_phone', 'guardian_document', 'court_order')", name="ck_patient_portal_verification_method"),
        sa.CheckConstraint("evidence_reference IS NULL OR evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_patient_portal_evidence_reference"),
        sa.CheckConstraint("(status = 'revoked' AND revoked_by_user_id IS NOT NULL AND revoked_at IS NOT NULL AND revocation_reason IS NOT NULL) OR (status != 'revoked' AND revoked_by_user_id IS NULL AND revoked_at IS NULL AND revocation_reason IS NULL)", name="ck_patient_portal_revocation_state"),
    )
    op.create_index("uq_patient_portal_link_open", "patient_portal_links", ["hospital_id", "patient_id", "portal_user_id"], unique=True, postgresql_where=sa.text("status IN ('pending', 'active')"))
    op.create_index("ix_patient_portal_user_status", "patient_portal_links", ["hospital_id", "portal_user_id", "status"])
    op.create_index("ix_patient_portal_patient_status", "patient_portal_links", ["hospital_id", "patient_id", "status"])
    op.create_table(
        "patient_portal_access_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("portal_link_id", sa.Uuid(), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("portal_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("resource_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "portal_link_id", "patient_id", "portal_user_id"], ["patient_portal_links.hospital_id", "patient_portal_links.id", "patient_portal_links.patient_id", "patient_portal_links.portal_user_id"], name="fk_patient_portal_event_link"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_patient_portal_event_hospital_id"),
        sa.CheckConstraint("action IN ('viewed_profile', 'viewed_encounters', 'viewed_lab_results', 'viewed_medications', 'viewed_invoices', 'viewed_consents')", name="ck_patient_portal_event_action"),
        sa.CheckConstraint("resource_count >= 0", name="ck_patient_portal_event_resource_count"),
    )
    op.create_index("ix_patient_portal_access_history", "patient_portal_access_events", ["hospital_id", "patient_id", "created_at"])
    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))
    op.execute("""
        CREATE FUNCTION prevent_patient_portal_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'patient portal access events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_patient_portal_events_immutable BEFORE UPDATE OR DELETE ON patient_portal_access_events FOR EACH ROW EXECUTE FUNCTION prevent_patient_portal_event_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_patient_portal_events_immutable ON patient_portal_access_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_patient_portal_event_mutation()")
    op.drop_index("uq_patient_portal_link_open", table_name="patient_portal_links")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
