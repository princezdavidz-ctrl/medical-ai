from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    BedAssignment,
    Department,
    Encounter,
    HospitalBed,
    HospitalMembership,
    InpatientAdmission,
    Patient,
    PatientCareAssignment,
    Role,
    Ward,
)
from app.schemas.inpatient import (
    AdmissionCreate,
    AdmissionRead,
    BedAssignmentCreate,
    BedAssignmentRead,
    BedCreate,
    BedRead,
    CareTeamAssignmentCreate,
    InpatientDischargeCreate,
    WardCreate,
    WardRead,
)

router = APIRouter(prefix="/inpatient", tags=["inpatient and ward management"])

_CLINICIAN_ROLES = {
    "doctor", "physician", "medical_officer", "clinician",
    "surgeon", "pediatrician", "midwife",
}
_NURSING_ROLES = {
    "nurse", "registered_nurse", "nursing_officer", "nursing_supervisor",
    "head_nurse", "midwife",
}
_WARD_ADMIN_ROLES = {
    "bed_manager", "ward_manager", "ward_clerk",
    "hospital_admin", "hospital_director", "system_admin",
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


def _require_role(
    db: Session,
    *,
    user_id: UUID,
    hospital_id: UUID,
    allowed: set[str],
    department_id: UUID | None = None,
    allow_ward_admin: bool = True,
) -> tuple[HospitalMembership, str]:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or (
        role_name not in allowed and not (allow_ward_admin and role_name in _WARD_ADMIN_ROLES)
    ):
        raise HTTPException(status_code=403, detail={"code": "inpatient_role_not_authorized"})
    if role_name not in _WARD_ADMIN_ROLES and department_id is not None:
        if membership.department_id != department_id:
            raise HTTPException(status_code=403, detail={"code": "inpatient_department_scope_required"})
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


def _has_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID, encounter_id: UUID,
    department_id: UUID,
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.encounter_id == encounter_id,
        PatientCareAssignment.department_id == department_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)) is not None


def _require_source_encounter(
    db: Session, *, user_id: UUID, hospital_id: UUID, encounter_id: UUID
) -> Encounter:
    membership, _ = _require_role(
        db, user_id=user_id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, allow_ward_admin=False,
    )
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None:
        raise HTTPException(status_code=404, detail={"code": "source_encounter_not_found"})
    if membership.department_id != encounter.department_id or not _has_assignment(
        db, user_id=user_id, hospital_id=hospital_id,
        encounter_id=encounter.id, department_id=encounter.department_id,
    ):
        raise HTTPException(status_code=404, detail={"code": "source_encounter_not_found"})
    if encounter.status not in {"in_progress", "admission_requested"}:
        raise HTTPException(status_code=409, detail={"code": "source_encounter_not_eligible_for_admission"})
    return encounter


def _get_admission(
    db: Session, *, hospital_id: UUID, admission_id: UUID, lock: bool = False
) -> InpatientAdmission:
    query = select(InpatientAdmission).where(
        InpatientAdmission.id == admission_id,
        InpatientAdmission.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    admission = db.scalar(query)
    if admission is None:
        raise HTTPException(status_code=404, detail={"code": "inpatient_admission_not_found"})
    return admission


def _require_admission_access(
    db: Session, *, user_id: UUID, hospital_id: UUID, admission: InpatientAdmission
) -> tuple[HospitalMembership, str]:
    ward = db.scalar(select(Ward).where(
        Ward.id == admission.ward_id, Ward.hospital_id == hospital_id
    ))
    if ward is None:
        raise HTTPException(status_code=404, detail={"code": "inpatient_admission_not_found"})
    membership, role_name = _require_role(
        db, user_id=user_id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES | _NURSING_ROLES,
    )
    if role_name in _WARD_ADMIN_ROLES:
        return membership, role_name
    if role_name in _CLINICIAN_ROLES and admission.requested_by_user_id == user_id:
        return membership, role_name
    if membership.department_id != ward.department_id or not _has_assignment(
        db, user_id=user_id, hospital_id=hospital_id,
        encounter_id=admission.encounter_id, department_id=ward.department_id,
    ):
        raise HTTPException(status_code=404, detail={"code": "inpatient_admission_not_found"})
    return membership, role_name


def _audit(db: Session, *, hospital_id: UUID, user_id: UUID,
           action: str, resource_type: str, resource_id: UUID | None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id,
        action=action, resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
    )


@router.post("/wards", response_model=WardRead, status_code=status.HTTP_201_CREATED)
def create_ward(
    payload: WardCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Ward:
    user, hospital_id = context
    _require_role(db, user_id=user.id, hospital_id=hospital_id, allowed=set())
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "ward_department_not_found"})
    ward = Ward(hospital_id=hospital_id, **payload.model_dump())
    db.add(ward)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.ward.created", resource_type="ward", resource_id=ward.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "ward_code_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(ward)
    return ward


