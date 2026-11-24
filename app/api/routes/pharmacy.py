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
    MedicationDefinition,
    MedicationDispense,
    MedicationOrder,
    MedicationOrderReviewEvent,
    Patient,
    PatientCareAssignment,
    Role,
)
from app.schemas.pharmacy import (
    MedicationDefinitionCreate,
    MedicationDefinitionRead,
    MedicationDefinitionRetire,
    MedicationDispenseCreate,
    MedicationDispenseRead,
    MedicationOrderCancel,
    MedicationOrderCreate,
    MedicationOrderDetailRead,
    MedicationOrderRead,
    MedicationOrderReviewCreate,
    MedicationOrderReviewEventRead,
    MedicationQueueItemRead,
)

router = APIRouter(prefix="/pharmacy", tags=["pharmacy and medication management"])

_CLINICIAN_ROLES = {
    "doctor", "physician", "medical_officer", "clinical_officer",
    "clinician", "pediatrician", "surgeon", "obstetrician", "midwife",
}
_CATALOG_ROLES = {
    "pharmacy_manager", "pharmacy_supervisor", "chief_pharmacist", "pharmacist",
}
_PHARMACY_QUEUE_ROLES = {
    "pharmacist", "clinical_pharmacist", "pharmacy_technician",
    "pharmacy_supervisor", "chief_pharmacist", "pharmacy_manager",
}
_PHARMACY_REVIEW_ROLES = {
    "pharmacist", "clinical_pharmacist", "pharmacy_supervisor", "chief_pharmacist",
}
_PHARMACY_DISPENSE_ROLES = {
    "pharmacist", "clinical_pharmacist", "pharmacy_supervisor", "chief_pharmacist",
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


def _require_pharmacy_role(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    allowed: set[str], department_id: UUID | None = None,
) -> HospitalMembership:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in allowed:
        raise HTTPException(status_code=403, detail={"code": "pharmacy_role_not_authorized"})
    if department_id is not None and membership.department_id != department_id:
        raise HTTPException(status_code=403, detail={"code": "pharmacy_department_scope_required"})
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
) -> MedicationDefinition:
    query = select(MedicationDefinition).where(
        MedicationDefinition.id == definition_id,
        MedicationDefinition.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    definition = db.scalar(query)
    if definition is None:
        raise HTTPException(status_code=404, detail={"code": "medication_definition_not_found"})
    return definition


def _get_order(
    db: Session, *, hospital_id: UUID, order_id: UUID, lock: bool = False
) -> MedicationOrder:
    query = select(MedicationOrder).where(
        MedicationOrder.id == order_id,
        MedicationOrder.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    order = db.scalar(query)
    if order is None:
        raise HTTPException(status_code=404, detail={"code": "medication_order_not_found"})
    return order


def _require_order_access(
    db: Session, *, user_id: UUID, hospital_id: UUID, order: MedicationOrder
) -> str:
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None:
        raise HTTPException(status_code=404, detail={"code": "medication_order_not_found"})
    if role_name in _PHARMACY_QUEUE_ROLES and membership.department_id == order.pharmacy_department_id:
        return "pharmacy"
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
    raise HTTPException(status_code=404, detail={"code": "medication_order_not_found"})


def _order_detail(db: Session, order: MedicationOrder) -> dict:
    patient = db.scalar(select(Patient).where(
        Patient.id == order.patient_id,
        Patient.hospital_id == order.hospital_id,
    ))
    definition = _get_definition(
        db, hospital_id=order.hospital_id,
        definition_id=order.medication_definition_id,
    )
    reviews = db.scalars(select(MedicationOrderReviewEvent).where(
        MedicationOrderReviewEvent.hospital_id == order.hospital_id,
        MedicationOrderReviewEvent.order_id == order.id,
    ).order_by(MedicationOrderReviewEvent.reviewed_at)).all()
    dispenses = db.scalars(select(MedicationDispense).where(
        MedicationDispense.hospital_id == order.hospital_id,
        MedicationDispense.order_id == order.id,
    ).order_by(MedicationDispense.dispensed_at)).all()
    return {
        "order": order,
        "patient": {
            "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name,
            "family_name": patient.family_name,
        },
        "medication": definition,
        "review_events": reviews,
        "dispenses": dispenses,
    }


@router.post(
    "/medication-definitions",
    response_model=MedicationDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_medication_definition(
    payload: MedicationDefinitionCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MedicationDefinition:
    user, hospital_id = context
    _require_pharmacy_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CATALOG_ROLES, department_id=payload.department_id,
    )
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_pharmacy_department_not_found"})
    definition = MedicationDefinition(
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
            action="pharmacy.medication_definition.created",
            resource_type="medication_definition", resource_id=str(definition.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "medication_definition_code_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.post(
    "/medication-definitions/{definition_id}/approve",
    response_model=MedicationDefinitionRead,
)
def approve_medication_definition(
    definition_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MedicationDefinition:
    user, hospital_id = context
    definition = _get_definition(
        db, hospital_id=hospital_id, definition_id=definition_id, lock=True
    )
    membership = _require_pharmacy_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_PHARMACY_REVIEW_ROLES, department_id=definition.department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "pharmacist_registration_required"})
    if definition.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "medication_definition_not_draft"})
    if definition.created_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "medication_catalog_two_person_approval_required"})
    definition.status = "active"
    definition.approved_by_user_id = user.id
    definition.approved_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pharmacy.medication_definition.approved",
        resource_type="medication_definition", resource_id=str(definition.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.post(
    "/medication-definitions/{definition_id}/retire",
    response_model=MedicationDefinitionRead,
)
def retire_medication_definition(
    definition_id: UUID,
    payload: MedicationDefinitionRetire,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MedicationDefinition:
    user, hospital_id = context
    definition = _get_definition(
        db, hospital_id=hospital_id, definition_id=definition_id, lock=True
    )
    membership = _require_pharmacy_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_PHARMACY_REVIEW_ROLES, department_id=definition.department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "pharmacist_registration_required"})
    if definition.status != "active":
        raise HTTPException(status_code=409, detail={"code": "only_active_medication_definition_can_be_retired"})
    definition.status = "retired"
    definition.retired_by_user_id = user.id
    definition.retired_at = datetime.now(timezone.utc)
    definition.retirement_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pharmacy.medication_definition.retired",
        resource_type="medication_definition", resource_id=str(definition.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(definition)
    return definition


@router.get("/medication-definitions", response_model=list[MedicationDefinitionRead])
def list_medication_definitions(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    department_id: UUID | None = None,
) -> list[MedicationDefinition]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _CLINICIAN_ROLES | _PHARMACY_QUEUE_ROLES | _CATALOG_ROLES:
        raise HTTPException(status_code=403, detail={"code": "medication_catalog_access_required"})
    query = select(MedicationDefinition).where(
        MedicationDefinition.hospital_id == hospital_id,
        MedicationDefinition.status == "active",
    )
    if role_name in _PHARMACY_QUEUE_ROLES | _CATALOG_ROLES:
        query = query.where(MedicationDefinition.department_id == membership.department_id)
    elif department_id is not None:
        query = query.where(MedicationDefinition.department_id == department_id)
    return list(db.scalars(query.order_by(MedicationDefinition.generic_name)).all())


@router.post(
    "/encounters/{encounter_id}/orders",
    response_model=MedicationOrderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_medication_order(
    encounter_id: UUID,
    payload: MedicationOrderCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MedicationOrder:
    user, hospital_id = context
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
    ).with_for_update())
    if encounter is None or encounter.status != "in_progress" or encounter.department_id is None:
        raise HTTPException(status_code=409, detail={"code": "active_medication_order_encounter_required"})
    _require_pharmacy_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_CLINICIAN_ROLES, department_id=encounter.department_id,
    )
    if not _has_assignment(
        db, user_id=user.id, hospital_id=hospital_id,
        patient_id=encounter.patient_id, encounter_id=encounter.id,
        department_id=encounter.department_id,
    ):
        raise HTTPException(status_code=403, detail={"code": "assigned_patient_required_for_medication_order"})
    patient = db.scalar(select(Patient).where(
        Patient.id == encounter.patient_id,
        Patient.hospital_id == hospital_id,
        Patient.status == "active",
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "medication_patient_not_found"})
    definition = _get_definition(
        db, hospital_id=hospital_id,
        definition_id=payload.medication_definition_id, lock=True,
    )
    if definition.status != "active":
        raise HTTPException(status_code=409, detail={"code": "medication_definition_not_active"})
    pharmacy_department = db.scalar(select(Department).where(
        Department.id == definition.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if pharmacy_department is None:
        raise HTTPException(status_code=409, detail={"code": "pharmacy_department_not_active"})
    order = MedicationOrder(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        ordering_department_id=encounter.department_id,
        pharmacy_department_id=definition.department_id,
        medication_definition_id=definition.id,
        prescribed_by_user_id=user.id,
        **payload.model_dump(),
        status="pending_pharmacy_review",
        quantity_dispensed_total=0,
    )
    db.add(order)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="pharmacy.medication_order.created",
            resource_type="medication_order", resource_id=str(order.id),
            metadata={"medication_definition_id": str(definition.id)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "medication_order_integrity_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(order)
    return order


@router.get("/orders", response_model=list[MedicationQueueItemRead])
def list_medication_orders(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    order_status: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _PHARMACY_QUEUE_ROLES:
        raise HTTPException(status_code=403, detail={"code": "pharmacy_work_queue_role_required"})
    query = select(MedicationOrder).where(
        MedicationOrder.hospital_id == hospital_id,
        MedicationOrder.pharmacy_department_id == membership.department_id,
    )
    if order_status is not None:
        if order_status not in {
            "pending_pharmacy_review", "approved_for_dispense", "on_hold",
            "rejected", "partially_dispensed", "dispensed", "cancelled",
        }:
            raise HTTPException(status_code=422, detail={"code": "invalid_medication_order_status"})
        query = query.where(MedicationOrder.status == order_status)
    else:
        query = query.where(MedicationOrder.status.in_(
            ("pending_pharmacy_review", "on_hold", "approved_for_dispense", "partially_dispensed")
        ))
    orders = list(db.scalars(
        query.order_by(
            case(
                (MedicationOrder.status == "pending_pharmacy_review", 0),
                (MedicationOrder.status == "on_hold", 1),
                (MedicationOrder.status == "approved_for_dispense", 2),
                else_=3,
            ),
            MedicationOrder.ordered_at.asc(),
            MedicationOrder.id.asc(),
        ).limit(limit).offset(offset)
    ).all())
    items = []
    for order in orders:
        patient = db.scalar(select(Patient).where(
            Patient.id == order.patient_id, Patient.hospital_id == hospital_id
        ))
        definition = _get_definition(
            db, hospital_id=hospital_id,
            definition_id=order.medication_definition_id,
        )
        if patient is not None:
            items.append({
                "order": order,
                "patient": {
                    "medical_record_number": patient.medical_record_number,
                    "given_name": patient.given_name,
                    "family_name": patient.family_name,
                },
                "medication": definition,
            })
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pharmacy.work_queue.viewed", resource_type="medication_order_queue",
        metadata={"returned_count": len(items), "status_filter": order_status},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return items


@router.get("/orders/{order_id}", response_model=MedicationOrderDetailRead)
def get_medication_order(
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
        action="pharmacy.medication_order.viewed", resource_type="medication_order",
        resource_id=str(order.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return result


@router.post("/orders/{order_id}/review", response_model=MedicationOrderReviewEventRead, status_code=status.HTTP_201_CREATED)
def review_medication_order(
    order_id: UUID,
    payload: MedicationOrderReviewCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MedicationOrderReviewEvent:
    user, hospital_id = context
    order = _get_order(db, hospital_id=hospital_id, order_id=order_id, lock=True)
    membership = _require_pharmacy_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_PHARMACY_REVIEW_ROLES, department_id=order.pharmacy_department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "pharmacist_registration_required"})
    if order.prescribed_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "prescriber_cannot_review_own_order"})
    if order.status not in {"pending_pharmacy_review", "on_hold", "approved_for_dispense"}:
        raise HTTPException(status_code=409, detail={"code": "medication_order_not_reviewable"})
    decision_to_status = {
        "approved": "approved_for_dispense",
        "on_hold": "on_hold",
        "rejected": "rejected",
    }
    if payload.decision == "rejected" and order.quantity_dispensed_total > 0:
        raise HTTPException(status_code=409, detail={"code": "partially_dispensed_order_cannot_be_rejected"})
    event = MedicationOrderReviewEvent(
        hospital_id=hospital_id,
        order_id=order.id,
        reviewed_by_user_id=user.id,
        decision=payload.decision,
        review_note=payload.review_note,
    )
    order.status = decision_to_status[payload.decision]
    db.add(event)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pharmacy.medication_order.reviewed",
        resource_type="medication_order", resource_id=str(order.id),
        metadata={"decision": payload.decision},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(event)
    return event


@router.post(
    "/orders/{order_id}/dispenses",
    response_model=MedicationDispenseRead,
    status_code=status.HTTP_201_CREATED,
)
def dispense_medication(
    order_id: UUID,
    payload: MedicationDispenseCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MedicationDispense:
    user, hospital_id = context
    order = _get_order(db, hospital_id=hospital_id, order_id=order_id, lock=True)
    membership = _require_pharmacy_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_PHARMACY_DISPENSE_ROLES, department_id=order.pharmacy_department_id,
    )
    if not membership.professional_registration or not membership.professional_registration.strip():
        raise HTTPException(status_code=403, detail={"code": "pharmacist_registration_required"})
    if order.status not in {"approved_for_dispense", "partially_dispensed"}:
        raise HTTPException(status_code=409, detail={"code": "medication_order_not_approved_for_dispense"})
    if payload.quantity_unit != order.quantity_unit:
        raise HTTPException(status_code=422, detail={"code": "dispense_quantity_unit_mismatch"})
    remaining = order.quantity_prescribed - order.quantity_dispensed_total
    if payload.quantity_dispensed > remaining:
        raise HTTPException(status_code=409, detail={"code": "dispense_exceeds_remaining_prescription_quantity"})
    new_total = order.quantity_dispensed_total + payload.quantity_dispensed
    dispense = MedicationDispense(
        hospital_id=hospital_id,
        order_id=order.id,
        dispensed_by_user_id=user.id,
        **payload.model_dump(),
    )
    order.quantity_dispensed_total = new_total
    order.status = "dispensed" if new_total == order.quantity_prescribed else "partially_dispensed"
    db.add(dispense)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="pharmacy.medication.dispensed",
            resource_type="medication_order", resource_id=str(order.id),
            metadata={"dispense_id": str(dispense.id), "order_status": order.status},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "medication_dispense_integrity_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(dispense)
    return dispense


@router.post("/orders/{order_id}/cancel", response_model=MedicationOrderRead)
def cancel_medication_order(
    order_id: UUID,
    payload: MedicationOrderCancel,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> MedicationOrder:
    user, hospital_id = context
    order = _get_order(db, hospital_id=hospital_id, order_id=order_id, lock=True)
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    clinician_owner = (
        membership is not None
        and role_name in _CLINICIAN_ROLES
        and membership.department_id == order.ordering_department_id
        and order.prescribed_by_user_id == user.id
        and _has_assignment(
            db, user_id=user.id, hospital_id=hospital_id,
            patient_id=order.patient_id, encounter_id=order.encounter_id,
            department_id=order.ordering_department_id,
        )
    )
    pharmacy_supervisor = (
        membership is not None
        and role_name in {"pharmacy_supervisor", "chief_pharmacist"}
        and membership.department_id == order.pharmacy_department_id
    )
    if not clinician_owner and not pharmacy_supervisor:
        raise HTTPException(status_code=403, detail={"code": "medication_order_cancellation_not_authorized"})
    if order.status in {"partially_dispensed", "dispensed", "cancelled"} or order.quantity_dispensed_total > 0:
        raise HTTPException(status_code=409, detail={"code": "medication_order_already_dispensed_or_cancelled"})
    order.status = "cancelled"
    order.cancelled_by_user_id = user.id
    order.cancelled_at = datetime.now(timezone.utc)
    order.cancellation_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="pharmacy.medication_order.cancelled",
        resource_type="medication_order", resource_id=str(order.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(order)
    return order
