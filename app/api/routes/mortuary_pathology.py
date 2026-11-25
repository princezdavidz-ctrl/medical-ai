from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Encounter, HospitalMembership, Patient, Role
from app.models.mortuary_pathology import (
    MortuaryCase, MortuaryAuthorization, MortuaryMovement, MortuaryPropertyItem,
    PathologyCase, PathologySpecimen, PathologyReport, PathologyEvent,
)
from app.schemas.mortuary_pathology import (
    MortuaryCaseCreate, MortuaryCaseRead, MortuaryAuthorizationCreate,
    MortuaryAuthorizationDecision, MortuaryMovementCreate, MortuaryPropertyCreate,
    MortuaryPropertyRelease, MortuaryRelease, LegalHoldUpdate,
    PathologyCaseCreate, PathologyCaseRead, PathologyAuthorityVerification,
    PathologyAssignment, PathologySpecimenCreate, PathologySpecimenRead,
    PathologySpecimenStatus, PathologyReportCreate, PathologyReportRead,
)

router = APIRouter(prefix="/mortuary-pathology", tags=["mortuary and pathology"])
_MORTUARY_STAFF = {"mortuary_officer", "mortuary_manager", "hospital_admin"}
_MORTUARY_MANAGERS = {"mortuary_manager", "hospital_admin"}
_PATHOLOGY_STAFF = {"pathology_technician", "pathologist", "pathology_manager", "hospital_admin"}
_PATHOLOGY_MANAGERS = {"pathology_manager", "hospital_admin"}
_PATHOLOGISTS = {"pathologist", "pathology_manager", "hospital_admin"}
_FORENSIC_AUTHORITIES = {"court_order", "coroner_directive", "public_health_order"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require(db: Session, user_id: UUID, hospital_id: UUID, allowed: set[str]) -> str:
    role = _role(db, user_id, hospital_id)
    if not role or role not in allowed:
        raise HTTPException(status_code=403, detail={"code": "mortuary_pathology_role_not_authorized"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, resource_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource, resource_id=str(resource_id), metadata=metadata or {},
    )


def _mortuary_case(db: Session, case_id: UUID, hospital_id: UUID, *, lock: bool = False):
    query = select(MortuaryCase).where(
        MortuaryCase.id == case_id, MortuaryCase.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "mortuary_case_not_found"})
    return item


def _pathology_case(db: Session, case_id: UUID, hospital_id: UUID, *, lock: bool = False):
    query = select(PathologyCase).where(
        PathologyCase.id == case_id, PathologyCase.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "pathology_case_not_found"})
    return item


def _movement(db: Session, hospital_id: UUID, user_id: UUID, case: MortuaryCase, movement_type: str, to_location: str, note=None, from_location=None):
    db.add(MortuaryMovement(
        hospital_id=hospital_id, mortuary_case_id=case.id, movement_type=movement_type,
        from_location=from_location if from_location is not None else case.storage_location, to_location=to_location, actor_user_id=user_id, note=note,
    ))


def _path_event(db: Session, hospital_id: UUID, user_id: UUID, case_id: UUID, event_type: str, note=None):
    db.add(PathologyEvent(
        hospital_id=hospital_id, pathology_case_id=case_id,
        actor_user_id=user_id, event_type=event_type, note=note,
    ))


def _has_verified_mortuary_authority(db: Session, hospital_id: UUID, case_id: UUID) -> bool:
    return db.scalar(select(MortuaryAuthorization.id).where(
        MortuaryAuthorization.hospital_id == hospital_id,
        MortuaryAuthorization.mortuary_case_id == case_id,
        MortuaryAuthorization.status == "verified",
    ).limit(1)) is not None


