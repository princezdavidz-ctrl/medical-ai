from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Department, Encounter, HospitalMembership, Patient, Role, User
from app.models.quality import CAPAAction, SafetyIncident, SafetyIncidentEvent, SafetyInvestigation
from app.schemas.quality import (
    CAPACreate, CAPAEffectivenessReview, CAPAEvidenceSubmit, CAPARead,
    SafetyIncidentCreate, SafetyIncidentRead, SafetyIncidentTriage,
    SafetyInvestigationAssign, SafetyInvestigationRead, SafetyInvestigationUpdate,
)

router = APIRouter(prefix="/quality", tags=["quality assurance and patient safety"])
_SAFETY_ROLES = {"patient_safety_officer", "safety_officer", "quality_manager", "hospital_admin", "hospital_director", "medical_director"}
_DEPARTMENT_ROLES = {"department_head", "nurse_manager"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require_safety_role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    role = _role(db, user_id, hospital_id)
    if role not in _SAFETY_ROLES:
        raise HTTPException(status_code=403, detail={"code": "patient_safety_officer_role_required"})
    return role


def _department_scope(db: Session, user_id: UUID, hospital_id: UUID, role: str) -> UUID | None:
    if role not in _DEPARTMENT_ROLES:
        return None
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    if membership is None or membership.department_id is None:
        raise HTTPException(status_code=403, detail={"code": "active_department_assignment_required"})
    return membership.department_id


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID) -> None:
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
                      resource_type=resource_type, resource_id=str(resource_id), metadata={})


def _event(db: Session, hospital_id: UUID, incident_id: UUID, user_id: UUID, event_type: str, metadata=None) -> None:
    db.add(SafetyIncidentEvent(
        hospital_id=hospital_id, incident_id=incident_id, actor_user_id=user_id,
        event_type=event_type, event_metadata=metadata or {},
    ))


def _incident(db: Session, hospital_id: UUID, incident_id: UUID, lock: bool = False) -> SafetyIncident:
    query = select(SafetyIncident).where(
        SafetyIncident.hospital_id == hospital_id,
        SafetyIncident.id == incident_id,
    )
    if lock:
        query = query.with_for_update()
    incident = db.scalar(query)
    if incident is None:
        raise HTTPException(status_code=404, detail={"code": "safety_incident_not_found"})
    return incident


def _incident_read(incident: SafetyIncident, viewer_user_id: UUID, can_view_reporter: bool) -> SafetyIncidentRead:
    result = SafetyIncidentRead.model_validate(incident)
    if incident.reporter_confidential and incident.reporter_user_id != viewer_user_id and not can_view_reporter:
        result = result.model_copy(update={"reporter_user_id": None})
    return result


