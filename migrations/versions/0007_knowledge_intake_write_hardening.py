"""Restrict tenant knowledge writes to untrusted proposal intake only."""

from alembic import op

revision = "0007_knowledge_intake_write_hardening"
down_revision = "0006_knowledge_review_publication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A tenant must never be able to self-verify a license, approve or publish content.
    op.execute("DROP POLICY knowledge_import_batches_hospital_write ON knowledge_import_batches")
    op.execute("""
        CREATE POLICY knowledge_import_batches_tenant_insert
        ON knowledge_import_batches FOR INSERT
        WITH CHECK (
            scope = 'hospital'
            AND hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            AND submitted_by_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            AND status = 'received' AND license_verified = false
        )
    """)

    op.execute("DROP POLICY staged_knowledge_hospital_write ON staged_knowledge_documents")
    op.execute("""
        CREATE POLICY staged_knowledge_tenant_insert
        ON staged_knowledge_documents FOR INSERT
        WITH CHECK (
            status = 'staged' AND duplicate_of_document_id IS NULL
            AND EXISTS (
                SELECT 1 FROM knowledge_import_batches b
                WHERE b.id = batch_id AND b.scope = 'hospital'
                  AND b.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
                  AND b.submitted_by_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            )
        )
    """)

    op.execute("DROP POLICY terminology_mappings_hospital_write ON terminology_mappings")
    op.execute("""
        CREATE POLICY terminology_mappings_tenant_proposal_insert
        ON terminology_mappings FOR INSERT
        WITH CHECK (
            status = 'proposed' AND license_verified = false
            AND verified_by_user_id IS NULL AND verified_at IS NULL
            AND EXISTS (
                SELECT 1 FROM clinical_concepts c
                JOIN medical_knowledge_documents d ON d.id = c.document_id
                JOIN medical_knowledge_sources s ON s.id = d.source_id
                WHERE c.id = concept_id AND s.scope = 'hospital'
                  AND s.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        )
    """)

    op.execute("DROP POLICY knowledge_review_events_tenant_insert ON knowledge_review_events")
    op.execute("""
        CREATE POLICY knowledge_review_events_tenant_submit
        ON knowledge_review_events FOR INSERT
        WITH CHECK (
            decision = 'submitted'
            AND actor_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            AND reviewer_authorization_id IS NULL
            AND EXISTS (
                SELECT 1 FROM staged_knowledge_documents d
                JOIN knowledge_import_batches b ON b.id = d.batch_id
                WHERE d.id = staged_document_id AND b.scope = 'hospital'
                  AND b.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
                  AND b.submitted_by_user_id = actor_user_id
            )
        )
    """)


def downgrade() -> None:
    # Restore the previous broad policies only for schema rollback compatibility.
    op.execute("DROP POLICY IF EXISTS knowledge_review_events_tenant_submit ON knowledge_review_events")
    op.execute("""
        CREATE POLICY knowledge_review_events_tenant_insert ON knowledge_review_events
        FOR INSERT WITH CHECK (
            actor_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            AND EXISTS (
                SELECT 1 FROM staged_knowledge_documents d
                JOIN knowledge_import_batches b ON b.id = d.batch_id
                WHERE d.id = staged_document_id AND b.scope = 'hospital'
                  AND b.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
        )
    """)
    op.execute("DROP POLICY IF EXISTS terminology_mappings_tenant_proposal_insert ON terminology_mappings")
    op.execute("""
        CREATE POLICY terminology_mappings_hospital_write ON terminology_mappings
        FOR ALL USING (EXISTS (
            SELECT 1 FROM clinical_concepts c
            JOIN medical_knowledge_documents d ON d.id = c.document_id
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE c.id = concept_id AND s.scope = 'hospital'
              AND s.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        )) WITH CHECK (EXISTS (
            SELECT 1 FROM clinical_concepts c
            JOIN medical_knowledge_documents d ON d.id = c.document_id
            JOIN medical_knowledge_sources s ON s.id = d.source_id
            WHERE c.id = concept_id AND s.scope = 'hospital'
              AND s.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
    """)
    op.execute("DROP POLICY IF EXISTS staged_knowledge_tenant_insert ON staged_knowledge_documents")
    op.execute("""
        CREATE POLICY staged_knowledge_hospital_write ON staged_knowledge_documents
        FOR ALL USING (EXISTS (
            SELECT 1 FROM knowledge_import_batches b
            WHERE b.id = batch_id AND b.scope = 'hospital'
              AND b.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        )) WITH CHECK (EXISTS (
            SELECT 1 FROM knowledge_import_batches b
            WHERE b.id = batch_id AND b.scope = 'hospital'
              AND b.hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
        ))
    """)
    op.execute("DROP POLICY IF EXISTS knowledge_import_batches_tenant_insert ON knowledge_import_batches")
    op.execute("""
        CREATE POLICY knowledge_import_batches_hospital_write ON knowledge_import_batches
        FOR ALL USING (scope = 'hospital' AND hospital_id =
            NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
        WITH CHECK (scope = 'hospital' AND hospital_id =
            NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)
    """)
