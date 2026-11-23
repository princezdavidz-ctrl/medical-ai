"""Add governed, tenant-aware medical knowledge registry and chunks."""

from alembic import op
import sqlalchemy as sa

revision = "0003_medical_knowledge"
down_revision = "0002_hospital_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "medical_knowledge_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("publisher", sa.String(240), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("license_name", sa.String(160), nullable=True),
        sa.Column("license_reference", sa.String(240), nullable=True),
        sa.Column("jurisdiction", sa.String(80), nullable=False),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('global', 'hospital')", name="ck_knowledge_source_scope"),
        sa.CheckConstraint("(scope = 'global' AND hospital_id IS NULL) OR (scope = 'hospital' AND hospital_id IS NOT NULL)", name="ck_knowledge_source_scope_owner"),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_knowledge_source_status"),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medical_knowledge_sources_hospital_id", "medical_knowledge_sources", ["hospital_id"])
    op.create_index("ix_knowledge_source_scope_hospital", "medical_knowledge_sources", ["scope", "hospital_id"])

    op.create_table(
        "medical_knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("clinical_domain", sa.String(100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidence_grade", sa.String(40), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_document_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'pending_review', 'approved', 'rejected', 'superseded', 'archived')", name="ck_knowledge_document_status"),
        sa.ForeignKeyConstraint(["source_id"], ["medical_knowledge_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["supersedes_document_id"], ["medical_knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_medical_knowledge_documents_source_id", "medical_knowledge_documents", ["source_id"])
    op.create_index("ix_knowledge_document_source_status", "medical_knowledge_documents", ["source_id", "status"])
    op.create_index("ix_knowledge_document_review_dates", "medical_knowledge_documents", ["status", "effective_from", "effective_to"])

    op.create_table(
        "medical_knowledge_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["medical_knowledge_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "sequence", name="uq_knowledge_chunk_document_sequence"),
    )
    op.create_index("ix_knowledge_chunk_document", "medical_knowledge_chunks", ["document_id"])

    for table in ("medical_knowledge_sources", "medical_knowledge_documents", "medical_knowledge_chunks"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY knowledge_source_read ON medical_knowledge_sources
        FOR SELECT USING (scope = 'global' OR hospital_id =
            NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
    """)
    op.execute("""
        CREATE POLICY knowledge_source_hospital_write ON medical_knowledge_sources
        FOR ALL USING (scope = 'hospital' AND hospital_id =
            NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
        WITH CHECK (scope = 'hospital' AND hospital_id =
            NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
    """)
    op.execute("""
        CREATE POLICY knowledge_document_read ON medical_knowledge_documents
        FOR SELECT USING (EXISTS (
            SELECT 1 FROM medical_knowledge_sources s WHERE s.id = source_id AND (
                s.scope = 'global' OR s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        ))
    """)
    op.execute("""
        CREATE POLICY knowledge_document_hospital_write ON medical_knowledge_documents
        FOR ALL USING (EXISTS (
            SELECT 1 FROM medical_knowledge_sources s
            WHERE s.id = source_id AND s.scope = 'hospital' AND s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM medical_knowledge_sources s
            WHERE s.id = source_id AND s.scope = 'hospital' AND s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
    """)
    op.execute("""
        CREATE POLICY knowledge_chunk_read ON medical_knowledge_chunks
        FOR SELECT USING (EXISTS (
            SELECT 1 FROM medical_knowledge_documents d
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE d.id = document_id AND (
                s.scope = 'global' OR s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        ))
    """)
    op.execute("""
        CREATE POLICY knowledge_chunk_hospital_write ON medical_knowledge_chunks
        FOR ALL USING (EXISTS (
            SELECT 1 FROM medical_knowledge_documents d
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE d.id = document_id AND s.scope = 'hospital' AND s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
        WITH CHECK (EXISTS (
            SELECT 1 FROM medical_knowledge_documents d
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE d.id = document_id AND s.scope = 'hospital' AND s.hospital_id =
                NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
    """)


def downgrade() -> None:
    for table, policies in (
        ("medical_knowledge_chunks", ("knowledge_chunk_read", "knowledge_chunk_hospital_write")),
        ("medical_knowledge_documents", ("knowledge_document_read", "knowledge_document_hospital_write")),
        ("medical_knowledge_sources", ("knowledge_source_read", "knowledge_source_hospital_write")),
    ):
        for policy in policies:
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_knowledge_chunk_document", table_name="medical_knowledge_chunks")
    op.drop_table("medical_knowledge_chunks")
    op.drop_index("ix_knowledge_document_review_dates", table_name="medical_knowledge_documents")
    op.drop_index("ix_knowledge_document_source_status", table_name="medical_knowledge_documents")
    op.drop_index("ix_medical_knowledge_documents_source_id", table_name="medical_knowledge_documents")
    op.drop_table("medical_knowledge_documents")
    op.drop_index("ix_knowledge_source_scope_hospital", table_name="medical_knowledge_sources")
    op.drop_index("ix_medical_knowledge_sources_hospital_id", table_name="medical_knowledge_sources")
    op.drop_table("medical_knowledge_sources")
