"""Add governed clinical knowledge review and publication controls."""

from alembic import op
import sqlalchemy as sa

revision = "0006_knowledge_review_publication"
down_revision = "0005_knowledge_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_staged_knowledge_status", "staged_knowledge_documents", type_="check")
    op.create_check_constraint(
        "ck_staged_knowledge_status",
        "staged_knowledge_documents",
        "status IN ('staged', 'duplicate', 'invalid', 'pending_review', 'approved', 'rejected', 'promoted')",
    )

    op.create_table(
        "clinical_knowledge_reviewer_authorizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=True),
        sa.Column("professional_registration", sa.String(160), nullable=False),
        sa.Column("credential_type", sa.String(100), nullable=False),
        sa.Column("credential_reference", sa.String(500), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'active', 'suspended', 'revoked')", name="ck_knowledge_reviewer_auth_status"),
        sa.CheckConstraint("(scope = 'global' AND hospital_id IS NULL) OR (scope = 'hospital' AND hospital_id IS NOT NULL)", name="ck_knowledge_reviewer_auth_scope"),
        sa.CheckConstraint("verified_by_user_id <> user_id", name="ck_knowledge_reviewer_verified_by_other"),
    )
    op.create_index("ix_knowledge_reviewer_auth_user_scope", "clinical_knowledge_reviewer_authorizations", ["user_id", "scope", "hospital_id"])

    op.create_table(
        "knowledge_review_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("staged_document_id", sa.Uuid(), sa.ForeignKey("staged_knowledge_documents.id"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewer_authorization_id", sa.Uuid(), sa.ForeignKey("clinical_knowledge_reviewer_authorizations.id"), nullable=True),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("decision IN ('submitted', 'approved', 'rejected', 'published', 'superseded')", name="ck_knowledge_review_event_decision"),
    )
    op.create_index("ix_knowledge_review_events_staged_document_id", "knowledge_review_events", ["staged_document_id"])
    op.create_index("ix_knowledge_review_event_document_time", "knowledge_review_events", ["staged_document_id", "occurred_at"])

    op.create_unique_constraint(
        "uq_knowledge_document_source_version",
        "medical_knowledge_documents",
        ["source_id", "version"],
    )
    op.execute("""
        CREATE FUNCTION prevent_knowledge_review_event_mutation()
        RETURNS trigger AS $fn$
        BEGIN
            RAISE EXCEPTION 'knowledge review events are append-only';
        END;
        $fn$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER knowledge_review_events_append_only
        BEFORE UPDATE OR DELETE ON knowledge_review_events
        FOR EACH ROW EXECUTE FUNCTION prevent_knowledge_review_event_mutation()
    """)

    # Credential grants are managed by a trusted platform process, never ordinary tenant users.
    op.execute("ALTER TABLE clinical_knowledge_reviewer_authorizations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clinical_knowledge_reviewer_authorizations FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY knowledge_reviewer_auth_read ON clinical_knowledge_reviewer_authorizations
        FOR SELECT USING (
            (scope = 'global' AND current_setting('app.platform_knowledge_admin', true) = 'true')
            OR (scope = 'hospital' AND hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
        )
    """)

    op.execute("ALTER TABLE knowledge_review_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE knowledge_review_events FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY knowledge_review_events_tenant_read ON knowledge_review_events
        FOR SELECT USING (EXISTS (
            SELECT 1 FROM staged_knowledge_documents d
            JOIN knowledge_import_batches b ON b.id = d.batch_id
            WHERE d.id = staged_document_id AND
              (b.scope = 'global' OR b.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
        ))
    """)
    op.execute("""
        CREATE POLICY knowledge_review_events_tenant_insert ON knowledge_review_events
        FOR INSERT WITH CHECK (
            actor_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            AND EXISTS (
                SELECT 1 FROM staged_knowledge_documents d
                JOIN knowledge_import_batches b ON b.id = d.batch_id
                WHERE d.id = staged_document_id AND b.scope = 'hospital'
                  AND b.hospital_id =
                    NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        )
    """)
    # No UPDATE or DELETE policies: review history is append-only for tenant roles.


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS knowledge_review_events_tenant_insert ON knowledge_review_events")
    op.execute("DROP POLICY IF EXISTS knowledge_review_events_tenant_read ON knowledge_review_events")
    op.execute("DROP POLICY IF EXISTS knowledge_reviewer_auth_read ON clinical_knowledge_reviewer_authorizations")
    op.execute("DROP TRIGGER IF EXISTS knowledge_review_events_append_only ON knowledge_review_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_knowledge_review_event_mutation()")
    op.drop_constraint("uq_knowledge_document_source_version", "medical_knowledge_documents", type_="unique")
    op.drop_index("ix_knowledge_review_event_document_time", table_name="knowledge_review_events")
    op.drop_index("ix_knowledge_review_events_staged_document_id", table_name="knowledge_review_events")
    op.drop_table("knowledge_review_events")
    op.drop_index("ix_knowledge_reviewer_auth_user_scope", table_name="clinical_knowledge_reviewer_authorizations")
    op.drop_table("clinical_knowledge_reviewer_authorizations")
    op.drop_constraint("ck_staged_knowledge_status", "staged_knowledge_documents", type_="check")
    op.create_check_constraint(
        "ck_staged_knowledge_status",
        "staged_knowledge_documents",
        "status IN ('staged', 'duplicate', 'invalid', 'pending_review', 'rejected', 'promoted')",
    )
