from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    AnesthesiaRecord,
    Department,
    Encounter,
    HospitalMembership,
    Patient,
    PatientCareAssignment,
    Role,
    SurgicalCase,
    SurgicalEvent,
    SurgicalNote,
    SurgicalSafetyChecklist,
    TheatreRoom,
    User,
)
from app.schemas.surgery import (
    AnesthesiaRecordCreate,
    AnesthesiaRecordRead,
    SurgicalCaseCancel,
    SurgicalCaseCreate,
    SurgicalCaseDetailRead,
    SurgicalCaseRead,
    SurgicalEventCreate,
    SurgicalEventRead,
    SurgicalLeadSurgeonAssignmentCreate,
    SurgicalNoteCreate,
    SurgicalNoteRead,
    SurgicalSafetyChecklistCreate,
    SurgicalSafetyChecklistRead,
    SurgicalTeamAssignmentCreate,
    TheatreRoomCreate,
    TheatreRoomRead,
)

router = APIRouter(prefix="/surgery", tags=["surgery and operating theatre"])

_SURGEON_ROLES = {
    "surgeon", "general_surgeon", "orthopedic_surgeon",
    "cardiac_surgeon", "neurosurgeon",
}
_ANESTHESIA_ROLES = {
    "anesthetist", "anaesthetist", "anesthesiologist", "anaesthesiologist",
}
_THEATRE_NURSE_ROLES = {
    "theatre_nurse", "scrub_nurse", "circulating_nurse",
    "nurse", "registered_nurse", "nursing_officer",
}
_TEAM_ROLES = _SURGEON_ROLES | _ANESTHESIA_ROLES | _THEATRE_NURSE_ROLES
_THEATRE_MANAGER_ROLES = {
    "theatre_manager", "operating_theatre_manager",
    "hospital_admin", "hospital_director", "system_admin",
}
_ADMIN_ROLES = {"hospital_admin", "hospital_director", "system_admin"}


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


def _require_role(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    allowed: set[str], department_id: UUID | None = None,
    allow_manager: bool = True,
) -> tuple[HospitalMembership, str]:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or (
        role_name not in allowed and not (allow_manager and role_name in _THEATRE_MANAGER_ROLES)
    ):
        raise HTTPException(status_code=403, detail={"code": "surgery_role_not_authorized"})
    if role_name not in _THEATRE_MANAGER_ROLES and department_id is not None:
        if membership.department_id != department_id:
            raise HTTPException(status_code=403, detail={"code": "surgery_department_scope_required"})
    return membership, role_name


def _restore_tenant_context(db: Session, *, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(
        text("SELECT set_config('app.current_hospital_id', :hospital_id, true)"),
        {"hospital_id": str(hospital_id)},
    )
    db.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def _audit(
    db: Session, *, hospital_id: UUID, user_id: UUID,
    action: str, resource_type: str, resource_id: UUID | None,
) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id,
        action=action, resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
    )


def _get_case(
    db: Session, *, hospital_id: UUID, case_id: UUID, lock: bool = False
) -> SurgicalCase:
    query = select(SurgicalCase).where(
        SurgicalCase.id == case_id, SurgicalCase.hospital_id == hospital_id
    )
    if lock:
        query = query.with_for_update()
    case = db.scalar(query)
    if case is None:
        raise HTTPException(status_code=404, detail={"code": "surgical_case_not_found"})
    return case


def _has_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID, case: SurgicalCase
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == case.patient_id,
        PatientCareAssignment.encounter_id == case.encounter_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)) is not None


def _require_case_team(
    db: Session, *, user_id: UUID, hospital_id: UUID, case: SurgicalCase,
    allowed: set[str] | None = None,
    allow_manager: bool = False,
) -> str:
    allowed = allowed or _TEAM_ROLES
    _, role_name = _require_role(
        db, user_id=user_id, hospital_id=hospital_id,
        allowed=allowed, allow_manager=allow_manager,
    )
    if role_name not in _THEATRE_MANAGER_ROLES and not _has_assignment(
        db, user_id=user_id, hospital_id=hospital_id, case=case
    ):
        raise HTTPException(status_code=404, detail={"code": "assigned_surgical_case_not_found"})
    return role_name


