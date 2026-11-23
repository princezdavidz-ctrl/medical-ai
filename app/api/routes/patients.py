from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    HospitalMembership,
    Patient,
    PatientCareAssignment,
    PatientDuplicateCase,
    PatientIdentityDocument,
    PatientNextOfKin,
    PatientRegistrationProfile,
    Role,
)
from app.schemas.patient import (
    PatientCreate,
    PatientDuplicateCandidateRead,
    PatientDuplicateCaseRead,
    PatientDuplicateCaseReview,
    PatientIdentityDocumentVerification,
    PatientDemographicsUpdate,
    PatientRead,
    PatientRegistrationProfileUpdate,
    PatientRegistrationRead,
    PatientStatusUpdate,
)

router = APIRouter(prefix="/patients", tags=["patients"])

_REGISTRATION_ROLES = {
    "registration_clerk", "receptionist", "medical_records_officer",
    "hospital_admin", "hospital_director", "system_admin",
}
_RECORDS_VERIFIER_ROLES = {
    "medical_records_officer", "hospital_admin", "hospital_director", "system_admin",
}


def _require_patient_role(
    db: Session, *, user, hospital_id: UUID, allowed_roles: set[str]
) -> str:
    membership = db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user.id,
            HospitalMembership.status == "active",
        )
    )
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name not in allowed_roles:
        raise HTTPException(status_code=403, detail={"code": "patient_registration_role_required"})
    return role_name


_CLINICAL_PATIENT_ROLES = {
    "doctor", "physician", "medical_officer", "clinician", "nurse",
    "triage_nurse", "emergency_nurse", "lab_technician", "radiologist",
    "pharmacist", "midwife", "pediatrician", "surgeon", "anesthetist",
    "dentist", "therapist",
}


def _patient_read_scope(db: Session, *, user, hospital_id: UUID) -> str:
    membership = db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user.id,
            HospitalMembership.status == "active",
        )
    )
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name in _REGISTRATION_ROLES:
        return "hospital"
    if role_name in _CLINICAL_PATIENT_ROLES:
        return "assigned"
    raise HTTPException(status_code=403, detail={"code": "patient_read_role_required"})


def _has_active_patient_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID, patient_id: UUID
) -> bool:
    now = datetime.now(timezone.utc)
    assignment = db.scalar(
        select(PatientCareAssignment.id)
        .join(
            HospitalMembership,
            and_(
                HospitalMembership.hospital_id == PatientCareAssignment.hospital_id,
                HospitalMembership.user_id == PatientCareAssignment.staff_user_id,
                HospitalMembership.status == "active",
            ),
        )
        .where(
            PatientCareAssignment.hospital_id == hospital_id,
            PatientCareAssignment.patient_id == patient_id,
            PatientCareAssignment.staff_user_id == user_id,
            PatientCareAssignment.status == "active",
            PatientCareAssignment.valid_from <= now,
            or_(
                PatientCareAssignment.valid_until.is_(None),
                PatientCareAssignment.valid_until > now,
            ),
            or_(
                PatientCareAssignment.department_id.is_(None),
                PatientCareAssignment.department_id == HospitalMembership.department_id,
            ),
        )
        .limit(1)
    )
    return assignment is not None


