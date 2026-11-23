"""Initial backend schema generated from the Phase 1 SQLAlchemy metadata.

This baseline migration is intended for a new, empty database. Future schema changes
must use explicit Alembic revisions rather than modifying this file.
"""
from alembic import op
from app.db.base import Base
from app import models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())

def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
