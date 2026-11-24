from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    Department,
    Encounter,
    HospitalMembership,
    ImagingCriticalAcknowledgement,
    ImagingOrder,
    ImagingProcedureDefinition,
    ImagingReport,
    ImagingStudy,
    Patient,
    PatientCareAssignment,
    Role,
)
from app.schemas.radiology import (
    ImagingCriticalAcknowledgementCreate,
    ImagingCriticalAcknowledgementRead,
    ImagingOrderCancel,
    ImagingOrderCreate,
    ImagingOrderDetailRead,
    ImagingOrderRead,
    ImagingQueueItemRead,
    ImagingProcedureDefinitionCreate,
    ImagingProcedureDefinitionRead,
    ImagingProcedureDefinitionRetire,
    ImagingReportCreate,
    ImagingReportRead,
    ImagingStudyComplete,
    ImagingStudyRead,
    ImagingStudyScheduleCreate,
)

router = APIRouter(prefix="/radiology", tags=["radiology and medical imaging"])

_CLINICIAN_ROLES = {
    "doctor", "physician", "medical_officer", "clinical_officer",
    "clinician", "pediatrician", "surgeon", "obstetrician", "midwife",
}
_CATALOG_ROLES = {
    "radiology_manager", "imaging_manager", "radiology_director", "radiologist",
}
_RADIOLOGY_WORK_ROLES = {
    "radiographer", "radiology_technologist", "imaging_technologist",
    "sonographer", "mammographer", "radiology_nurse",
    "radiology_supervisor", "imaging_supervisor", "radiology_director",
    "radiologist", "radiology_resident",
}
_REPORT_AUTHOR_ROLES = {"radiologist", "radiology_resident"}
_REPORT_VERIFY_ROLES = {
    "radiologist", "radiology_director", "radiology_supervisor", "imaging_supervisor",
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


def _require_radiology_role(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    allowed: set[str], department_id: UUID | None = None,
) -> HospitalMembership:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in allowed:
        raise HTTPException(status_code=403, detail={"code": "radiology_role_not_authorized"})
    if department_id is not None and membership.department_id != department_id:
        raise HTTPException(status_code=403, detail={"code": "radiology_department_scope_required"})
    return membership


def _has_assignment(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    patient_id: UUID, encounter_id: UUID, department_id: UUID,
) -> bool:
    now = datetime.now(timezone.utc)
    return db.scalar(select(PatientCareAssignment.id).where(
        PatientCareAssignment.hospital_id == hospital_id,
        PatientCareAssignment.patient_id == patient_id,
        PatientCareAssignment.encounter_id == encounter_id,
        PatientCareAssignment.department_id == department_id,
        PatientCareAssignment.staff_user_id == user_id,
        PatientCareAssignment.status == "active",
        PatientCareAssignment.valid_from <= now,
        or_(
            PatientCareAssignment.valid_until.is_(None),
            PatientCareAssignment.valid_until > now,
        ),
    ).limit(1)) is not None


def _get_definition(
    db: Session, *, hospital_id: UUID, definition_id: UUID, lock: bool = False
) -> ImagingProcedureDefinition:
    query = select(ImagingProcedureDefinition).where(
        ImagingProcedureDefinition.id == definition_id,
        ImagingProcedureDefinition.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    definition = db.scalar(query)
    if definition is None:
        raise HTTPException(status_code=404, detail={"code": "imaging_procedure_definition_not_found"})
    return definition


def _get_order(
    db: Session, *, hospital_id: UUID, order_id: UUID, lock: bool = False
) -> ImagingOrder:
    query = select(ImagingOrder).where(
        ImagingOrder.id == order_id,
        ImagingOrder.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    order = db.scalar(query)
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "imaging_order_not_found"})
    return order


def _get_study(
    db: Session, *, hospital_id: UUID, study_id: UUID, lock: bool = False
) -> ImagingStudy:
    query = select(ImagingStudy).where(
        ImagingStudy.id == study_id,
        ImagingStudy.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    study = db.scalar(query)
    if study is None:
        raise HTTPException(status_code=404, detail={"code": "imaging_study_not_found"})
    return study


def _get_report(
    db: Session, *, hospital_id: UUID, report_id: UUID, lock: bool = False
) -> ImagingReport:
    query = select(ImagingReport).where(
        ImagingReport.id == report_id,
        ImagingReport.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    report = db.scalar(query)
    if report is None:
        raise HTTPException(status_code=404, detail={"code": "imaging_report_not_found"})
    return report


def _require_order_access(
    db: Session, *, user_id: UUID, hospital_id: UUID, order: ImagingOrder
) -> str:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None:
        raise HTTPException(status_code=404, detail={"code": "imaging_order_not_found"})
    if role_name in _RADIOLOGY_WORK_ROLES and membership.department_id == order.imaging_department_id:
        return "radiology"
    if (
        role_name in _CLINICIAN_ROLES
        and membership.department_id == order.ordering_department_id
        and _has_assignment(
            db, user_id=user_id, hospital_id=hospital_id,
            patient_id=order.patient_id, encounter_id=order.encounter_id,
            department_id=order.ordering_department_id,
        )
    ):
        return "clinician"
    raise HTTPException(status_code=404, detail={"code": "imaging_order_not_found"})


def _order_detail(db: Session, order: ImagingOrder) -> dict:
    patient = db.scalar(select(Patient).where(
        Patient.id == order.patient_id,
        Patient.hospital_id == order.hospital_id,
    ))
    definition = _get_definition(
        db, hospital_id=order.hospital_id, definition_id=order.procedure_definition_id
    )
    study = db.scalar(select(ImagingStudy).where(
        ImagingStudy.hospital_id == order.hospital_id,
        ImagingStudy.order_id == order.id,
    ))
    report = None
    acknowledgement = None
    if study is not None:
        report = db.scalar(select(ImagingReport).where(
            ImagingReport.hospital_id == order.hospital_id,
            ImagingReport.study_id == study.id,
        ))
        if report is not None and report.critical_flag and report.status == "final":
            acknowledgement = db.scalar(select(ImagingCriticalAcknowledgement).where(
                ImagingCriticalAcknowledgement.hospital_id == order.hospital_id,
                ImagingCriticalAcknowledgement.report_id == report.id,
            ))
    return {
        "order": order,
        "patient": {
            "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name,
            "family_name": patient.family_name,
        },
        "procedure": definition,
        "study": study,
        "report": report,
        "critical_acknowledgement": acknowledgement,
    }


@router.post(
    "/procedure-definitions",
    response_model=ImagingProcedureDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_imaging_procedure_definition(
    payload: ImagingProcedureDefinitionCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingProcedureDefinition:
    user, hospital_id = context
    _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CATALOG_ROLES, department_id=payload.department_id,
    )
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_imaging_department_not_found"})
    definition = ImagingProcedureDefinition(
        hospital_id=hospital_id,
        created_by_user_id=user.id,
        status="draft",
        **payload.model_dump(),
    )
    db.add(definition)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="radiology.procedure_definition.created",
            resource_type="imaging_procedure_definition", resource_id=str(definition.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "imaging_procedure_code_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.post(
    "/procedure-definitions/{definition_id}/approve",
    response_model=ImagingProcedureDefinitionRead,
)
def approve_imaging_procedure_definition(
    definition_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingProcedureDefinition:
    user, hospital_id = context
    definition = _get_definition(
        db, hospital_id=hospital_id, definition_id=definition_id, lock=True
    )
    membership = _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REPORT_VERIFY_ROLES, department_id=definition.department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "imaging_approver_registration_required"})
    if definition.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "imaging_procedure_definition_not_draft"})
    if definition.created_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "imaging_catalog_two_person_approval_required"})
    definition.status = "active"
    definition.approved_by_user_id = user.id
    definition.approved_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.procedure_definition.approved",
        resource_type="imaging_procedure_definition", resource_id=str(definition.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.post(
    "/procedure-definitions/{definition_id}/retire",
    response_model=ImagingProcedureDefinitionRead,
)
def retire_imaging_procedure_definition(
    definition_id: UUID,
    payload: ImagingProcedureDefinitionRetire,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingProcedureDefinition:
    user, hospital_id = context
    definition = _get_definition(
        db, hospital_id=hospital_id, definition_id=definition_id, lock=True
    )
    membership = _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REPORT_VERIFY_ROLES, department_id=definition.department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "imaging_retirement_registration_required"})
    if definition.status != "active":
        raise HTTPException(status_code=409, detail={"code": "only_active_imaging_definition_can_be_retired"})
    definition.status = "retired"
    definition.retired_by_user_id = user.id
    definition.retired_at = datetime.now(timezone.utc)
    definition.retirement_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.procedure_definition.retired",
        resource_type="imaging_procedure_definition", resource_id=str(definition.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.get("/procedure-definitions", response_model=list[ImagingProcedureDefinitionRead])
def list_imaging_procedure_definitions(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    department_id: UUID | None = None,
) -> list[ImagingProcedureDefinition]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _CLINICIAN_ROLES | _RADIOLOGY_WORK_ROLES | _CATALOG_ROLES:
        raise HTTPException(status_code=403, detail={"code": "imaging_catalog_access_required"})
    query = select(ImagingProcedureDefinition).where(
        ImagingProcedureDefinition.hospital_id == hospital_id,
        ImagingProcedureDefinition.status == "active",
    )
    if role_name in _RADIOLOGY_WORK_ROLES | _CATALOG_ROLES:
        query = query.where(ImagingProcedureDefinition.department_id == membership.department_id)
    elif department_id is not None:
        query = query.where(ImagingProcedureDefinition.department_id == department_id)
    return list(db.scalars(query.order_by(ImagingProcedureDefinition.name)).all())


@router.post(
    "/encounters/{encounter_id}/orders",
    response_model=ImagingOrderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_imaging_order(
    encounter_id: UUID,
    payload: ImagingOrderCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingOrder:
    user, hospital_id = context
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None or encounter.status != "in_progress" or encounter.department_id is None:
        raise HTTPException(status_code=409, detail={"code": "active_imaging_encounter_required"})
    _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=encounter.department_id,
    )
    if not _has_assignment(
        db, user_id=user.id, hospital_id=hospital_id,
        patient_id=encounter.patient_id, encounter_id=encounter.id,
        department_id=encounter.department_id,
    ):
        raise HTTPException(status_code=403, detail={"code": "assigned_patient_required_for_imaging_order"})
    patient = db.scalar(select(Patient).where(
        Patient.id == encounter.patient_id,
        Patient.hospital_id == hospital_id,
        Patient.status == "active",
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "imaging_patient_not_found"})
    definition = _get_definition(
        db, hospital_id=hospital_id, definition_id=payload.procedure_definition_id,
        lock=True,
    )
    if definition.status != "active":
        raise HTTPException(status_code=409, detail={"code": "imaging_procedure_definition_not_active"})
    imaging_department = db.scalar(select(Department).where(
        Department.id == definition.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if imaging_department is None:
        raise HTTPException(status_code=409, detail={"code": "imaging_department_not_active"})
    order = ImagingOrder(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        ordering_department_id=encounter.department_id,
        imaging_department_id=definition.department_id,
        procedure_definition_id=definition.id,
        ordered_by_user_id=user.id,
        priority=payload.priority,
        clinical_indication=payload.clinical_indication,
        status="ordered",
    )
    db.add(order)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="radiology.order.created", resource_type="imaging_order",
            resource_id=str(order.id),
            metadata={"priority": order.priority, "procedure_definition_id": str(definition.id)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "imaging_order_integrity_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(order)
    return order


@router.get("/orders", response_model=list[ImagingQueueItemRead])
def list_imaging_orders(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    order_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _RADIOLOGY_WORK_ROLES:
        raise HTTPException(status_code=403, detail={"code": "radiology_work_queue_role_required"})
    query = select(ImagingOrder).where(
        ImagingOrder.hospital_id == hospital_id,
        ImagingOrder.imaging_department_id == membership.department_id,
    )
    if order_status is not None:
        if order_status not in {"ordered", "scheduled", "in_progress", "completed", "cancelled"}:
            raise HTTPException(status_code=422, detail={"code": "invalid_imaging_order_status"})
        query = query.where(ImagingOrder.status == order_status)
    else:
        query = query.where(ImagingOrder.status.in_(("ordered", "scheduled", "in_progress")))
    orders = list(db.scalars(
        query.order_by(
            case(
                (ImagingOrder.priority == "stat", 0),
                (ImagingOrder.priority == "urgent", 1),
                else_=2,
            ),
            ImagingOrder.ordered_at.asc(),
            ImagingOrder.id.asc(),
        ).limit(limit).offset(offset)
    ).all())
    items = []
    for order in orders:
        patient = db.scalar(select(Patient).where(
            Patient.id == order.patient_id, Patient.hospital_id == hospital_id
        ))
        definition = _get_definition(
            db, hospital_id=hospital_id, definition_id=order.procedure_definition_id
        )
        if patient is not None:
            items.append({
                "order": order,
                "patient": {
                    "medical_record_number": patient.medical_record_number,
                    "given_name": patient.given_name,
                    "family_name": patient.family_name,
                },
                "procedure": definition,
            })
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.work_queue.viewed", resource_type="imaging_order_queue",
        metadata={"returned_count": len(items), "status_filter": order_status},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return items


@router.get("/orders/{order_id}", response_model=ImagingOrderDetailRead)
def get_imaging_order(
    order_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    order = _get_order(db, hospital_id=hospital_id, order_id=order_id)
    _require_order_access(db, user_id=user.id, hospital_id=hospital_id, order=order)
    result = _order_detail(db, order)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.order.viewed", resource_type="imaging_order",
        resource_id=str(order.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return result


@router.post(
    "/orders/{order_id}/schedule",
    response_model=ImagingStudyRead,
    status_code=status.HTTP_201_CREATED,
)
def schedule_imaging_study(
    order_id: UUID,
    payload: ImagingStudyScheduleCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingStudy:
    user, hospital_id = context
    order = _get_order(db, hospital_id=hospital_id, order_id=order_id, lock=True)
    _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_RADIOLOGY_WORK_ROLES, department_id=order.imaging_department_id,
    )
    if order.status != "ordered":
        raise HTTPException(status_code=409, detail={"code": "only_ordered_imaging_can_be_scheduled"})
    study = ImagingStudy(
        hospital_id=hospital_id,
        order_id=order.id,
        accession_number=payload.accession_number,
        scheduled_at=payload.scheduled_at,
        status="scheduled",
    )
    order.status = "scheduled"
    db.add(study)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="radiology.study.scheduled", resource_type="imaging_study",
            resource_id=str(study.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "imaging_accession_or_schedule_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(study)
    return study


@router.post("/studies/{study_id}/start", response_model=ImagingStudyRead)
def start_imaging_study(
    study_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingStudy:
    user, hospital_id = context
    study_ref = _get_study(db, hospital_id=hospital_id, study_id=study_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=study_ref.order_id, lock=True)
    study = _get_study(db, hospital_id=hospital_id, study_id=study_id, lock=True)
    _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_RADIOLOGY_WORK_ROLES, department_id=order.imaging_department_id,
    )
    if order.status != "scheduled" or study.status != "scheduled":
        raise HTTPException(status_code=409, detail={"code": "imaging_study_not_scheduled"})
    now = datetime.now(timezone.utc)
    study.status = "in_progress"
    study.performed_by_user_id = user.id
    study.started_at = now
    order.status = "in_progress"
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.study.started", resource_type="imaging_study",
        resource_id=str(study.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(study)
    return study


@router.post("/studies/{study_id}/complete", response_model=ImagingStudyRead)
def complete_imaging_study(
    study_id: UUID,
    payload: ImagingStudyComplete,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingStudy:
    user, hospital_id = context
    study_ref = _get_study(db, hospital_id=hospital_id, study_id=study_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=study_ref.order_id, lock=True)
    study = _get_study(db, hospital_id=hospital_id, study_id=study_id, lock=True)
    _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_RADIOLOGY_WORK_ROLES, department_id=order.imaging_department_id,
    )
    if (
        order.status != "in_progress"
        or study.status != "in_progress"
        or study.performed_by_user_id != user.id
    ):
        raise HTTPException(status_code=409, detail={"code": "imaging_study_not_owned_or_in_progress"})
    study.status = "completed"
    study.completed_at = datetime.now(timezone.utc)
    study.pacs_system_reference = payload.pacs_system_reference
    study.pacs_study_uid = payload.pacs_study_uid
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.study.completed", resource_type="imaging_study",
        resource_id=str(study.id),
        metadata={"pacs_reference_present": payload.pacs_study_uid is not None},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(study)
    return study


@router.post(
    "/studies/{study_id}/reports",
    response_model=ImagingReportRead,
    status_code=status.HTTP_201_CREATED,
)
def enter_imaging_report(
    study_id: UUID,
    payload: ImagingReportCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingReport:
    user, hospital_id = context
    study_ref = _get_study(db, hospital_id=hospital_id, study_id=study_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=study_ref.order_id, lock=True)
    study = _get_study(db, hospital_id=hospital_id, study_id=study_id, lock=True)
    _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REPORT_AUTHOR_ROLES, department_id=order.imaging_department_id,
    )
    if study.status != "completed" or order.status != "in_progress":
        raise HTTPException(status_code=409, detail={"code": "completed_imaging_study_required"})
    existing = db.scalar(select(ImagingReport.id).where(
        ImagingReport.hospital_id == hospital_id,
        ImagingReport.study_id == study.id,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "imaging_report_already_entered"})
    report = ImagingReport(
        hospital_id=hospital_id,
        study_id=study.id,
        entered_by_user_id=user.id,
        **payload.model_dump(),
        status="preliminary",
    )
    db.add(report)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="radiology.report.entered", resource_type="imaging_report",
            resource_id=str(report.id),
            metadata={"critical_flag": report.critical_flag},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "imaging_report_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(report)
    return report


@router.post("/reports/{report_id}/verify", response_model=ImagingReportRead)
def verify_imaging_report(
    report_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingReport:
    user, hospital_id = context
    report_ref = _get_report(db, hospital_id=hospital_id, report_id=report_id)
    study_ref = _get_study(db, hospital_id=hospital_id, study_id=report_ref.study_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=study_ref.order_id, lock=True)
    study = _get_study(db, hospital_id=hospital_id, study_id=study_ref.id, lock=True)
    report = _get_report(db, hospital_id=hospital_id, report_id=report_id, lock=True)
    membership = _require_radiology_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_REPORT_VERIFY_ROLES, department_id=order.imaging_department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "radiology_verifier_registration_required"})
    if (
        report.status != "preliminary"
        or study.status != "completed"
        or order.status != "in_progress"
    ):
        raise HTTPException(status_code=409, detail={"code": "imaging_report_not_verifiable"})
    if report.entered_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "imaging_report_two_person_verification_required"})
    report.status = "final"
    report.verified_by_user_id = user.id
    report.verified_at = datetime.now(timezone.utc)
    order.status = "completed"
    order.completed_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.report.verified", resource_type="imaging_report",
        resource_id=str(report.id),
        metadata={"critical_flag": report.critical_flag, "order_id": str(order.id)},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(report)
    return report


@router.post(
    "/reports/{report_id}/acknowledge-critical",
    response_model=ImagingCriticalAcknowledgementRead,
    status_code=status.HTTP_201_CREATED,
)
def acknowledge_critical_imaging_report(
    report_id: UUID,
    payload: ImagingCriticalAcknowledgementCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingCriticalAcknowledgement:
    user, hospital_id = context
    report_ref = _get_report(db, hospital_id=hospital_id, report_id=report_id)
    study_ref = _get_study(db, hospital_id=hospital_id, study_id=report_ref.study_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=study_ref.order_id, lock=True)
    study = _get_study(db, hospital_id=hospital_id, study_id=study_ref.id, lock=True)
    report = _get_report(db, hospital_id=hospital_id, report_id=report_id, lock=True)
    if report.status != "final" or not report.critical_flag:
        raise HTTPException(status_code=409, detail={"code": "final_critical_imaging_report_required"})
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    if (
        membership is None
        or _role_name(db, membership) not in _CLINICIAN_ROLES
        or membership.department_id != order.ordering_department_id
        or not _has_assignment(
            db, user_id=user.id, hospital_id=hospital_id,
            patient_id=order.patient_id, encounter_id=order.encounter_id,
            department_id=order.ordering_department_id,
        )
    ):
        raise HTTPException(status_code=403, detail={"code": "assigned_ordering_clinician_required"})
    existing = db.scalar(select(ImagingCriticalAcknowledgement.id).where(
        ImagingCriticalAcknowledgement.hospital_id == hospital_id,
        ImagingCriticalAcknowledgement.report_id == report.id,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "imaging_critical_report_already_acknowledged"})
    acknowledgement = ImagingCriticalAcknowledgement(
        hospital_id=hospital_id,
        report_id=report.id,
        acknowledged_by_user_id=user.id,
        acknowledgement_note=payload.acknowledgement_note,
    )
    db.add(acknowledgement)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="radiology.critical_report.acknowledged",
            resource_type="imaging_report", resource_id=str(report.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "imaging_critical_acknowledgement_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(acknowledgement)
    return acknowledgement


@router.post("/orders/{order_id}/cancel", response_model=ImagingOrderRead)
def cancel_imaging_order(
    order_id: UUID,
    payload: ImagingOrderCancel,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> ImagingOrder:
    user, hospital_id = context
    order = _get_order(db, hospital_id=hospital_id, order_id=order_id, lock=True)
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    clinician_owner = (
        membership is not None
        and role_name in _CLINICIAN_ROLES
        and membership.department_id == order.ordering_department_id
        and order.ordered_by_user_id == user.id
        and _has_assignment(
            db, user_id=user.id, hospital_id=hospital_id,
            patient_id=order.patient_id, encounter_id=order.encounter_id,
            department_id=order.ordering_department_id,
        )
    )
    radiology_supervisor = (
        membership is not None
        and role_name in _REPORT_VERIFY_ROLES
        and membership.department_id == order.imaging_department_id
    )
    if not clinician_owner and not radiology_supervisor:
        raise HTTPException(status_code=403, detail={"code": "imaging_order_cancellation_not_authorized"})
    if order.status not in {"ordered", "scheduled"}:
        raise HTTPException(status_code=409, detail={"code": "imaging_order_not_cancellable"})
    study = db.scalar(select(ImagingStudy).where(
        ImagingStudy.hospital_id == hospital_id,
        ImagingStudy.order_id == order.id,
    ).with_for_update())
    if study is not None:
        if study.status != "scheduled":
            raise HTTPException(status_code=409, detail={"code": "imaging_study_already_started"})
        study.status = "cancelled"
        study.cancelled_at = datetime.now(timezone.utc)
    order.status = "cancelled"
    order.cancelled_by_user_id = user.id
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancellation_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="radiology.order.cancelled", resource_type="imaging_order",
        resource_id=str(order.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(order)
    return order
