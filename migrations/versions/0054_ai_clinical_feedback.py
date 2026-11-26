"""Add structured clinician feedback metadata to AI clinical reviews."""
from alembic import op
import sqlalchemy as sa

revision = "0054_ai_clinical_feedback"
down_revision = "0053_ai_clinical_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_clinical_review_records", sa.Column("feedback_category", sa.String(24), nullable=True))
    op.add_column("ai_clinical_review_records", sa.Column("correction_reference", sa.String(80), nullable=True))
    op.create_check_constraint(
        "ck_ai_clinical_review_feedback_category",
        "ai_clinical_review_records",
        "feedback_category IS NULL OR feedback_category IN ('helpful', 'inaccurate', 'missing_context', 'unsafe', 'unsupported', 'needs_revision', 'other')",
    )
    op.create_check_constraint(
        "ck_ai_clinical_review_correction_ref",
        "ai_clinical_review_records",
        "correction_reference IS NULL OR correction_reference ~ '^vault://[0-9a-fA-F-]{36}$'",
    )
    op.create_index(
        "ix_ai_clinical_review_feedback_category",
        "ai_clinical_review_records",
        ["hospital_id", "feedback_category", "reviewed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_clinical_review_feedback_category", table_name="ai_clinical_review_records")
    op.drop_constraint("ck_ai_clinical_review_correction_ref", "ai_clinical_review_records", type_="check")
    op.drop_constraint("ck_ai_clinical_review_feedback_category", "ai_clinical_review_records", type_="check")
    op.drop_column("ai_clinical_review_records", "correction_reference")
    op.drop_column("ai_clinical_review_records", "feedback_category")
