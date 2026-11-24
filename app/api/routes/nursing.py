from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select, text, text
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    Encounter,
    HospitalMembership,
    NursingAssessment,
    NursingCarePlan,
    NursingCarePlanReview,
    NursingNote,
    NursingObservation,
    PatientCareAssignment,
    Role,
)
from app.schemas.nursing import (
    NursingAssessmentCreate,
    NursingAssessmentRead,
    NursingCarePlanCreate,
    NursingCarePlanRead,
    NursingCarePlanReviewCreate,
    NursingCarePlanReviewRead,
    NursingNoteCreate,
    NursingNoteRead,
    NursingObservationCreate,
    NursingObservationRead,
)

router = APIRouter(prefix="/nursing", tags=["nursing"])

_NURSING_ROLES = {
    "nurse", "registered_nurse", "nursing_officer", "midwife",
    "nursing_supervisor", "head_nurse",
}


def _membership(db: Session, *, user_id: UUID, hospital_id: UUID):
    return db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user_id,
            HospitalMembership.status == "active",
        )
    )


def _role_name(db: Session, membership: HospitalMembership | None) -> str:
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _restore_tenant_context(db: Session, *, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(hospital_id)},
    )
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def _require_assigned_encounter(
    db: Session,
    *,
    user_id: UUID,
    hospital_id: UUID,
    encounter_id: UUID,
    require_open: bool = True,
) -> Encounter:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _NURSING_ROLES:
        raise HTTPException(status_code=403, detail={"code": "nursing_role_required"})
    if membership.department_id is None:
        raise HTTPException(status_code=403, detail={"code": "nursing_department_required"})

    now = datetime.now(timezone.utc)
    assignment = db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.department_id == membership.department_id,
        PatientCareAssignment.encounter_id == encounter_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1))
    if assignment is None:
        raise HTTPException(status_code=404, detail={"code": "assigned_nursing_encounter_not_found"})

    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
        Encounter.department_id == membership.department_id,
    ))
    if encounter is None:
        raise HTTPException(status_code=404, detail={"code": "nursing_encounter_not_found"})
    if require_open and encounter.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "nursing_encounter_not_open"})
    return encounter


def _require_assigned_care_plan(
    db: Session, *, user_id: UUID, hospital_id: UUID, care_plan_id: UUID
) -> NursingCarePlan:
    plan = db.scalar(select(NursingCarePlan).where(
        NursingCarePlan.id == care_plan_id,
        NursingCarePlan.hospital_id == hospital_id,
    ).with_for_update())
    if plan is None:
        raise HTTPException(status_code=404, detail={"code": "nursing_care_plan_not_found"})
    _require_assigned_encounter(
        db, user_id=user_id, hospital_id=hospital_id,
        encounter_id=plan.encounter_id,
    )
    if plan.status != "active":
        raise HTTPException(status_code=409, detail={"code": "nursing_care_plan_not_active"})
    return plan


def _audit(
    db: Session, *, hospital_id: UUID, user_id: UUID,
    action: str, resource_type: str, resource_id: UUID,
) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id,
        action=action, resource_type=resource_type,
        resource_id=str(resource_id),
    )