def _latest_checklist(
    db: Session, *, hospital_id: UUID, case_id: UUID, phase: str
) -> SurgicalSafetyChecklist | None:
    return db.scalar(select(SurgicalSafetyChecklist).where(
        SurgicalSafetyChecklist.hospital_id == hospital_id,
        SurgicalSafetyChecklist.surgical_case_id == case_id,
        SurgicalSafetyChecklist.phase == phase,
    ).order_by(SurgicalSafetyChecklist.revision.desc()).limit(1))


def _checklist_passed(checklist: SurgicalSafetyChecklist | None) -> bool:
    if checklist is None:
        return False
    return all((
        checklist.patient_identity_confirmed,
        checklist.procedure_confirmed,
        (not checklist.site_marking_applicable or checklist.site_confirmed),
        checklist.consent_verified,
        checklist.allergies_reviewed,
        checklist.anesthesia_safety_confirmed,
        checklist.equipment_ready,
        (not checklist.counts_applicable or checklist.counts_confirmed),
    ))


def _case_detail(db: Session, case: SurgicalCase) -> dict:
    checklists = db.scalars(select(SurgicalSafetyChecklist).where(
        SurgicalSafetyChecklist.hospital_id == case.hospital_id,
        SurgicalSafetyChecklist.surgical_case_id == case.id,
    ).order_by(SurgicalSafetyChecklist.recorded_at)).all()
    anesthesia = db.scalar(select(AnesthesiaRecord).where(
        AnesthesiaRecord.hospital_id == case.hospital_id,
        AnesthesiaRecord.surgical_case_id == case.id,
    ))
    events = db.scalars(select(SurgicalEvent).where(
        SurgicalEvent.hospital_id == case.hospital_id,
        SurgicalEvent.surgical_case_id == case.id,
    ).order_by(SurgicalEvent.performed_at)).all()
    notes = db.scalars(select(SurgicalNote).where(
        SurgicalNote.hospital_id == case.hospital_id,
        SurgicalNote.surgical_case_id == case.id,
    ).order_by(SurgicalNote.signed_at)).all()
    return {
        "surgical_case": case,
        "checklists": checklists,
        "anesthesia": anesthesia,
        "events": events,
        "notes": notes,
    }


@router.post("/theatres", response_model=TheatreRoomRead, status_code=status.HTTP_201_CREATED)
def create_theatre_room(
    payload: TheatreRoomCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> TheatreRoom:
    user, hospital_id = context
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=set(),
    )
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "theatre_department_not_found"})
    theatre = TheatreRoom(hospital_id=hospital_id, **payload.model_dump())
    db.add(theatre)
    try:
        db.flush()
        _audit(db, hospital_id=hospital_id, user_id=user.id,
               action="surgery.theatre.created", resource_type="theatre_room", resource_id=theatre.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "theatre_code_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(theatre)
    return theatre


@router.get("/theatres", response_model=list[TheatreRoomRead])
def list_theatres(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    department_id: UUID | None = None,
    active_only: bool = True,
) -> list[TheatreRoom]:
    user, hospital_id = context
    membership, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_SURGEON_ROLES | _ANESTHESIA_ROLES | _THEATRE_NURSE_ROLES,
    )
    query = select(TheatreRoom).where(TheatreRoom.hospital_id == hospital_id)
    if role_name in _THEATRE_MANAGER_ROLES:
        if department_id is not None:
            query = query.where(TheatreRoom.department_id == department_id)
    elif role_name not in _SURGEON_ROLES | _ANESTHESIA_ROLES | {"theatre_nurse", "scrub_nurse", "circulating_nurse"}:
        if department_id is not None and department_id != membership.department_id:
            raise HTTPException(status_code=403, detail={"code": "surgery_department_scope_required"})
        query = query.where(TheatreRoom.department_id == membership.department_id)
    elif department_id is not None:
        query = query.where(TheatreRoom.department_id == department_id)
    if active_only:
        query = query.where(TheatreRoom.status == "active")
    rooms = list(db.scalars(query.order_by(TheatreRoom.name)).all())
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.theatres.viewed", resource_type="theatre_room_list", resource_id=None)
    db.commit()
    return rooms


