"""Purpose-bound, minimum-necessary patient context assembly for local-only AI use."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import (
    Department,
    Encounter,
    HospitalMembership,
    Patient,
    PatientCareAssignment,
    PatientConsent,
    Role,
)


CONSENT_PURPOSE = "clinical_ai_assistance"
ALLOWED_CLINICAL_ROLES = frozenset({
    "doctor",
    "nurse",
    "clinical_officer",
    "pharmacist",
    "lab_technician",
    "radiologist",
    "midwife",
    "dentist",
    "physiotherapist",
})


class PatientContextDenied(PermissionError):
    """Raised when any required patient-context authorization condition is absent."""


@dataclass(frozen=True, slots=True)
class AuthorizedPatientContext:
    patient_context: dict[str, object]
    encounter_id: UUID
    consent_id: UUID
    assignment_id: UUID


def _age_in_years(date_of_birth, current: datetime) -> int | None:
    if date_of_birth is None:
        return None
    today = current.date()
    return today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )


def load_authorized_patient_context(
    db: Session,
    *,
    hospital_id: UUID,
    actor_user_id: UUID,
    patient_id: UUID,
    encounter_id: UUID | None = None,
    now: datetime | None = None,
) -> AuthorizedPatientContext:
    """Require active clinical role, assignment and explicit purpose-bound consent."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise PatientContextDenied("timezone_required")

    membership = db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == actor_user_id,
            HospitalMembership.status == "active",
        )
    )
    if membership is None:
        raise PatientContextDenied("active_hospital_membership_required")

    role = db.get(Role, membership.role_id)
    if role is None or role.name.strip().casefold() not in ALLOWED_CLINICAL_ROLES:
        raise PatientContextDenied("clinical_role_not_authorized")

    patient = db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.hospital_id == hospital_id,
            Patient.status == "active",
        )
    )
    if patient is None:
        raise PatientContextDenied("patient_not_available_in_hospital")

    assignment_query = select(PatientCareAssignment).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == patient_id,
        PatientCareAssignment.staff_user_id == actor_user_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= current,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > current,
        ),
        PatientCareAssignment.revoked_at.is_(None),
    )
    if encounter_id is not None:
        assignment_query = assignment_query.where(
            or_(
                PatientCareAssignment.encounter_id.is_(None),
                PatientCareAssignment.encounter_id == encounter_id,
            )
        )
    assignment = db.scalar(assignment_query.order_by(PatientCareAssignment.created_at.desc()))
    if assignment is None:
        raise PatientContextDenied("active_patient_care_assignment_required")

    encounter_query = select(Encounter).where(
        Encounter.hospital_id == hospital_id,
        Encounter.patient_id == patient_id,
        Encounter.status == "in_progress",
    )
    if encounter_id is not None:
        encounter_query = encounter_query.where(Encounter.id == encounter_id)
    encounter = db.scalar(encounter_query.order_by(Encounter.started_at.desc()))
    if encounter is None:
        raise PatientContextDenied("active_patient_encounter_required")
    if assignment.encounter_id is not None and assignment.encounter_id != encounter.id:
        raise PatientContextDenied("assignment_encounter_mismatch")

    consents = db.scalars(
        select(PatientConsent).where(
            PatientConsent.hospital_id == hospital_id,
            PatientConsent.patient_id == patient_id,
            PatientConsent.purpose == CONSENT_PURPOSE,
            PatientConsent.status == "granted",
            PatientConsent.granted_at.is_not(None),
            PatientConsent.granted_at <= current,
            PatientConsent.withdrawn_at.is_(None),
            or_(PatientConsent.expires_at.is_(None), PatientConsent.expires_at > current),
        )
    ).all()
    required_categories = {"demographics", "encounter"}
    consent = next(
        (
            item for item in consents
            if isinstance(item.scope, dict)
            and item.scope.get("ai_processing") is True
            and required_categories.issubset(set(item.scope.get("data_categories", [])))
        ),
        None,
    )
    if consent is None:
        raise PatientContextDenied("active_ai_purpose_consent_required")

    department_name = None
    if encounter.department_id is not None:
        department = db.scalar(
            select(Department).where(
                Department.id == encounter.department_id,
                Department.hospital_id == hospital_id,
            )
        )
        department_name = department.name if department else None

    # Exclude direct identifiers, MRN, name, phone, exact DOB and staff identifiers.
    context: dict[str, object] = {
        "patient_age_years": _age_in_years(patient.date_of_birth, current),
        "administrative_sex": patient.administrative_sex,
        "encounter": {
            "type": encounter.encounter_type,
            "status": encounter.status,
            "department": department_name,
        },
        "context_notice": (
            "Minimum-necessary structured patient data supplied for the authorized clinical purpose. "
            "Free-text clinical notes and direct identifiers are excluded from this context."
        ),
    }
    return AuthorizedPatientContext(
        patient_context=context,
        encounter_id=encounter.id,
        consent_id=consent.id,
        assignment_id=assignment.id,
    )