@router.get("/wards", response_model=list[WardRead])
def list_wards(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    department_id: UUID | None = None,
    active_only: bool = True,
) -> list[Ward]:
    user, hospital_id = context
    membership, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES | _NURSING_ROLES,
    )
    query = select(Ward).where(Ward.hospital_id == hospital_id)
    if role_name not in _WARD_ADMIN_ROLES:
        if department_id is not None and department_id != membership.department_id:
            raise HTTPException(status_code=403, detail={"code": "inpatient_department_scope_required"})
        query = query.where(Ward.department_id == membership.department_id)
    elif department_id is not None:
        query = query.where(Ward.department_id == department_id)
    if active_only:
        query = query.where(Ward.status == "active")
    wards = list(db.scalars(query.order_by(Ward.name)).all())
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.wards.viewed", resource_type="ward_list", resource_id=None)
    db.commit()
    return wards


@router.post("/wards/{ward_id}/beds", response_model=BedRead, status_code=status.HTTP_201_CREATED)
def create_bed(
    ward_id: UUID,
    payload: BedCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> HospitalBed:
    user, hospital_id = context
    _require_role(db, user_id=user.id, hospital_id=hospital_id, allowed=set())
    ward = db.scalar(select(Ward).where(
        Ward.id == ward_id, Ward.hospital_id == hospital_id, Ward.status == "active"
    ))
    if ward is None:
        raise HTTPException(status_code=404, detail={"code": "active_ward_not_found"})
    bed = HospitalBed(hospital_id=hospital_id, ward_id=ward.id, **payload.model_dump())
    db.add(bed)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.bed.created", resource_type="hospital_bed", resource_id=bed.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "bed_number_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(bed)
    return bed


@router.get("/wards/{ward_id}/beds", response_model=list[BedRead])
def list_ward_beds(
    ward_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status", max_length=24),
) -> list[HospitalBed]:
    user, hospital_id = context
    ward = db.scalar(select(Ward).where(
        Ward.id == ward_id, Ward.hospital_id == hospital_id
    ))
    if ward is None:
        raise HTTPException(status_code=404, detail={"code": "ward_not_found"})
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES | _NURSING_ROLES,
        department_id=ward.department_id,
    )
    query = select(HospitalBed).where(
        HospitalBed.hospital_id == hospital_id, HospitalBed.ward_id == ward.id
    )
    if status_filter is not None:
        query = query.where(HospitalBed.status == status_filter)
    beds = list(db.scalars(query.order_by(HospitalBed.bed_number)).all())
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.beds.viewed", resource_type="hospital_bed_list",
           resource_id=None)
    db.commit()
    return beds


