"""Add locale-specific versions of notification templates."""
from alembic import op
import sqlalchemy as sa

revision = "0045_notification_locales"
down_revision = "0044_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_templates",
        sa.Column("locale", sa.String(12), nullable=False, server_default="en"),
    )
    op.drop_constraint("uq_notification_template_version", "notification_templates", type_="unique")
    op.create_unique_constraint(
        "uq_notification_template_locale_version",
        "notification_templates",
        ["hospital_id", "template_code", "locale", "version"],
    )
    op.create_check_constraint(
        "ck_notification_template_locale",
        "notification_templates",
        "locale ~ '^[a-z]{2}(-[A-Z]{2})?$'",
    )
    op.alter_column("notification_templates", "locale", server_default=None)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM notification_templates
                GROUP BY hospital_id, template_code, version
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION 'cannot downgrade notification locales while localized template versions exist';
            END IF;
        END
        $$;
    """)
    op.drop_constraint("ck_notification_template_locale", "notification_templates", type_="check")
    op.drop_constraint("uq_notification_template_locale_version", "notification_templates", type_="unique")
    op.create_unique_constraint(
        "uq_notification_template_version",
        "notification_templates",
        ["hospital_id", "template_code", "version"],
    )
    op.drop_column("notification_templates", "locale")
