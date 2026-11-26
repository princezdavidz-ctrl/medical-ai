from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import HospitalMembership, Role, User
from app.models.compliance import (
    CompliancePolicy, ComplianceRisk, PolicyAcknowledgement,
    SecurityIncident, SecurityIncidentEvent,
)
from app.schemas.compliance import (
    CompliancePolicyCreate, CompliancePolicyPublish, CompliancePolicyRead,
    ComplianceRiskCreate, ComplianceRiskRead, ComplianceRiskReview,
    PolicyAcknowledgementRead, SecurityIncidentAssign, SecurityIncidentCreate,
    SecurityIncidentRead, SecurityIncidentTriage, SecurityIncidentUpdate,
)

router = APIRouter(prefix="/compliance", tags=["compliance and security management"])
_COMPLIANCE_ROLES = {"compliance_officer", "privacy_officer", "security_officer", "information_security_officer", "hospital_admin", "hospital_director", "medical_director"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require_compliance(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    role = _role(db, user_id, hospital_id)
    if role not in _COMPLIANCE_ROLES:
        raise HTTPException(status_code=403, detail={"code": "compliance_or_security_officer_role_required"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID) -> None:
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
                      resource_type=resource_type, resource_id=str(resource_id), metadata={})


def _security_event(db: Session, hospital_id: UUID, incident_id: UUID, user_id: UUID, event_type: str, metadata=None) -> None:
    db.add(SecurityIncidentEvent(
        hospital_id=hospital_id, incident_id=incident_id, actor_user_id=user_id,
        event_type=event_type, event_metadata=metadata or {},
    ))


def _security_incident(db: Session, hospital_id: UUID, incident_id: UUID, lock: bool = False) -> SecurityIncident:
    query = select(SecurityIncident).where(
        SecurityIncident.hospital_id == hospital_id,
        SecurityIncident.id == incident_id,
    )
    if lock:
        query = query.with_for_update()
    incident = db.scalar(query)
    if incident is None:
        raise HTTPException(status_code=404, detail={"code": "security_incident_not_found"})
    return incident


def _security_incident_read(incident: SecurityIncident, user_id: UUID, can_view_reporter: bool) -> SecurityIncidentRead:
    result = SecurityIncidentRead.model_validate(incident)
    if incident.reporter_confidential and incident.reporter_user_id != user_id and not can_view_reporter:
        result = result.model_copy(update={"reporter_user_id": None})
    return result


@router.post("/policies", response_model=CompliancePolicyRead, status_code=status.HTTP_201_CREATED)
def create_compliance_policy(payload: CompliancePolicyCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    latest = db.scalar(select(CompliancePolicy).where(
        CompliancePolicy.hospital_id == hospital_id,
        CompliancePolicy.policy_code == payload.policy_code,
    ).order_by(CompliancePolicy.version.desc()).limit(1))
    policy = CompliancePolicy(
        hospital_id=hospital_id, version=(latest.version + 1 if latest else 1),
        created_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(policy)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "compliance.policy_created", "compliance_policy", policy.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "compliance_policy_version_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(policy)
    return policy


@router.post("/policies/{policy_id}/publish", response_model=CompliancePolicyRead)
def publish_compliance_policy(policy_id: UUID, payload: CompliancePolicyPublish, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    policy = db.scalar(select(CompliancePolicy).where(
        CompliancePolicy.hospital_id == hospital_id,
        CompliancePolicy.id == policy_id,
    ).with_for_update())
    if policy is None:
        raise HTTPException(status_code=404, detail={"code": "compliance_policy_not_found"})
    if policy.status != "draft" or policy.created_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_policy_publication_required"})
    policy.status = "published"
    policy.effective_at = payload.effective_at
    policy.published_by_user_id = user.id
    policy.published_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "compliance.policy_published", "compliance_policy", policy.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(policy)
    return policy


@router.get("/policies", response_model=list[CompliancePolicyRead])
def list_compliance_policies(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    return db.scalars(select(CompliancePolicy).where(
        CompliancePolicy.hospital_id == hospital_id,
        CompliancePolicy.status == "published",
        CompliancePolicy.effective_at <= datetime.now(timezone.utc),
    ).order_by(CompliancePolicy.policy_code, CompliancePolicy.version.desc()).limit(300)).all()


@router.post("/policies/{policy_id}/acknowledge", response_model=PolicyAcknowledgementRead, status_code=status.HTTP_201_CREATED)
def acknowledge_compliance_policy(policy_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    policy = db.scalar(select(CompliancePolicy).where(
        CompliancePolicy.hospital_id == hospital_id,
        CompliancePolicy.id == policy_id,
        CompliancePolicy.status == "published",
        CompliancePolicy.effective_at <= datetime.now(timezone.utc),
    ))
    if policy is None:
        raise HTTPException(status_code=404, detail={"code": "effective_published_policy_not_found"})
    existing = db.scalar(select(PolicyAcknowledgement).where(
        PolicyAcknowledgement.hospital_id == hospital_id,
        PolicyAcknowledgement.policy_id == policy.id,
        PolicyAcknowledgement.user_id == user.id,
    ))
    if existing is not None:
        return existing
    acknowledgement = PolicyAcknowledgement(
        hospital_id=hospital_id, policy_id=policy.id, user_id=user.id,
        acknowledgement_method="electronic",
    )
    db.add(acknowledgement)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "compliance.policy_acknowledged", "compliance_policy", policy.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        existing = db.scalar(select(PolicyAcknowledgement).where(
            PolicyAcknowledgement.hospital_id == hospital_id,
            PolicyAcknowledgement.policy_id == policy.id,
            PolicyAcknowledgement.user_id == user.id,
        ))
        if existing is not None:
            return existing
        raise HTTPException(status_code=409, detail={"code": "policy_acknowledgement_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(acknowledgement)
    return acknowledgement


@router.get("/policies/{policy_id}/acknowledgements", response_model=list[PolicyAcknowledgementRead])
def list_policy_acknowledgements(policy_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    policy = db.scalar(select(CompliancePolicy.id).where(
        CompliancePolicy.hospital_id == hospital_id,
        CompliancePolicy.id == policy_id,
    ))
    if policy is None:
        raise HTTPException(status_code=404, detail={"code": "compliance_policy_not_found"})
    return db.scalars(select(PolicyAcknowledgement).where(
        PolicyAcknowledgement.hospital_id == hospital_id,
        PolicyAcknowledgement.policy_id == policy_id,
    ).order_by(PolicyAcknowledgement.acknowledged_at.desc()).limit(1000)).all()


@router.post("/security-incidents", response_model=SecurityIncidentRead, status_code=status.HTTP_201_CREATED)
def report_security_incident(payload: SecurityIncidentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    incident = SecurityIncident(
        hospital_id=hospital_id, reporter_user_id=user.id, reporter_confidential=True,
        category=payload.category, affected_system=payload.affected_system,
        summary=payload.summary, immediate_actions=payload.immediate_actions,
    )
    db.add(incident)
    db.flush()
    _security_event(db, hospital_id, incident.id, user.id, "reported")
    _audit(db, hospital_id, user.id, "compliance.security_incident_reported", "security_incident", incident.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _security_incident_read(incident, user.id, False)


@router.get("/security-incidents", response_model=list[SecurityIncidentRead])
def list_security_incidents(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    query = select(SecurityIncident).where(SecurityIncident.hospital_id == hospital_id)
    if role not in _COMPLIANCE_ROLES:
        query = query.where(or_(
            SecurityIncident.reporter_user_id == user.id,
            SecurityIncident.assigned_to_user_id == user.id,
        ))
    incidents = db.scalars(query.order_by(SecurityIncident.reported_at.desc()).limit(300)).all()
    return [_security_incident_read(item, user.id, role in _COMPLIANCE_ROLES) for item in incidents]


@router.post("/security-incidents/{incident_id}/triage", response_model=SecurityIncidentRead)
def triage_security_incident(incident_id: UUID, payload: SecurityIncidentTriage, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    incident = _security_incident(db, hospital_id, incident_id, lock=True)
    if incident.status != "reported":
        raise HTTPException(status_code=409, detail={"code": "security_incident_not_reported"})
    incident.severity = payload.severity
    incident.breach_assessment = payload.breach_assessment
    incident.status = "triaged"
    _security_event(db, hospital_id, incident.id, user.id, "triaged", {"severity": payload.severity, "breach_assessment": payload.breach_assessment})
    _audit(db, hospital_id, user.id, "compliance.security_incident_triaged", "security_incident", incident.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _security_incident_read(incident, user.id, True)


@router.post("/security-incidents/{incident_id}/assign", response_model=SecurityIncidentRead)
def assign_security_incident(incident_id: UUID, payload: SecurityIncidentAssign, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    incident = _security_incident(db, hospital_id, incident_id, lock=True)
    member = db.scalar(select(HospitalMembership.id).join(
        User, User.id == HospitalMembership.user_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.assigned_to_user_id,
        HospitalMembership.status == "active",
        User.is_active.is_(True),
    ))
    if member is None:
        raise HTTPException(status_code=404, detail={"code": "active_same_hospital_security_assignee_required"})
    incident.assigned_to_user_id = payload.assigned_to_user_id
    if incident.status == "triaged":
        incident.status = "investigating"
    _security_event(db, hospital_id, incident.id, user.id, "assigned", {"assignee_user_id": str(payload.assigned_to_user_id)})
    _audit(db, hospital_id, user.id, "compliance.security_incident_assigned", "security_incident", incident.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _security_incident_read(incident, user.id, True)


@router.patch("/security-incidents/{incident_id}", response_model=SecurityIncidentRead)
def update_security_incident(incident_id: UUID, payload: SecurityIncidentUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    incident = _security_incident(db, hospital_id, incident_id, lock=True)
    if incident.assigned_to_user_id != user.id and _role(db, user.id, hospital_id) not in _COMPLIANCE_ROLES:
        raise HTTPException(status_code=403, detail={"code": "assigned_security_investigator_required"})
    if incident.status in ("resolved", "closed"):
        raise HTTPException(status_code=409, detail={"code": "security_incident_already_resolved"})
    if payload.status == "investigating" and incident.status not in ("triaged", "investigating"):
        raise HTTPException(status_code=409, detail={"code": "security_incident_must_be_triaged"})
    if payload.status == "contained":
        if incident.status not in ("triaged", "investigating", "contained"):
            raise HTTPException(status_code=409, detail={"code": "security_incident_cannot_be_contained"})
        incident.contained_at = incident.contained_at or datetime.now(timezone.utc)
        _security_event(db, hospital_id, incident.id, user.id, "contained")
    if payload.status == "resolved":
        if incident.contained_at is None or incident.breach_assessment == "pending":
            raise HTTPException(status_code=409, detail={"code": "containment_and_breach_assessment_required"})
        incident.resolved_at = datetime.now(timezone.utc)
        _security_event(db, hospital_id, incident.id, user.id, "resolved")
    incident.status = payload.status
    if payload.immediate_actions is not None:
        incident.immediate_actions = payload.immediate_actions
    _audit(db, hospital_id, user.id, "compliance.security_incident_updated", "security_incident", incident.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _security_incident_read(incident, user.id, _role(db, user.id, hospital_id) in _COMPLIANCE_ROLES)


@router.post("/security-incidents/{incident_id}/close", response_model=SecurityIncidentRead)
def close_security_incident(incident_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    incident = _security_incident(db, hospital_id, incident_id, lock=True)
    if incident.status != "resolved" or incident.breach_assessment == "pending":
        raise HTTPException(status_code=409, detail={"code": "resolved_incident_and_breach_assessment_required"})
    incident.status = "closed"
    _security_event(db, hospital_id, incident.id, user.id, "closed")
    _audit(db, hospital_id, user.id, "compliance.security_incident_closed", "security_incident", incident.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(incident)
    return _security_incident_read(incident, user.id, True)


@router.post("/risks", response_model=ComplianceRiskRead, status_code=status.HTTP_201_CREATED)
def create_compliance_risk(payload: ComplianceRiskCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    owner = db.scalar(select(HospitalMembership.id).join(
        User, User.id == HospitalMembership.user_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.owner_user_id,
        HospitalMembership.status == "active",
        User.is_active.is_(True),
    ))
    if owner is None:
        raise HTTPException(status_code=404, detail={"code": "active_same_hospital_risk_owner_required"})
    risk = ComplianceRisk(
        hospital_id=hospital_id, owner_user_id=payload.owner_user_id,
        category=payload.category, title=payload.title, description=payload.description,
        likelihood=payload.likelihood, impact=payload.impact,
        inherent_score=payload.likelihood * payload.impact,
        residual_likelihood=payload.likelihood, residual_impact=payload.impact,
        residual_score=payload.likelihood * payload.impact,
        mitigation_plan=payload.mitigation_plan, due_at=payload.due_at,
        created_by_user_id=user.id,
    )
    db.add(risk)
    db.flush()
    _audit(db, hospital_id, user.id, "compliance.risk_created", "compliance_risk", risk.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(risk)
    return risk


@router.get("/risks", response_model=list[ComplianceRiskRead])
def list_compliance_risks(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    query = select(ComplianceRisk).where(ComplianceRisk.hospital_id == hospital_id)
    if role not in _COMPLIANCE_ROLES:
        query = query.where(ComplianceRisk.owner_user_id == user.id)
    return db.scalars(query.order_by(ComplianceRisk.inherent_score.desc(), ComplianceRisk.due_at).limit(500)).all()


@router.post("/risks/{risk_id}/review", response_model=ComplianceRiskRead)
def review_compliance_risk(risk_id: UUID, payload: ComplianceRiskReview, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    risk = db.scalar(select(ComplianceRisk).where(
        ComplianceRisk.hospital_id == hospital_id,
        ComplianceRisk.id == risk_id,
    ).with_for_update())
    if risk is None:
        raise HTTPException(status_code=404, detail={"code": "compliance_risk_not_found"})
    if risk.owner_user_id == user.id:
        raise HTTPException(status_code=403, detail={"code": "independent_risk_review_required"})
    risk.residual_likelihood = payload.residual_likelihood
    risk.residual_impact = payload.residual_impact
    risk.residual_score = payload.residual_likelihood * payload.residual_impact
    risk.mitigation_plan = payload.mitigation_plan
    risk.status = payload.status
    risk.reviewed_by_user_id = user.id
    risk.reviewed_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "compliance.risk_reviewed", "compliance_risk", risk.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(risk)
    return risk


@router.get("/dashboard")
def get_compliance_dashboard(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    incident_rows = db.execute(select(
        SecurityIncident.status, func.count(SecurityIncident.id),
    ).where(SecurityIncident.hospital_id == hospital_id).group_by(SecurityIncident.status)).all()
    risk_rows = db.execute(select(
        ComplianceRisk.status, func.count(ComplianceRisk.id),
    ).where(ComplianceRisk.hospital_id == hospital_id).group_by(ComplianceRisk.status)).all()
    outstanding_policy_count = db.scalar(select(func.count(CompliancePolicy.id)).where(
        CompliancePolicy.hospital_id == hospital_id,
        CompliancePolicy.status == "published",
    )) or 0
    return {
        "security_incidents_by_status": {state: count for state, count in incident_rows},
        "risks_by_status": {state: count for state, count in risk_rows},
        "published_policy_versions": outstanding_policy_count,
    }
