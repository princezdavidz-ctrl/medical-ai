import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    BillingServiceDefinition,
    Department,
    Encounter,
    Invoice,
    InvoiceLine,
    InvoicePayment,
    Patient,
)
from app.schemas.billing import (
    BillingServiceDefinitionCreate,
    BillingServiceDefinitionRead,
    BillingServiceDefinitionRetire,
    BillingPatientSummary,
    InvoiceCreate,
    InvoiceDetailRead,
    InvoiceLineCreate,
    InvoiceLineRead,
    InvoicePaymentCreate,
    InvoicePaymentFail,
    InvoicePaymentRead,
    InvoiceQueueItemRead,
    InvoiceRead,
    InvoiceVoid,
)

router = APIRouter(prefix="/billing", tags=["billing and finance"])

_BILLING_STAFF_ROLES = {
    "billing_clerk", "cashier", "accounts_officer", "finance_officer",
    "billing_manager", "billing_supervisor", "finance_manager", "finance_director",
}
_INVOICE_CREATE_ROLES = _BILLING_STAFF_ROLES
_SERVICE_CATALOG_ROLES = {
    "billing_manager", "billing_supervisor", "finance_manager", "finance_director",
}
_SERVICE_APPROVER_ROLES = {"finance_manager", "finance_director"}
_INVOICE_ISSUER_ROLES = {"finance_manager", "finance_director"}
_PAYMENT_CREATE_ROLES = {"cashier", "billing_clerk", "accounts_officer"}
_PAYMENT_CONFIRM_ROLES = {"finance_officer", "finance_manager", "finance_director"}
_PAYMENT_FAIL_ROLES = _BILLING_STAFF_ROLES
_INVOICE_VOID_ROLES = {"finance_manager", "finance_director"}


def _membership(db: Session, *, user_id: UUID, hospital_id: UUID):
    from app.models import HospitalMembership, Role

    return db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user_id,
            HospitalMembership.status == "active",
        )
    )


def _role_name(db: Session, membership) -> str:
    from app.models import Role

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


