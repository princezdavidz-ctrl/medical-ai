from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    EmergencyVisit, HospitalBed, HospitalMembership, InpatientAdmission,
    Invoice, Role, SafetyIncident, SecurityIncident, ComplianceRisk, Ward,
)
from app.models.analytics import ReportDefinition, ReportRun, ReportExportJob
from app.schemas.analytics import (
    ReportDefinitionCreate, ReportDefinitionPublish, ReportDefinitionRead,
    ReportExportCreate, ReportExportJobRead, ReportRunCreate, ReportRunRead,
)

router = APIRouter(prefix="/reports", tags=["reports and hospital analytics"])
_ADMIN_ROLES = {"hospital_admin", "hospital_director"}
_DEFINITION_ROLES = _ADMIN_ROLES | {"report_manager", "quality_manager", "finance_manager", "compliance_officer", "security_officer"}
_FINANCE_ROLES = {"finance_manager", "finance_officer", "hospital_admin", "hospital_director"}
_COMPLIANCE_ROLES = {"compliance_officer", "privacy_officer", "security_officer", "information_security_officer", "hospital_admin", "hospital_director", "medical_director"}
_DEPARTMENT_ROLES = {"department_head", "nurse_manager"}
_REPORT_DOMAIN = {
    "patient_flow": "clinical", "bed_occupancy": "operations",
    "emergency_volume": "clinical", "billing_summary": "finance",
    "quality_safety": "quality", "compliance_overview": "compliance",
}
_REPORT_ALLOWED_ROLES = {
    "patient_flow": {"hospital_admin", "hospital_director", "report_manager", "department_head", "nurse_manager", "doctor", "physician", "consultant", "medical_officer", "nurse", "registered_nurse", "ward_nurse"},
    "bed_occupancy": {"hospital_admin", "hospital_director", "report_manager", "department_head", "nurse_manager", "ward_nurse"},
    "emergency_volume": {"hospital_admin", "hospital_director", "report_manager", "department_head", "nurse_manager", "emergency_doctor", "emergency_nurse"},
    "billing_summary": _FINANCE_ROLES | {"report_manager"},
    "quality_safety": {"hospital_admin", "hospital_director", "report_manager", "quality_manager", "patient_safety_officer", "department_head"},
    "compliance_overview": _COMPLIANCE_ROLES | {"report_manager"},
}
_PRIVACY_THRESHOLD = 5


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _department(db: Session, user_id: UUID, hospital_id: UUID) -> UUID:
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    if membership is None or membership.department_id is None:
        raise HTTPException(status_code=403, detail={"code": "active_department_assignment_required"})
    return membership.department_id


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID) -> None:
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
                      resource_type=resource_type, resource_id=str(resource_id), metadata={})


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


