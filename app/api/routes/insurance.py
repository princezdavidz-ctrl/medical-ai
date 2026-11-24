from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import HospitalMembership, Role
from app.models.insurance import InsurerDefinition, PatientCoverage, InsuranceClaim, InsuranceClaimEvent
from app.models.billing import Invoice
from app.schemas.insurance import (
    InsurerCreate, InsurerRead, CoverageCreate, CoverageRead,
    ClaimCreate, ClaimRead, ClaimSubmit, ClaimAdjudicate, ClaimPayment,
)

router = APIRouter(prefix="/insurance", tags=["insurance and claims"])

_ADMIN = {"finance_manager", "finance_director", "hospital_admin", "insurance_manager"}
_STAFF = _ADMIN | {"insurance_officer", "claims_officer", "billing_manager", "billing_supervisor"}
_VERIFIERS = {"finance_manager", "finance_director", "hospital_admin", "insurance_manager"}


def _identity(db: Session, context):
    hospital_id = context.hospital_id
    user_id = context.user_id
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})
    membership = db.scalar(
        select(HospitalMembership).join(Role, Role.id == HospitalMembership.role_id).where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user_id,
            HospitalMembership.status == "active",
        )
    )
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if not membership:
        raise HTTPException(status_code=403, detail={"code": "insurance_membership_required"})
    return hospital_id, user_id, role_name


def _require(role_name: str, allowed: set[str]):
    if role_name not in allowed:
        raise HTTPException(status_code=403, detail={"code": "insurance_role_not_authorized"})


def _event(db: Session, hospital_id, claim, actor_id, event_type, old_status, new_status, note=None):
    db.add(InsuranceClaimEvent(
        hospital_id=hospital_id, claim_id=claim.id, actor_user_id=actor_id,
        event_type=event_type, from_status=old_status, to_status=new_status, note=note,
    ))


@router.post("/insurers", response_model=InsurerRead, status_code=status.HTTP_201_CREATED)
def create_insurer(payload: InsurerCreate, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _ADMIN)
    item = InsurerDefinition(hospital_id=hospital_id, created_by_user_id=user_id, **payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "insurer_code_conflict"})
    db.refresh(item)
    return item


@router.post("/insurers/{insurer_id}/approve", response_model=InsurerRead)
def approve_insurer(insurer_id: UUID, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _VERIFIERS)
    item = db.scalar(select(InsurerDefinition).where(InsurerDefinition.id == insurer_id, InsurerDefinition.hospital_id == hospital_id).with_for_update())
    if not item:
        raise HTTPException(404, detail={"code": "insurer_not_found"})
    if item.status != "draft" or item.created_by_user_id == user_id:
        raise HTTPException(409, detail={"code": "insurer_independent_approval_required"})
    item.status, item.approved_by_user_id, item.approved_at = "active", user_id, datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/coverages", response_model=CoverageRead, status_code=status.HTTP_201_CREATED)
def create_coverage(payload: CoverageCreate, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _STAFF)
    insurer = db.scalar(select(InsurerDefinition).where(
        InsurerDefinition.id == payload.insurer_definition_id,
        InsurerDefinition.hospital_id == hospital_id,
        InsurerDefinition.status == "active",
    ))
    if not insurer:
        raise HTTPException(404, detail={"code": "active_insurer_not_found"})
    item = PatientCoverage(hospital_id=hospital_id, created_by_user_id=user_id, **payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(404, detail={"code": "patient_or_insurer_not_found"})
    db.refresh(item)
    return item


@router.post("/coverages/{coverage_id}/verify", response_model=CoverageRead)
def verify_coverage(coverage_id: UUID, verification_reference: str, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _VERIFIERS)
    item = db.scalar(select(PatientCoverage).where(PatientCoverage.id == coverage_id, PatientCoverage.hospital_id == hospital_id).with_for_update())
    if not item or item.status != "reported":
        raise HTTPException(404, detail={"code": "reported_coverage_not_found"})
    if not verification_reference.strip():
        raise HTTPException(422, detail={"code": "verification_reference_required"})
    item.status, item.verification_reference = "verified", verification_reference.strip()[:160]
    item.verified_by_user_id, item.verified_at = user_id, datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


@router.post("/claims", response_model=ClaimRead, status_code=status.HTTP_201_CREATED)
def create_claim(payload: ClaimCreate, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _STAFF)
    coverage = db.scalar(select(PatientCoverage).where(
        PatientCoverage.id == payload.coverage_id, PatientCoverage.hospital_id == hospital_id,
        PatientCoverage.patient_id == payload.patient_id, PatientCoverage.status == "verified",
    ))
    invoice = db.scalar(select(Invoice).where(
        Invoice.id == payload.invoice_id, Invoice.hospital_id == hospital_id,
        Invoice.patient_id == payload.patient_id, Invoice.encounter_id == payload.encounter_id,
        Invoice.status.in_(["issued", "partially_paid", "paid"]),
    ))
    if not coverage or not invoice:
        raise HTTPException(409, detail={"code": "verified_coverage_and_issued_invoice_required"})
    if payload.currency != invoice.currency or payload.claimed_amount > invoice.subtotal_total:
        raise HTTPException(422, detail={"code": "claim_amount_or_currency_invalid"})
    claim = InsuranceClaim(hospital_id=hospital_id, created_by_user_id=user_id, **payload.model_dump())
    db.add(claim)
    try:
        db.flush()
        _event(db, hospital_id, claim, user_id, "created", None, "draft")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"code": "claim_conflict"})
    db.refresh(claim)
    return claim