@router.post(
    "/encounters/{encounter_id}/assessments",
    response_model=NursingAssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_nursing_assessment(
    encounter_id: UUID,
    payload: NursingAssessmentCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NursingAssessment:
    user, hospital_id = context
    encounter = _require_assigned_encounter(
        db, user_id=user.id, hospital_id=hospital_id, encounter_id=encounter_id,
    )
    assessment = NursingAssessment(
        hospital_id=hospital_id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        department_id=encounter.department_id,
        assessed_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(assessment)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="nursing.assessment.recorded",
        resource_type="nursing_assessment", resource_id=assessment.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(assessment)
    return assessment


@router.post(
    "/encounters/{encounter_id}/observations",
    response_model=NursingObservationRead,
    status_code=status.HTTP_201_CREATED,
)
def record_nursing_observation(
    encounter_id: UUID,
    payload: NursingObservationCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NursingObservation:
    user, hospital_id = context
    encounter = _require_assigned_encounter(
        db, user_id=user.id, hospital_id=hospital_id, encounter_id=encounter_id,
    )
    observation = NursingObservation(
        hospital_id=hospital_id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        recorded_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(observation)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="nursing.observation.recorded",
        resource_type="nursing_observation", resource_id=observation.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(observation)
    return observation


@router.post(
    "/encounters/{encounter_id}/notes",
    response_model=NursingNoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_nursing_note(
    encounter_id: UUID,
    payload: NursingNoteCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NursingNote:
    user, hospital_id = context
    encounter = _require_assigned_encounter(
        db, user_id=user.id, hospital_id=hospital_id, encounter_id=encounter_id,
    )
    note = NursingNote(
        hospital_id=hospital_id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        author_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(note)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="nursing.note.signed",
        resource_type="nursing_note", resource_id=note.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(note)
    return note


@router.post(
    "/encounters/{encounter_id}/care-plans",
    response_model=NursingCarePlanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_nursing_care_plan(
    encounter_id: UUID,
    payload: NursingCarePlanCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NursingCarePlan:
    user, hospital_id = context
    encounter = _require_assigned_encounter(
        db, user_id=user.id, hospital_id=hospital_id, encounter_id=encounter_id,
    )
    plan = NursingCarePlan(
        hospital_id=hospital_id,
        patient_id=encounter.patient_id,
        encounter_id=encounter.id,
        department_id=encounter.department_id,
        created_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(plan)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="nursing.care_plan.created",
        resource_type="nursing_care_plan", resource_id=plan.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(plan)
    return plan


@router.post(
    "/care-plans/{care_plan_id}/reviews",
    response_model=NursingCarePlanReviewRead,
    status_code=status.HTTP_201_CREATED,
)
def review_nursing_care_plan(
    care_plan_id: UUID,
    payload: NursingCarePlanReviewCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NursingCarePlanReview:
    user, hospital_id = context
    plan = _require_assigned_care_plan(
        db, user_id=user.id, hospital_id=hospital_id, care_plan_id=care_plan_id,
    )
    review = NursingCarePlanReview(
        hospital_id=hospital_id,
        care_plan_id=plan.id,
        reviewed_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(review)
    if payload.outcome == "achieved":
        plan.status = "completed"
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="nursing.care_plan.reviewed",
        resource_type="nursing_care_plan", resource_id=plan.id,
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(review)
    return review


@router.post("/care-plans/{care_plan_id}/close", response_model=NursingCarePlanRead)
def close_nursing_care_plan(
    care_plan_id: UUID,
    cancelled: bool = False,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> NursingCarePlan:
    user, hospital_id = context
    plan = _require_assigned_care_plan(
        db, user_id=user.id, hospital_id=hospital_id, care_plan_id=care_plan_id,
    )
    plan.status = "cancelled" if cancelled else "completed"
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="nursing.care_plan.closed",
        resource_type="nursing_care_plan", resource_id=plan.id,
    )
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/encounters/{encounter_id}/records")
def get_nursing_encounter_records(
    encounter_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    encounter = _require_assigned_encounter(
        db, user_id=user.id, hospital_id=hospital_id,
        encounter_id=encounter_id, require_open=False,
    )
    assessments = db.scalars(select(NursingAssessment).where(
        NursingAssessment.hospital_id == hospital_id,
        NursingAssessment.encounter_id == encounter.id,
    ).order_by(NursingAssessment.assessed_at.desc()).limit(100)).all()
    observations = db.scalars(select(NursingObservation).where(
        NursingObservation.hospital_id == hospital_id,
        NursingObservation.encounter_id == encounter.id,
    ).order_by(NursingObservation.observed_at.desc()).limit(500)).all()
    notes = db.scalars(select(NursingNote).where(
        NursingNote.hospital_id == hospital_id,
        NursingNote.encounter_id == encounter.id,
    ).order_by(NursingNote.signed_at.desc()).limit(200)).all()
    plans = db.scalars(select(NursingCarePlan).where(
        NursingCarePlan.hospital_id == hospital_id,
        NursingCarePlan.encounter_id == encounter.id,
    ).order_by(NursingCarePlan.created_at.desc()).limit(100)).all()
    plan_ids = [plan.id for plan in plans]
    reviews = db.scalars(select(NursingCarePlanReview).where(
        NursingCarePlanReview.hospital_id == hospital_id,
        NursingCarePlanReview.care_plan_id.in_(plan_ids),
    ).order_by(NursingCarePlanReview.reviewed_at.desc())).all() if plan_ids else []
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="nursing.encounter.records_viewed",
        resource_type="encounter", resource_id=encounter.id,
    )
    db.commit()
    return {
        "encounter_id": encounter.id,
        "patient_id": encounter.patient_id,
        "assessments": assessments,
        "observations": observations,
        "notes": notes,
        "care_plans": plans,
        "care_plan_reviews": reviews,
    }