@router.post("/incidents", response_model=SafetyIncidentRead, status_code=status.HTTP_201_CREATED)
def report_safety_incident(payload: SafetyIncidentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    department_id = payload.department_id
    if department_id is not None:
        department = db.scalar(select(Department.id).where(
            Department.hospital_id == hospital_id,
            Department.id == department_id,
            Department.status == "active",
        ))
        if department is None:
            raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
    if payload.patient_id is not None:
        patient = db.scalar(select(Patient.id).where(
            Patient.hospital_id == hospital_id,
            Patient.id == payload.patient_id,
        ))
        if patient is None:
            raise HTTPException(status_code=404, detail={"code": "patient_not_found"})
    if payload.encounter_id is not None:
        encounter = db.scalar(select(Encounter.id).where(
            Encounter.hospital_id == hospital_id,
            Encounter.id == payload.encounter_id,
            Encounter.patient_id == payload.patient_id,
        ))
        if encounter is None:
            raise HTTPException(status_code=404, detail={"code": "patient_encounter_not_found"})
    incident = SafetyIncident(
        hospital_id=hospital_id, department_id=department_id,
        patient_id=payload.patient_id, encounter_id=payload.encounter_id,
        reporter_user_id=user.id, reporter_confidential=True,
        category=payload.category, occurred_at=payload.occurred_at,
        summary=payload.summary, immediate_actions=payload.immediate_actions,
    )
    db.add(incident)
    try:
        db.flush()
        _event(db, hospital_id, incident.id, user.id, "reported")
        _audit(db, hospital_id, user.id, "quality.incident_reported", "safety_incident", incident.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "safety_incident_reference_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _incident_read(incident, user.id, False)


@router.get("/incidents", response_model=list[SafetyIncidentRead])
def list_safety_incidents(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    query = select(SafetyIncident).where(SafetyIncident.hospital_id == hospital_id)
    if role not in _SAFETY_ROLES:
        if role in _DEPARTMENT_ROLES:
            department_id = _department_scope(db, user.id, hospital_id, role)
            query = query.where(or_(SafetyIncident.department_id == department_id, SafetyIncident.reporter_user_id == user.id))
        else:
            query = query.where(SafetyIncident.reporter_user_id == user.id)
    incidents = db.scalars(query.order_by(SafetyIncident.reported_at.desc()).limit(300)).all()
    can_view_reporter = role in _SAFETY_ROLES
    return [_incident_read(item, user.id, can_view_reporter) for item in incidents]


@router.get("/incidents/{incident_id}", response_model=SafetyIncidentRead)
def get_safety_incident(incident_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    incident = _incident(db, hospital_id, incident_id)
    allowed = role in _SAFETY_ROLES or incident.reporter_user_id == user.id
    if role in _DEPARTMENT_ROLES:
        allowed = incident.reporter_user_id == user.id or incident.department_id == _department_scope(db, user.id, hospital_id, role)
    if not allowed:
        raise HTTPException(status_code=404, detail={"code": "safety_incident_not_found"})
    _audit(db, hospital_id, user.id, "quality.incident_viewed", "safety_incident", incident.id)
    return _incident_read(incident, user.id, role in _SAFETY_ROLES)


@router.post("/incidents/{incident_id}/triage", response_model=SafetyIncidentRead)
def triage_safety_incident(incident_id: UUID, payload: SafetyIncidentTriage, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_safety_role(db, user.id, hospital_id)
    incident = _incident(db, hospital_id, incident_id, lock=True)
    if incident.status not in ("reported", "triaged", "reopened"):
        raise HTTPException(status_code=409, detail={"code": "incident_not_available_for_triage"})
    incident.severity = payload.severity
    incident.harm_level = payload.harm_level
    incident.status = "triaged"
    _event(db, hospital_id, incident.id, user.id, "triaged", {"severity": payload.severity, "harm_level": payload.harm_level})
    _audit(db, hospital_id, user.id, "quality.incident_triaged", "safety_incident", incident.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _incident_read(incident, user.id, True)


@router.post("/incidents/{incident_id}/investigation", response_model=SafetyInvestigationRead, status_code=status.HTTP_201_CREATED)
def assign_safety_investigation(incident_id: UUID, payload: SafetyInvestigationAssign, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_safety_role(db, user.id, hospital_id)
    incident = _incident(db, hospital_id, incident_id, lock=True)
    if incident.status not in ("triaged", "investigating", "reopened"):
        raise HTTPException(status_code=409, detail={"code": "incident_must_be_triaged_before_investigation"})
    assignee = db.scalar(select(HospitalMembership).join(
        User, User.id == HospitalMembership.user_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.assigned_to_user_id,
        HospitalMembership.status == "active",
        User.is_active.is_(True),
    ))
    if assignee is None:
        raise HTTPException(status_code=404, detail={"code": "active_same_hospital_investigator_not_found"})
    investigation = db.scalar(select(SafetyInvestigation).where(
        SafetyInvestigation.hospital_id == hospital_id,
        SafetyInvestigation.incident_id == incident.id,
    ).with_for_update())
    if investigation is None:
        investigation = SafetyInvestigation(
            hospital_id=hospital_id, incident_id=incident.id,
            assigned_to_user_id=payload.assigned_to_user_id, status="assigned",
        )
        db.add(investigation)
    else:
        investigation.assigned_to_user_id = payload.assigned_to_user_id
        investigation.status = "assigned"
        investigation.findings = None
        investigation.contributing_factors = []
        investigation.reviewed_by_user_id = None
        investigation.reviewed_at = None
    incident.status = "investigating"
    db.flush()
    _event(db, hospital_id, incident.id, user.id, "assigned", {"investigator_user_id": str(payload.assigned_to_user_id)})
    _audit(db, hospital_id, user.id, "quality.investigation_assigned", "safety_investigation", investigation.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(investigation)
    return investigation


@router.patch("/investigations/{investigation_id}", response_model=SafetyInvestigationRead)
def update_safety_investigation(investigation_id: UUID, payload: SafetyInvestigationUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    investigation = db.scalar(select(SafetyInvestigation).where(
        SafetyInvestigation.hospital_id == hospital_id,
        SafetyInvestigation.id == investigation_id,
    ).with_for_update())
    if investigation is None:
        raise HTTPException(status_code=404, detail={"code": "safety_investigation_not_found"})
    if investigation.assigned_to_user_id != user.id and _role(db, user.id, hospital_id) not in _SAFETY_ROLES:
        raise HTTPException(status_code=403, detail={"code": "assigned_investigator_required"})
    if investigation.status not in ("assigned", "in_progress", "rejected"):
        raise HTTPException(status_code=409, detail={"code": "investigation_not_editable"})
    investigation.findings = payload.findings
    investigation.contributing_factors = payload.contributing_factors
    investigation.status = "pending_review"
    incident = _incident(db, hospital_id, investigation.incident_id, lock=True)
    _event(db, hospital_id, incident.id, user.id, "investigation_completed")
    _audit(db, hospital_id, user.id, "quality.investigation_submitted", "safety_investigation", investigation.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(investigation)
    return investigation


@router.post("/investigations/{investigation_id}/review", response_model=SafetyInvestigationRead)
def review_safety_investigation(investigation_id: UUID, approved: bool, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_safety_role(db, user.id, hospital_id)
    investigation = db.scalar(select(SafetyInvestigation).where(
        SafetyInvestigation.hospital_id == hospital_id,
        SafetyInvestigation.id == investigation_id,
    ).with_for_update())
    if investigation is None:
        raise HTTPException(status_code=404, detail={"code": "safety_investigation_not_found"})
    if investigation.status != "pending_review" or investigation.assigned_to_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_investigation_review_required"})
    investigation.status = "approved" if approved else "rejected"
    investigation.reviewed_by_user_id = user.id
    investigation.reviewed_at = datetime.now(timezone.utc)
    incident = _incident(db, hospital_id, investigation.incident_id, lock=True)
    incident.status = "capa_open" if approved else "investigating"
    _event(db, hospital_id, incident.id, user.id, "status_changed", {"investigation_review": investigation.status})
    _audit(db, hospital_id, user.id, "quality.investigation_reviewed", "safety_investigation", investigation.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(investigation)
    return investigation


@router.post("/incidents/{incident_id}/capa", response_model=CAPARead, status_code=status.HTTP_201_CREATED)
def create_capa_action(incident_id: UUID, payload: CAPACreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_safety_role(db, user.id, hospital_id)
    incident = _incident(db, hospital_id, incident_id, lock=True)
    if incident.status not in ("capa_open", "pending_review"):
        raise HTTPException(status_code=409, detail={"code": "approved_investigation_required_before_capa"})
    owner = db.scalar(select(HospitalMembership.id).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.owner_user_id,
        HospitalMembership.status == "active",
    ))
    if owner is None:
        raise HTTPException(status_code=404, detail={"code": "active_same_hospital_capa_owner_not_found"})
    action = CAPAAction(
        hospital_id=hospital_id, incident_id=incident.id, owner_user_id=payload.owner_user_id,
        action_description=payload.action_description, due_at=payload.due_at,
        created_by_user_id=user.id,
    )
    db.add(action)
    incident.status = "capa_open"
    db.flush()
    _event(db, hospital_id, incident.id, user.id, "capa_created", {"capa_action_id": str(action.id)})
    _audit(db, hospital_id, user.id, "quality.capa_created", "safety_capa_action", action.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(action)
    return action


@router.post("/capa/{action_id}/evidence", response_model=CAPARead)
def submit_capa_evidence(action_id: UUID, payload: CAPAEvidenceSubmit, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    action = db.scalar(select(CAPAAction).where(
        CAPAAction.hospital_id == hospital_id,
        CAPAAction.id == action_id,
    ).with_for_update())
    if action is None:
        raise HTTPException(status_code=404, detail={"code": "capa_action_not_found"})
    if action.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "capa_action_owner_required"})
    if action.status not in ("open", "in_progress"):
        raise HTTPException(status_code=409, detail={"code": "capa_action_not_accepting_evidence"})
    action.evidence_reference = payload.evidence_reference
    action.status = "pending_effectiveness_review"
    _audit(db, hospital_id, user.id, "quality.capa_evidence_submitted", "safety_capa_action", action.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(action)
    return action


@router.post("/capa/{action_id}/effectiveness-review", response_model=CAPARead)
def review_capa_effectiveness(action_id: UUID, payload: CAPAEffectivenessReview, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_safety_role(db, user.id, hospital_id)
    action = db.scalar(select(CAPAAction).where(
        CAPAAction.hospital_id == hospital_id,
        CAPAAction.id == action_id,
    ).with_for_update())
    if action is None:
        raise HTTPException(status_code=404, detail={"code": "capa_action_not_found"})
    if action.status != "pending_effectiveness_review" or action.owner_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_capa_effectiveness_review_required"})
    action.effectiveness_review = payload.effectiveness_review
    action.effectiveness_reviewer_user_id = user.id
    action.effectiveness_reviewed_at = datetime.now(timezone.utc)
    action.status = "completed"
    incident = _incident(db, hospital_id, action.incident_id, lock=True)
    remaining = db.scalar(select(CAPAAction.id).where(
        CAPAAction.hospital_id == hospital_id,
        CAPAAction.incident_id == incident.id,
        CAPAAction.status != "completed",
    ).limit(1))
    if remaining is None:
        incident.status = "pending_review"
    _event(db, hospital_id, incident.id, user.id, "status_changed", {"capa_action_id": str(action.id), "capa_status": "completed"})
    _audit(db, hospital_id, user.id, "quality.capa_effectiveness_reviewed", "safety_capa_action", action.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(action)
    return action


@router.post("/incidents/{incident_id}/close", response_model=SafetyIncidentRead)
def close_safety_incident(incident_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_safety_role(db, user.id, hospital_id)
    incident = _incident(db, hospital_id, incident_id, lock=True)
    if incident.status == "closed":
        raise HTTPException(status_code=409, detail={"code": "safety_incident_already_closed"})
    investigation = db.scalar(select(SafetyInvestigation).where(
        SafetyInvestigation.hospital_id == hospital_id,
        SafetyInvestigation.incident_id == incident.id,
        SafetyInvestigation.status == "approved",
    ))
    pending_capa = db.scalar(select(CAPAAction.id).where(
        CAPAAction.hospital_id == hospital_id,
        CAPAAction.incident_id == incident.id,
        CAPAAction.status != "completed",
    ).limit(1))
    if investigation is None or pending_capa is not None:
        raise HTTPException(status_code=409, detail={"code": "approved_investigation_and_completed_capa_required"})
    incident.status = "closed"
    _event(db, hospital_id, incident.id, user.id, "closed")
    _audit(db, hospital_id, user.id, "quality.incident_closed", "safety_incident", incident.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _incident_read(incident, user.id, True)


@router.get("/incidents/{incident_id}/investigation", response_model=SafetyInvestigationRead)
def get_safety_investigation(incident_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    incident = _incident(db, hospital_id, incident_id)
    role = _role(db, user.id, hospital_id)
    investigation = db.scalar(select(SafetyInvestigation).where(
        SafetyInvestigation.hospital_id == hospital_id,
        SafetyInvestigation.incident_id == incident_id,
    ))
    if investigation is None or (role not in _SAFETY_ROLES and investigation.assigned_to_user_id != user.id):
        raise HTTPException(status_code=404, detail={"code": "safety_investigation_not_found"})
    return investigation


@router.get("/incidents/{incident_id}/capa", response_model=list[CAPARead])
def list_incident_capa(incident_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _incident(db, hospital_id, incident_id)
    role = _role(db, user.id, hospital_id)
    query = select(CAPAAction).where(
        CAPAAction.hospital_id == hospital_id,
        CAPAAction.incident_id == incident_id,
    )
    if role not in _SAFETY_ROLES:
        query = query.where(CAPAAction.owner_user_id == user.id)
    return db.scalars(query.order_by(CAPAAction.due_at)).all()


@router.get("/dashboard")
def get_quality_dashboard(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role not in _SAFETY_ROLES and role not in _DEPARTMENT_ROLES:
        raise HTTPException(status_code=403, detail={"code": "quality_dashboard_role_required"})
    status_query = select(
        SafetyIncident.status, func.count(SafetyIncident.id),
    ).where(SafetyIncident.hospital_id == hospital_id)
    severity_query = select(
        SafetyIncident.severity, func.count(SafetyIncident.id),
    ).where(SafetyIncident.hospital_id == hospital_id)
    if role in _DEPARTMENT_ROLES:
        department_id = _department_scope(db, user.id, hospital_id, role)
        status_query = status_query.where(SafetyIncident.department_id == department_id)
        severity_query = severity_query.where(SafetyIncident.department_id == department_id)
    status_rows = db.execute(status_query.group_by(SafetyIncident.status)).all()
    severity_rows = db.execute(severity_query.group_by(SafetyIncident.severity)).all()
    return {
        "by_status": {state: count for state, count in status_rows},
        "by_severity": {severity: count for severity, count in severity_rows},
    }


@router.get("/my-capa", response_model=list[CAPARead])
def list_my_capa_actions(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    return db.scalars(select(CAPAAction).where(
        CAPAAction.hospital_id == hospital_id,
        CAPAAction.owner_user_id == user.id,
        CAPAAction.status.in_(("open", "in_progress", "pending_effectiveness_review")),
    ).order_by(CAPAAction.due_at).limit(200)).all()