@router.post("/admissions", response_model=AdmissionRead, status_code=status.HTTP_201_CREATED)
def request_admission(
    payload: AdmissionCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InpatientAdmission:
    user, hospital_id = context
    source = _require_source_encounter(
        db, user_id=user.id, hospital_id=hospital_id,
        encounter_id=payload.source_encounter_id,
    )
    patient = db.scalar(select(Patient).where(
        Patient.id == source.patient_id, Patient.hospital_id == hospital_id
    ).with_for_update())
    if patient is None or patient.status != "active":
        raise HTTPException(status_code=409, detail={"code": "admission_patient_not_active"})
    ward = db.scalar(select(Ward).where(
        Ward.id == payload.ward_id,
        Ward.hospital_id == hospital_id,
        Ward.status == "active",
    ))
    if ward is None:
        raise HTTPException(status_code=404, detail={"code": "active_ward_not_found"})
    now = datetime.now(timezone.utc)
    inpatient_encounter = Encounter(
        hospital_id=hospital_id,
        patient_id=patient.id,
        department_id=ward.department_id,
        encounter_type="inpatient",
        status="admission_requested",
        chief_complaint=payload.admission_reason,
        started_at=now,
    )
    db.add(inpatient_encounter)
    db.flush()
    admission = InpatientAdmission(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=inpatient_encounter.id,
        source_encounter_id=source.id,
        ward_id=ward.id,
        requested_by_user_id=user.id,
        admission_reason=payload.admission_reason,
        status="requested",
    )
    db.add(admission)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.admission.requested",
           resource_type="inpatient_admission", resource_id=admission.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "patient_has_active_inpatient_admission"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(admission)
    return admission


@router.get("/admissions/{admission_id}", response_model=AdmissionRead)
def get_admission(
    admission_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InpatientAdmission:
    user, hospital_id = context
    admission = _get_admission(db, hospital_id=hospital_id, admission_id=admission_id)
    _require_admission_access(
        db, user_id=user.id, hospital_id=hospital_id, admission=admission,
    )
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.admission.viewed",
           resource_type="inpatient_admission", resource_id=admission.id)
    db.commit()
    return admission


@router.get("/admissions", response_model=list[AdmissionRead])
def list_admissions(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    ward_id: UUID | None = None,
    admission_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[InpatientAdmission]:
    user, hospital_id = context
    membership, role_name = _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES | _NURSING_ROLES,
    )
    query = select(InpatientAdmission).where(
        InpatientAdmission.hospital_id == hospital_id
    )
    if ward_id is not None:
        query = query.where(InpatientAdmission.ward_id == ward_id)
    if admission_status is not None:
        query = query.where(InpatientAdmission.status == admission_status)
    if role_name not in _WARD_ADMIN_ROLES:
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
            or_(
                InpatientAdmission.requested_by_user_id == user.id,
                InpatientAdmission.encounter_id.in_(assigned_encounters),
            )
        )
    admissions = list(db.scalars(
        query.order_by(InpatientAdmission.requested_at.desc())
        .limit(limit).offset(offset)
    ).all())
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.admissions.viewed",
           resource_type="inpatient_admission_list", resource_id=None)
    db.commit()
    return admissions


@router.post("/admissions/{admission_id}/accept", response_model=AdmissionRead)
def accept_admission(
    admission_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InpatientAdmission:
    user, hospital_id = context
    admission = _get_admission(db, hospital_id=hospital_id, admission_id=admission_id, lock=True)
    ward = db.scalar(select(Ward).where(
        Ward.id == admission.ward_id, Ward.hospital_id == hospital_id
    ))
    if ward is None:
        raise HTTPException(status_code=404, detail={"code": "inpatient_ward_not_found"})
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=ward.department_id,
        allow_ward_admin=False,
    )
    if admission.status != "requested":
        raise HTTPException(status_code=409, detail={"code": "admission_not_in_requested_state"})
    now = datetime.now(timezone.utc)
    admission.status = "accepted"
    admission.accepted_by_user_id = user.id
    admission.accepted_at = now
    db.add(PatientCareAssignment(
        hospital_id=hospital_id,
        patient_id=admission.patient_id,
        staff_user_id=user.id,
        assigned_by_user_id=user.id,
        department_id=ward.department_id,
        encounter_id=admission.encounter_id,
        assignment_reason="Inpatient admission clinical acceptance",
        status="active",
        valid_from=now,
    ))
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.admission.accepted",
           resource_type="inpatient_admission", resource_id=admission.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(admission)
    return admission


@router.post("/admissions/{admission_id}/cancel", response_model=AdmissionRead)
def cancel_pending_admission(
    admission_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InpatientAdmission:
    user, hospital_id = context
    _require_role(db, user_id=user.id, hospital_id=hospital_id, allowed=set())
    admission = _get_admission(db, hospital_id=hospital_id, admission_id=admission_id, lock=True)
    if admission.status not in {"requested", "accepted"}:
        raise HTTPException(status_code=409, detail={"code": "only_pending_admission_can_be_cancelled"})
    now = datetime.now(timezone.utc)
    admission.status = "cancelled"
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == admission.encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is not None:
        encounter.status = "cancelled"
        encounter.ended_at = now
    if admission.source_encounter_id is not None:
        source_encounter = db.scalar(select(Encounter).where(
            Encounter.id == admission.source_encounter_id,
            Encounter.hospital_id == hospital_id,
        ).with_for_update())
        if source_encounter is not None and source_encounter.status == "admission_requested":
            source_encounter.status = "completed"
    assignments = db.scalars(select(PatientCareAssignment).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.encounter_id == admission.encounter_id,
        PatientCareAssignment.status == "active",
    ).with_for_update()).all()
    for assignment in assignments:
        assignment.valid_until = max(now, assignment.valid_from + timedelta(seconds=1))
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.admission.cancelled",
           resource_type="inpatient_admission", resource_id=admission.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(admission)
    return admission


