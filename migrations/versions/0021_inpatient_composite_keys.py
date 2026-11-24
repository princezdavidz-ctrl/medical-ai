"""Add composite keys for admission and bed assignment references."""

from alembic import op

revision = "0021_inpatient_composite_keys"
down_revision = "0020_emergency_trauma"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_inpatient_admission_hospital_id_patient",
        "inpatient_admissions",
        ["hospital_id", "id", "patient_id"],
    )
    op.create_unique_constraint(
        "uq_bed_assignment_hospital_id_id",
        "bed_assignments",
        ["hospital_id", "id"],
    )
    op.create_unique_constraint(
        "uq_bed_assignment_hospital_id_id_admission",
        "bed_assignments",
        ["hospital_id", "id", "admission_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_bed_assignment_hospital_id_id_admission",
        "bed_assignments",
        type_="unique",
    )
    op.drop_constraint(
        "uq_bed_assignment_hospital_id_id",
        "bed_assignments",
        type_="unique",
    )
    op.drop_constraint(
        "uq_inpatient_admission_hospital_id_patient",
        "inpatient_admissions",
        type_="unique",
    )
