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
    LaboratoryCriticalAcknowledgement,
    LaboratoryOrder,
    LaboratoryResult,
    LaboratorySpecimen,
    LaboratoryTestDefinition,
    Patient,
    PatientCareAssignment,
    Role,
)
from app.schemas.laboratory import (
    LaboratoryCriticalAcknowledgementCreate,
    LaboratoryCriticalAcknowledgementRead,
    LaboratoryOrderCancel,
    LaboratoryOrderCreate,
    LaboratoryOrderDetailRead,
    LaboratoryOrderRead,
    LaboratoryQueueItemRead,
    LaboratoryResultCreate,
    LaboratoryResultRead,
    LaboratorySpecimenCreate,
    LaboratorySpecimenRead,
    LaboratorySpecimenReject,
    LaboratoryTestDefinitionCreate,
    LaboratoryTestDefinitionRead,
    LaboratoryTestDefinitionRetire,
)

router = APIRouter(prefix="/laboratory", tags=["laboratory and diagnostics"])

_CLINICIAN_ROLES = {
    "doctor", "physician", "medical_officer", "clinical_officer",
    "clinician", "pediatrician", "surgeon", "obstetrician", "midwife",
}
_CATALOG_ROLES = {
    "lab_manager", "laboratory_manager", "lab_supervisor",
    "laboratory_supervisor", "lab_director", "pathologist",
}
_LAB_WORK_ROLES = {
    "lab_technician", "laboratory_technician", "medical_lab_scientist",
    "lab_scientist", "medical_lab_technologist", "medical_laboratory_technologist",
    "lab_supervisor",
    "laboratory_supervisor", "lab_director", "pathologist",
}
_LAB_VERIFY_ROLES = {
    "lab_supervisor", "laboratory_supervisor", "lab_director", "pathologist",
}
_LAB_COLLECTION_ROLES = _LAB_WORK_ROLES | {"phlebotomist"}


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


def _require_lab_role(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    allowed: set[str], department_id: UUID | None = None,
) -> HospitalMembership:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in allowed:
        raise HTTPException(status_code=403, detail={"code": "laboratory_role_not_authorized"})
    if department_id is not None and membership.department_id != department_id:
        raise HTTPException(status_code=403, detail={"code": "laboratory_department_scope_required"})
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



def _require_specimen_collection_access(
    db: Session, *, user_id: UUID, hospital_id: UUID, order: LaboratoryOrder
) -> None:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None:
        raise HTTPException(status_code=403, detail={"code": "specimen_collection_role_required"})
    if role_name in _LAB_COLLECTION_ROLES and membership.department_id == order.laboratory_department_id:
        return
    care_team_roles = _CLINICIAN_ROLES | {
        "nurse", "registered_nurse", "nursing_officer", "midwife",
        "emergency_nurse", "triage_nurse",
    }
    if (
        role_name in care_team_roles
        and membership.department_id == order.ordering_department_id
        and _has_assignment(
            db, user_id=user_id, hospital_id=hospital_id,
            patient_id=order.patient_id, encounter_id=order.encounter_id,
            department_id=order.ordering_department_id,
        )
    ):
        return
    raise HTTPException(status_code=403, detail={"code": "specimen_collection_role_or_assignment_required"})

def _get_test_definition(
    db: Session, *, hospital_id: UUID, definition_id: UUID, lock: bool = False
) -> LaboratoryTestDefinition:
    query = select(LaboratoryTestDefinition).where(
        LaboratoryTestDefinition.id == definition_id,
        LaboratoryTestDefinition.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    definition = db.scalar(query)
    if definition is None:
        raise HTTPException(status_code=404, detail={"code": "laboratory_test_definition_not_found"})
    return definition


def _get_order(
    db: Session, *, hospital_id: UUID, order_id: UUID, lock: bool = False
) -> LaboratoryOrder:
    query = select(LaboratoryOrder).where(
        LaboratoryOrder.id == order_id,
        LaboratoryOrder.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    order = db.scalar(query)
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "laboratory_order_not_found"})
    return order