@router.post(
    "/admissions/{admission_id}/bed-assignment",
    response_model=BedAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_admission_bed(
    admission_id: UUID,
    payload: BedAssignmentCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> BedAssignment:
    user, hospital_id = context
    _require_role(db, user_id=user.id, hospital_id=hospital_id, allowed=set())
    admission = _get_admission(db, hospital_id=hospital_id, admission_id=admission_id, lock=True)
    if admission.status != "accepted":
        raise HTTPException(status_code=409, detail={"code": "admission_must_be_accepted_before_bed_assignment"})
    bed = db.scalar(select(HospitalBed).where(
        HospitalBed.id == payload.bed_id,
        HospitalBed.hospital_id == hospital_id,
    ).with_for_update())
    if bed is None:
        raise HTTPException(status_code=404, detail={"code": "hospital_bed_not_found"})
    if bed.ward_id != admission.ward_id:
        raise HTTPException(status_code=422, detail={"code": "bed_not_in_requested_ward"})
    if bed.status != "available":
        raise HTTPException(status_code=409, detail={"code": "bed_not_available"})
    ward = db.scalar(select(Ward).where(
        Ward.id == bed.ward_id, Ward.hospital_id == hospital_id
    ))
    if ward is None or ward.status != "active" or ward.id != admission.ward_id:
        raise HTTPException(status_code=409, detail={"code": "bed_ward_missing_or_inactive"})
    if ward.ward_type == "icu" and bed.bed_type not in {"critical_care", "high_dependency"}:
        raise HTTPException(status_code=422, detail={"code": "icu_ward_requires_critical_or_high_dependency_bed"})
    if ward.ward_type == "maternity" and bed.bed_type not in {"maternity", "standard", "isolation"}:
        raise HTTPException(status_code=422, detail={"code": "bed_type_not_compatible_with_maternity_ward"})
    if ward.ward_type == "pediatric" and bed.bed_type not in {"pediatric", "standard", "isolation"}:
        raise HTTPException(status_code=422, detail={"code": "bed_type_not_compatible_with_pediatric_ward"})
    now = datetime.now(timezone.utc)
    assignment = BedAssignment(
        hospital_id=hospital_id,
        admission_id=admission.id,
        bed_id=bed.id,
        assigned_by_user_id=user.id,
        status="active",
    )
    db.add(assignment)
    bed.status = "occupied"
    admission.status = "admitted"
    admission.admitted_at = now
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == admission.encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None:
        raise HTTPException(status_code=409, detail={"code": "inpatient_encounter_missing"})
    encounter.status = "in_progress"
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.bed.assigned",
           resource_type="bed_assignment", resource_id=assignment.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "bed_or_admission_already_has_active_assignment"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(assignment)
    return assignment


@router.post("/admissions/{admission_id}/care-team", status_code=status.HTTP_201_CREATED)
def assign_inpatient_care_team_member(
    admission_id: UUID,
    payload: CareTeamAssignmentCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    _require_role(db, user_id=user.id, hospital_id=hospital_id, allowed=set())
    admission = _get_admission(db, hospital_id=hospital_id, admission_id=admission_id, lock=True)
    if admission.status != "admitted":
        raise HTTPException(status_code=409, detail={"code": "patient_must_be_admitted_before_care_team_assignment"})
    ward = db.scalar(select(Ward).where(Ward.id == admission.ward_id, Ward.hospital_id == hospital_id))
    staff_membership = _membership(db, user_id=payload.staff_user_id, hospital_id=hospital_id)
    staff_role = _role_name(db, staff_membership)
    if (
        ward is None or staff_membership is None
        or staff_membership.department_id != ward.department_id
        or staff_role not in _CLINICIAN_ROLES | _NURSING_ROLES
    ):
        raise HTTPException(status_code=422, detail={"code": "care_team_member_not_valid_for_ward"})
    now = datetime.now(timezone.utc)
    existing = db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == admission.patient_id,
        PatientCareAssignment.encounter_id == admission.encounter_id,
        PatientCareAssignment.staff_user_id == payload.staff_user_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "care_team_member_already_assigned"})
    assignment = PatientCareAssignment(
        hospital_id=hospital_id,
        patient_id=admission.patient_id,
        staff_user_id=payload.staff_user_id,
        assigned_by_user_id=user.id,
        department_id=ward.department_id,
        encounter_id=admission.encounter_id,
        assignment_reason=payload.assignment_reason,
        status="active",
        valid_from=now,
    )
    db.add(assignment)
    db.flush()
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.care_team.assigned",
           resource_type="patient_care_assignment", resource_id=assignment.id)
    db.commit()
    return {"assignment_id": assignment.id, "staff_user_id": payload.staff_user_id}


