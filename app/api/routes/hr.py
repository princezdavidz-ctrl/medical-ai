from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Department, HospitalMembership, Role, User
from app.models.hr import EmployeeProfile, StaffCredential, StaffLeaveRequest
from app.schemas.hr import (
    EmployeeCreate, EmployeeRead, EmployeeStatusUpdate,
    CredentialCreate, CredentialDecision, CredentialRead,
    LeaveCreate, LeaveDecision, LeaveRead,
)

router = APIRouter(prefix="/hr", tags=["human resources"])

_HR_ADMIN = {"hr_manager", "hr_director", "hospital_admin"}
_HR_STAFF = _HR_ADMIN | {"hr_officer", "hr_assistant"}
_CREDENTIAL_REVIEWERS = {"hr_manager", "hr_director", "hospital_admin"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(
        select(HospitalMembership)
        .join(Role, Role.id == HospitalMembership.role_id)
        .where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == user_id,
            HospitalMembership.status == "active",
        )
    )
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require(db: Session, user_id: UUID, hospital_id: UUID, allowed: set[str]) -> str:
    role = _role(db, user_id, hospital_id)
    if not role:
        raise HTTPException(status_code=403, detail={"code": "hr_active_membership_required"})
    if role not in allowed:
        raise HTTPException(status_code=403, detail={"code": "hr_role_not_authorized"})
    return role


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, item_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id,
        action=action, resource_type=resource, resource_id=str(item_id),
        metadata=metadata or {},
    )


def _employee(db: Session, hospital_id: UUID, employee_id: UUID, lock: bool = False):
    query = select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.id == employee_id,
    )
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "employee_not_found"})
    return item


@router.post("/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
def create_employee(payload: EmployeeCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _HR_ADMIN)
    staff_user = db.scalar(select(User).where(User.id == payload.user_id, User.is_active.is_(True)))
    if staff_user is None:
        raise HTTPException(status_code=404, detail={"code": "active_user_not_found"})
    if payload.manager_user_id is not None:
        manager_membership = db.scalar(select(HospitalMembership).where(
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.user_id == payload.manager_user_id,
            HospitalMembership.status == "active",
        ))
        if manager_membership is None:
            raise HTTPException(status_code=422, detail={"code": "manager_must_belong_to_hospital"})
    if payload.department_id is not None:
        department = db.scalar(select(Department).where(
            Department.id == payload.department_id,
            Department.hospital_id == hospital_id,
            Department.status == "active",
        ))
        if department is None:
            raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
    item = EmployeeProfile(hospital_id=hospital_id, created_by_user_id=user.id, **payload.model_dump())
    db.add(item)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "hr.employee.created", "employee_profile", item.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "employee_profile_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.get("/employees", response_model=list[EmployeeRead])
def list_employees(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _HR_STAFF)
    return db.scalars(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id
    ).order_by(EmployeeProfile.employee_number)).all()


@router.patch("/employees/{employee_id}/status", response_model=EmployeeRead)
def update_employee_status(employee_id: UUID, payload: EmployeeStatusUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _HR_ADMIN)
    item = _employee(db, hospital_id, employee_id, lock=True)
    if item.employment_status == "terminated":
        raise HTTPException(status_code=409, detail={"code": "terminated_employee_is_final"})
    if payload.employment_status == "terminated" and payload.end_date is None:
        raise HTTPException(status_code=422, detail={"code": "termination_end_date_required"})
    item.employment_status = payload.employment_status
    item.end_date = payload.end_date
    _audit(db, hospital_id, user.id, "hr.employee.status_changed", "employee_profile", item.id, {"status": payload.employment_status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.post("/employees/{employee_id}/credentials", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
def add_credential(employee_id: UUID, payload: CredentialCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _HR_STAFF)
    employee = _employee(db, hospital_id, employee_id)
    item = StaffCredential(
        hospital_id=hospital_id, employee_profile_id=employee.id,
        created_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    _audit(db, hospital_id, user.id, "hr.credential.recorded", "staff_credential", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.post("/credentials/{credential_id}/decision", response_model=CredentialRead)
def decide_credential(credential_id: UUID, payload: CredentialDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _CREDENTIAL_REVIEWERS)
    item = db.scalar(select(StaffCredential).where(
        StaffCredential.id == credential_id,
        StaffCredential.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.verification_status != "reported":
        raise HTTPException(status_code=404, detail={"code": "reported_credential_not_found"})
    if item.created_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_credential_review_required"})
    item.verification_status = payload.outcome
    if payload.outcome == "verified":
        item.verified_by_user_id, item.verified_at = user.id, datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "hr.credential.decision", "staff_credential", item.id, {"outcome": payload.outcome, "note": payload.note})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.post("/leave-requests", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
def create_leave_request(payload: LeaveCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    profile = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == user.id,
        EmployeeProfile.employment_status.in_(["active", "on_leave"]),
    ))
    if profile is None:
        raise HTTPException(status_code=403, detail={"code": "active_employee_profile_required"})
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=422, detail={"code": "leave_end_must_follow_start"})
    item = StaffLeaveRequest(
        hospital_id=hospital_id, employee_profile_id=profile.id,
        requested_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    _audit(db, hospital_id, user.id, "hr.leave.requested", "staff_leave_request", item.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item


@router.get("/leave-requests", response_model=list[LeaveRead])
def list_leave_requests(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role in _HR_STAFF:
        query = select(StaffLeaveRequest).where(StaffLeaveRequest.hospital_id == hospital_id)
    else:
        profile = db.scalar(select(EmployeeProfile).where(
            EmployeeProfile.hospital_id == hospital_id,
            EmployeeProfile.user_id == user.id,
        ))
        if profile is None:
            raise HTTPException(status_code=403, detail={"code": "employee_profile_required"})
        query = select(StaffLeaveRequest).where(
            StaffLeaveRequest.hospital_id == hospital_id,
            StaffLeaveRequest.employee_profile_id == profile.id,
        )
    return db.scalars(query.order_by(StaffLeaveRequest.created_at.desc())).all()


@router.post("/leave-requests/{request_id}/decision", response_model=LeaveRead)
def decide_leave_request(request_id: UUID, payload: LeaveDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require(db, user.id, hospital_id, _HR_ADMIN)
    item = db.scalar(select(StaffLeaveRequest).where(
        StaffLeaveRequest.id == request_id,
        StaffLeaveRequest.hospital_id == hospital_id,
    ).with_for_update())
    if item is None or item.status != "pending":
        raise HTTPException(status_code=404, detail={"code": "pending_leave_request_not_found"})
    if item.requested_by_user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "independent_leave_approval_required"})
    item.status = payload.outcome
    item.decided_by_user_id, item.decided_at = user.id, datetime.now(timezone.utc)
    item.decision_note = payload.decision_note
    _audit(db, hospital_id, user.id, "hr.leave.decided", "staff_leave_request", item.id, {"outcome": payload.outcome})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(item)
    return item
