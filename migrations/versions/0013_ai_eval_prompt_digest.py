"""Pin capability prompt digest to each AI evaluation run."""

from alembic import op
import sqlalchemy as sa

revision = "0013_ai_eval_prompt_digest"
down_revision = "0012_ai_usage_accounting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_evaluation_runs",
        sa.Column("prompt_sha256", sa.String(64), nullable=True),
    )
    op.create_check_constraint(
        "ck_ai_eval_run_prompt_sha256",
        "ai_evaluation_runs",
        "prompt_sha256 IS NULL OR prompt_sha256 ~ '^[0-9a-f]{64}$'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ai_eval_run_prompt_sha256",
        "ai_evaluation_runs",
        type_="check",
    )
    op.drop_column("ai_evaluation_runs", "prompt_sha256")