@router.post("/claims/{claim_id}/submit", response_model=ClaimRead)
def submit_claim(claim_id: UUID, payload: ClaimSubmit, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _STAFF)
    claim = db.scalar(select(InsuranceClaim).where(InsuranceClaim.id == claim_id, InsuranceClaim.hospital_id == hospital_id).with_for_update())
    if not claim or claim.status != "draft":
        raise HTTPException(404, detail={"code": "draft_claim_not_found"})
    old = claim.status
    claim.status, claim.external_claim_reference = "submitted", payload.external_claim_reference
    claim.submitted_by_user_id, claim.submitted_at = user_id, datetime.now(timezone.utc)
    claim.submission_note = payload.note
    _event(db, hospital_id, claim, user_id, "submitted", old, claim.status, payload.note)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/claims/{claim_id}/adjudicate", response_model=ClaimRead)
def adjudicate_claim(claim_id: UUID, payload: ClaimAdjudicate, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _VERIFIERS)
    claim = db.scalar(select(InsuranceClaim).where(InsuranceClaim.id == claim_id, InsuranceClaim.hospital_id == hospital_id).with_for_update())
    if not claim or claim.status != "submitted":
        raise HTTPException(404, detail={"code": "submitted_claim_not_found"})
    if payload.approved_amount > claim.claimed_amount or (payload.outcome == "rejected" and payload.approved_amount != 0) or (payload.outcome == "accepted" and payload.approved_amount != claim.claimed_amount) or (payload.outcome == "partially_approved" and not 0 < payload.approved_amount < claim.claimed_amount):
        raise HTTPException(422, detail={"code": "adjudication_amount_mismatch"})
    old = claim.status
    claim.status, claim.approved_amount = payload.outcome, payload.approved_amount
    claim.adjudicated_by_user_id, claim.adjudicated_at = user_id, datetime.now(timezone.utc)
    claim.adjudication_note = payload.note
    _event(db, hospital_id, claim, user_id, "adjudicated", old, claim.status, payload.note)
    db.commit()
    db.refresh(claim)
    return claim


@router.post("/claims/{claim_id}/payments", response_model=ClaimRead)
def record_claim_payment(claim_id: UUID, payload: ClaimPayment, context=Depends(get_current_context), db: Session=Depends(get_db)):
    hospital_id, user_id, role = _identity(db, context)
    _require(role, _VERIFIERS)
    claim = db.scalar(select(InsuranceClaim).where(InsuranceClaim.id == claim_id, InsuranceClaim.hospital_id == hospital_id).with_for_update())
    if not claim or claim.status not in {"accepted", "partially_approved", "partially_paid"}:
        raise HTTPException(409, detail={"code": "claim_not_payable"})
    if payload.amount > claim.approved_amount - claim.paid_amount:
        raise HTTPException(422, detail={"code": "claim_payment_exceeds_balance"})
    old = claim.status
    claim.paid_amount += payload.amount
    claim.status = "paid" if claim.paid_amount == claim.approved_amount else "partially_paid"
    claim.last_payment_recorded_by_user_id, claim.last_payment_recorded_at = user_id, datetime.now(timezone.utc)
    _event(db, hospital_id, claim, user_id, "payment_recorded", old, claim.status, payload.note)
    db.commit()
    db.refresh(claim)
    return claim
