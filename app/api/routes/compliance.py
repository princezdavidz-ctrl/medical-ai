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
    AccessReviewCampaign, AccessReviewItem, ComplianceControl, ControlAssessment,
    CompliancePolicy, ComplianceRisk, PolicyAcknowledgement,
    LegalHold, RetentionPolicy, RetentionDispositionRequest,
    SecurityIncident, SecurityIncidentEvent,
)
from app.schemas.compliance_access import (
    AccessReviewCampaignCreate, AccessReviewCampaignRead, AccessReviewItemApproval,
    AccessReviewItemDecision, AccessReviewItemRead, ComplianceControlCreate,
    ComplianceControlRead, ControlAssessmentCreate, ControlAssessmentRead,
    ControlAssessmentReview,
)
from app.schemas.retention import (
    LegalHoldCreate, LegalHoldRead, LegalHoldRelease, RetentionDispositionCreate,
    RetentionDispositionRead, RetentionDispositionReview, RetentionPolicyActivate,
    RetentionPolicyCreate, RetentionPolicyRead,
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


@router.post("/controls", response_model=ComplianceControlRead, status_code=status.HTTP_201_CREATED)
def create_compliance_control(payload: ComplianceControlCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=404, detail={"code": "active_same_hospital_control_owner_required"})
    latest = db.scalar(select(ComplianceControl).where(
        ComplianceControl.hospital_id == hospital_id,
        ComplianceControl.code == payload.code,
    ).order_by(ComplianceControl.version.desc()).limit(1))
    control = ComplianceControl(
        hospital_id=hospital_id, version=(latest.version + 1 if latest else 1),
        created_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(control)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "compliance.control_created", "compliance_control", control.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "compliance_control_version_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(control)
    return control


@router.post("/controls/{control_id}/activate", response_model=ComplianceControlRead)
def activate_compliance_control(control_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    control = db.scalar(select(ComplianceControl).where(
        ComplianceControl.hospital_id == hospital_id,
        ComplianceControl.id == control_id,
    ).with_for_update())
    if control is None:
        raise HTTPException(status_code=404, detail={"code": "compliance_control_not_found"})
    if control.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "only_draft_compliance_controls_can_be_activated"})
    control.status = "active"
    _audit(db, hospital_id, user.id, "compliance.control_activated", "compliance_control", control.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(control)
    return control


@router.get("/controls", response_model=list[ComplianceControlRead])
def list_compliance_controls(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    return db.scalars(select(ComplianceControl).where(
        ComplianceControl.hospital_id == hospital_id,
        ComplianceControl.status == "active",
    ).order_by(ComplianceControl.framework, ComplianceControl.code, ComplianceControl.version.desc()).limit(500)).all()


@router.post("/controls/{control_id}/assessments", response_model=ControlAssessmentRead, status_code=status.HTTP_201_CREATED)
def create_control_assessment(control_id: UUID, payload: ControlAssessmentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    control = db.scalar(select(ComplianceControl).where(
        ComplianceControl.hospital_id == hospital_id,
        ComplianceControl.id == control_id,
        ComplianceControl.status == "active",
    ))
    if control is None:
        raise HTTPException(status_code=404, detail={"code": "active_compliance_control_not_found"})
    if payload.next_review_at is not None and payload.next_review_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail={"code": "control_next_review_must_be_future"})
    assessment = ControlAssessment(
        hospital_id=hospital_id, control_id=control.id, assessor_user_id=user.id,
        findings=payload.findings, evidence_reference=payload.evidence_reference,
        next_review_at=payload.next_review_at,
    )
    db.add(assessment)
    db.flush()
    _audit(db, hospital_id, user.id, "compliance.control_assessed", "control_assessment", assessment.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(assessment)
    return assessment


@router.post("/assessments/{assessment_id}/review", response_model=ControlAssessmentRead)
def review_control_assessment(assessment_id: UUID, payload: ControlAssessmentReview, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    assessment = db.scalar(select(ControlAssessment).where(
        ControlAssessment.hospital_id == hospital_id,
        ControlAssessment.id == assessment_id,
    ).with_for_update())
    if assessment is None:
        raise HTTPException(status_code=404, detail={"code": "control_assessment_not_found"})
    if assessment.status != "pending_review" or assessment.assessor_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_control_assessment_review_required"})
    assessment.status = payload.status
    assessment.reviewed_by_user_id = user.id
    assessment.reviewed_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "compliance.control_assessment_reviewed", "control_assessment", assessment.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(assessment)
    return assessment


@router.post("/access-reviews", response_model=AccessReviewCampaignRead, status_code=status.HTTP_201_CREATED)
def create_access_review_campaign(payload: AccessReviewCampaignCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    campaign = AccessReviewCampaign(
        hospital_id=hospital_id, title=payload.title,
        period_start=payload.period_start, period_end=payload.period_end,
        due_at=payload.due_at, status="open", created_by_user_id=user.id,
    )
    db.add(campaign)
    db.flush()
    memberships = db.execute(select(
        HospitalMembership.user_id, HospitalMembership.department_id, Role.name,
    ).join(Role, Role.id == HospitalMembership.role_id).join(
        User, User.id == HospitalMembership.user_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.status == "active",
        User.is_active.is_(True),
    )).all()
    for subject_user_id, department_id, role_name in memberships:
        db.add(AccessReviewItem(
            hospital_id=hospital_id, campaign_id=campaign.id,
            subject_user_id=subject_user_id, department_id=department_id,
            role_name_snapshot=role_name, decision="pending", review_status="pending",
        ))
    _audit(db, hospital_id, user.id, "compliance.access_review_campaign_created", "access_review_campaign", campaign.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(campaign)
    return campaign


@router.get("/access-reviews", response_model=list[AccessReviewCampaignRead])
def list_access_review_campaigns(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    return db.scalars(select(AccessReviewCampaign).where(
        AccessReviewCampaign.hospital_id == hospital_id,
    ).order_by(AccessReviewCampaign.created_at.desc()).limit(200)).all()


@router.get("/access-reviews/{campaign_id}/items", response_model=list[AccessReviewItemRead])
def list_access_review_items(campaign_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    return db.scalars(select(AccessReviewItem).where(
        AccessReviewItem.hospital_id == hospital_id,
        AccessReviewItem.campaign_id == campaign_id,
    ).order_by(AccessReviewItem.role_name_snapshot, AccessReviewItem.subject_user_id).limit(2000)).all()


@router.post("/access-review-items/{item_id}/review", response_model=AccessReviewItemRead)
def review_access_item(item_id: UUID, payload: AccessReviewItemDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    item = db.scalar(select(AccessReviewItem).where(
        AccessReviewItem.hospital_id == hospital_id,
        AccessReviewItem.id == item_id,
    ).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "access_review_item_not_found"})
    campaign = db.scalar(select(AccessReviewCampaign).where(
        AccessReviewCampaign.hospital_id == hospital_id,
        AccessReviewCampaign.id == item.campaign_id,
    ))
    if campaign is None or campaign.status != "open":
        raise HTTPException(status_code=409, detail={"code": "open_access_review_campaign_required"})
    if item.review_status != "pending" or item.subject_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_access_review_required"})
    item.decision = payload.decision
    item.justification = payload.justification
    item.review_status = "awaiting_approval"
    item.reviewed_by_user_id = user.id
    item.reviewed_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "compliance.access_review_item_reviewed", "access_review_item", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.post("/access-review-items/{item_id}/approve", response_model=AccessReviewItemRead)
def approve_access_item(item_id: UUID, payload: AccessReviewItemApproval, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    item = db.scalar(select(AccessReviewItem).where(
        AccessReviewItem.hospital_id == hospital_id,
        AccessReviewItem.id == item_id,
    ).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "access_review_item_not_found"})
    campaign = db.scalar(select(AccessReviewCampaign).where(
        AccessReviewCampaign.hospital_id == hospital_id,
        AccessReviewCampaign.id == item.campaign_id,
    ))
    if campaign is None or campaign.status != "open":
        raise HTTPException(status_code=409, detail={"code": "open_access_review_campaign_required"})
    if item.review_status != "awaiting_approval" or item.reviewed_by_user_id == user.id or item.subject_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_access_review_approval_required"})
    item.review_status = "approved"
    item.approved_by_user_id = user.id
    item.approved_at = datetime.now(timezone.utc)
    item.approval_note = payload.approval_note
    _audit(db, hospital_id, user.id, "compliance.access_review_item_approved", "access_review_item", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.post("/access-reviews/{campaign_id}/complete", response_model=AccessReviewCampaignRead)
def complete_access_review_campaign(campaign_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    campaign = db.scalar(select(AccessReviewCampaign).where(
        AccessReviewCampaign.hospital_id == hospital_id,
        AccessReviewCampaign.id == campaign_id,
    ).with_for_update())
    if campaign is None:
        raise HTTPException(status_code=404, detail={"code": "access_review_campaign_not_found"})
    if campaign.status != "open":
        raise HTTPException(status_code=409, detail={"code": "access_review_campaign_not_open"})
    pending = db.scalar(select(AccessReviewItem.id).where(
        AccessReviewItem.hospital_id == hospital_id,
        AccessReviewItem.campaign_id == campaign_id,
        AccessReviewItem.review_status != "approved",
    ).limit(1))
    if pending is not None:
        raise HTTPException(status_code=409, detail={"code": "all_access_review_items_must_be_approved"})
    campaign.status = "completed"
    campaign.completed_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "compliance.access_review_campaign_completed", "access_review_campaign", campaign.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(campaign)
    return campaign


@router.post("/retention-policies", response_model=RetentionPolicyRead, status_code=status.HTTP_201_CREATED)
def create_retention_policy(payload: RetentionPolicyCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    latest = db.scalar(select(RetentionPolicy).where(
        RetentionPolicy.hospital_id == hospital_id,
        RetentionPolicy.policy_code == payload.policy_code,
    ).order_by(RetentionPolicy.version.desc()).limit(1))
    policy = RetentionPolicy(
        hospital_id=hospital_id, version=(latest.version + 1 if latest else 1),
        created_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(policy)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "compliance.retention_policy_created", "retention_policy", policy.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "retention_policy_version_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(policy)
    return policy


@router.post("/retention-policies/{policy_id}/activate", response_model=RetentionPolicyRead)
def activate_retention_policy(policy_id: UUID, payload: RetentionPolicyActivate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    policy = db.scalar(select(RetentionPolicy).where(
        RetentionPolicy.hospital_id == hospital_id,
        RetentionPolicy.id == policy_id,
    ).with_for_update())
    if policy is None:
        raise HTTPException(status_code=404, detail={"code": "retention_policy_not_found"})
    if policy.status != "draft" or policy.created_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_retention_policy_approval_required"})
    policy.status = "active"
    policy.effective_at = payload.effective_at
    policy.approved_by_user_id = user.id
    policy.approved_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "compliance.retention_policy_activated", "retention_policy", policy.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(policy)
    return policy


@router.get("/retention-policies", response_model=list[RetentionPolicyRead])
def list_retention_policies(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    return db.scalars(select(RetentionPolicy).where(
        RetentionPolicy.hospital_id == hospital_id,
    ).order_by(RetentionPolicy.policy_code, RetentionPolicy.version.desc()).limit(500)).all()


@router.post("/legal-holds", response_model=LegalHoldRead, status_code=status.HTTP_201_CREATED)
def create_legal_hold(payload: LegalHoldCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    now = datetime.now(timezone.utc)
    if payload.expires_at is not None and payload.expires_at <= now:
        raise HTTPException(status_code=422, detail={"code": "legal_hold_expiry_must_be_future"})
    import re
    if any(re.fullmatch(r"vault://[0-9a-fA-F-]{36}", ref) is None for ref in payload.resource_references):
        raise HTTPException(status_code=422, detail={"code": "legal_hold_resource_reference_invalid"})
    hold = LegalHold(
        hospital_id=hospital_id, hold_reference=payload.hold_reference,
        scope={"resource_references": payload.resource_references},
        reason=payload.reason, issued_by_user_id=user.id, expires_at=payload.expires_at,
    )
    db.add(hold)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "compliance.legal_hold_issued", "legal_hold", hold.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "legal_hold_reference_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(hold)
    return hold


@router.get("/legal-holds", response_model=list[LegalHoldRead])
def list_legal_holds(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    return db.scalars(select(LegalHold).where(
        LegalHold.hospital_id == hospital_id,
    ).order_by(LegalHold.issued_at.desc()).limit(500)).all()


@router.post("/legal-holds/{hold_id}/release", response_model=LegalHoldRead)
def release_legal_hold(hold_id: UUID, payload: LegalHoldRelease, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    hold = db.scalar(select(LegalHold).where(
        LegalHold.hospital_id == hospital_id,
        LegalHold.id == hold_id,
    ).with_for_update())
    if hold is None:
        raise HTTPException(status_code=404, detail={"code": "legal_hold_not_found"})
    if hold.status != "active":
        raise HTTPException(status_code=409, detail={"code": "only_active_legal_holds_can_be_released"})
    hold.status = "released"
    hold.released_by_user_id = user.id
    hold.released_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "compliance.legal_hold_released", "legal_hold", hold.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(hold)
    return hold


@router.post("/dispositions", response_model=RetentionDispositionRead, status_code=status.HTTP_201_CREATED)
def request_retention_disposition(payload: RetentionDispositionCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    policy = db.scalar(select(RetentionPolicy).where(
        RetentionPolicy.hospital_id == hospital_id,
        RetentionPolicy.id == payload.policy_id,
        RetentionPolicy.status == "active",
        RetentionPolicy.effective_at <= datetime.now(timezone.utc),
        RetentionPolicy.data_domain == payload.resource_type,
    ))
    if policy is None:
        raise HTTPException(status_code=404, detail={"code": "active_matching_retention_policy_not_found"})
    eligible_at = payload.resource_created_at + __import__("datetime").timedelta(days=policy.retention_days)
    now = datetime.now(timezone.utc)
    if now < eligible_at:
        raise HTTPException(status_code=409, detail={"code": "retention_period_not_elapsed", "eligible_at": eligible_at.isoformat()})
    holds = db.scalars(select(LegalHold).where(
        LegalHold.hospital_id == hospital_id,
        LegalHold.status == "active",
        or_(LegalHold.expires_at.is_(None), LegalHold.expires_at > now),
    )).all()
    if any(payload.resource_reference in (hold.scope or {}).get("resource_references", []) for hold in holds):
        raise HTTPException(status_code=409, detail={"code": "active_legal_hold_blocks_disposition"})
    request = RetentionDispositionRequest(
        hospital_id=hospital_id, policy_id=policy.id,
        resource_type=payload.resource_type, resource_reference=payload.resource_reference,
        action=payload.action, reason=payload.reason, eligible_at=eligible_at,
        requested_by_user_id=user.id,
    )
    db.add(request)
    db.flush()
    _audit(db, hospital_id, user.id, "compliance.retention_disposition_requested", "retention_disposition_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.get("/dispositions", response_model=list[RetentionDispositionRead])
def list_retention_dispositions(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    return db.scalars(select(RetentionDispositionRequest).where(
        RetentionDispositionRequest.hospital_id == hospital_id,
    ).order_by(RetentionDispositionRequest.created_at.desc()).limit(500)).all()


@router.post("/dispositions/{request_id}/review", response_model=RetentionDispositionRead)
def review_retention_disposition(request_id: UUID, payload: RetentionDispositionReview, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_compliance(db, user.id, hospital_id)
    request = db.scalar(select(RetentionDispositionRequest).where(
        RetentionDispositionRequest.hospital_id == hospital_id,
        RetentionDispositionRequest.id == request_id,
    ).with_for_update())
    if request is None:
        raise HTTPException(status_code=404, detail={"code": "retention_disposition_not_found"})
    if request.status != "pending" or request.requested_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_retention_disposition_review_required"})
    now = datetime.now(timezone.utc)
    if payload.decision == "approved":
        holds = db.scalars(select(LegalHold).where(
            LegalHold.hospital_id == hospital_id,
            LegalHold.status == "active",
            or_(LegalHold.expires_at.is_(None), LegalHold.expires_at > now),
        )).all()
        if any(request.resource_reference in (hold.scope or {}).get("resource_references", []) for hold in holds):
            request.status = "blocked_by_legal_hold"
        else:
            request.status = "approved"
    else:
        request.status = "rejected"
    request.reviewed_by_user_id = user.id
    request.reviewed_at = now
    request.review_note = payload.review_note
    _audit(db, hospital_id, user.id, "compliance.retention_disposition_reviewed", "retention_disposition_request", request.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request
