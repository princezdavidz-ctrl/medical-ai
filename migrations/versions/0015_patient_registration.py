"""Create the governed patient registration domain and duplicate review workflow."""

from alembic import op
import sqlalchemy as sa

revision = "0015_patient_registration"
down_revision = "0014_ai_hospital_controls"
branch_labels = None
depends_on = None

TABLES = (
    "patient_registration_profiles",
    "patient_identity_documents",
    "patient_next_of_kin",
    "patient_duplicate_cases",
)


def upgrade() -> None:
    op.add_column("patients", sa.Column("middle_name", sa.String(120), nullable=True))
    op.add_column("patients", sa.Column("preferred_name", sa.String(120), nullable=True))
    op.add_column("patients", sa.Column("nationality", sa.String(2), nullable=True))
    op.create_unique_constraint(
        "uq_patient_hospital_id_id", "patients", ["hospital_id", "id"]
    )

    op.create_table(
        "patient_registration_profiles",
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), primary_key=True),
        sa.Column("patient_id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320)),
        sa.Column("alternate_phone_number", sa.String(40)),
        sa.Column("address_line_1", sa.String(240)),
        sa.Column("address_line_2", sa.String(240)),
        sa.Column("county", sa.String(100)),
        sa.Column("sub_county", sa.String(100)),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="KE"),
        sa.Column("postal_code", sa.String(24)),
        sa.Column("preferred_language", sa.String(60)),
        sa.Column("registration_source", sa.String(24), nullable=False, server_default="walk_in"),
        sa.Column("registered_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("registration_completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"],
            name="fk_patient_registration_profile_patient", ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "registration_source IN ('walk_in', 'referral', 'transfer', 'portal', 'import')",
            name="ck_patient_registration_source",
        ),
    )

    op.create_table(
        "patient_identity_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("issuing_country", sa.String(2), nullable=False, server_default="KE"),
        sa.Column("encrypted_identifier_ref", sa.String(500), nullable=False),
        sa.Column("identifier_fingerprint_hmac", sa.String(64)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("verification_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("verified_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"],
            name="fk_patient_identity_document_patient", ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "document_type IN ('national_id', 'passport', 'birth_certificate', 'alien_id', 'refugee_document', 'other')",
            name="ck_patient_identity_document_type",
        ),
        sa.CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="ck_patient_identity_document_status",
        ),
        sa.CheckConstraint(
            "identifier_fingerprint_hmac IS NULL OR length(identifier_fingerprint_hmac) = 64",
            name="ck_patient_identity_fingerprint_length",
        ),
    )
    op.create_index(
        "ix_patient_identity_hospital_patient",
        "patient_identity_documents", ["hospital_id", "patient_id"],
    )

    op.create_table(
        "patient_next_of_kin",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("relationship", sa.String(80), nullable=False),
        sa.Column("phone_number", sa.String(40), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("can_be_contacted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("permission_basis", sa.String(32)),
        sa.Column("permission_recorded_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"],
            name="fk_patient_next_of_kin_patient", ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "(permission_basis IS NULL OR permission_basis IN ('patient_consent', 'legal_guardian_consent', 'other_lawful_basis')) "
            "AND (can_be_contacted = false OR (permission_basis IS NOT NULL AND permission_recorded_at IS NOT NULL))",
            name="ck_patient_next_of_kin_permission_basis",
        ),
    )
    op.create_index(
        "ix_patient_next_of_kin_hospital_patient",
        "patient_next_of_kin", ["hospital_id", "patient_id"],
    )

    op.create_table(
        "patient_duplicate_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_patient_id", sa.Uuid(), nullable=False),
        sa.Column("match_score", sa.SmallInteger(), nullable=False),
        sa.Column("matching_signals_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("review_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"], ["patients.hospital_id", "patients.id"],
            name="fk_patient_duplicate_case_patient", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "candidate_patient_id"], ["patients.hospital_id", "patients.id"],
            name="fk_patient_duplicate_case_candidate", ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "hospital_id", "patient_id", "candidate_patient_id",
            name="uq_patient_duplicate_case_pair",
        ),
        sa.CheckConstraint("patient_id <> candidate_patient_id", name="ck_patient_duplicate_distinct"),
        sa.CheckConstraint("match_score BETWEEN 0 AND 100", name="ck_patient_duplicate_score"),
        sa.CheckConstraint(
            "status IN ('pending', 'not_duplicate', 'confirmed_duplicate', 'closed')",
            name="ck_patient_duplicate_status",
        ),
    )
    op.create_index(
        "ix_patient_duplicate_review_queue",
        "patient_duplicate_cases", ["hospital_id", "status", "created_at"],
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY hospital_tenant_isolation ON {table} "
            "USING (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid) "
            "WITH CHECK (hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid)"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS hospital_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_patient_duplicate_review_queue", table_name="patient_duplicate_cases")
    op.drop_table("patient_duplicate_cases")
    op.drop_index("ix_patient_next_of_kin_hospital_patient", table_name="patient_next_of_kin")
    op.drop_table("patient_next_of_kin")
    op.drop_index("ix_patient_identity_hospital_patient", table_name="patient_identity_documents")
    op.drop_table("patient_identity_documents")
    op.drop_table("patient_registration_profiles")
    op.drop_constraint("uq_patient_hospital_id_id", "patients", type_="unique")
    op.drop_column("patients", "nationality")
    op.drop_column("patients", "preferred_name")
    op.drop_column("patients", "middle_name")
