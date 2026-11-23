"""Add quarantined knowledge imports and license-aware terminology mappings."""

from alembic import op
import sqlalchemy as sa

revision = "0005_knowledge_ingestion"
down_revision = "0004_clinical_taxonomy"
branch_labels = None
depends_on = None


def _enable_rls(table: str, select_policy: str, write_policy: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(select_policy)
    op.execute(write_policy)


def upgrade() -> None:
    op.create_table(
        "knowledge_import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=True),
        sa.Column("submitted_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_identity", sa.String(240), nullable=False),
        sa.Column("declared_license", sa.String(160), nullable=True),
        sa.Column("license_reference", sa.String(500), nullable=True),
        sa.Column("license_verified", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("validation_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("scope IN ('global', 'hospital')", name="ck_knowledge_import_scope"),
        sa.CheckConstraint("(scope = 'global' AND hospital_id IS NULL) OR (scope = 'hospital' AND hospital_id IS NOT NULL)", name="ck_knowledge_import_scope_owner"),
        sa.CheckConstraint("status IN ('received', 'validating', 'needs_review', 'rejected', 'closed')", name="ck_knowledge_import_status"),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.id"]),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["medical_knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_import_batches_hospital_id", "knowledge_import_batches", ["hospital_id"])
    op.create_index("ix_knowledge_import_scope_hospital", "knowledge_import_batches", ["scope", "hospital_id"])

    op.create_table(
        "staged_knowledge_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_identity", sa.String(240), nullable=False),
        sa.Column("external_document_id", sa.String(240), nullable=True),
        sa.Column("external_version", sa.String(80), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("jurisdiction", sa.String(80), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("payload_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("duplicate_of_document_id", sa.Uuid(), nullable=True),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('staged', 'duplicate', 'invalid', 'pending_review', 'rejected', 'promoted')", name="ck_staged_knowledge_status"),
        sa.ForeignKeyConstraint(["batch_id"], ["knowledge_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["duplicate_of_document_id"], ["medical_knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "content_sha256", name="uq_staged_batch_content_hash"),
    )
    op.create_index("ix_staged_knowledge_documents_batch_id", "staged_knowledge_documents", ["batch_id"])
    op.create_index("ix_staged_knowledge_hash", "staged_knowledge_documents", ["content_sha256"])
    op.create_index("ix_staged_knowledge_source_version", "staged_knowledge_documents", ["source_identity", "external_version"])

    op.create_table(
        "terminology_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("concept_id", sa.Uuid(), nullable=False),
        sa.Column("code_system", sa.String(24), nullable=False),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("release_version", sa.String(80), nullable=False),
        sa.Column("jurisdiction", sa.String(80), nullable=False),
        sa.Column("license_reference", sa.String(500), nullable=True),
        sa.Column("license_verified", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("code_system IN ('ICD-10', 'SNOMED-CT', 'LOINC', 'LOCAL', 'OTHER')", name="ck_terminology_mapping_system"),
        sa.CheckConstraint("status IN ('proposed', 'verified', 'rejected', 'retired')", name="ck_terminology_mapping_status"),
        sa.ForeignKeyConstraint(["concept_id"], ["clinical_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("concept_id", "code_system", "code", "release_version", name="uq_terminology_mapping_release_code"),
    )
    op.create_index("ix_terminology_mapping_lookup", "terminology_mappings", ["code_system", "code"])

    op.create_table(
        "laboratory_unit_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_unit", sa.String(80), nullable=False),
        sa.Column("canonical_unit", sa.String(80), nullable=False),
        sa.Column("specimen", sa.String(100), nullable=True),
        sa.Column("method", sa.String(160), nullable=True),
        sa.Column("conversion_factor", sa.Numeric(24, 12), nullable=True),
        sa.Column("conversion_offset", sa.Numeric(24, 12), nullable=True),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('proposed', 'verified', 'rejected', 'retired')", name="ck_lab_unit_mapping_status"),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_unit", "canonical_unit", "specimen", "method", name="uq_lab_unit_mapping_context"),
    )

    _enable_rls(
        "knowledge_import_batches",
        """CREATE POLICY knowledge_import_batches_tenant_read ON knowledge_import_batches
        FOR SELECT USING (scope = 'global' OR hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)""",
        """CREATE POLICY knowledge_import_batches_hospital_write ON knowledge_import_batches
        FOR ALL USING (scope = 'hospital' AND hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
        WITH CHECK (scope = 'hospital' AND hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)""",
    )
    _enable_rls(
        "staged_knowledge_documents",
        """CREATE POLICY staged_knowledge_tenant_read ON staged_knowledge_documents
        FOR SELECT USING (EXISTS (SELECT 1 FROM knowledge_import_batches b
        WHERE b.id = batch_id AND (b.scope = 'global' OR b.hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)))""",
        """CREATE POLICY staged_knowledge_hospital_write ON staged_knowledge_documents
        FOR ALL USING (EXISTS (SELECT 1 FROM knowledge_import_batches b
        WHERE b.id = batch_id AND b.scope = 'hospital' AND b.hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid))
        WITH CHECK (EXISTS (SELECT 1 FROM knowledge_import_batches b
        WHERE b.id = batch_id AND b.scope = 'hospital' AND b.hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid))""",
    )
    _enable_rls(
        "terminology_mappings",
        """CREATE POLICY terminology_mappings_tenant_read ON terminology_mappings
        FOR SELECT USING (EXISTS (SELECT 1 FROM clinical_concepts c
        JOIN medical_knowledge_documents d ON d.id = c.document_id
        JOIN medical_knowledge_sources s ON s.id = d.source_id
        WHERE c.id = concept_id AND (s.scope = 'global' OR s.hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)))""",
        """CREATE POLICY terminology_mappings_hospital_write ON terminology_mappings
        FOR ALL USING (EXISTS (SELECT 1 FROM clinical_concepts c
        JOIN medical_knowledge_documents d ON d.id = c.document_id
        JOIN medical_knowledge_sources s ON s.id = d.source_id
        WHERE c.id = concept_id AND s.scope = 'hospital' AND s.hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid))
        WITH CHECK (EXISTS (SELECT 1 FROM clinical_concepts c
        JOIN medical_knowledge_documents d ON d.id = c.document_id
        JOIN medical_knowledge_sources s ON s.id = d.source_id
        WHERE c.id = concept_id AND s.scope = 'hospital' AND s.hospital_id =
        NULLIF(current_setting('app.current_hospital_id', true), '')::uuid))""",
    )

    op.execute("ALTER TABLE laboratory_unit_mappings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE laboratory_unit_mappings FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY laboratory_unit_mappings_read ON laboratory_unit_mappings FOR SELECT USING (true)")


def downgrade() -> None:
    for table in ("knowledge_import_batches", "staged_knowledge_documents", "terminology_mappings", "laboratory_unit_mappings"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_read ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_hospital_write ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_read ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_terminology_mapping_lookup", table_name="terminology_mappings")
    op.drop_table("terminology_mappings")
    op.drop_table("laboratory_unit_mappings")
    op.drop_index("ix_staged_knowledge_source_version", table_name="staged_knowledge_documents")
    op.drop_index("ix_staged_knowledge_hash", table_name="staged_knowledge_documents")
    op.drop_index("ix_staged_knowledge_documents_batch_id", table_name="staged_knowledge_documents")
    op.drop_table("staged_knowledge_documents")
    op.drop_index("ix_knowledge_import_scope_hospital", table_name="knowledge_import_batches")
    op.drop_index("ix_knowledge_import_batches_hospital_id", table_name="knowledge_import_batches")
    op.drop_table("knowledge_import_batches")
