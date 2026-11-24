"""Create billing service catalog, invoices, invoice lines and payment records."""

from alembic import op
import sqlalchemy as sa

revision = "0030_billing"
down_revision = "0029_pharmacy"
branch_labels = None
depends_on = None

TABLES = (
    "billing_service_definitions",
    "invoices",
    "invoice_lines",
    "invoice_payments",
)


def upgrade() -> None:
    op.create_table(
        "billing_service_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("retired_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.Column("retirement_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_billing_service_department",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_billing_service_hospital_id"),
        sa.UniqueConstraint("hospital_id", "code", name="uq_billing_service_code"),
        sa.CheckConstraint("status IN ('draft', 'active', 'retired')", name="ck_billing_service_status"),
        sa.CheckConstraint(
            "(status = 'draft' AND approved_by_user_id IS NULL AND approved_at IS NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'active' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NULL AND retired_at IS NULL AND retirement_reason IS NULL) OR "
            "(status = 'retired' AND approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL "
            "AND retired_by_user_id IS NOT NULL AND retired_at IS NOT NULL "
            "AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) >= 3)",
            name="ck_billing_service_approval_state",
        ),
        sa.CheckConstraint(
            "approved_by_user_id IS NULL OR approved_by_user_id != created_by_user_id",
            name="ck_billing_service_two_person",
        ),
        sa.CheckConstraint("unit_price >= 0", name="ck_billing_service_price"),
        sa.CheckConstraint("length(trim(code)) >= 2 AND length(trim(name)) >= 2", name="ck_billing_service_text"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_billing_service_currency"),
    )
    op.create_index(
        "ix_billing_service_department_status",
        "billing_service_definitions",
        ["hospital_id", "department_id", "status"],
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("encounter_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_number", sa.String(80), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("subtotal_total", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("amount_paid_total", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("issued_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("void_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("void_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "patient_id"],
            ["patients.hospital_id", "patients.id"],
            name="fk_invoice_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "encounter_id", "patient_id"],
            ["encounters.hospital_id", "encounters.id", "encounters.patient_id"],
            name="fk_invoice_encounter_patient",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "department_id"],
            ["departments.hospital_id", "departments.id"],
            name="fk_invoice_department",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_invoice_hospital_id"),
        sa.UniqueConstraint("hospital_id", "invoice_number", name="uq_invoice_number"),
        sa.CheckConstraint("status IN ('draft', 'issued', 'partially_paid', 'paid', 'void')", name="ck_invoice_status"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_invoice_currency"),
        sa.CheckConstraint("subtotal_total >= 0 AND amount_paid_total >= 0", name="ck_invoice_amounts_nonnegative"),
        sa.CheckConstraint("amount_paid_total <= subtotal_total", name="ck_invoice_amount_paid_limit"),
        sa.CheckConstraint(
            "issued_by_user_id IS NULL OR issued_by_user_id != created_by_user_id",
            name="ck_invoice_issue_two_person",
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND issued_by_user_id IS NULL AND issued_at IS NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'issued' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = 0 AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'partially_paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total > 0 AND amount_paid_total < subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'paid' AND issued_by_user_id IS NOT NULL AND issued_at IS NOT NULL "
            "AND amount_paid_total = subtotal_total "
            "AND void_by_user_id IS NULL AND void_at IS NULL AND void_reason IS NULL) OR "
            "(status = 'void' AND void_by_user_id IS NOT NULL AND void_at IS NOT NULL "
            "AND void_reason IS NOT NULL AND length(trim(void_reason)) >= 3 AND amount_paid_total = 0)",
            name="ck_invoice_lifecycle_state",
        ),
        sa.CheckConstraint("length(trim(invoice_number)) >= 3", name="ck_invoice_number_text"),
    )
    op.create_index("ix_invoice_patient_created", "invoices", ["hospital_id", "patient_id", "created_at"])
    op.create_index("ix_invoice_encounter", "invoices", ["hospital_id", "encounter_id"])
    op.create_index(
        "ix_invoice_department_status",
        "invoices",
        ["hospital_id", "department_id", "status", "created_at"],
    )

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("service_definition_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(240), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_line_invoice",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id", "service_definition_id"],
            ["billing_service_definitions.hospital_id", "billing_service_definitions.id"],
            name="fk_invoice_line_service",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_line_quantity"),
        sa.CheckConstraint("unit_price >= 0 AND line_total >= 0", name="ck_invoice_line_amounts"),
        sa.CheckConstraint("line_total = round(quantity * unit_price, 2)", name="ck_invoice_line_total_calculation"),
        sa.CheckConstraint("length(trim(description)) >= 2", name="ck_invoice_line_description"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_invoice_line_currency"),
    )
    op.create_index("ix_invoice_line_invoice", "invoice_lines", ["hospital_id", "invoice_id"])

    op.create_table(
        "invoice_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hospital_id", sa.Uuid(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("method", sa.String(24), nullable=False),
        sa.Column("external_reference", sa.String(160)),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("confirmed_by_user_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("failure_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id", "invoice_id"],
            ["invoices.hospital_id", "invoices.id"],
            name="fk_invoice_payment_invoice",
        ),
        sa.UniqueConstraint("hospital_id", "id", name="uq_invoice_payment_hospital_id"),
        sa.UniqueConstraint("hospital_id", "external_reference", name="uq_invoice_payment_external_reference"),
        sa.CheckConstraint("status IN ('pending', 'confirmed', 'failed')", name="ck_invoice_payment_status"),
        sa.CheckConstraint("amount > 0", name="ck_invoice_payment_amount"),
        sa.CheckConstraint(
            "method IN ('cash', 'card', 'bank_transfer', 'mobile_money', 'cheque', 'other')",
            name="ck_invoice_payment_method",
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_invoice_payment_currency"),
        sa.CheckConstraint(
            "(status = 'pending' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL AND failure_note IS NULL) OR "
            "(status = 'confirmed' AND confirmed_by_user_id IS NOT NULL AND confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id != created_by_user_id AND failure_note IS NULL) OR "
            "(status = 'failed' AND confirmed_by_user_id IS NULL AND confirmed_at IS NULL "
            "AND failure_note IS NOT NULL AND length(trim(failure_note)) >= 3)",
            name="ck_invoice_payment_lifecycle_state",
        ),
    )
    op.create_index(
        "ix_invoice_payment_invoice_time",
        "invoice_payments",
        ["hospital_id", "invoice_id", "created_at"],
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION protect_billing_history()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $billing_history$
        DECLARE
            invoice_state text;
            invoice_currency text;
            invoice_department uuid;
            service_state text;
            service_currency text;
            service_department uuid;
            invoice_subtotal numeric;
            invoice_paid numeric;
        BEGIN
            IF TG_TABLE_NAME = 'invoice_lines' THEN
                IF TG_OP = 'INSERT' THEN
                    SELECT status, currency, department_id
                    INTO invoice_state, invoice_currency, invoice_department
                    FROM invoices
                    WHERE hospital_id = NEW.hospital_id AND id = NEW.invoice_id
                    FOR UPDATE;
                    IF invoice_state IS DISTINCT FROM 'draft' THEN
                        RAISE EXCEPTION 'invoice lines can only be added to draft invoices';
                    END IF;
                    SELECT status, currency, department_id
                    INTO service_state, service_currency, service_department
                    FROM billing_service_definitions
                    WHERE hospital_id = NEW.hospital_id AND id = NEW.service_definition_id
                    FOR SHARE;
                    IF service_state IS DISTINCT FROM 'active'
                        OR service_currency IS DISTINCT FROM invoice_currency
                        OR service_department IS DISTINCT FROM invoice_department
                        OR NEW.currency IS DISTINCT FROM invoice_currency THEN
                        RAISE EXCEPTION 'invoice line service must be active and match invoice department and currency';
                    END IF;
                    UPDATE invoices
                    SET subtotal_total = subtotal_total + NEW.line_total
                    WHERE hospital_id = NEW.hospital_id AND id = NEW.invoice_id;
                    RETURN NEW;
                END IF;
                RAISE EXCEPTION 'invoice lines are append-only';
            END IF;

            IF TG_OP = 'INSERT' THEN
                SELECT status, currency, subtotal_total, amount_paid_total
                INTO invoice_state, invoice_currency, invoice_subtotal, invoice_paid
                FROM invoices
                WHERE hospital_id = NEW.hospital_id AND id = NEW.invoice_id
                FOR UPDATE;
                IF NEW.status != 'pending'
                    OR invoice_state NOT IN ('issued', 'partially_paid')
                    OR NEW.currency IS DISTINCT FROM invoice_currency
                    OR NEW.amount > invoice_subtotal - invoice_paid THEN
                    RAISE EXCEPTION 'new payment must be pending, match invoice currency and fit the open balance';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'payment records cannot be deleted';
            END IF;
            IF OLD.status != 'pending' THEN
                RAISE EXCEPTION 'final payment records are immutable';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.hospital_id IS DISTINCT FROM OLD.hospital_id
                OR NEW.invoice_id IS DISTINCT FROM OLD.invoice_id
                OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
                OR NEW.amount IS DISTINCT FROM OLD.amount
                OR NEW.currency IS DISTINCT FROM OLD.currency
                OR NEW.method IS DISTINCT FROM OLD.method
                OR NEW.external_reference IS DISTINCT FROM OLD.external_reference
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.status NOT IN ('confirmed', 'failed') THEN
                RAISE EXCEPTION 'only pending payment finalization is permitted';
            END IF;
            IF NEW.status = 'confirmed' THEN
                SELECT status, currency, subtotal_total, amount_paid_total
                INTO invoice_state, invoice_currency, invoice_subtotal, invoice_paid
                FROM invoices
                WHERE hospital_id = NEW.hospital_id AND id = NEW.invoice_id
                FOR UPDATE;
                IF invoice_state NOT IN ('issued', 'partially_paid')
                    OR NEW.currency IS DISTINCT FROM invoice_currency
                    OR NEW.amount > invoice_subtotal - invoice_paid THEN
                    RAISE EXCEPTION 'confirmed payment exceeds or does not match the open invoice balance';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $billing_history$
    """)
    op.execute(
        "CREATE TRIGGER invoice_lines_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON invoice_lines "
        "FOR EACH ROW EXECUTE FUNCTION protect_billing_history()"
    )
    op.execute(
        "CREATE TRIGGER invoice_payments_guard "
        "BEFORE INSERT OR UPDATE OR DELETE ON invoice_payments "
        "FOR EACH ROW EXECUTE FUNCTION protect_billing_history()"
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
    op.execute("DROP TRIGGER IF EXISTS invoice_payments_guard ON invoice_payments")
    op.execute("DROP TRIGGER IF EXISTS invoice_lines_guard ON invoice_lines")
    op.execute("DROP FUNCTION IF EXISTS protect_billing_history()")
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS hospital_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_invoice_payment_invoice_time", table_name="invoice_payments")
    op.drop_table("invoice_payments")
    op.drop_index("ix_invoice_line_invoice", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoice_department_status", table_name="invoices")
    op.drop_index("ix_invoice_encounter", table_name="invoices")
    op.drop_index("ix_invoice_patient_created", table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_billing_service_department_status", table_name="billing_service_definitions")
    op.drop_table("billing_service_definitions")