@router.post("/admissions/{admission_id}/discharge", response_model=AdmissionRead)
def discharge_inpatient(
    admission_id: UUID,
    payload: InpatientDischargeCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InpatientAdmission:
    user, hospital_id = context
    admission = _get_admission(db, hospital_id=hospital_id, admission_id=admission_id, lock=True)
    ward = db.scalar(select(Ward).where(Ward.id == admission.ward_id, Ward.hospital_id == hospital_id))
    _require_role(
        db, user_id=user.id, hospital_id=hospital_id, allowed=_CLINICIAN_ROLES,
        department_id=ward.department_id if ward else None,
        allow_ward_admin=False,
    )
    if (
        admission.status != "admitted"
        or ward is None
        or not _has_assignment(
            db, user_id=user.id, hospital_id=hospital_id,
            encounter_id=admission.encounter_id, department_id=ward.department_id,
        )
    ):
        raise HTTPException(status_code=403, detail={"code": "active_inpatient_clinician_assignment_required"})
    now = datetime.now(timezone.utc)
    active_bed_assignment = db.scalar(select(BedAssignment).where(
        BedAssignment.hospital_id == hospital_id,
        BedAssignment.admission_id == admission.id,
        BedAssignment.status == "active",
    ).with_for_update())
    if active_bed_assignment is None:
        raise HTTPException(status_code=409, detail={"code": "active_bed_assignment_missing"})
    bed = db.scalar(select(HospitalBed).where(
        HospitalBed.id == active_bed_assignment.bed_id,
        HospitalBed.hospital_id == hospital_id,
    ).with_for_update())
    if bed is None:
        raise HTTPException(status_code=409, detail={"code": "assigned_bed_missing"})
    active_bed_assignment.status = "released"
    active_bed_assignment.released_by_user_id = user.id
    active_bed_assignment.released_at = now
    bed.status = "cleaning"
    admission.status = "discharged"
    admission.discharged_by_user_id = user.id
    admission.discharged_at = now
    admission.discharge_summary = payload.discharge_summary
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == admission.encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is not None:
        encounter.status = "completed"
        encounter.ended_at = now
    assignments = db.scalars(select(PatientCareAssignment).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.encounter_id == admission.encounter_id,
        PatientCareAssignment.status == "active",
    ).with_for_update()).all()
    for assignment in assignments:
        assignment.valid_until = now + timedelta(hours=24)
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.admission.discharged",
           resource_type="inpatient_admission", resource_id=admission.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(admission)
    return admission


@router.post("/beds/{bed_id}/ready", response_model=BedRead)
def mark_bed_ready(
    bed_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> HospitalBed:
    user, hospital_id = context
    _require_role(db, user_id=user.id, hospital_id=hospital_id, allowed=set())
    bed = db.scalar(select(HospitalBed).where(
        HospitalBed.id == bed_id, HospitalBed.hospital_id == hospital_id
    ).with_for_update())
    if bed is None:
        raise HTTPException(status_code=404, detail={"code": "hospital_bed_not_found"})
    if bed.status != "cleaning":
        raise HTTPException(status_code=409, detail={"code": "bed_not_in_cleaning_state"})
    active_assignment = db.scalar(select(BedAssignment.id).where(
        BedAssignment.hospital_id == hospital_id,
        BedAssignment.bed_id == bed.id,
        BedAssignment.status == "active",
    ).limit(1))
    if active_assignment is not None:
        raise HTTPException(status_code=409, detail={"code": "bed_still_has_active_assignment"})
    bed.status = "available"
    _audit(db, hospital_id=hospital_id, user_id=user.id,
           action="inpatient.bed.ready", resource_type="hospital_bed", resource_id=bed.id)
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(bed)
    return bed