@router.post("/encounters/{encounter_id}/lead-surgeon-assignment", status_code=status.HTTP_201_CREATED)
def assign_lead_surgeon_to_encounter(
    encounter_id: UUID,
    payload: SurgicalLeadSurgeonAssignmentCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id, allowed=set(),
    )
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None or encounter.status != "in_progress":
        raise HTTPException(status_code=404, detail={"code": "active_surgical_encounter_not_found"})
    theatre = db.scalar(select(TheatreRoom).where(
        TheatreRoom.id == payload.theatre_room_id,
        TheatreRoom.hospital_id == hospital_id,
        TheatreRoom.status == "active",
    ).with_for_update())
    if theatre is None:
        raise HTTPException(status_code=404, detail={"code": "active_theatre_not_found"})
    surgeon_membership = _membership(db, user_id=payload.surgeon_user_id, hospital_id=hospital_id)
    surgeon_role = _role_name(db, surgeon_membership)
    if (
        surgeon_membership is None
        or surgeon_membership.department_id is None
        or surgeon_role not in _SURGEON_ROLES
    ):
        raise HTTPException(status_code=422, detail={"code": "lead_surgeon_role_required"})
    if _has_assignment_for_encounter(
        db, user_id=payload.surgeon_user_id, hospital_id=hospital_id,
        patient_id=encounter.patient_id, encounter_id=encounter.id,
    ):
        raise HTTPException(status_code=409, detail={"code": "lead_surgeon_already_assigned"})
    assignment = PatientCareAssignment(
        hospital_id=hospital_id,
        patient_id=encounter.patient_id,
        staff_user_id=payload.surgeon_user_id,
        assigned_by_user_id=user.id,
        department_id=surgeon_membership.department_id,
        encounter_id=encounter.id,
        assignment_reason=payload.assignment_reason,
        status="active",
        valid_from=datetime.now(timezone.utc),
        valid_until=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(assignment)
    db.flush()
    _audit(
        db, hospital_id=hospital_id, user_id=user.id,
        action="surgery.lead_surgeon.assigned",
        resource_type="patient_care_assignment", resource_id=assignment.id,
    )
    db.commit()
    return {"assignment_id": assignment.id, "surgeon_user_id": payload.surgeon_user_id}


@router.post("/cases", response_model=SurgicalCaseRead, status_code=status.HTTP_201_CREATED)
def schedule_surgical_case(
    payload: SurgicalCaseCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalCase:
    user, hospital_id = context
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == payload.encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None:
        raise HTTPException(status_code=404, detail={"code": "surgical_encounter_not_found"})
    if encounter.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "surgical_encounter_not_active"})
    patient = db.scalar(select(Patient).where(
        Patient.id == encounter.patient_id, Patient.hospital_id == hospital_id
    ).with_for_update())
    if patient is None or patient.status != "active":
        raise HTTPException(status_code=409, detail={"code": "surgical_patient_not_active"})
    theatre = db.scalar(select(TheatreRoom).where(
        TheatreRoom.id == payload.theatre_room_id,
        TheatreRoom.hospital_id == hospital_id,
    ).with_for_update())
    if theatre is None or theatre.status != "active":
        raise HTTPException(status_code=404, detail={"code": "active_theatre_not_found"})
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_SURGEON_ROLES, allow_manager=False,
    )
    surgeon_assignment = db.scalar(select(PatientCareAssignment).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == patient.id,
        PatientCareAssignment.encounter_id == encounter.id,
        PatientCareAssignment.staff_user_id == user.id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= datetime.now(timezone.utc),
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > datetime.now(timezone.utc),
        ),
    ).with_for_update())
    if surgeon_assignment is None:
        raise HTTPException(status_code=403, detail={"code": "assigned_surgeon_required"})
    minimum_assignment_until = payload.scheduled_end_at + timedelta(hours=24)
    if (
        surgeon_assignment.valid_until is not None
        and surgeon_assignment.valid_until < minimum_assignment_until
    ):
        surgeon_assignment.valid_until = minimum_assignment_until
    surgeon_row = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if surgeon_row is None:
        raise HTTPException(status_code=404, detail={"code": "surgeon_user_not_found"})
    resource_conflict = or_(
        SurgicalCase.theatre_room_id == theatre.id,
        SurgicalCase.surgeon_user_id == user.id,
        SurgicalCase.patient_id == patient.id,
    )
    overlap = db.scalar(select(SurgicalCase.id).where(
        SurgicalCase.hospital_id == hospital_id,
        or_(
            and_(
                SurgicalCase.status.in_(("in_progress", "recovery")),
                resource_conflict,
            ),
            and_(
                SurgicalCase.status == "scheduled",
                SurgicalCase.scheduled_start_at < payload.scheduled_end_at,
                SurgicalCase.scheduled_end_at > payload.scheduled_start_at,
                resource_conflict,
            ),
        ),
    ).limit(1))
    if overlap is not None:
        raise HTTPException(status_code=409, detail={"code": "theatre_surgeon_or_patient_schedule_conflict"})
    surgical_case = SurgicalCase(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        theatre_room_id=theatre.id,
        surgeon_user_id=user.id,
        requested_by_user_id=user.id,
        planned_procedure=payload.planned_procedure,
        urgency=payload.urgency,
        status="scheduled",
        scheduled_start_at=payload.scheduled_start_at,
        scheduled_end_at=payload.scheduled_end_at,
    )
    db.add(surgical_case)
    try:
        db.flush()
        _audit(db, hospital_id=hospital_id, user_id=user.id,
               action="surgery.case.scheduled", resource_type="surgical_case", resource_id=surgical_case.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "surgical_case_schedule_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(surgical_case)
    return surgical_case


def _has_assignment_for_encounter(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    patient_id: UUID, encounter_id: UUID,
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == patient_id,
        PatientCareAssignment.encounter_id == encounter_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)) is not None


