"""Add encrypted, hospital-scoped AI conversation sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0011_ai_conversation_sessions"
down_revision = "0010_patient_care_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "hospital_id", "owner_user_id", name="uq_ai_session_identity_owner"),
        sa.CheckConstraint("status IN ('active', 'deleted', 'expired')", name="ck_ai_session_status"),
        sa.CheckConstraint("message_count >= 0", name="ck_ai_session_message_count"),
    )
    op.create_index("ix_ai_session_owner_status", "ai_sessions", ["hospital_id", "owner_user_id", "status"])
    op.create_index("ix_ai_session_expiry", "ai_sessions", ["status", "expires_at"])

    op.create_table(
        "ai_session_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.String(80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "sequence_number", name="uq_ai_session_message_sequence"),
        sa.ForeignKeyConstraint(
            ["session_id", "hospital_id", "owner_user_id"],
            ["ai_sessions.id", "ai_sessions.hospital_id", "ai_sessions.owner_user_id"],
            ondelete="CASCADE",
            name="fk_ai_session_message_owner",
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_session_message_role"),
        sa.CheckConstraint("sequence_number > 0", name="ck_ai_session_message_sequence"),
        sa.CheckConstraint("length(nonce) = 12", name="ck_ai_session_message_nonce"),
    )
    op.create_index(
        "ix_ai_session_message_tenant_session",
        "ai_session_messages",
        ["hospital_id", "session_id", "sequence_number"],
    )

    for table in ("ai_sessions", "ai_session_messages"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY hospital_owner_isolation ON {table} "
            "USING ("
            "hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid "
            "AND owner_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"
            ") "
            "WITH CHECK ("
            "hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid "
            "AND owner_user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid"
            )
        )


def downgrade() -> None:
    for table in ("ai_session_messages", "ai_sessions"):
        op.execute(f"DROP POLICY IF EXISTS hospital_owner_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_ai_session_message_tenant_session", table_name="ai_session_messages")
    op.drop_table("ai_session_messages")
    op.drop_index("ix_ai_session_expiry", table_name="ai_sessions")
    op.drop_index("ix_ai_session_owner_status", table_name="ai_sessions")
    op.drop_table("ai_sessions")
