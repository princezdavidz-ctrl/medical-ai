"""Create medical record index, release requests and amendment workflows."""
from alembic import op
import sqlalchemy as sa

revision = "0042_patient_records"
down_revision = "0041_staff_scheduling"
branch_labels = None
depends_on = None

TABLES = (
    "patient_record_documents",
    "patient_record_release_requests",
    "patient_record_amendment_requests",
    "patient_record_events",
)


def upgrade() -> None:
    op.create_table(
        "patient_record_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid()),
        sa.Column("source_module", sa.String(24), nullable=False),
        sa.Column("source_record_id", sa.Uuid()),
        sa.Column("record_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("document_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mime_type", sa.String(80), nullable=False),
        sa.Column("vault_reference", sa.String(80), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_document_id", sa.Uuid()),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending_review"),
        sa.Column("rejection_reason", sa.String(1000)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_record_document_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "encounter_id", "patient_id"], ["encounters.hospital_id", "encounters.id", "encounters.patient_id"], name="fk_record_document_encounter_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "supersedes_document_id", "patient_id"], ["patient_record_documents.hospital_id", "patient_record_documents.id", "patient_record_documents.patient_id"], name="fk_record_document_supersedes"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_record_document_hospital_id_patient"),
        sa.UniqueConstraint("hospital_id", "vault_reference", name="uq_record_document_vault_reference"),
 
        sa.CheckConstraint("source_module IN ('opd', 'nursing', 'inpatient', 'emergency', 'icu', 'surgery', 'maternity', 'pediatrics', 'laboratory', 'radiology', 'pharmacy', 'billing', 'insurance', 'external', 'other')", name="ck_record_document_source"),
        sa.CheckConstraint("record_type IN ('clinical_note', 'discharge_summary', 'lab_report', 'imaging_report', 'prescription', 'referral', 'consent', 'identity_document', 'administrative', 'external_record', 'other')", name="ck_record_document_type"),
        sa.CheckConstraint("status IN ('pending_review', 'verified', 'rejected', 'superseded')", name="ck_record_document_status"),
        sa.CheckConstraint("version_number >= 1", name="ck_record_document_version"),
        sa.CheckConstraint("length(trim(title)) >= 2", name="ck_record_document_title"),
        sa.CheckConstraint("vault_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_document_vault_ref"),
        sa.CheckConstraint("sha256_checksum ~ '^[0-9a-fA-F]{64}$'", name="ck_record_document_checksum"),
        sa.CheckConstraint("mime_type IN ('application/pdf', 'image/jpeg', 'image/png', 'application/dicom', 'text/plain', 'application/octet-stream')", name="ck_record_document_mime"),
        sa.CheckConstraint("(status = 'pending_review' AND verified_by_user_id IS NULL AND verified_at IS NULL AND rejection_reason IS NULL) OR (status = 'verified' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND rejection_reason IS NULL) OR (status = 'rejected' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND rejection_reason IS NOT NULL) OR (status = 'superseded' AND verified_by_user_id IS NOT NULL AND verified_at IS NOT NULL AND rejection_reason IS NULL)", name="ck_record_document_review_state"),
        sa.CheckConstraint("supersedes_document_id IS NULL OR supersedes_document_id != id", name="ck_record_document_no_self_supersede"),
    )
    op.create_index("uq_record_document_source_version_active", "patient_record_documents", ["hospital_id", "patient_id", "source_module", "source_record_id", "version_number"], unique=True, postgresql_where=sa.text("status IN ('pending_review', 'verified', 'superseded')"))
    op.create_index("ix_record_document_patient_date", "patient_record_documents", ["hospital_id", "patient_id", "document_date"])
    op.create_index("ix_record_document_patient_type", "patient_record_documents", ["hospital_id", "patient_id", "record_type", "status"])
    op.create_index("ix_record_document_encounter", "patient_record_documents", ["hospital_id", "encounter_id"])

    op.create_table(
        "patient_record_release_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("consent_id", sa.Uuid(), nullable=False),
        sa.Column("requester_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requester_type", sa.String(32), nullable=False),
        sa.Column("requester_name", sa.String(180), nullable=False),
        sa.Column("requester_evidence_reference", sa.String(80)),
        sa.Column("recipient_name", sa.String(180), nullable=False),
        sa.Column("recipient_type", sa.String(32), nullable=False),
        sa.Column("recipient_contact", sa.String(320)),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("data_categories", sa.JSON(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("request_reason", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("decision_reason", sa.String(1000)),
        sa.Column("released_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("release_vault_reference", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_record_release_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "consent_id", "patient_id"], ["patient_consents.hospital_id", "patient_consents.id", "patient_consents.patient_id"], name="fk_record_release_consent"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_record_release_hospital_id_patient"),
        sa.CheckConstraint("requester_type IN ('treating_provider', 'insurer', 'court', 'regulator', 'other')", name="ck_record_release_requester_type"),
        sa.CheckConstraint("recipient_type IN ('hospital', 'clinic', 'provider', 'insurer', 'patient', 'court', 'regulator', 'other')", name="ck_record_release_recipient_type"),
        sa.CheckConstraint("requester_evidence_reference IS NULL OR requester_evidence_reference ~ '^vault://[0-9a-fA-F-]{36}
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'released', 'cancelled')", name="ck_record_release_status"),
        sa.CheckConstraint("purpose IN ('record_sharing', 'care_coordination', 'referral', 'patient_portal', 'insurance_claim', 'legal_requirement', 'other')", name="ck_record_release_purpose"),
        sa.CheckConstraint("json_typeof(data_categories) = 'array' AND json_array_length(data_categories) > 0", name="ck_record_release_categories"),
        sa.CheckConstraint("period_end IS NULL OR period_start IS NULL OR period_end >= period_start", name="ck_record_release_period"),
        sa.CheckConstraint("length(trim(recipient_name)) >= 2 AND length(trim(request_reason)) >= 5", name="ck_record_release_text"),
        sa.CheckConstraint("(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND decision_reason IS NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'approved' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'rejected' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NOT NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'released' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL AND release_vault_reference IS NOT NULL) OR (status = 'cancelled' AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL)", name="ck_record_release_state"),
        sa.CheckConstraint("release_vault_reference IS NULL OR release_vault_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_release_vault_ref"),
    )
    op.create_index("ix_record_release_patient_status", "patient_record_release_requests", ["hospital_id", "patient_id", "status", "created_at"])
    op.create_index("ix_record_release_review_queue", "patient_record_release_requests", ["hospital_id", "status", "created_at"])

    op.create_table(
        "patient_record_amendment_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid()),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amendment_type", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("supporting_evidence_reference", sa.String(80)),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("decision_reason", sa.String(1000)),
        sa.Column("fulfilled_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True)),
        sa.Column("amendment_vault_reference", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_record_amendment_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "document_id", "patient_id"], ["patient_record_documents.hospital_id", "patient_record_documents.id", "patient_record_documents.patient_id"], name="fk_record_amendment_document"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_record_amendment_hospital_id_patient"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'fulfilled', 'cancelled')", name="ck_record_amendment_status"),
        sa.CheckConstraint("amendment_type IN ('demographic', 'clinical_content', 'metadata', 'identity')", name="ck_record_amendment_type"),
        sa.CheckConstraint("length(trim(reason)) >= 5", name="ck_record_amendment_reason"),
        sa.CheckConstraint("(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND decision_reason IS NULL AND amendment_vault_reference IS NULL) OR (status = 'approved' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NULL AND amendment_vault_reference IS NULL) OR (status = 'rejected' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NOT NULL AND amendment_vault_reference IS NULL) OR (status = 'fulfilled' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND fulfilled_by_user_id IS NOT NULL AND fulfilled_at IS NOT NULL AND amendment_vault_reference IS NOT NULL) OR (status = 'cancelled' AND amendment_vault_reference IS NULL)", name="ck_record_amendment_state"),
        sa.CheckConstraint("amendment_vault_reference IS NULL OR amendment_vault_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_amendment_vault_ref"),
        sa.CheckConstraint("supporting_evidence_reference IS NULL OR supporting_evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_amendment_evidence_ref"),
    )
    op.create_index("ix_record_amendment_patient_status", "patient_record_amendment_requests", ["hospital_id", "patient_id", "status", "created_at"])

    op.create_table(
        "patient_record_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(48), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_patient_record_event_patient"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_patient_record_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('document_registered', 'document_verified', 'document_rejected', 'document_superseded', 'release_requested', 'release_approved', 'release_rejected', 'release_cancelled', 'records_released', 'amendment_requested', 'amendment_approved', 'amendment_rejected', 'amendment_fulfilled', 'amendment_cancelled')", name="ck_patient_record_event_type"),
    )
    op.create_index("ix_patient_record_event_history", "patient_record_events", ["hospital_id", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_patient_record_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'patient record events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_patient_record_events_immutable BEFORE UPDATE OR DELETE ON patient_record_events FOR EACH ROW EXECUTE FUNCTION prevent_patient_record_event_mutation()")
    op.execute("""
        CREATE FUNCTION guard_patient_record_document_mutation() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'patient record documents cannot be deleted';
            END IF;
            IF OLD.status = 'pending_review' AND NEW.status IN ('verified', 'rejected') THEN
                IF (to_jsonb(NEW) - ARRAY['status', 'verified_by_user_id', 'verified_at', 'rejection_reason'])
                   IS DISTINCT FROM
                   (to_jsonb(OLD) - ARRAY['status', 'verified_by_user_id', 'verified_at', 'rejection_reason']) THEN
                    RAISE EXCEPTION 'record document content is immutable after registration';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.status = 'verified' AND NEW.status = 'superseded' THEN
                IF (to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status') THEN
                    RAISE EXCEPTION 'verified record document content is immutable';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'invalid patient record document mutation';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_patient_record_documents_immutable BEFORE UPDATE OR DELETE ON patient_record_documents FOR EACH ROW EXECUTE FUNCTION guard_patient_record_document_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_patient_record_documents_immutable ON patient_record_documents")
    op.execute("DROP FUNCTION IF EXISTS guard_patient_record_document_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_patient_record_events_immutable ON patient_record_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_patient_record_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
", name="ck_record_release_requester_evidence_ref"),
        sa.CheckConstraint("requester_type = 'treating_provider' OR requester_evidence_reference IS NOT NULL", name="ck_record_release_external_requester_evidence_required"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'released', 'cancelled')", name="ck_record_release_status"),
        sa.CheckConstraint("purpose IN ('record_sharing', 'care_coordination', 'referral', 'patient_portal', 'insurance_claim', 'legal_requirement', 'other')", name="ck_record_release_purpose"),
        sa.CheckConstraint("json_typeof(data_categories) = 'array' AND json_array_length(data_categories) > 0", name="ck_record_release_categories"),
        sa.CheckConstraint("period_end IS NULL OR period_start IS NULL OR period_end >= period_start", name="ck_record_release_period"),
        sa.CheckConstraint("length(trim(recipient_name)) >= 2 AND length(trim(request_reason)) >= 5", name="ck_record_release_text"),
        sa.CheckConstraint("(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND decision_reason IS NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'approved' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'rejected' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NOT NULL AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL) OR (status = 'released' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND released_by_user_id IS NOT NULL AND released_at IS NOT NULL AND release_vault_reference IS NOT NULL) OR (status = 'cancelled' AND released_by_user_id IS NULL AND released_at IS NULL AND release_vault_reference IS NULL)", name="ck_record_release_state"),
        sa.CheckConstraint("release_vault_reference IS NULL OR release_vault_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_release_vault_ref"),
    )
    op.create_index("ix_record_release_patient_status", "patient_record_release_requests", ["hospital_id", "patient_id", "status", "created_at"])
    op.create_index("ix_record_release_review_queue", "patient_record_release_requests", ["hospital_id", "status", "created_at"])

    op.create_table(
        "patient_record_amendment_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid()),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amendment_type", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("supporting_evidence_reference", sa.String(80)),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("decision_reason", sa.String(1000)),
        sa.Column("fulfilled_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True)),
        sa.Column("amendment_vault_reference", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_record_amendment_patient"),
        sa.ForeignKeyConstraint(["hospital_id", "document_id", "patient_id"], ["patient_record_documents.hospital_id", "patient_record_documents.id", "patient_record_documents.patient_id"], name="fk_record_amendment_document"),
        sa.UniqueConstraint("hospital_id", "id", "patient_id", name="uq_record_amendment_hospital_id_patient"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'fulfilled', 'cancelled')", name="ck_record_amendment_status"),
        sa.CheckConstraint("amendment_type IN ('demographic', 'clinical_content', 'metadata', 'identity')", name="ck_record_amendment_type"),
        sa.CheckConstraint("length(trim(reason)) >= 5", name="ck_record_amendment_reason"),
        sa.CheckConstraint("(status = 'pending' AND reviewed_by_user_id IS NULL AND reviewed_at IS NULL AND decision_reason IS NULL AND amendment_vault_reference IS NULL) OR (status = 'approved' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NULL AND amendment_vault_reference IS NULL) OR (status = 'rejected' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NOT NULL AND amendment_vault_reference IS NULL) OR (status = 'fulfilled' AND reviewed_by_user_id IS NOT NULL AND reviewed_at IS NOT NULL AND fulfilled_by_user_id IS NOT NULL AND fulfilled_at IS NOT NULL AND amendment_vault_reference IS NOT NULL) OR (status = 'cancelled' AND amendment_vault_reference IS NULL)", name="ck_record_amendment_state"),
        sa.CheckConstraint("amendment_vault_reference IS NULL OR amendment_vault_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_amendment_vault_ref"),
        sa.CheckConstraint("supporting_evidence_reference IS NULL OR supporting_evidence_reference ~ '^vault://[0-9a-fA-F-]{36}$'", name="ck_record_amendment_evidence_ref"),
    )
    op.create_index("ix_record_amendment_patient_status", "patient_record_amendment_requests", ["hospital_id", "patient_id", "status", "created_at"])

    op.create_table(
        "patient_record_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("resource_type", sa.String(48), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"], name="fk_patient_record_event_patient"),
        sa.UniqueConstraint("hospital_id", "id", name="uq_patient_record_event_hospital_id"),
        sa.CheckConstraint("event_type IN ('document_registered', 'document_verified', 'document_rejected', 'document_superseded', 'release_requested', 'release_approved', 'release_rejected', 'release_cancelled', 'records_released', 'amendment_requested', 'amendment_approved', 'amendment_rejected', 'amendment_fulfilled', 'amendment_cancelled')", name="ck_patient_record_event_type"),
    )
    op.create_index("ix_patient_record_event_history", "patient_record_events", ["hospital_id", "created_at"])

    for table in TABLES:
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'CREATE POLICY "{table}_hospital_isolation" ON "{table}" USING (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid) WITH CHECK (hospital_id = NULLIF(current_setting(\'app.current_hospital_id\', true), \'\')::uuid)'))

    op.execute("""
        CREATE FUNCTION prevent_patient_record_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'patient record events are append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_patient_record_events_immutable BEFORE UPDATE OR DELETE ON patient_record_events FOR EACH ROW EXECUTE FUNCTION prevent_patient_record_event_mutation()")
    op.execute("""
        CREATE FUNCTION guard_patient_record_document_mutation() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'patient record documents cannot be deleted';
            END IF;
            IF OLD.status = 'pending_review' AND NEW.status IN ('verified', 'rejected') THEN
                IF (to_jsonb(NEW) - ARRAY['status', 'verified_by_user_id', 'verified_at', 'rejection_reason'])
                   IS DISTINCT FROM
                   (to_jsonb(OLD) - ARRAY['status', 'verified_by_user_id', 'verified_at', 'rejection_reason']) THEN
                    RAISE EXCEPTION 'record document content is immutable after registration';
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.status = 'verified' AND NEW.status = 'superseded' THEN
                IF (to_jsonb(NEW) - 'status') IS DISTINCT FROM (to_jsonb(OLD) - 'status') THEN
                    RAISE EXCEPTION 'verified record document content is immutable';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'invalid patient record document mutation';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("CREATE TRIGGER trg_patient_record_documents_immutable BEFORE UPDATE OR DELETE ON patient_record_documents FOR EACH ROW EXECUTE FUNCTION guard_patient_record_document_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_patient_record_documents_immutable ON patient_record_documents")
    op.execute("DROP FUNCTION IF EXISTS guard_patient_record_document_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_patient_record_events_immutable ON patient_record_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_patient_record_event_mutation()")
    for table in reversed(TABLES):
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{table}_hospital_isolation" ON "{table}"'))
        op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        op.drop_table(table)