@router.get("/cases", response_model=list[SurgicalCaseRead])
def list_surgical_cases(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    case_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[SurgicalCase]:
    user, hospital_id = context
    membership, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_TEAM_ROLES,
    )
    query = select(SurgicalCase).where(SurgicalCase.hospital_id == hospital_id)
    if role_name not in _THEATRE_MANAGER_ROLES:
        now = datetime.now(timezone.utc)
        assigned_encounters = select(PatientCareAssignment.encounter_id).where(
            PatientCareAssignment.hospital_id == hospital_id,
            PatientCareAssignment.staff_user_id == user.id,
            PatientCareAssignment.department_id == membership.department_id,
            PatientCareAssignment.status == "active",
            PatientCareAssignment.valid_from <= now,
            or_(
                PatientCareAssignment.valid_until.is_(None),
                PatientCareAssignment.valid_until > now,
            ),
        )
        query = query.where(
            SurgicalCase.encounter_id.in_(assigned_encounters)
        )
    if case_status is not None:
        query = query.where(SurgicalCase.status == case_status)
    cases = list(db.scalars(
        query.order_by(SurgicalCase.scheduled_start_at).limit(limit).offset(offset)
    ).all())
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.cases.viewed", resource_type="surgical_case_list", resource_id=None)
    db.commit()
    return cases


@router.get("/cases/{case_id}", response_model=SurgicalCaseDetailRead)
def get_surgical_case(
    case_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id)
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if role_name not in _ADMIN_ROLES:
        _require_case_team(db, user_id=user.id, hospital_id=hospital_id, case=surgical_case)
    result = _case_detail(db, surgical_case)
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.case.viewed", resource_type="surgical_case", resource_id=surgical_case.id)
    db.commit()
    return result