def _require_billing_role(
    db: Session, *, user_id: UUID, hospital_id: UUID,
    allowed: set[str], department_id: UUID | None = None,
):
    membership = _membership(db, user_id=user_id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in allowed:
        raise HTTPException(status_code=403, detail={"code": "billing_role_not_authorized"})
    if department_id is not None and membership.department_id != department_id:
        raise HTTPException(status_code=403, detail={"code": "billing_department_scope_required"})
    return membership


def _get_service(
    db: Session, *, hospital_id: UUID, service_id: UUID, lock: bool = False
) -> BillingServiceDefinition:
    query = select(BillingServiceDefinition).where(
        BillingServiceDefinition.id == service_id,
        BillingServiceDefinition.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    service = db.scalar(query)
    if service is None:
        raise HTTPException(status_code=404, detail={"code": "billing_service_not_found"})
    return service


def _get_invoice(
    db: Session, *, hospital_id: UUID, invoice_id: UUID, lock: bool = False
) -> Invoice:
    query = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    invoice = db.scalar(query)
    if invoice is None:
        raise HTTPException(status_code=404, detail={"code": "invoice_not_found"})
    return invoice


def _get_payment(
    db: Session, *, hospital_id: UUID, payment_id: UUID, lock: bool = False
) -> InvoicePayment:
    query = select(InvoicePayment).where(
        InvoicePayment.id == payment_id,
        InvoicePayment.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    payment = db.scalar(query)
    if payment is None:
        raise HTTPException(status_code=404, detail={"code": "invoice_payment_not_found"})
    return payment


def _invoice_detail(db: Session, invoice: Invoice) -> dict:
    patient = db.scalar(select(Patient).where(
        Patient.id == invoice.patient_id,
        Patient.hospital_id == invoice.hospital_id,
    ))
    lines = db.scalars(select(InvoiceLine).where(
        InvoiceLine.hospital_id == invoice.hospital_id,
        InvoiceLine.invoice_id == invoice.id,
    ).order_by(InvoiceLine.created_at, InvoiceLine.id)).all()
    payments = db.scalars(select(InvoicePayment).where(
        InvoicePayment.hospital_id == invoice.hospital_id,
        InvoicePayment.invoice_id == invoice.id,
    ).order_by(InvoicePayment.created_at, InvoicePayment.id)).all()
    return {
        "invoice": invoice,
        "patient": {
            "medical_record_number": patient.medical_record_number,
            "given_name": patient.given_name,
            "family_name": patient.family_name,
        },
        "lines": lines,
        "payments": payments,
    }


@router.post(
    "/service-definitions",
    response_model=BillingServiceDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_billing_service_definition(
    payload: BillingServiceDefinitionCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> BillingServiceDefinition:
    user, hospital_id = context
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_SERVICE_CATALOG_ROLES, department_id=payload.department_id,
    )
    department = db.scalar(select(Department).where(
        Department.id == payload.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_billing_department_not_found"})
    service = BillingServiceDefinition(
        hospital_id=hospital_id,
        created_by_user_id=user.id,
        status="draft",
        **payload.model_dump(),
    )
    db.add(service)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="billing.service_definition.created",
            resource_type="billing_service_definition", resource_id=str(service.id),
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "billing_service_code_already_exists"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(service)
    return service


@router.post(
    "/service-definitions/{service_id}/approve",
    response_model=BillingServiceDefinitionRead,
)
def approve_billing_service_definition(
    service_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> BillingServiceDefinition:
    user, hospital_id = context
    service = _get_service(db, hospital_id=hospital_id, service_id=service_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_SERVICE_APPROVER_ROLES, department_id=service.department_id,
    )
    if service.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "billing_service_not_draft"})
    if service.created_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "billing_catalog_two_person_approval_required"})
    service.status = "active"
    service.approved_by_user_id = user.id
    service.approved_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.service_definition.approved",
        resource_type="billing_service_definition", resource_id=str(service.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(service)
    return service


@router.post(
    "/service-definitions/{service_id}/retire",
    response_model=BillingServiceDefinitionRead,
)
def retire_billing_service_definition(
    service_id: UUID,
    payload: BillingServiceDefinitionRetire,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> BillingServiceDefinition:
    user, hospital_id = context
    service = _get_service(db, hospital_id=hospital_id, service_id=service_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_SERVICE_APPROVER_ROLES, department_id=service.department_id,
    )
    if service.status != "active":
        raise HTTPException(status_code=409, detail={"code": "only_active_billing_service_can_be_retired"})
    service.status = "retired"
    service.retired_by_user_id = user.id
    service.retired_at = datetime.now(timezone.utc)
    service.retirement_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.service_definition.retired",
        resource_type="billing_service_definition", resource_id=str(service.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(service)
    return service


@router.get("/service-definitions", response_model=list[BillingServiceDefinitionRead])
def list_billing_service_definitions(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    department_id: UUID | None = None,
) -> list[BillingServiceDefinition]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _BILLING_STAFF_ROLES:
        raise HTTPException(status_code=403, detail={"code": "billing_catalog_access_required"})
    if department_id is not None and department_id != membership.department_id:
        raise HTTPException(status_code=403, detail={"code": "billing_department_scope_required"})
    query = select(BillingServiceDefinition).where(
        BillingServiceDefinition.hospital_id == hospital_id,
        BillingServiceDefinition.status == "active",
        BillingServiceDefinition.department_id == membership.department_id,
    )
    return list(db.scalars(query.order_by(BillingServiceDefinition.name)).all())


@router.post(
    "/encounters/{encounter_id}/invoices",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice(
    encounter_id: UUID,
    payload: InvoiceCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Invoice:
    user, hospital_id = context
    membership = _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_INVOICE_CREATE_ROLES,
    )
    encounter = db.scalar(select(Encounter).where(
        Encounter.id == encounter_id,
        Encounter.hospital_id == hospital_id,
    ))
    if encounter is None:
        raise HTTPException(status_code=404, detail={"code": "billing_encounter_not_found"})
    department = db.scalar(select(Department).where(
        Department.id == membership.department_id,
        Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=403, detail={"code": "active_billing_department_required"})
    patient = db.scalar(select(Patient).where(
        Patient.id == encounter.patient_id,
        Patient.hospital_id == hospital_id,
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "billing_patient_not_found"})
    invoice = Invoice(
        hospital_id=hospital_id,
        patient_id=patient.id,
        encounter_id=encounter.id,
        department_id=membership.department_id,
        invoice_number=f"INV-{secrets.token_hex(6).upper()}",
        currency=payload.currency,
        subtotal_total=Decimal("0.00"),
        amount_paid_total=Decimal("0.00"),
        status="draft",
        created_by_user_id=user.id,
    )
    db.add(invoice)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="billing.invoice.created",
            resource_type="invoice", resource_id=str(invoice.id),
            metadata={"currency": invoice.currency},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "invoice_number_conflict_retry"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(invoice)
    return invoice


@router.post(
    "/invoices/{invoice_id}/lines",
    response_model=InvoiceLineRead,
    status_code=status.HTTP_201_CREATED,
)
def add_invoice_line(
    invoice_id: UUID,
    payload: InvoiceLineCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InvoiceLine:
    user, hospital_id = context
    invoice = _get_invoice(db, hospital_id=hospital_id, invoice_id=invoice_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_BILLING_STAFF_ROLES, department_id=invoice.department_id,
    )
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "invoice_not_draft"})
    service = _get_service(
        db, hospital_id=hospital_id, service_id=payload.service_definition_id, lock=True
    )
    if service.status != "active":
        raise HTTPException(status_code=409, detail={"code": "billing_service_not_active"})
    if service.department_id != invoice.department_id:
        raise HTTPException(status_code=403, detail={"code": "billing_service_department_mismatch"})
    if service.currency != invoice.currency:
        raise HTTPException(status_code=422, detail={"code": "billing_service_currency_mismatch"})
    line_total = (payload.quantity * service.unit_price).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    line = InvoiceLine(
        hospital_id=hospital_id,
        invoice_id=invoice.id,
        service_definition_id=service.id,
        description=service.name,
        quantity=payload.quantity,
        unit_price=service.unit_price,
        line_total=line_total,
        currency=invoice.currency,
        created_by_user_id=user.id,
    )
    db.add(line)
    try:
        db.flush()
        db.refresh(invoice)
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="billing.invoice.line_added",
            resource_type="invoice", resource_id=str(invoice.id),
            metadata={"service_definition_id": str(service.id), "line_total": str(line_total)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "invoice_line_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(line)
    return line


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceRead)
def issue_invoice(
    invoice_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Invoice:
    user, hospital_id = context
    invoice = _get_invoice(db, hospital_id=hospital_id, invoice_id=invoice_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_INVOICE_ISSUER_ROLES, department_id=invoice.department_id,
    )
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "invoice_not_draft"})
    if invoice.created_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "invoice_issue_two_person_approval_required"})
    if invoice.subtotal_total <= 0:
        raise HTTPException(status_code=409, detail={"code": "invoice_requires_positive_total"})
    invoice.status = "issued"
    invoice.issued_by_user_id = user.id
    invoice.issued_at = datetime.now(timezone.utc)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.invoice.issued", resource_type="invoice",
        resource_id=str(invoice.id),
        metadata={"currency": invoice.currency, "subtotal_total": str(invoice.subtotal_total)},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(invoice)
    return invoice


@router.get("/invoices", response_model=list[InvoiceQueueItemRead])
def list_invoices(
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
    invoice_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    user, hospital_id = context
    membership = _membership(db, user_id=user.id, hospital_id=hospital_id)
    role_name = _role_name(db, membership)
    if membership is None or role_name not in _BILLING_STAFF_ROLES:
        raise HTTPException(status_code=403, detail={"code": "billing_queue_role_required"})
    query = select(Invoice).where(
        Invoice.hospital_id == hospital_id,
        Invoice.department_id == membership.department_id,
    )
    if invoice_status is not None:
        if invoice_status not in {"draft", "issued", "partially_paid", "paid", "void"}:
            raise HTTPException(status_code=422, detail={"code": "invalid_invoice_status"})
        query = query.where(Invoice.status == invoice_status)
    else:
        query = query.where(Invoice.status.in_(("draft", "issued", "partially_paid")))
    invoices = list(db.scalars(
        query.order_by(
            case(
                (Invoice.status == "issued", 0),
                (Invoice.status == "partially_paid", 1),
                else_=2,
            ),
            Invoice.created_at.asc(),
            Invoice.id.asc(),
        ).limit(limit).offset(offset)
    ).all())
    items = []
    for invoice in invoices:
        patient = db.scalar(select(Patient).where(
            Patient.id == invoice.patient_id, Patient.hospital_id == hospital_id
        ))
        if patient is not None:
            items.append({
                "invoice": invoice,
                "patient": {
                    "medical_record_number": patient.medical_record_number,
                    "given_name": patient.given_name,
                    "family_name": patient.family_name,
                },
            })
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.invoice_queue.viewed", resource_type="invoice_queue",
        metadata={"returned_count": len(items), "status_filter": invoice_status},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return items


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetailRead)
def get_invoice(
    invoice_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> dict:
    user, hospital_id = context
    invoice = _get_invoice(db, hospital_id=hospital_id, invoice_id=invoice_id)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_BILLING_STAFF_ROLES, department_id=invoice.department_id,
    )
    result = _invoice_detail(db, invoice)
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.invoice.viewed", resource_type="invoice",
        resource_id=str(invoice.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    return result


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=InvoicePaymentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice_payment(
    invoice_id: UUID,
    payload: InvoicePaymentCreate,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InvoicePayment:
    user, hospital_id = context
    invoice = _get_invoice(db, hospital_id=hospital_id, invoice_id=invoice_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_PAYMENT_CREATE_ROLES, department_id=invoice.department_id,
    )
    if invoice.status not in {"issued", "partially_paid"}:
        raise HTTPException(status_code=409, detail={"code": "invoice_not_payable"})
    if payload.amount > invoice.subtotal_total - invoice.amount_paid_total:
        raise HTTPException(status_code=409, detail={"code": "payment_exceeds_invoice_balance"})
    payment = InvoicePayment(
        hospital_id=hospital_id,
        invoice_id=invoice.id,
        created_by_user_id=user.id,
        amount=payload.amount,
        currency=invoice.currency,
        method=payload.method,
        external_reference=payload.external_reference,
        status="pending",
    )
    db.add(payment)
    try:
        db.flush()
        write_audit_event(
            db, hospital_id=hospital_id, actor_user_id=user.id,
            action="billing.payment.recorded_pending",
            resource_type="invoice_payment", resource_id=str(payment.id),
            metadata={"method": payment.method, "currency": payment.currency},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "payment_external_reference_conflict"}) from None
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(payment)
    return payment


@router.post("/payments/{payment_id}/confirm", response_model=InvoicePaymentRead)
def confirm_invoice_payment(
    payment_id: UUID,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InvoicePayment:
    user, hospital_id = context
    payment_ref = _get_payment(db, hospital_id=hospital_id, payment_id=payment_id)
    invoice = _get_invoice(db, hospital_id=hospital_id, invoice_id=payment_ref.invoice_id, lock=True)
    payment = _get_payment(db, hospital_id=hospital_id, payment_id=payment_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_PAYMENT_CONFIRM_ROLES, department_id=invoice.department_id,
    )
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "payment_not_pending"})
    if payment.created_by_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "payment_confirmation_two_person_required"})
    if invoice.status not in {"issued", "partially_paid"}:
        raise HTTPException(status_code=409, detail={"code": "invoice_not_payable"})
    outstanding = invoice.subtotal_total - invoice.amount_paid_total
    if payment.amount > outstanding:
        raise HTTPException(status_code=409, detail={"code": "payment_exceeds_current_invoice_balance"})
    now = datetime.now(timezone.utc)
    payment.status = "confirmed"
    payment.confirmed_by_user_id = user.id
    payment.confirmed_at = now
    db.flush()
    invoice.amount_paid_total += payment.amount
    invoice.status = "paid" if invoice.amount_paid_total == invoice.subtotal_total else "partially_paid"
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.payment.confirmed", resource_type="invoice_payment",
        resource_id=str(payment.id),
        metadata={"invoice_id": str(invoice.id), "invoice_status": invoice.status},
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(payment)
    return payment


@router.post("/payments/{payment_id}/fail", response_model=InvoicePaymentRead)
def fail_invoice_payment(
    payment_id: UUID,
    payload: InvoicePaymentFail,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> InvoicePayment:
    user, hospital_id = context
    payment_ref = _get_payment(db, hospital_id=hospital_id, payment_id=payment_id)
    invoice = _get_invoice(db, hospital_id=hospital_id, invoice_id=payment_ref.invoice_id, lock=True)
    payment = _get_payment(db, hospital_id=hospital_id, payment_id=payment_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_PAYMENT_FAIL_ROLES, department_id=invoice.department_id,
    )
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail={"code": "payment_not_pending"})
    payment.status = "failed"
    payment.failure_note = payload.failure_note
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.payment.failed", resource_type="invoice_payment",
        resource_id=str(payment.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(payment)
    return payment


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceRead)
def void_invoice(
    invoice_id: UUID,
    payload: InvoiceVoid,
    context: tuple = Depends(get_current_context),
    db: Session = Depends(get_db),
) -> Invoice:
    user, hospital_id = context
    invoice = _get_invoice(db, hospital_id=hospital_id, invoice_id=invoice_id, lock=True)
    _require_billing_role(
        db, user_id=user.id, hospital_id=hospital_id,
        allowed=_INVOICE_VOID_ROLES, department_id=invoice.department_id,
    )
    if invoice.status not in {"draft", "issued"} or invoice.amount_paid_total != 0:
        raise HTTPException(status_code=409, detail={"code": "invoice_not_voidable"})
    pending_payment = db.scalar(select(InvoicePayment.id).where(
        InvoicePayment.hospital_id == hospital_id,
        InvoicePayment.invoice_id == invoice.id,
        InvoicePayment.status == "pending",
    ).limit(1))
    if pending_payment is not None:
        raise HTTPException(status_code=409, detail={"code": "pending_payment_must_be_failed_before_void"})
    invoice.status = "void"
    invoice.void_by_user_id = user.id
    invoice.void_at = datetime.now(timezone.utc)
    invoice.void_reason = payload.reason
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user.id,
        action="billing.invoice.voided", resource_type="invoice",
        resource_id=str(invoice.id),
    )
    db.commit()
    _restore_tenant_context(db, user_id=user.id, hospital_id=hospital_id)
    db.refresh(invoice)
    return invoice
