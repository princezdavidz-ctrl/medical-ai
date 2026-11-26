"""Add recipient read state to notification intents."""
from alembic import op
import sqlalchemy as sa

revision = "0046_notification_read_state"
down_revision = "0045_notification_locales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_intents",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notification_intents", "read_at")
