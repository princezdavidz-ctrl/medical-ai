"""Enable PostgreSQL row-level security for hospital-owned tables.

The application sets app.current_hospital_id from a signed access token for each
authenticated request. Missing tenant context denies access by design.
"""
from alembic import op

revision = "0002_hospital_rls"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "departments",
    "roles",
    "hospital_memberships",
    "patients",
    "encounters",
    "patient_consents",
    "audit_events",
)

def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY hospital_tenant_isolation ON {table}
            USING (
                hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
            WITH CHECK (
                hospital_id = NULLIF(current_setting('app.current_hospital_id', true), '')::uuid
            )
            """
        )

def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS hospital_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