def _get_specimen(
    db: Session, *, hospital_id: UUID, specimen_id: UUID, lock: bool = False
) -> LaboratorySpecimen:
    query = select(LaboratorySpecimen).where(
        LaboratorySpecimen.id == specimen_id,
        LaboratorySpecimen.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    specimen = db.scalar(query)
    if specimen is None:
        raise HTTPException(status_code=404, detail={"code": "laboratory_specimen_not_found"})
    return specimen


def _get_result(
    db: Session, *, hospital_id: UUID, result_id: UUID, lock: bool = False
) -> LaboratoryResult:
    query = select(LaboratoryResult).where(
        LaboratoryResult.id == result_id,
        LaboratoryResult.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    result = db.scalar(query)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "laboratory_result_not_found"})
    return result


def _require_order_access(
    db: Session, *, user_id: UUID, hospital_id: UUID, order: LaboratoryOrder
) -> str:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None:
        raise HTTPException(status_code=404, detail={"code": "laboratory_order_not_found"})
    if role_name in _LAB_COLLECTION_ROLES and membership.department_id == order.laboratory_department_id:
        return "laboratory"
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
    raise HTTPException(status_code=404, detail={"code": "laboratory_order_not_found"})


def _order_detail(db: Session, order: LaboratoryOrder) -> dict:
    patient = db.scalar(select(Patient).where(
        Patient.id == order.patient_id,
        Patient.hospital_id == order.hospital_id,
    ))
    definition = _get_test_definition(
        db, hospital_id=order.hospital_id, definition_id=order.test_definition_id
    )
    specimens = db.scalars(select(LaboratorySpecimen).where(
        LaboratorySpecimen.hospital_id == order.hospital_id,
        LaboratorySpecimen.order_id == order.id,
    ).order_by(LaboratorySpecimen.collected_at)).all()
    results = []
    for specimen in specimens:
        result = db.scalar(select(LaboratoryResult).where(
            LaboratoryResult.hospital_id == order.hospital_id,
            LaboratoryResult.specimen_id == specimen.id,
        ))
        if result is not None:
            results.append(result)
    critical_ack = None
    critical_result_ids = [r.id for r in results if r.critical_flag and r.status == "final"]
    if critical_result_ids:
        critical_ack = db.scalar(select(LaboratoryCriticalAcknowledgement).where(
            LaboratoryCriticalAcknowledgement.hospital_id == order.hospital_id,
            LaboratoryCriticalAcknowledgement.result_id == critical_result_ids[0],
        ))
    return {
        "order": order,
        "patient": {
            "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name,
            "family_name": patient.family_name,
        },
        "test": definition,
        "specimens": specimens,
        "results": results,
        "critical_acknowledgement": critical_ack,
    }


