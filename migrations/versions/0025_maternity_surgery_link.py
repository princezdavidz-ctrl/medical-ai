"""Link cesarean maternity delivery records to surgical cases."""

from alembic import op
import sqlalchemy as sa

revision = "0025_maternity_surgery_link"
down_revision = "0024_maternity_newborn"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_surgical_case_hospital_id_patient",
        "surgical_cases",
        ["hospital_id", "id", "patient_id"],
    )
    op.add_column("maternity_deliveries", sa.Column("surgical_case_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_maternity_delivery_surgical_case_mother",
        "maternity_deliveries",
        "surgical_cases",
        ["hospital_id", "surgical_case_id", "mother_patient_id"],
        ["hospital_id", "id", "patient_id"],
    )
    op.create_unique_constraint(
        "uq_maternity_delivery_surgical_case",
        "maternity_deliveries",
        ["hospital_id", "surgical_case_id"],
    )
    op.create_check_constraint(
        "ck_maternity_delivery_surgical_case",
        "maternity_deliveries",
        "(delivery_mode = 'cesarean' AND surgical_case_id IS NOT NULL) OR "
        "(delivery_mode != 'cesarean' AND surgical_case_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_maternity_delivery_surgical_case", "maternity_deliveries", type_="check")
    op.drop_constraint("uq_maternity_delivery_surgical_case", "maternity_deliveries", type_="unique")
    op.drop_constraint("fk_maternity_delivery_surgical_case_mother", "maternity_deliveries", type_="foreignkey")
    op.drop_column("maternity_deliveries", "surgical_case_id")
    op.drop_constraint("uq_surgical_case_hospital_id_patient", "surgical_cases", type_="unique")