@router.post("/cases/{case_id}/team", status_code=status.HTTP_201_CREATED)
def assign_surgical_team_member(
    case_id: UUID,
    payload: SurgicalTeamAssignmentCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    theatre = db.scalar(select(TheatreRoom).where(
        TheatreRoom.id == surgical_case.theatre_room_id,
        TheatreRoom.hospital_id == hospital_id,
    ))
    _, actor_role = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_SURGEON_ROLES,
    )
    if actor_role not in _THEATRE_MANAGER_ROLES and (
        surgical_case.surgeon_user_id != user.id
        or not _has_assignment(db, user_id=user.id, hospital_id=hospital_id, case=surgical_case)
    ):
        raise HTTPException(status_code=403, detail={"code": "lead_surgeon_or_theatre_manager_required"})
    if surgical_case.status not in {"scheduled", "in_progress"}:
        raise HTTPException(status_code=409, detail={"code": "surgical_case_team_locked"})
    staff_membership = _membership(db, user_id=payload.staff_user_id, hospital_id=hospital_id)
    staff_role = _role_name(db, staff_membership)
    if (
        theatre is None or staff_membership is None
        or staff_membership.department_id is None
        or staff_role not in _TEAM_ROLES
    ):
        raise HTTPException(status_code=422, detail={"code": "surgical_team_member_not_valid_for_theatre"})
    if _has_assignment_for_encounter(
        db, user_id=payload.staff_user_id, hospital_id=hospital_id,
        patient_id=surgical_case.patient_id, encounter_id=surgical_case.encounter_id,
    ):
        raise HTTPException(status_code=409, detail={"code": "surgical_team_member_already_assigned"})
    assignment = PatientCareAssignment(
        hospital_id=hospital_id,
        patient_id=surgical_case.patient_id,
        staff_user_id=payload.staff_user_id,
        assigned_by_user_id=user.id,
        department_id=staff_membership.department_id,
        encounter_id=surgical_case.encounter_id,
        assignment_reason=payload.assignment_reason,
        status="active",
        valid_from=datetime.now(timezone.utc),
    )
    db.add(assignment)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.team.assigned", resource_type="patient_care_assignment", resource_id=assignment.id)
    db.commit()
    return {"assignment_id": assignment.id, "staff_user_id": payload.staff_user_id}