def _duplicate_candidates(
    db: Session,
    *,
    hospital_id: UUID,
    given_name: str,
    family_name: str,
    date_of_birth,
    phone_number: str | None,
    exclude_patient_id: UUID | None = None,
) -> list[tuple[Patient, int, dict[str, bool]]]:
    given = given_name.strip().casefold()
    family = family_name.strip().casefold()
    conditions = []
    if date_of_birth is not None:
        conditions.append(and_(
            func.lower(func.trim(Patient.given_name)) == given,
            func.lower(func.trim(Patient.family_name)) == family,
            Patient.date_of_birth == date_of_birth,
        ))
    if phone_number:
        conditions.append(Patient.phone_number == phone_number.strip())
    if not conditions:
        return []

    query = select(Patient).where(
        Patient.hospital_id == hospital_id, or_(*conditions)
    )
    if exclude_patient_id is not None:
        query = query.where(Patient.id != exclude_patient_id)
    candidates = db.scalars(
        query.order_by(Patient.created_at.desc()).limit(25)
    ).all()
    matches = []
    for candidate in candidates:
        same_name = (
            candidate.given_name.strip().casefold() == given
            and candidate.family_name.strip().casefold() == family
        )
        same_dob = date_of_birth is not None and candidate.date_of_birth == date_of_birth
        same_phone = bool(
            phone_number
            and candidate.phone_number
            and candidate.phone_number.strip() == phone_number.strip()
        )
        signals = {
            "same_normalized_name": same_name,
            "same_date_of_birth": same_dob,
            "same_phone_number": same_phone,
        }
        score = 95 if same_name and same_dob else 90 if same_name and same_phone else 80
        matches.append((candidate, score, signals))
    return matches


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Patient:
    user, hospital_id = context
    _require_patient_role(
        db, user=user, hospital_id=hospital_id, allowed_roles=_REGISTRATION_ROLES
    )
    candidates = _duplicate_candidates(
        db,
        hospital_id=hospital_id,
        given_name=payload.given_name,
        family_name=payload.family_name,
        date_of_birth=payload.date_of_birth,
        phone_number=payload.phone_number,
    )
    now = datetime.now(timezone.utc)
    patient_data = payload.model_dump(
        exclude={"profile", "identity_documents", "next_of_kin"}
    )
    patient = Patient(hospital_id=hospital_id, **patient_data)
    db.add(patient)
    try:
        db.flush()
        if payload.profile is not None:
            db.add(PatientRegistrationProfile(
                hospital_id=hospital_id,
                patient_id=patient.id,
                registered_by_user_id=user.id,
                registration_completed_at=now,
                **payload.profile.model_dump(),
            ))
        for document in payload.identity_documents:
            db.add(PatientIdentityDocument(
                hospital_id=hospital_id,
                patient_id=patient.id,
                created_by_user_id=user.id,
                verification_status="pending",
                **document.model_dump(),
            ))
        for contact in payload.next_of_kin:
            data = contact.model_dump()
            can_be_contacted = data.pop("can_be_contacted")
            permission_basis = data.pop("permission_basis")
            db.add(PatientNextOfKin(
                hospital_id=hospital_id,
                patient_id=patient.id,
                can_be_contacted=can_be_contacted,
                permission_basis=permission_basis,
                permission_recorded_at=now if can_be_contacted else None,
                **data,
            ))
        for candidate, score, signals in candidates:
            db.add(PatientDuplicateCase(
                hospital_id=hospital_id,
                patient_id=patient.id,
                candidate_patient_id=candidate.id,
                match_score=score,
                matching_signals_json=signals,
                status="pending",
            ))
        write_audit_event(
            db,
            hospital_id=hospital_id,
            actor_user_id=user.id,
            action="patient.registered",
            resource_type="patient",
            resource_id=str(patient.id),
            metadata={
                "identity_document_count": len(payload.identity_documents),
                "next_of_kin_count": len(payload.next_of_kin),
                "duplicate_candidate_count": len(candidates),
            },
        )
        if candidates:
            write_audit_event(
                db,
                hospital_id=hospital_id,
                actor_user_id=user.id,
                action="patient.duplicate_candidates.detected",
                resource_type="patient",
                resource_id=str(patient.id),
                metadata={"candidate_count": len(candidates)},
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint_name == "uq_patient_hospital_mrn":
            raise HTTPException(
                status_code=409,
                detail={"code": "patient_mrn_already_exists", "message": "Medical record number already exists in this hospital."},
            ) from None
        raise HTTPException(
            status_code=409,
            detail={"code": "patient_registration_integrity_conflict"},
        ) from None
    db.refresh(patient)
    return patient


@router.get("", response_model=list[PatientRead])
def list_patients(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Patient]:
    user, hospital_id = context
    scope = _patient_read_scope(db, user=user, hospital_id=hospital_id)
    query = select(Patient).where(Patient.hospital_id == hospital_id)
    if scope == "assigned":
        assignment_now = datetime.now(timezone.utc)
        assigned_patient_ids = (
            select(PatientCareAssignment.patient_id)
            .join(
                HospitalMembership,
                and_(
                    HospitalMembership.hospital_id == PatientCareAssignment.hospital_id,
                    HospitalMembership.user_id == PatientCareAssignment.staff_user_id,
                    HospitalMembership.status == "active",
                ),
            )
            .where(
                PatientCareAssignment.hospital_id == hospital_id,
                PatientCareAssignment.staff_user_id == user.id,
                PatientCareAssignment.status == "active",
                PatientCareAssignment.valid_from <= assignment_now,
                or_(
                    PatientCareAssignment.valid_until.is_(None),
                    PatientCareAssignment.valid_until > assignment_now,
                ),
                or_(
                    PatientCareAssignment.department_id.is_(None),
                    PatientCareAssignment.department_id == HospitalMembership.department_id,
                ),
            )
        )
        query = query.where(Patient.id.in_(assigned_patient_ids))
    patients = list(
        db.scalars(
            query.order_by(Patient.created_at.desc()).limit(limit).offset(offset)
        ).all()
    )
    write_audit_event(
        db,
        hospital_id=hospital_id,
        actor_user_id=user.id,
        action="patient.list",
        resource_type="patient_collection",
        resource_id=None,
        metadata={"limit": limit, "offset": offset, "returned_count": len(patients)},
    )
    db.commit()
    return patients


@router.get("/{patient_id}/registration", response_model=PatientRegistrationRead)
def get_patient_registration(
    patient_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    _require_patient_role(
        db, user=user, hospital_id=hospital_id, allowed_roles=_REGISTRATION_ROLES
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.hospital_id == hospital_id
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    profile = db.get(PatientRegistrationProfile, (hospital_id, patient_id))
    documents = db.scalars(select(PatientIdentityDocument).where(
        PatientIdentityDocument.hospital_id == hospital_id,
        PatientIdentityDocument.patient_id == patient_id,
    )).all()
    contacts = db.scalars(select(PatientNextOfKin).where(
        PatientNextOfKin.hospital_id == hospital_id,
        PatientNextOfKin.patient_id == patient_id,
    )).all()
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="patient.registration.read", resource_type="patient",
        resource_id=str(patient_id),
        metadata={"identity_document_count": len(documents), "next_of_kin_count": len(contacts)},
    )
    db.commit()
    return {
        "patient": patient,
        "profile": profile,
        "identity_documents": [{
            "id": item.id,
            "document_type": item.document_type,
            "issuing_country": item.issuing_country,
            "verification_status": item.verification_status,
            "verification_reason_code": item.verification_reason_code,
            "expires_at": item.expires_at,
            "verified_at": item.verified_at,
        } for item in documents],
        "next_of_kin": contacts,
    }


@router.patch("/{patient_id}/registration")
def update_patient_registration(
    patient_id: UUID,
    payload: PatientRegistrationProfileUpdate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    _require_patient_role(
        db, user=user, hospital_id=hospital_id, allowed_roles=_REGISTRATION_ROLES
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.hospital_id == hospital_id
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    profile = db.get(PatientRegistrationProfile, (hospital_id, patient_id))
    if profile is None:
        profile = PatientRegistrationProfile(
            hospital_id=hospital_id,
            patient_id=patient_id,
            registered_by_user_id=user.id,
            registration_source="walk_in",
            country_code="KE",
            registration_completed_at=datetime.now(timezone.utc),
        )
        db.add(profile)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="patient.registration.updated", resource_type="patient",
        resource_id=str(patient_id),
        metadata={"updated_fields": sorted(payload.model_dump(exclude_unset=True))},
    )
    db.commit()
    return {"patient_id": str(patient_id), "status": "updated"}


@router.get("/{patient_id}/duplicate-cases", response_model=list[PatientDuplicateCandidateRead])
def list_patient_duplicate_cases(
    patient_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> list[dict]:
    user, hospital_id = context
    _require_patient_role(
        db, user=user, hospital_id=hospital_id, allowed_roles=_REGISTRATION_ROLES
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.hospital_id == hospital_id
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    cases = db.scalars(select(PatientDuplicateCase).where(
        PatientDuplicateCase.hospital_id == hospital_id,
        or_(
            PatientDuplicateCase.patient_id == patient_id,
            PatientDuplicateCase.candidate_patient_id == patient_id,
        ),
    ).order_by(PatientDuplicateCase.created_at.desc())).all()
    result = []
    for case in cases:
        other_id = (
            case.candidate_patient_id
            if case.patient_id == patient_id else case.patient_id
        )
        candidate = db.scalar(select(Patient).where(
            Patient.id == other_id, Patient.hospital_id == hospital_id
        ))
        if candidate is not None:
            result.append({"case": case, "candidate": candidate})
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="patient.duplicate_cases.listed", resource_type="patient",
        resource_id=str(patient_id), metadata={"case_count": len(result)},
    )
    db.commit()
    return result


@router.patch("/duplicate-cases/{case_id}", response_model=PatientDuplicateCaseRead)
def review_patient_duplicate_case(
    case_id: UUID,
    payload: PatientDuplicateCaseReview,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> PatientDuplicateCase:
    user, hospital_id = context
    _require_patient_role(
        db, user=user, hospital_id=hospital_id, allowed_roles=_RECORDS_VERIFIER_ROLES
    )
    case = db.scalar(select(PatientDuplicateCase).where(
        PatientDuplicateCase.id == case_id,
        PatientDuplicateCase.hospital_id == hospital_id,
    ).with_for_update())
    if case is None:
        raise HTTPException(status_code=404, detail={"code": "duplicate_case_not_found"})
    if case.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "duplicate_case_already_reviewed"})
    case.status = payload.status
    case.reviewed_by_user_id = user.id
    case.reviewed_at = datetime.now(timezone.utc)
    case.review_note = payload.review_note.strip()
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="patient.duplicate_case.reviewed", resource_type="patient_duplicate_case",
        resource_id=str(case.id),
        metadata={"status": case.status},
    )
    db.commit()
    db.refresh(case)
    return case


@router.patch(
    "/{patient_id}/identity-documents/{document_id}/verification"
)
def verify_patient_identity_document(
    patient_id: UUID,
    document_id: UUID,
    payload: PatientIdentityDocumentVerification,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    _require_patient_role(
        db, user=user, hospital_id=hospital_id, allowed_roles=_RECORDS_VERIFIER_ROLES
    )
    document = db.scalar(select(PatientIdentityDocument).where(
        PatientIdentityDocument.id == document_id,
        PatientIdentityDocument.patient_id == patient_id,
        PatientIdentityDocument.hospital_id == hospital_id,
    ).with_for_update())
    if document is None:
        raise HTTPException(status_code=404, detail={"code": "identity_document_not_found"})
    if document.verification_status != "pending":
        raise HTTPException(status_code=409, detail={"code": "identity_document_already_reviewed"})
    document.verification_status = payload.verification_status
    document.verification_reason_code = payload.reason_code
    document.verified_by_user_id = user.id
    document.verified_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="patient.identity_document.reviewed", resource_type="patient_identity_document",
        resource_id=str(document.id),
        metadata={
            "verification_status": document.verification_status,
            "reason_code": document.verification_reason_code,
        },
    )
    db.commit()
    return {"document_id": str(document.id), "verification_status": document.verification_status}


@router.patch("/{patient_id}/status")
def update_patient_status(
    patient_id: UUID,
    payload: PatientStatusUpdate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    _require_patient_role(
        db, user=user, hospital_id=hospital_id, allowed_roles=_RECORDS_VERIFIER_ROLES
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == patient_id, Patient.hospital_id == hospital_id
    ).with_for_update())
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    if patient.status == "deceased" and payload.status != "deceased":
        raise HTTPException(status_code=409, detail={"code": "deceased_patient_status_is_terminal"})
    if patient.status == payload.status:
        raise HTTPException(status_code=409, detail={"code": "patient_status_unchanged"})
    patient.status = payload.status
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="patient.status.changed", resource_type="patient",
        resource_id=str(patient_id),
        metadata={"status": payload.status, "reason_code": payload.reason_code},
    )
    db.commit()
    return {"patient_id": str(patient_id), "status": patient.status}


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(
    patient_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Patient:
    user, hospital_id = context
    scope = _patient_read_scope(db, user=user, hospital_id=hospital_id)
    patient = db.scalar(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.hospital_id == hospital_id,
        )
    )
    if patient is None or (
        scope == "assigned" and not _has_active_patient_assignment(
            db, user_id=user.id, hospital_id=hospital_id, patient_id=patient_id
        )
    ):
        raise HTTPException(status_code=404, detail="Patient not found")
    write_audit_event(
        db,
        hospital_id=hospital_id,
        actor_user_id=user.id,
        action="patient.read",
        resource_type="patient",
        resource_id=str(patient.id),
    )
    db.commit()
    return patient
