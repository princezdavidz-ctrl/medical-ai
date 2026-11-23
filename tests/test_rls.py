import os
from uuid import uuid4
import psycopg

def test_rls_hides_patient_rows_from_other_hospitals() -> None:
    database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    organization_id = uuid4()
    hospital_a = uuid4()
    hospital_b = uuid4()
    patient_id = uuid4()

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO organizations (id, legal_name, status) VALUES (%s, %s, %s)",
                (organization_id, "RLS test organization", "active"),
            )
            cursor.execute(
                """INSERT INTO hospitals (id, organization_id, name, facility_code, ownership_type, country_code, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s), (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    hospital_a, organization_id, "Hospital A", f"A-{hospital_a}", "public", "KE", "active",
                    hospital_b, organization_id, "Hospital B", f"B-{hospital_b}", "private", "KE", "active",
                ),
            )
            cursor.execute(
                "SELECT set_config('app.current_hospital_id', %s, true)",
                (str(hospital_a),),
            )
            cursor.execute(
                """INSERT INTO patients
                   (id, hospital_id, medical_record_number, given_name, family_name, status)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (patient_id, hospital_a, f"MRN-{patient_id}", "Test", "Patient", "active"),
            )

            cursor.execute(
                "SELECT set_config('app.current_hospital_id', %s, true)",
                (str(hospital_b),),
            )
            cursor.execute("SELECT count(*) FROM patients WHERE id = %s", (patient_id,))
            assert cursor.fetchone()[0] == 0

            cursor.execute(
                "SELECT set_config('app.current_hospital_id', %s, true)",
                (str(hospital_a),),
            )
            cursor.execute("SELECT count(*) FROM patients WHERE id = %s", (patient_id,))
            assert cursor.fetchone()[0] == 1

        connection.rollback()