@router.post(
    "/test-definitions",
    response_model=LaboratoryTestDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_laboratory_test_definition(
    payload: LaboratoryTestDefinitionCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryTestDefinition:
    user, hospital_id = context
    _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CATALOG_ROLES, department_id=payload.department_id,
    )
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_laboratory_department_not_found"})
    definition = LaboratoryTestDefinition(
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
            action="laboratory.test_definition.created",
            resource_type="laboratory_test_definition", resource_id=str(definition.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "laboratory_test_code_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.post(
    "/test-definitions/{definition_id}/approve",
    response_model=LaboratoryTestDefinitionRead,
)
def approve_laboratory_test_definition(
    definition_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryTestDefinition:
    user, hospital_id = context
    definition = _get_test_definition(
        db, hospital_id=hospital_id, definition_id=definition_id, lock=True
    )
    membership = _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_LAB_VERIFY_ROLES, department_id=definition.department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "laboratory_approver_registration_required"})
    if definition.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "laboratory_definition_not_draft"})
    if definition.created_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "laboratory_two_person_approval_required"})
    definition.status = "active"
    definition.approved_by_user_id = user.id
    definition.approved_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.test_definition.approved",
        resource_type="laboratory_test_definition", resource_id=str(definition.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition



@router.post("/test-definitions/{definition_id}/retire", response_model=LaboratoryTestDefinitionRead)
def retire_laboratory_test_definition(
    definition_id: UUID,
    payload: LaboratoryTestDefinitionRetire,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryTestDefinition:
    user, hospital_id = context
    definition = _get_test_definition(
        db, hospital_id=hospital_id, definition_id=definition_id, lock=True
    )
    _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_LAB_VERIFY_ROLES, department_id=definition.department_id,
    )
    if definition.status != "active":
        raise HTTPException(status_code=409, detail={"code": "only_active_laboratory_definition_can_be_retired"})
    definition.status = "retired"
    definition.retired_by_user_id = user.id
    definition.retired_at = datetime.now(timezone.utc)
    definition.retirement_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.test_definition.retired",
        resource_type="laboratory_test_definition", resource_id=str(definition.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.get("/test-definitions", response_model=list[LaboratoryTestDefinitionRead])
def list_laboratory_test_definitions(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    department_id: UUID | None = None,
) -> list[LaboratoryTestDefinition]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _CLINICIAN_ROLES | _LAB_COLLECTION_ROLES | _CATALOG_ROLES:
        raise HTTPException(status_code=403, detail={"code": "laboratory_catalog_access_required"})
    query = select(LaboratoryTestDefinition).where(
        LaboratoryTestDefinition.hospital_id == hospital_id,
        LaboratoryTestDefinition.status == "active",
    )
    if role_name in _LAB_COLLECTION_ROLES | _CATALOG_ROLES:
        query = query.where(LaboratoryTestDefinition.department_id == membership.department_id)
    elif department_id is not None:
        query = query.where(LaboratoryTestDefinition.department_id == department_id)
    return list(db.scalars(query.order_by(LaboratoryTestDefinition.name)).all())


@router.post(
    "/encounters/{encounter_id}/orders",
    response_model=LaboratoryOrderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_laboratory_order(
    encounter_id: UUID,
    payload: LaboratoryOrderCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryOrder:
    user, hospital_id = context
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None or encounter.status != "in_progress" or encounter.department_id is None:
        raise HTTPException(status_code=409, detail={"code": "active_laboratory_order_encounter_required"})
    _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=encounter.department_id,
    )
    if not _has_assignment(
        db, user_id=user.id, hospital_id=hospital_id,
        patient_id=encounter.patient_id, encounter_id=encounter.id,
        department_id=encounter.department_id,
    ):
        raise HTTPException(status_code=403, detail={"code": "assigned_patient_required_for_laboratory_order"})
    patient = db.scalar(select(Patient).where(
        Patient.id == encounter.patient_id,
        Patient.hospital_id == hospital_id,
        Patient.status == "active",
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "laboratory_patient_not_found"})
    definition = _get_test_definition(
        db, hospital_id=hospital_id, definition_id=payload.test_definition_id
    )
    if definition.status != "active":
        raise HTTPException(status_code=409, detail={"code": "laboratory_test_definition_not_active"})
    lab_department = db.scalar(select(Department).where(
        Department.id == definition.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if lab_department is None:
        raise HTTPException(status_code=409, detail={"code": "laboratory_department_not_active"})
    order = LaboratoryOrder(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        ordering_department_id=encounter.department_id,
        laboratory_department_id=definition.department_id,
        test_definition_id=definition.id,
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
            action="laboratory.order.created", resource_type="laboratory_order",
            resource_id=str(order.id),
            metadata={"priority": order.priority, "test_definition_id": str(definition.id)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "laboratory_order_integrity_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(order)
    return order


@router.get("/orders", response_model=list[LaboratoryQueueItemRead])
def list_laboratory_orders(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    order_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _LAB_COLLECTION_ROLES:
        raise HTTPException(status_code=403, detail={"code": "laboratory_work_queue_role_required"})
    query = select(LaboratoryOrder).where(
        LaboratoryOrder.hospital_id == hospital_id,
        LaboratoryOrder.laboratory_department_id == membership.department_id,
    )
    if order_status is not None:
        if order_status not in {"ordered", "in_progress", "completed", "cancelled"}:
            raise HTTPException(status_code=422, detail={"code": "invalid_laboratory_order_status"})
        query = query.where(LaboratoryOrder.status == order_status)
    else:
        query = query.where(LaboratoryOrder.status.in_(("ordered", "in_progress")))
    orders = list(db.scalars(
        query.order_by(
            case(
                (LaboratoryOrder.priority == "stat", 0),
                (LaboratoryOrder.priority == "urgent", 1),
                else_=2,
            ),
            LaboratoryOrder.ordered_at.asc(),
            LaboratoryOrder.id.asc(),
        ).limit(limit).offset(offset)
    ).all())
    items = []
    for order in orders:
        patient = db.scalar(select(Patient).where(
            Patient.id == order.patient_id, Patient.hospital_id == hospital_id
        ))
        definition = _get_test_definition(
            db, hospital_id=hospital_id, definition_id=order.test_definition_id
        )
        if patient is not None:
            items.append({
                "order": order,
                "patient": {
                    "medical_record_number": patient.medical_record_number,
                    "given_name": patient.given_name,
                    "family_name": patient.family_name,
                },
                "test": definition,
            })
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.work_queue.viewed", resource_type="laboratory_order_queue",
        metadata={"returned_count": len(items), "status_filter": order_status},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return items


@router.get("/orders/{order_id}", response_model=LaboratoryOrderDetailRead)
def get_laboratory_order(
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
        action="laboratory.order.viewed", resource_type="laboratory_order",
        resource_id=str(order.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return result


@router.post(
    "/orders/{order_id}/specimens",
    response_model=LaboratorySpecimenRead,
    status_code=status.HTTP_201_CREATED,
)
def create_laboratory_specimen(
    order_id: UUID,
    payload: LaboratorySpecimenCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratorySpecimen:
    user, hospital_id = context
    order = _get_order(db, hospital_id=hospital_id, order_id=order_id, lock=True)
    _require_specimen_collection_access(
        db, user_id=user.id, hospital_id=hospital_id, order=order
    )
    if order.status not in {"ordered", "in_progress"}:
        raise HTTPException(status_code=409, detail={"code": "laboratory_order_not_open"})
    if payload.collected_at < order.ordered_at:
        raise HTTPException(status_code=422, detail={"code": "specimen_collection_before_order"})
    definition = _get_test_definition(
        db, hospital_id=hospital_id, definition_id=order.test_definition_id
    )
    now = datetime.now(timezone.utc)
    rejected = payload.collection_status == "rejected"
    specimen = LaboratorySpecimen(
        hospital_id=hospital_id,
        order_id=order.id,
        accession_number=payload.accession_number,
        specimen_type=definition.specimen_type,
        collected_by_user_id=user.id,
        collected_at=payload.collected_at,
        status="rejected" if rejected else "collected",
        rejected_at=now if rejected else None,
        rejection_reason=payload.rejection_reason if rejected else None,
    )
    db.add(specimen)
    if not rejected and order.status == "ordered":
        order.status = "in_progress"
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="laboratory.specimen.recorded", resource_type="laboratory_specimen",
            resource_id=str(specimen.id),
            metadata={"collection_status": specimen.status, "order_id": str(order.id)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "laboratory_accession_or_active_specimen_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(specimen)
    return specimen


@router.post("/specimens/{specimen_id}/receive", response_model=LaboratorySpecimenRead)
def receive_laboratory_specimen(
    specimen_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratorySpecimen:
    user, hospital_id = context
    specimen_ref = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=specimen_ref.order_id, lock=True)
    specimen = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id, lock=True)
    _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_LAB_WORK_ROLES, department_id=order.laboratory_department_id,
    )
    if specimen.status != "collected":
        raise HTTPException(status_code=409, detail={"code": "only_collected_specimen_can_be_received"})
    specimen.status = "received"
    specimen.received_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.specimen.received", resource_type="laboratory_specimen",
        resource_id=str(specimen.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(specimen)
    return specimen



@router.post("/specimens/{specimen_id}/reject", response_model=LaboratorySpecimenRead)
def reject_laboratory_specimen(
    specimen_id: UUID,
    payload: LaboratorySpecimenReject,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratorySpecimen:
    user, hospital_id = context
    specimen_ref = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=specimen_ref.order_id, lock=True)
    specimen = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id, lock=True)
    _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_LAB_WORK_ROLES, department_id=order.laboratory_department_id,
    )
    if specimen.status not in {"collected", "received"}:
        raise HTTPException(status_code=409, detail={"code": "specimen_not_rejectable_in_current_state"})
    specimen.status = "rejected"
    specimen.rejected_at = datetime.now(timezone.utc)
    specimen.rejection_reason = payload.reason
    remaining_active = db.scalar(select(LaboratorySpecimen.id).where(
        LaboratorySpecimen.hospital_id == hospital_id,
        LaboratorySpecimen.order_id == order.id,
        LaboratorySpecimen.id != specimen.id,
        LaboratorySpecimen.status != "rejected",
    ).limit(1))
    if remaining_active is None and order.status == "in_progress":
        order.status = "ordered"
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.specimen.rejected", resource_type="laboratory_specimen",
        resource_id=str(specimen.id),
        metadata={"order_id": str(order.id)},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(specimen)
    return specimen


@router.post("/specimens/{specimen_id}/start-processing", response_model=LaboratorySpecimenRead)
def start_laboratory_processing(
    specimen_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratorySpecimen:
    user, hospital_id = context
    specimen_ref = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=specimen_ref.order_id, lock=True)
    specimen = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id, lock=True)
    _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_LAB_WORK_ROLES, department_id=order.laboratory_department_id,
    )
    if specimen.status != "received":
        raise HTTPException(status_code=409, detail={"code": "only_received_specimen_can_start_processing"})
    specimen.status = "processing"
    specimen.processing_started_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.specimen.processing_started", resource_type="laboratory_specimen",
        resource_id=str(specimen.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(specimen)
    return specimen


@router.post(
    "/specimens/{specimen_id}/results",
    response_model=LaboratoryResultRead,
    status_code=status.HTTP_201_CREATED,
)
def enter_laboratory_result(
    specimen_id: UUID,
    payload: LaboratoryResultCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryResult:
    user, hospital_id = context
    specimen_ref = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=specimen_ref.order_id, lock=True)
    specimen = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_id, lock=True)
    _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_LAB_WORK_ROLES, department_id=order.laboratory_department_id,
    )
    if specimen.status != "processing":
        raise HTTPException(status_code=409, detail={"code": "specimen_not_in_processing"})
    definition = _get_test_definition(
        db, hospital_id=hospital_id, definition_id=order.test_definition_id
    )
    if payload.value_numeric is not None:
        if definition.result_unit is None or payload.unit != definition.result_unit:
            raise HTTPException(status_code=422, detail={"code": "laboratory_result_unit_must_match_catalog"})
    existing = db.scalar(select(LaboratoryResult.id).where(
        LaboratoryResult.hospital_id == hospital_id,
        LaboratoryResult.specimen_id == specimen.id,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "laboratory_result_already_entered"})
    result = LaboratoryResult(
        hospital_id=hospital_id,
        specimen_id=specimen.id,
        entered_by_user_id=user.id,
        **payload.model_dump(),
        status="preliminary",
    )
    db.add(result)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="laboratory.result.entered", resource_type="laboratory_result",
            resource_id=str(result.id),
            metadata={"specimen_id": str(specimen.id), "critical_flag": result.critical_flag},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "laboratory_result_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(result)
    return result


@router.post("/results/{result_id}/verify", response_model=LaboratoryResultRead)
def verify_laboratory_result(
    result_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryResult:
    user, hospital_id = context
    result_ref = _get_result(db, hospital_id=hospital_id, result_id=result_id)
    specimen_ref = _get_specimen(db, hospital_id=hospital_id, specimen_id=result_ref.specimen_id)
    order = _get_order(db, hospital_id=hospital_id, order_id=specimen_ref.order_id, lock=True)
    specimen = _get_specimen(db, hospital_id=hospital_id, specimen_id=specimen_ref.id, lock=True)
    result = _get_result(db, hospital_id=hospital_id, result_id=result_id, lock=True)
    membership = _require_lab_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_LAB_VERIFY_ROLES, department_id=order.laboratory_department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "laboratory_verifier_registration_required"})
    if result.status != "preliminary" or specimen.status != "processing":
        raise HTTPException(status_code=409, detail={"code": "laboratory_result_not_verifiable"})
    if result.entered_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "laboratory_result_two_person_verification_required"})
    now = datetime.now(timezone.utc)
    result.status = "final"
    result.verified_by_user_id = user.id
    result.verified_at = now
    specimen.status = "completed"
    order.status = "completed"
    order.completed_at = now
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.result.verified", resource_type="laboratory_result",
        resource_id=str(result.id),
        metadata={"critical_flag": result.critical_flag, "order_id": str(order.id)},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(result)
    return result


@router.post(
    "/results/{result_id}/acknowledge-critical",
    response_model=LaboratoryCriticalAcknowledgementRead,
    status_code=status.HTTP_201_CREATED,
)
def acknowledge_critical_laboratory_result(
    result_id: UUID,
    payload: LaboratoryCriticalAcknowledgementCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryCriticalAcknowledgement:
    user, hospital_id = context
    result_ref = _get_result(db, hospital_id=hospital_id, result_id=result_id)
    specimen_ref = _get_specimen(
        db, hospital_id=hospital_id, specimen_id=result_ref.specimen_id
    )
    order = _get_order(
        db, hospital_id=hospital_id, order_id=specimen_ref.order_id, lock=True
    )
    specimen = _get_specimen(
        db, hospital_id=hospital_id, specimen_id=specimen_ref.id, lock=True
    )
    result = _get_result(db, hospital_id=hospital_id, result_id=result_id, lock=True)
    if result.status != "final" or not result.critical_flag:
        raise HTTPException(status_code=409, detail={"code": "final_critical_result_required"})
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
    existing = db.scalar(select(LaboratoryCriticalAcknowledgement.id).where(
        LaboratoryCriticalAcknowledgement.hospital_id == hospital_id,
        LaboratoryCriticalAcknowledgement.result_id == result.id,
    ))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "critical_result_already_acknowledged"})
    acknowledgement = LaboratoryCriticalAcknowledgement(
        hospital_id=hospital_id,
        result_id=result.id,
        acknowledged_by_user_id=user.id,
        acknowledgement_note=payload.acknowledgement_note,
    )
    db.add(acknowledgement)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="laboratory.critical_result.acknowledged",
            resource_type="laboratory_result", resource_id=str(result.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "critical_result_acknowledgement_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(acknowledgement)
    return acknowledgement


@router.post("/orders/{order_id}/cancel", response_model=LaboratoryOrderRead)
def cancel_laboratory_order(
    order_id: UUID,
    payload: LaboratoryOrderCancel,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> LaboratoryOrder:
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
    lab_supervisor = (
        membership is not None
        and role_name in _LAB_VERIFY_ROLES
        and membership.department_id == order.laboratory_department_id
    )
    if not clinician_owner and not lab_supervisor:
        raise HTTPException(status_code=403, detail={"code": "laboratory_order_cancellation_not_authorized"})
    if order.status in {"completed", "cancelled"}:
        raise HTTPException(status_code=409, detail={"code": "laboratory_order_not_cancellable"})
    active_specimen = db.scalar(select(LaboratorySpecimen.id).where(
        LaboratorySpecimen.hospital_id == hospital_id,
        LaboratorySpecimen.order_id == order.id,
        LaboratorySpecimen.status != "rejected",
    ).limit(1))
    if active_specimen is not None:
        raise HTTPException(status_code=409, detail={"code": "active_specimen_must_be_rejected_before_cancellation"})
    order.status = "cancelled"
    order.cancelled_by_user_id = user.id
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancellation_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="laboratory.order.cancelled", resource_type="laboratory_order",
        resource_id=str(order.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(order)
    return order