@router.post("/cases", response_model=MortuaryCaseRead, status_code=status.HTTP_201_CREATED)
def create_mortuary_case(payload: MortuaryCaseCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    now = datetime.now(timezone.utc)
    if payload.death_occurred_at.tzinfo is None or payload.death_occurred_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail={"code": "death_time_must_include_timezone"})
    if payload.death_occurred_at > now:
        raise HTTPException(status_code=422, detail={"code": "death_time_cannot_be_in_future"})
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id, Patient.hospital_id == hospital_id,
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    if payload.encounter_id is not None:
        encounter = db.scalar(select(Encounter).where(
            Encounter.id == payload.encounter_id, Encounter.hospital_id == hospital_id,
            Encounter.patient_id == patient.id,
        ))
        if encounter is None:
            raise HTTPException(status_code=404, detail={"code": "matching_encounter_not_found"})
    case = MortuaryCase(
        hospital_id=hospital_id, received_by_user_id=user.id,
        status="received", **payload.model_dump(),
    )
    db.add(case)
    try:
        db.flush()
        _movement(db, hospital_id, user.id, case, "received", case.storage_location)
        _audit(db, hospital_id, user.id, "mortuary.case.received", "mortuary_case", case.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "mortuary_case_or_body_reference_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.get("/cases", response_model=list[MortuaryCaseRead])
def list_mortuary_cases(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    return db.scalars(select(MortuaryCase).where(
        MortuaryCase.hospital_id == hospital_id,
    ).order_by(MortuaryCase.received_at.desc()).limit(300)).all()


@router.post("/cases/{case_id}/authorizations", status_code=status.HTTP_201_CREATED)
def submit_mortuary_authorization(case_id: UUID, payload: MortuaryAuthorizationCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    case = _mortuary_case(db, case_id, hospital_id)
    if case.status in ("released", "transferred"):
        raise HTTPException(status_code=409, detail={"code": "closed_mortuary_case"})
    item = MortuaryAuthorization(
        hospital_id=hospital_id, mortuary_case_id=case.id,
        submitted_by_user_id=user.id, status="pending", **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    _audit(db, hospital_id, user.id, "mortuary.authorization.submitted", "mortuary_authorization", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"id": item.id, "status": item.status, "authority_type": item.authority_type}


@router.post("/authorizations/{authorization_id}/decision")
def decide_mortuary_authorization(authorization_id: UUID, payload: MortuaryAuthorizationDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_MANAGERS)
    item = db.scalar(select(MortuaryAuthorization).where(
        MortuaryAuthorization.id == authorization_id,
        MortuaryAuthorization.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.status != "pending":
        raise HTTPException(status_code=404, detail={"code": "pending_mortuary_authorization_not_found"})
    if item.submitted_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_authorization_verification_required"})
    if payload.status == "verified":
        if not payload.evidence_reference:
            raise HTTPException(status_code=422, detail={"code": "verified_authorization_requires_vault_evidence"})
        item.status = "verified"
        item.evidence_reference = payload.evidence_reference
        item.verified_by_user_id = user.id
        item.verified_at = datetime.now(timezone.utc)
    else:
        item.status = "rejected"
    _audit(db, hospital_id, user.id, "mortuary.authorization."+payload.status, "mortuary_authorization", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"id": item.id, "status": item.status, "verified_at": item.verified_at}


@router.get("/cases/{case_id}/authorizations")
def list_mortuary_authorizations(case_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    _mortuary_case(db, case_id, hospital_id)
    rows = db.scalars(select(MortuaryAuthorization).where(
        MortuaryAuthorization.hospital_id == hospital_id,
        MortuaryAuthorization.mortuary_case_id == case_id,
    ).order_by(MortuaryAuthorization.created_at)).all()
    return [{
        "id": row.id, "authority_type": row.authority_type, "authority_reference": row.authority_reference,
        "evidence_reference": row.evidence_reference, "status": row.status,
        "submitted_by_user_id": row.submitted_by_user_id, "verified_by_user_id": row.verified_by_user_id,
        "verified_at": row.verified_at, "created_at": row.created_at,
    } for row in rows]


@router.post("/authorizations/{authorization_id}/revoke")
def revoke_mortuary_authorization(authorization_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_MANAGERS)
    item = db.scalar(select(MortuaryAuthorization).where(
        MortuaryAuthorization.id == authorization_id,
        MortuaryAuthorization.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.status != "verified":
        raise HTTPException(status_code=409, detail={"code": "verified_mortuary_authorization_required"})
    item.status = "revoked"
    item.verified_by_user_id = None
    item.verified_at = None
    _audit(db, hospital_id, user.id, "mortuary.authorization.revoked", "mortuary_authorization", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"id": item.id, "status": item.status}


@router.post("/cases/{case_id}/movements", response_model=MortuaryCaseRead)
def record_mortuary_movement(case_id: UUID, payload: MortuaryMovementCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    case = _mortuary_case(db, case_id, hospital_id, lock=True)
    previous_location = case.storage_location
    if case.status in ("released", "transferred"):
        raise HTTPException(status_code=409, detail={"code": "terminal_mortuary_case"})
    if case.legal_hold and payload.movement_type == "release_pending":
        raise HTTPException(status_code=409, detail={"code": "legal_hold_blocks_release"})
    if payload.movement_type == "release_pending":
        if not _has_verified_mortuary_authority(db, hospital_id, case.id):
            raise HTTPException(status_code=409, detail={"code": "verified_release_authority_required"})
        case.status = "release_pending"
    elif payload.movement_type == "retained":
        case.legal_hold = True
        case.status = "retained_by_authority"
    elif payload.movement_type == "stored":
        case.status = "stored"
    elif payload.movement_type == "relocated":
        if case.status not in ("stored", "received", "retained_by_authority"):
            raise HTTPException(status_code=409, detail={"code": "case_not_relocatable"})
        if case.status == "received":
            case.status = "stored"
    case.storage_location = payload.to_location
    _movement(db, hospital_id, user.id, case, payload.movement_type, payload.to_location, payload.note, previous_location)
    _audit(db, hospital_id, user.id, "mortuary.case.moved", "mortuary_case", case.id, {"movement_type": payload.movement_type})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.post("/cases/{case_id}/legal-hold", response_model=MortuaryCaseRead)
def update_mortuary_legal_hold(case_id: UUID, payload: LegalHoldUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_MANAGERS)
    case = _mortuary_case(db, case_id, hospital_id, lock=True)
    if case.status in ("released", "transferred"):
        raise HTTPException(status_code=409, detail={"code": "terminal_mortuary_case"})
    case.legal_hold = payload.legal_hold
    if payload.legal_hold:
        case.status = "retained_by_authority"
        _movement(db, hospital_id, user.id, case, "retained", case.storage_location, "Legal hold applied")
    elif case.status == "retained_by_authority":
        case.status = "stored"
        _movement(db, hospital_id, user.id, case, "stored", case.storage_location, "Legal hold lifted")
    _audit(db, hospital_id, user.id, "mortuary.legal_hold.changed", "mortuary_case", case.id, {"legal_hold": payload.legal_hold})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.post("/cases/{case_id}/release", response_model=MortuaryCaseRead)
def release_mortuary_case(case_id: UUID, payload: MortuaryRelease, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_MANAGERS)
    case = _mortuary_case(db, case_id, hospital_id, lock=True)
    if case.status != "release_pending" or case.legal_hold:
        raise HTTPException(status_code=409, detail={"code": "release_pending_case_without_legal_hold_required"})
    if not _has_verified_mortuary_authority(db, hospital_id, case.id):
        raise HTTPException(status_code=409, detail={"code": "verified_release_authority_required"})
    outstanding_property = db.scalar(select(MortuaryPropertyItem.id).where(
        MortuaryPropertyItem.hospital_id == hospital_id,
        MortuaryPropertyItem.mortuary_case_id == case.id,
        MortuaryPropertyItem.status.in_(["received", "sealed"]),
    ).limit(1))
    if outstanding_property:
        raise HTTPException(status_code=409, detail={"code": "personal_effects_custody_must_be_resolved"})
    case.status = "released"
    case.released_to_name = payload.released_to_name
    case.released_to_identity_reference = payload.identity_reference
    case.released_by_user_id = user.id
    case.released_at = datetime.now(timezone.utc)
    _movement(db, hospital_id, user.id, case, "released", "Released to authorized recipient")
    _audit(db, hospital_id, user.id, "mortuary.case.released", "mortuary_case", case.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.post("/cases/{case_id}/property", status_code=status.HTTP_201_CREATED)
def add_mortuary_property(case_id: UUID, payload: MortuaryPropertyCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    case = _mortuary_case(db, case_id, hospital_id)
    if case.status in ("released", "transferred"):
        raise HTTPException(status_code=409, detail={"code": "terminal_mortuary_case"})
    item = MortuaryPropertyItem(
        hospital_id=hospital_id, mortuary_case_id=case.id,
        received_by_user_id=user.id, status="sealed" if payload.sealed else "received",
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    _audit(db, hospital_id, user.id, "mortuary.property.received", "mortuary_property_item", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"id": item.id, "status": item.status, "property_reference": item.property_reference}


@router.patch("/property/{property_id}/custody")
def update_mortuary_property(property_id: UUID, payload: MortuaryPropertyRelease, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_MANAGERS)
    item = db.scalar(select(MortuaryPropertyItem).where(
        MortuaryPropertyItem.id == property_id, MortuaryPropertyItem.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.status in ("released", "retained"):
        raise HTTPException(status_code=404, detail={"code": "active_property_item_not_found"})
    case = _mortuary_case(db, item.mortuary_case_id, hospital_id, lock=True)
    if payload.status == "released":
        if case.legal_hold or case.status not in ("release_pending", "released") or not payload.released_to_name:
            raise HTTPException(status_code=409, detail={"code": "authorized_case_release_required"})
        if not _has_verified_mortuary_authority(db, hospital_id, case.id):
            raise HTTPException(status_code=409, detail={"code": "verified_release_authority_required"})
        item.released_to_name = payload.released_to_name
        item.released_by_user_id = user.id
        item.released_at = datetime.now(timezone.utc)
    elif payload.status == "sealed":
        item.sealed = True
    item.status = payload.status
    _audit(db, hospital_id, user.id, "mortuary.property.custody_changed", "mortuary_property_item", item.id, {"status": payload.status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return {"id": item.id, "status": item.status, "released_to_name": item.released_to_name}


@router.get("/cases/{case_id}/property")
def list_mortuary_property(case_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    _mortuary_case(db, case_id, hospital_id)
    rows = db.scalars(select(MortuaryPropertyItem).where(
        MortuaryPropertyItem.hospital_id == hospital_id,
        MortuaryPropertyItem.mortuary_case_id == case_id,
    ).order_by(MortuaryPropertyItem.created_at)).all()
    return [{
        "id": row.id, "property_description": row.property_description,
        "property_reference": row.property_reference, "sealed": row.sealed,
        "status": row.status, "released_to_name": row.released_to_name,
        "released_by_user_id": row.released_by_user_id, "released_at": row.released_at,
        "received_by_user_id": row.received_by_user_id, "created_at": row.created_at,
    } for row in rows]


@router.get("/cases/{case_id}/movements")
def list_mortuary_movements(case_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _MORTUARY_STAFF)
    _mortuary_case(db, case_id, hospital_id)
    rows = db.scalars(select(MortuaryMovement).where(
        MortuaryMovement.hospital_id == hospital_id,
        MortuaryMovement.mortuary_case_id == case_id,
    ).order_by(MortuaryMovement.created_at)).all()
    return [{
        "id": row.id, "movement_type": row.movement_type, "from_location": row.from_location,
        "to_location": row.to_location, "actor_user_id": row.actor_user_id, "note": row.note,
        "created_at": row.created_at,
    } for row in rows]


@router.post("/pathology/cases", response_model=PathologyCaseRead, status_code=status.HTTP_201_CREATED)
def create_pathology_case(payload: PathologyCaseCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_STAFF)
    patient = db.scalar(select(Patient).where(
        Patient.id == payload.patient_id, Patient.hospital_id == hospital_id,
    ))
    if patient is None:
        raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    if payload.encounter_id is not None:
        encounter = db.scalar(select(Encounter).where(
            Encounter.id == payload.encounter_id, Encounter.hospital_id == hospital_id,
            Encounter.patient_id == patient.id,
        ))
        if encounter is None:
            raise HTTPException(status_code=404, detail={"code": "matching_encounter_not_found"})
    if payload.case_type in ("autopsy", "forensic") and (not payload.authority_type or not payload.authority_reference):
        raise HTTPException(status_code=422, detail={"code": "autopsy_or_forensic_authority_required"})
    if payload.case_type == "forensic" and payload.authority_type not in _FORENSIC_AUTHORITIES:
        raise HTTPException(status_code=422, detail={"code": "forensic_case_requires_legal_authority"})
    case = PathologyCase(
        hospital_id=hospital_id, opened_by_user_id=user.id, status="opened",
        **payload.model_dump(),
    )
    db.add(case)
    try:
        db.flush()
        _path_event(db, hospital_id, user.id, case.id, "case_opened")
        _audit(db, hospital_id, user.id, "pathology.case.opened", "pathology_case", case.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "pathology_case_number_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.get("/pathology/cases", response_model=list[PathologyCaseRead])
def list_pathology_cases(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_STAFF)
    return db.scalars(select(PathologyCase).where(
        PathologyCase.hospital_id == hospital_id,
    ).order_by(PathologyCase.created_at.desc()).limit(300)).all()


@router.post("/pathology/cases/{case_id}/verify-authority", response_model=PathologyCaseRead)
def verify_pathology_authority(case_id: UUID, payload: PathologyAuthorityVerification, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_MANAGERS)
    case = _pathology_case(db, case_id, hospital_id, lock=True)
    if case.case_type not in ("autopsy", "forensic") or case.authority_verified_at is not None:
        raise HTTPException(status_code=409, detail={"code": "unverified_autopsy_authority_required"})
    if case.opened_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_pathology_authority_verification_required"})
    if not payload.verified:
        case.status = "cancelled"
        _path_event(db, hospital_id, user.id, case.id, "case_cancelled", "Authority was not verified")
        _audit(db, hospital_id, user.id, "pathology.authority.rejected", "pathology_case", case.id)
    else:
        if not payload.evidence_reference:
            raise HTTPException(status_code=422, detail={"code": "vault_evidence_reference_required"})
        case.authority_evidence_reference = payload.evidence_reference
        case.authority_verified_by_user_id = user.id
        case.authority_verified_at = datetime.now(timezone.utc)
        _path_event(db, hospital_id, user.id, case.id, "authority_verified")
        _audit(db, hospital_id, user.id, "pathology.authority.verified", "pathology_case", case.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.post("/pathology/cases/{case_id}/assign", response_model=PathologyCaseRead)
def assign_pathologist(case_id: UUID, payload: PathologyAssignment, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_MANAGERS)
    case = _pathology_case(db, case_id, hospital_id, lock=True)
    if case.status in ("finalized", "closed", "cancelled"):
        raise HTTPException(status_code=409, detail={"code": "pathology_case_assignment_locked"})
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.pathologist_user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name not in _PATHOLOGISTS:
        raise HTTPException(status_code=422, detail={"code": "active_pathologist_required"})
    case.assigned_pathologist_user_id = payload.pathologist_user_id
    _audit(db, hospital_id, user.id, "pathology.case.assigned", "pathology_case", case.id, {"pathologist_user_id": str(payload.pathologist_user_id)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.post("/pathology/cases/{case_id}/specimens", response_model=PathologySpecimenRead, status_code=status.HTTP_201_CREATED)
def add_pathology_specimen(case_id: UUID, payload: PathologySpecimenCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_STAFF)
    case = _pathology_case(db, case_id, hospital_id, lock=True)
    if case.status in ("report_draft", "finalized", "closed", "cancelled"):
        raise HTTPException(status_code=409, detail={"code": "pathology_case_not_open"})
    if case.case_type in ("autopsy", "forensic") and case.authority_verified_at is None:
        raise HTTPException(status_code=403, detail={"code": "verified_autopsy_authority_required"})
    specimen = PathologySpecimen(
        hospital_id=hospital_id, pathology_case_id=case.id,
        status="collected", **payload.model_dump(),
    )
    db.add(specimen)
    try:
        db.flush()
        _path_event(db, hospital_id, user.id, case.id, "specimen_added")
        _audit(db, hospital_id, user.id, "pathology.specimen.added", "pathology_specimen", specimen.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "specimen_accession_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(specimen)
    return specimen


@router.patch("/pathology/specimens/{specimen_id}/status", response_model=PathologySpecimenRead)
def update_pathology_specimen_status(specimen_id: UUID, payload: PathologySpecimenStatus, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_STAFF)
    specimen = db.scalar(select(PathologySpecimen).where(
        PathologySpecimen.id == specimen_id, PathologySpecimen.hospital_id == hospital_id,
    ).with_for_update())
    if specimen is None:
        raise HTTPException(status_code=404, detail={"code": "pathology_specimen_not_found"})
    allowed = {
        "collected": {"received", "rejected"},
        "received": {"processing", "rejected"},
        "processing": {"processed", "rejected"},
        "processed": {"archived"},
    }
    if payload.status not in allowed.get(specimen.status, set()):
        raise HTTPException(status_code=409, detail={"code": "invalid_specimen_transition"})
    case = _pathology_case(db, specimen.pathology_case_id, hospital_id, lock=True)
    if case.status in ("report_draft", "finalized", "closed", "cancelled"):
        raise HTTPException(status_code=409, detail={"code": "pathology_case_locked_for_reporting"})
    if payload.status == "received":
        specimen.received_at = datetime.now(timezone.utc)
        specimen.received_by_user_id = user.id
        case.status = "specimens_received"
        event_type = "specimen_received"
    elif payload.status == "processing":
        case.status = "in_progress"
        event_type = "specimen_status_changed"
    else:
        event_type = "specimen_status_changed"
    specimen.status = payload.status
    _path_event(db, hospital_id, user.id, case.id, event_type, payload.status)
    _audit(db, hospital_id, user.id, "pathology.specimen.status_changed", "pathology_specimen", specimen.id, {"status": payload.status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(specimen)
    return specimen


@router.post("/pathology/cases/{case_id}/reports", response_model=PathologyReportRead, status_code=status.HTTP_201_CREATED)
def create_pathology_report(case_id: UUID, payload: PathologyReportCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require(db, user.id, hospital_id, _PATHOLOGISTS)
    case = _pathology_case(db, case_id, hospital_id, lock=True)
    if case.status in ("closed", "cancelled") or case.assigned_pathologist_user_id not in (None, user.id) and role not in _PATHOLOGY_MANAGERS:
        raise HTTPException(status_code=403, detail={"code": "assigned_pathologist_required"})
    if case.case_type in ("autopsy", "forensic") and case.authority_verified_at is None:
        raise HTTPException(status_code=403, detail={"code": "verified_autopsy_authority_required"})
    processed = db.scalar(select(PathologySpecimen.id).where(
        PathologySpecimen.hospital_id == hospital_id,
        PathologySpecimen.pathology_case_id == case.id,
        PathologySpecimen.status.in_(["processed", "archived"]),
    ).limit(1))
    if processed is None:
        raise HTTPException(status_code=409, detail={"code": "processed_specimen_required_before_reporting"})
    open_draft = db.scalar(select(PathologyReport.id).where(
        PathologyReport.hospital_id == hospital_id,
        PathologyReport.pathology_case_id == case.id,
        PathologyReport.status == "draft",
    ).limit(1))
    if open_draft is not None:
        raise HTTPException(status_code=409, detail={"code": "pathology_draft_report_already_exists"})
    version = (db.scalar(select(func.max(PathologyReport.version)).where(
        PathologyReport.hospital_id == hospital_id,
        PathologyReport.pathology_case_id == case.id,
    )) or 0) + 1
    report = PathologyReport(
        hospital_id=hospital_id, pathology_case_id=case.id, version=version,
        authored_by_user_id=user.id, status="draft", **payload.model_dump(),
    )
    db.add(report)
    case.status = "report_draft"
    db.flush()
    _path_event(db, hospital_id, user.id, case.id, "report_drafted", f"Report version {version}")
    _audit(db, hospital_id, user.id, "pathology.report.drafted", "pathology_report", report.id, {"version": version})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(report)
    return report


@router.post("/pathology/reports/{report_id}/finalize", response_model=PathologyReportRead)
def finalize_pathology_report(report_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require(db, user.id, hospital_id, _PATHOLOGISTS)
    report = db.scalar(select(PathologyReport).where(
        PathologyReport.id == report_id, PathologyReport.hospital_id == hospital_id,
    ).with_for_update())
    if report is None or report.status != "draft":
        raise HTTPException(status_code=404, detail={"code": "draft_pathology_report_not_found"})
    case = _pathology_case(db, report.pathology_case_id, hospital_id, lock=True)
    if case.assigned_pathologist_user_id not in (None, user.id) and role not in _PATHOLOGY_MANAGERS:
        raise HTTPException(status_code=403, detail={"code": "assigned_pathologist_required"})
    if report.authored_by_user_id != user.id and role not in _PATHOLOGY_MANAGERS:
        raise HTTPException(status_code=403, detail={"code": "report_author_or_pathology_manager_required"})
    report.status = "final"
    report.signed_by_user_id = user.id
    report.signed_at = datetime.now(timezone.utc)
    case.status = "finalized"
    _path_event(db, hospital_id, user.id, case.id, "report_finalized", f"Report version {report.version}")
    _audit(db, hospital_id, user.id, "pathology.report.finalized", "pathology_report", report.id, {"version": report.version})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(report)
    return report


@router.get("/pathology/cases/{case_id}/specimens", response_model=list[PathologySpecimenRead])
def list_pathology_specimens(case_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_STAFF)
    _pathology_case(db, case_id, hospital_id)
    return db.scalars(select(PathologySpecimen).where(
        PathologySpecimen.hospital_id == hospital_id,
        PathologySpecimen.pathology_case_id == case_id,
    ).order_by(PathologySpecimen.created_at)).all()


@router.get("/pathology/cases/{case_id}/reports", response_model=list[PathologyReportRead])
def list_pathology_reports(case_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_STAFF)
    _pathology_case(db, case_id, hospital_id)
    return db.scalars(select(PathologyReport).where(
        PathologyReport.hospital_id == hospital_id,
        PathologyReport.pathology_case_id == case_id,
    ).order_by(PathologyReport.version)).all()


@router.post("/pathology/cases/{case_id}/close", response_model=PathologyCaseRead)
def close_pathology_case(case_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_MANAGERS)
    case = _pathology_case(db, case_id, hospital_id, lock=True)
    if case.status != "finalized":
        raise HTTPException(status_code=409, detail={"code": "finalized_pathology_case_required"})
    case.status = "closed"
    _path_event(db, hospital_id, user.id, case.id, "case_closed")
    _audit(db, hospital_id, user.id, "pathology.case.closed", "pathology_case", case.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(case)
    return case


@router.get("/pathology/cases/{case_id}/events")
def list_pathology_events(case_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _PATHOLOGY_STAFF)
    _pathology_case(db, case_id, hospital_id)
    rows = db.scalars(select(PathologyEvent).where(
        PathologyEvent.hospital_id == hospital_id,
        PathologyEvent.pathology_case_id == case_id,
    ).order_by(PathologyEvent.created_at)).all()
    return [{"id": e.id, "event_type": e.event_type, "actor_user_id": e.actor_user_id, "note": e.note, "created_at": e.created_at} for e in rows]