@router.post(
    "/cases/{case_id}/checklists",
    response_model=SurgicalSafetyChecklistRead,
    status_code=status.HTTP_201_CREATED,
)
def record_surgical_checklist(
    case_id: UUID,
    payload: SurgicalSafetyChecklistCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalSafetyChecklist:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    _require_case_team(db, user_id=user.id, hospital_id=hospital_id, case=surgical_case)
    if payload.phase in {"sign_in", "time_out"} and surgical_case.status != "scheduled":
        raise HTTPException(status_code=409, detail={"code": "preoperative_checklist_requires_scheduled_case"})
    if payload.phase == "sign_out" and surgical_case.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "sign_out_checklist_requires_active_surgery"})
    latest = _latest_checklist(
        db, hospital_id=hospital_id, case_id=surgical_case.id, phase=payload.phase
    )
    checklist = SurgicalSafetyChecklist(
        hospital_id=hospital_id,
        surgical_case_id=surgical_case.id,
        revision=(latest.revision + 1) if latest else 1,
        recorded_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(checklist)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.checklist.recorded", resource_type="surgical_checklist", resource_id=checklist.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(checklist)
    return checklist


@router.post(
    "/cases/{case_id}/anesthesia",
    response_model=AnesthesiaRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_anesthesia_record(
    case_id: UUID,
    payload: AnesthesiaRecordCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> AnesthesiaRecord:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    _require_case_team(
        db, user_id=user.id, hospital_id=hospital_id,
        case=surgical_case, allowed=_ANESTHESIA_ROLES,
    )
    if surgical_case.status != "scheduled":
        raise HTTPException(status_code=409, detail={"code": "anesthesia_record_requires_scheduled_case"})
    existing = db.scalar(select(AnesthesiaRecord.id).where(
        AnesthesiaRecord.hospital_id == hospital_id,
        AnesthesiaRecord.surgical_case_id == surgical_case.id,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "anesthesia_record_already_exists"})
    if (
        payload.started_at < surgical_case.scheduled_start_at - timedelta(hours=12)
        or payload.started_at > surgical_case.scheduled_end_at
    ):
        raise HTTPException(status_code=422, detail={"code": "anesthesia_start_time_outside_case_window"})
    record = AnesthesiaRecord(
        hospital_id=hospital_id,
        surgical_case_id=surgical_case.id,
        anesthesia_provider_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(record)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.anesthesia.recorded", resource_type="anesthesia_record", resource_id=record.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(record)
    return record


@router.post(
    "/cases/{case_id}/events",
    response_model=SurgicalEventRead,
    status_code=status.HTTP_201_CREATED,
)
def record_surgical_event(
    case_id: UUID,
    payload: SurgicalEventCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalEvent:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    _require_case_team(db, user_id=user.id, hospital_id=hospital_id, case=surgical_case)
    if surgical_case.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "surgical_event_requires_active_case"})
    if surgical_case.actual_started_at is None or payload.performed_at < surgical_case.actual_started_at:
        raise HTTPException(status_code=422, detail={"code": "surgical_event_before_actual_start"})
    event = SurgicalEvent(
        hospital_id=hospital_id,
        surgical_case_id=surgical_case.id,
        performed_by_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(event)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.event.recorded", resource_type="surgical_event", resource_id=event.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(event)
    return event


@router.post(
    "/cases/{case_id}/notes",
    response_model=SurgicalNoteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_surgical_note(
    case_id: UUID,
    payload: SurgicalNoteCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalNote:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    _require_case_team(db, user_id=user.id, hospital_id=hospital_id, case=surgical_case)
    if surgical_case.status not in {"scheduled", "in_progress", "recovery"}:
        raise HTTPException(status_code=409, detail={"code": "surgical_case_not_open_for_notes"})
    if payload.note_type == "operative" and surgical_case.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "operative_note_requires_active_surgery"})
    if payload.note_type == "post_op" and surgical_case.status != "recovery":
        raise HTTPException(status_code=409, detail={"code": "post_op_note_requires_recovery"})
    note = SurgicalNote(
        hospital_id=hospital_id,
        surgical_case_id=surgical_case.id,
        author_user_id=user.id,
        **payload.model_dump(),
    )
    db.add(note)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.note.signed", resource_type="surgical_note", resource_id=note.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(note)
    return note


@router.post("/cases/{case_id}/start", response_model=SurgicalCaseRead)
def start_surgical_case(
    case_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalCase:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    role_name = _require_case_team(
        db, user_id=user.id, hospital_id=hospital_id,
        case=surgical_case, allowed=_SURGEON_ROLES,
    )
    if surgical_case.surgeon_user_id != user.id or role_name not in _SURGEON_ROLES:
        raise HTTPException(status_code=403, detail={"code": "lead_surgeon_required"})
    if surgical_case.status != "scheduled":
        raise HTTPException(status_code=409, detail={"code": "surgical_case_not_scheduled"})
    if not _checklist_passed(_latest_checklist(
        db, hospital_id=hospital_id, case_id=surgical_case.id, phase="sign_in"
    )):
        raise HTTPException(status_code=409, detail={"code": "sign_in_checklist_incomplete"})
    if not _checklist_passed(_latest_checklist(
        db, hospital_id=hospital_id, case_id=surgical_case.id, phase="time_out"
    )):
        raise HTTPException(status_code=409, detail={"code": "time_out_checklist_incomplete"})
    anesthesia = db.scalar(select(AnesthesiaRecord).where(
        AnesthesiaRecord.hospital_id == hospital_id,
        AnesthesiaRecord.surgical_case_id == surgical_case.id,
    ))
    now = datetime.now(timezone.utc)
    if anesthesia is None or anesthesia.started_at > now:
        raise HTTPException(status_code=409, detail={"code": "valid_anesthesia_record_required"})
    surgical_case.status = "in_progress"
    surgical_case.actual_started_at = now
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.case.started", resource_type="surgical_case", resource_id=surgical_case.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(surgical_case)
    return surgical_case


@router.post("/cases/{case_id}/complete-procedure", response_model=SurgicalCaseRead)
def complete_surgical_procedure(
    case_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalCase:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    role_name = _require_case_team(
        db, user_id=user.id, hospital_id=hospital_id,
        case=surgical_case, allowed=_SURGEON_ROLES,
    )
    if surgical_case.surgeon_user_id != user.id or role_name not in _SURGEON_ROLES:
        raise HTTPException(status_code=403, detail={"code": "lead_surgeon_required"})
    if surgical_case.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "surgical_case_not_in_progress"})
    if not _checklist_passed(_latest_checklist(
        db, hospital_id=hospital_id, case_id=surgical_case.id, phase="sign_out"
    )):
        raise HTTPException(status_code=409, detail={"code": "sign_out_checklist_incomplete"})
    operative_note = db.scalar(select(SurgicalNote.id).where(
        SurgicalNote.hospital_id == hospital_id,
        SurgicalNote.surgical_case_id == surgical_case.id,
        SurgicalNote.note_type == "operative",
    ))
    if operative_note is None:
        raise HTTPException(status_code=409, detail={"code": "signed_operative_note_required"})
    now = datetime.now(timezone.utc)
    surgical_case.status = "recovery"
    surgical_case.actual_ended_at = now
    anesthesia = db.scalar(select(AnesthesiaRecord).where(
        AnesthesiaRecord.hospital_id == hospital_id,
        AnesthesiaRecord.surgical_case_id == surgical_case.id,
    ).with_for_update())
    if anesthesia is not None and anesthesia.ended_at is None:
        if now <= anesthesia.started_at:
            raise HTTPException(status_code=409, detail={"code": "anesthesia_start_time_not_before_completion"})
        anesthesia.ended_at = now
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.procedure.completed", resource_type="surgical_case", resource_id=surgical_case.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(surgical_case)
    return surgical_case


@router.post("/cases/{case_id}/complete-recovery", response_model=SurgicalCaseRead)
def complete_surgical_recovery(
    case_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalCase:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    role_name = _require_case_team(
        db, user_id=user.id, hospital_id=hospital_id, case=surgical_case,
        allowed=_SURGEON_ROLES,
    )
    if surgical_case.surgeon_user_id != user.id or role_name not in _SURGEON_ROLES:
        raise HTTPException(status_code=403, detail={"code": "lead_surgeon_required"})
    if surgical_case.status != "recovery":
        raise HTTPException(status_code=409, detail={"code": "surgical_case_not_in_recovery"})
    recovery_note = db.scalar(select(SurgicalNote.id).where(
        SurgicalNote.hospital_id == hospital_id,
        SurgicalNote.surgical_case_id == surgical_case.id,
        SurgicalNote.note_type.in_(("post_op", "handover")),
    ))
    if recovery_note is None:
        raise HTTPException(status_code=409, detail={"code": "signed_recovery_handover_note_required"})
    surgical_case.status = "completed"
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.recovery.completed", resource_type="surgical_case", resource_id=surgical_case.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(surgical_case)
    return surgical_case


@router.post("/cases/{case_id}/cancel", response_model=SurgicalCaseRead)
def cancel_surgical_case(
    case_id: UUID,
    payload: SurgicalCaseCancel,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> SurgicalCase:
    user, hospital_id = context
    surgical_case = _get_case(db, hospital_id=hospital_id, case_id=case_id, lock=True)
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if role_name in _THEATRE_MANAGER_ROLES:
        pass
    elif role_name in _SURGEON_ROLES and surgical_case.surgeon_user_id == user.id:
        if not _has_assignment(db, user_id=user.id, hospital_id=hospital_id, case=surgical_case):
            raise HTTPException(status_code=403, detail={"code": "assigned_lead_surgeon_required"})
    else:
        raise HTTPException(status_code=403, detail={"code": "lead_surgeon_or_theatre_manager_required"})
    if surgical_case.status != "scheduled":
        raise HTTPException(status_code=409, detail={"code": "only_scheduled_surgical_case_can_be_cancelled"})
    surgical_case.status = "cancelled"
    surgical_case.cancellation_reason = payload.reason
    surgical_case.cancelled_at = datetime.now(timezone.utc)
    surgical_case.cancelled_by_user_id = user.id
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="surgery.case.cancelled", resource_type="surgical_case", resource_id=surgical_case.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(surgical_case)
    return surgical_case