@router.post("/definitions", response_model=ReportDefinitionRead, status_code=status.HTTP_201_CREATED)
def create_report_definition(payload: ReportDefinitionCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role not in _DEFINITION_ROLES:
        raise HTTPException(status_code=403, detail={"code": "report_definition_manager_role_required"})
    if _REPORT_DOMAIN[payload.report_key] != payload.data_domain:
        raise HTTPException(status_code=422, detail={"code": "report_key_data_domain_mismatch"})
    roles = {name.strip().casefold().replace(" ", "_") for name in payload.required_roles}
    if not roles or len(roles) != len(payload.required_roles) or not roles.issubset(_REPORT_ALLOWED_ROLES[payload.report_key]):
        raise HTTPException(status_code=422, detail={"code": "report_roles_invalid_for_report_domain"})
    latest = db.scalar(select(ReportDefinition).where(
        ReportDefinition.hospital_id == hospital_id,
        ReportDefinition.report_code == payload.report_code,
    ).order_by(ReportDefinition.version.desc()).limit(1))
    definition = ReportDefinition(
        hospital_id=hospital_id, version=(latest.version + 1 if latest else 1),
        created_by_user_id=user.id, required_roles=sorted(roles),
        **payload.model_dump(exclude={"required_roles"}),
    )
    db.add(definition)
    db.flush()
    _audit(db, hospital_id, user.id, "reports.definition_created", "report_definition", definition.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(definition)
    return definition


@router.post("/definitions/{definition_id}/publish", response_model=ReportDefinitionRead)
def publish_report_definition(definition_id: UUID, payload: ReportDefinitionPublish, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role not in _DEFINITION_ROLES:
        raise HTTPException(status_code=403, detail={"code": "report_definition_publisher_role_required"})
    definition = db.scalar(select(ReportDefinition).where(
        ReportDefinition.hospital_id == hospital_id,
        ReportDefinition.id == definition_id,
    ).with_for_update())
    if definition is None:
        raise HTTPException(status_code=404, detail={"code": "report_definition_not_found"})
    if definition.status != "draft" or definition.created_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_report_publication_required"})
    definition.status = "published"
    definition.published_by_user_id = user.id
    definition.published_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "reports.definition_published", "report_definition", definition.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(definition)
    return definition


@router.get("/catalog", response_model=list[ReportDefinitionRead])
def list_report_catalog(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    definitions = db.scalars(select(ReportDefinition).where(
        ReportDefinition.hospital_id == hospital_id,
        ReportDefinition.status == "published",
    ).order_by(ReportDefinition.data_domain, ReportDefinition.report_code, ReportDefinition.version.desc()).limit(500)).all()
    return [item for item in definitions if role in item.required_roles or role in _ADMIN_ROLES]


def _run_report(db: Session, hospital_id: UUID, definition: ReportDefinition, start_at: datetime | None, end_at: datetime | None, department_id: UUID | None) -> dict:
    key = definition.report_key

    if key == "patient_flow":
        query = select(InpatientAdmission.status, func.count(InpatientAdmission.id)).where(InpatientAdmission.hospital_id == hospital_id)
        if start_at: query = query.where(InpatientAdmission.requested_at >= start_at)
        if end_at: query = query.where(InpatientAdmission.requested_at < end_at)
        if department_id: query = query.join(Ward, (Ward.hospital_id == InpatientAdmission.hospital_id) & (Ward.id == InpatientAdmission.ward_id)).where(Ward.department_id == department_id)
        rows = db.execute(query.group_by(InpatientAdmission.status)).all()
        return {"admissions_by_status": {state: ("suppressed" if count < _PRIVACY_THRESHOLD else count) for state, count in rows}}

    if key == "bed_occupancy":
        query = select(HospitalBed.status, func.count(HospitalBed.id)).where(HospitalBed.hospital_id == hospital_id)
        if department_id: query = query.join(Ward, (Ward.hospital_id == HospitalBed.hospital_id) & (Ward.id == HospitalBed.ward_id)).where(Ward.department_id == department_id)
        rows = db.execute(query.group_by(HospitalBed.status)).all()
        return {"beds_by_status": {state: ("suppressed" if count < _PRIVACY_THRESHOLD else count) for state, count in rows}}

    if key == "emergency_volume":
        query = select(EmergencyVisit.status, EmergencyVisit.priority, func.count(EmergencyVisit.id)).where(EmergencyVisit.hospital_id == hospital_id)
        if start_at: query = query.where(EmergencyVisit.arrival_at >= start_at)
        if end_at: query = query.where(EmergencyVisit.arrival_at < end_at)
        if department_id: query = query.where(EmergencyVisit.department_id == department_id)
        rows = db.execute(query.group_by(EmergencyVisit.status, EmergencyVisit.priority)).all()
        return {"visits": [{"status": state, "priority": priority, "count": ("suppressed" if count < _PRIVACY_THRESHOLD else count)} for state, priority, count in rows]}

    if key == "billing_summary":
        query = select(Invoice.currency, Invoice.status, func.count(Invoice.id), func.sum(Invoice.subtotal_total), func.sum(Invoice.amount_paid_total)).where(Invoice.hospital_id == hospital_id)
        if start_at: query = query.where(Invoice.created_at >= start_at)
        if end_at: query = query.where(Invoice.created_at < end_at)
        if department_id: query = query.where(Invoice.department_id == department_id)
        rows = db.execute(query.group_by(Invoice.currency, Invoice.status)).all()
        return {"invoice_totals": [{"currency": currency, "status": state, "count": ("suppressed" if count < _PRIVACY_THRESHOLD else count), "invoiced": ("suppressed" if count < _PRIVACY_THRESHOLD else str(invoiced or 0)), "paid": ("suppressed" if count < _PRIVACY_THRESHOLD else str(paid or 0))} for currency, state, count, invoiced, paid in rows]}

    if key == "quality_safety":
        query = select(SafetyIncident.status, SafetyIncident.severity, func.count(SafetyIncident.id)).where(SafetyIncident.hospital_id == hospital_id)
        if start_at: query = query.where(SafetyIncident.reported_at >= start_at)
        if end_at: query = query.where(SafetyIncident.reported_at < end_at)
        if department_id: query = query.where(SafetyIncident.department_id == department_id)
        rows = db.execute(query.group_by(SafetyIncident.status, SafetyIncident.severity)).all()
        return {"incidents": [{"status": state, "severity": severity, "count": ("suppressed" if count < _PRIVACY_THRESHOLD else count)} for state, severity, count in rows]}

    if key == "compliance_overview":
        incidents = db.execute(select(SecurityIncident.status, func.count(SecurityIncident.id)).where(
            SecurityIncident.hospital_id == hospital_id,
        ).group_by(SecurityIncident.status)).all()
        risks = db.execute(select(ComplianceRisk.status, func.count(ComplianceRisk.id)).where(
            ComplianceRisk.hospital_id == hospital_id,
        ).group_by(ComplianceRisk.status)).all()
        return {
            "security_incidents_by_status": {state: ("suppressed" if count < _PRIVACY_THRESHOLD else count) for state, count in incidents},
            "risks_by_status": {state: ("suppressed" if count < _PRIVACY_THRESHOLD else count) for state, count in risks},
        }
    raise HTTPException(status_code=422, detail={"code": "unsupported_report_key"})


@router.post("/definitions/{definition_id}/run", response_model=ReportRunRead, status_code=status.HTTP_201_CREATED)
def run_report(definition_id: UUID, payload: ReportRunCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    definition = db.scalar(select(ReportDefinition).where(
        ReportDefinition.hospital_id == hospital_id,
        ReportDefinition.id == definition_id,
        ReportDefinition.status == "published",
    ))
    if definition is None:
        raise HTTPException(status_code=404, detail={"code": "published_report_not_found"})
    if role not in definition.required_roles and role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "report_role_access_denied"})
    if definition.report_key == "billing_summary" and role not in _FINANCE_ROLES:
        raise HTTPException(status_code=403, detail={"code": "finance_report_access_required"})
    if definition.report_key == "bed_occupancy" and (payload.start_at is not None or payload.end_at is not None):
        raise HTTPException(status_code=422, detail={"code": "bed_occupancy_is_a_current_snapshot_report"})
    if definition.report_key == "compliance_overview" and role not in _COMPLIANCE_ROLES:
        raise HTTPException(status_code=403, detail={"code": "compliance_report_access_required"})

    department_id = payload.department_id
    if role in _DEPARTMENT_ROLES:
        own_department = _department(db, user.id, hospital_id)
        if department_id is not None and department_id != own_department:
            raise HTTPException(status_code=403, detail={"code": "report_department_scope_denied"})
        department_id = own_department
    elif definition.department_scoped and department_id is None:
        raise HTTPException(status_code=422, detail={"code": "department_filter_required_for_scoped_report"})

    filters = payload.model_dump(mode="json", exclude_none=True)
    summary = _run_report(db, hospital_id, definition, payload.start_at, payload.end_at, department_id)
    now = datetime.now(timezone.utc)
    run = ReportRun(
        hospital_id=hospital_id, definition_id=definition.id, requested_by_user_id=user.id,
        filters={**filters, "resolved_department_id": str(department_id) if department_id else None},
        result_summary=summary,
        source_versions={"report_definition": definition.version, "calculation_version": "1", "source_modules": [definition.report_key]},
        status="completed", generated_at=now, expires_at=now + timedelta(hours=24),
    )
    db.add(run)
    db.flush()
    _audit(db, hospital_id, user.id, "reports.run_completed", "report_run", run.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(run)
    return run


@router.get("/runs", response_model=list[ReportRunRead])
def list_report_runs(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    query = select(ReportRun).where(ReportRun.hospital_id == hospital_id)
    if role not in _ADMIN_ROLES:
        query = query.where(ReportRun.requested_by_user_id == user.id)
    return db.scalars(query.order_by(ReportRun.generated_at.desc()).limit(300)).all()


@router.post("/runs/{run_id}/exports", response_model=ReportExportJobRead, status_code=status.HTTP_202_ACCEPTED)
def request_report_export(run_id: UUID, payload: ReportExportCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    run = db.scalar(select(ReportRun).where(
        ReportRun.hospital_id == hospital_id,
        ReportRun.id == run_id,
    ))
    if run is None or run.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail={"code": "active_report_run_not_found"})
    role = _role(db, user.id, hospital_id)
    if run.requested_by_user_id != user.id and role not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "report_export_owner_required"})
    now = datetime.now(timezone.utc)
    job = ReportExportJob(
        hospital_id=hospital_id, run_id=run.id, requested_by_user_id=user.id,
        format=payload.format, status="queued", expires_at=now + timedelta(hours=24),
    )
    db.add(job)
    db.flush()
    _audit(db, hospital_id, user.id, "reports.export_requested", "report_export_job", job.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(job)
    return job
