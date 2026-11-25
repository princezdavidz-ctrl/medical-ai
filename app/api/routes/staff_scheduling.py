from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Department, HospitalMembership, Role, User
from app.models.hr import EmployeeProfile, StaffLeaveRequest
from app.models.staff_scheduling import (
    StaffShiftTemplate, StaffShiftAssignment, StaffShiftSwapRequest,
    StaffShiftAttendance, StaffScheduleEvent,
)
from app.schemas.staff_scheduling import (
    ShiftTemplateCreate, ShiftTemplateUpdate, ShiftTemplateRead,
    ShiftAssignmentCreate, ShiftAssignmentUpdate, ShiftAssignmentRead,
    ShiftSwapRequestCreate, ShiftSwapResponse, ShiftSwapDecision, ShiftSwapRequestRead,
    AttendanceCheckOut, AttendanceDecision, AttendanceResubmission, ShiftAttendanceRead,
)

router = APIRouter(prefix="/staff-scheduling", tags=["staff management and scheduling"])
_MANAGER_ROLES = {"hospital_admin", "hospital_owner", "hr_manager", "roster_manager", "department_head", "nurse_manager"}


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


def _require_manager(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    role = _role(db, user_id, hospital_id)
    if role not in _MANAGER_ROLES:
        raise HTTPException(status_code=403, detail={"code": "staff_roster_manager_role_required"})
    return role

def _manager_department(db: Session, user_id: UUID, hospital_id: UUID, role: str) -> UUID | None:
    if role not in {"department_head", "nurse_manager"}:
        return None
    employee = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == user_id,
        EmployeeProfile.employment_status == "active",
    ))
    if employee is None or employee.department_id is None:
        raise HTTPException(status_code=403, detail={"code": "active_manager_department_required"})
    return employee.department_id


def _enforce_manager_department(manager_department_id: UUID | None, target_department_id: UUID | None) -> None:
    if manager_department_id is not None and target_department_id != manager_department_id:
        raise HTTPException(status_code=403, detail={"code": "department_schedule_scope_denied"})


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _event(db: Session, hospital_id: UUID, user_id: UUID, event_type: str, resource_type: str, resource_id: UUID | None, metadata=None) -> None:
    db.add(StaffScheduleEvent(
        hospital_id=hospital_id, actor_user_id=user_id, event_type=event_type,
        resource_type=resource_type, resource_id=resource_id, event_metadata=metadata or {},
    ))


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID | None, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource_type, resource_id=str(resource_id) if resource_id else None,
        metadata=metadata or {},
    )


def _active_employee(db: Session, hospital_id: UUID, employee_profile_id: UUID, *, lock: bool = False):
    query = select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.id == employee_profile_id,
        EmployeeProfile.employment_status == "active",
    )
    if lock:
        query = query.with_for_update()
    employee = db.scalar(query)
    if employee is None:
        raise HTTPException(status_code=404, detail={"code": "active_employee_profile_not_found"})
    membership = db.scalar(select(HospitalMembership.id).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == employee.user_id,
        HospitalMembership.status == "active",
    ).limit(1))
    if membership is None:
        raise HTTPException(status_code=403, detail={"code": "active_hospital_membership_required"})
    user = db.get(User, employee.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "active_user_account_required"})
    return employee


def _validate_schedule_conflicts(db: Session, hospital_id: UUID, employee: EmployeeProfile, starts_at: datetime, ends_at: datetime, *, exclude_shift_id: UUID | None = None) -> None:
    query = select(StaffShiftAssignment.id).where(
        StaffShiftAssignment.hospital_id == hospital_id,
        StaffShiftAssignment.staff_user_id == employee.user_id,
        StaffShiftAssignment.status.in_(["scheduled", "confirmed"]),
        StaffShiftAssignment.starts_at < ends_at,
        StaffShiftAssignment.ends_at > starts_at,
    )
    if exclude_shift_id is not None:
        query = query.where(StaffShiftAssignment.id != exclude_shift_id)
    if db.scalar(query.limit(1)) is not None:
        raise HTTPException(status_code=409, detail={"code": "staff_shift_overlap"})
    leave_conflict = db.scalar(select(StaffLeaveRequest.id).where(
        StaffLeaveRequest.hospital_id == hospital_id,
        StaffLeaveRequest.employee_profile_id == employee.id,
        StaffLeaveRequest.status == "approved",
        StaffLeaveRequest.start_at < ends_at,
        StaffLeaveRequest.end_at > starts_at,
    ).limit(1))
    if leave_conflict is not None:
        raise HTTPException(status_code=409, detail={"code": "approved_leave_conflicts_with_shift"})


def _validate_employee_for_shift(db: Session, hospital_id: UUID, employee: EmployeeProfile, department_id: UUID | None, starts_at: datetime, ends_at: datetime, *, exclude_shift_id: UUID | None = None) -> None:
    if employee.employment_status != "active":
        raise HTTPException(status_code=409, detail={"code": "employee_not_active"})
    if department_id is not None and employee.department_id is not None and employee.department_id != department_id:
        raise HTTPException(status_code=422, detail={"code": "employee_department_mismatch"})
    _validate_schedule_conflicts(db, hospital_id, employee, starts_at, ends_at, exclude_shift_id=exclude_shift_id)


def _validate_shift_times(starts_at: datetime, ends_at: datetime) -> None:
    if starts_at.tzinfo is None or ends_at.tzinfo is None:
        raise HTTPException(status_code=422, detail={"code": "shift_times_must_be_timezone_aware"})
    if ends_at <= starts_at or ends_at > starts_at + timedelta(hours=24):
        raise HTTPException(status_code=422, detail={"code": "shift_duration_must_be_positive_and_at_most_24_hours"})


def _shift(db: Session, hospital_id: UUID, shift_id: UUID, *, lock: bool = False):
    query = select(StaffShiftAssignment).where(
        StaffShiftAssignment.id == shift_id, StaffShiftAssignment.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "shift_assignment_not_found"})
    return item


def _ensure_no_attendance(db: Session, hospital_id: UUID, shift_id: UUID) -> None:
    attendance = db.scalar(select(StaffShiftAttendance.id).where(
        StaffShiftAttendance.hospital_id == hospital_id,
        StaffShiftAttendance.shift_assignment_id == shift_id,
    ).limit(1))
    if attendance is not None:
        raise HTTPException(status_code=409, detail={"code": "shift_has_attendance_record"})


@router.post("/templates", response_model=ShiftTemplateRead, status_code=status.HTTP_201_CREATED)
def create_shift_template(payload: ShiftTemplateCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_manager(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    department_id = payload.department_id or manager_department_id
    _enforce_manager_department(manager_department_id, department_id)
    if payload.start_time == payload.end_time:
        raise HTTPException(status_code=422, detail={"code": "shift_template_times_must_differ"})
    if department_id is not None:
        department = db.scalar(select(Department.id).where(
            Department.id == department_id, Department.hospital_id == hospital_id,
            Department.status == "active",
        ))
        if department is None:
            raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
    template_values = payload.model_dump()
    template_values["department_id"] = department_id
    template = StaffShiftTemplate(hospital_id=hospital_id, created_by_user_id=user.id, **template_values)
    db.add(template)
    try:
        db.flush()
        _event(db, hospital_id, user.id, "shift_template_created", "staff_shift_template", template.id)
        _audit(db, hospital_id, user.id, "staff_scheduling.template_created", "staff_shift_template", template.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "shift_template_code_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(template)
    return template


@router.get("/templates", response_model=list[ShiftTemplateRead])
def list_shift_templates(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    employee = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id, EmployeeProfile.user_id == user.id,
        EmployeeProfile.employment_status == "active",
    ))
    department_id = employee.department_id if employee else None
    query = select(StaffShiftTemplate).where(
        StaffShiftTemplate.hospital_id == hospital_id,
        StaffShiftTemplate.status == "active",
    )
    if role in {"department_head", "nurse_manager"}:
        department_id = _manager_department(db, user.id, hospital_id, role)
        query = query.where(or_(StaffShiftTemplate.department_id == department_id, StaffShiftTemplate.department_id.is_(None)))
    elif department_id is not None:
        query = query.where(or_(StaffShiftTemplate.department_id == department_id, StaffShiftTemplate.department_id.is_(None)))
    else:
        query = query.where(StaffShiftTemplate.department_id.is_(None))
    return db.scalars(query.order_by(StaffShiftTemplate.name)).all()


@router.patch("/templates/{template_id}", response_model=ShiftTemplateRead)
def update_shift_template(template_id: UUID, payload: ShiftTemplateUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_manager(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    template = db.scalar(select(StaffShiftTemplate).where(
        StaffShiftTemplate.id == template_id, StaffShiftTemplate.hospital_id == hospital_id,
    ).with_for_update())
    if template is None:
        raise HTTPException(status_code=404, detail={"code": "shift_template_not_found"})
    _enforce_manager_department(manager_department_id, template.department_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "shift_template_update_requires_changes"})
    if any(changes.get(field) is None for field in ("name", "category", "start_time", "end_time", "break_minutes", "status") if field in changes):
        raise HTTPException(status_code=422, detail={"code": "shift_template_fields_cannot_be_null"})
    new_start = changes.get("start_time", template.start_time)
    new_end = changes.get("end_time", template.end_time)
    if new_start == new_end:
        raise HTTPException(status_code=422, detail={"code": "shift_template_times_must_differ"})
    for key, value in changes.items():
        setattr(template, key, value)
    _event(db, hospital_id, user.id, "shift_template_updated", "staff_shift_template", template.id)
    _audit(db, hospital_id, user.id, "staff_scheduling.template_updated", "staff_shift_template", template.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "shift_template_update_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(template)
    return template


@router.post("/shifts", response_model=ShiftAssignmentRead, status_code=status.HTTP_201_CREATED)
def create_shift_assignment(payload: ShiftAssignmentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_manager(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    _validate_shift_times(payload.starts_at, payload.ends_at)
    employee = _active_employee(db, hospital_id, payload.employee_profile_id, lock=True)
    template = db.scalar(select(StaffShiftTemplate).where(
        StaffShiftTemplate.id == payload.shift_template_id,
        StaffShiftTemplate.hospital_id == hospital_id,
        StaffShiftTemplate.status == "active",
    ))
    if template is None:
        raise HTTPException(status_code=404, detail={"code": "active_shift_template_not_found"})
    department_id = payload.department_id or employee.department_id or template.department_id
    if template.department_id is not None and department_id != template.department_id:
        raise HTTPException(status_code=422, detail={"code": "shift_template_department_mismatch"})
    if template.department_id is not None and employee.department_id is not None and employee.department_id != template.department_id:
        raise HTTPException(status_code=422, detail={"code": "employee_not_in_template_department"})
    _enforce_manager_department(manager_department_id, department_id)
    if department_id is not None:
        department = db.scalar(select(Department.id).where(
            Department.id == department_id, Department.hospital_id == hospital_id,
            Department.status == "active",
        ))
        if department is None:
            raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
    _validate_employee_for_shift(db, hospital_id, employee, department_id, payload.starts_at, payload.ends_at)
    shift = StaffShiftAssignment(
        hospital_id=hospital_id, employee_profile_id=employee.id,
        staff_user_id=employee.user_id, department_id=department_id,
        shift_template_id=template.id, starts_at=payload.starts_at,
        ends_at=payload.ends_at, note=payload.note,
        status="scheduled", assigned_by_user_id=user.id,
    )
    db.add(shift)
    try:
        db.flush()
        _event(db, hospital_id, user.id, "shift_assigned", "staff_shift_assignment", shift.id, {"staff_user_id": str(employee.user_id)})
        _audit(db, hospital_id, user.id, "staff_scheduling.shift_assigned", "staff_shift_assignment", shift.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "shift_assignment_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(shift)
    return shift


@router.get("/my-shifts", response_model=list[ShiftAssignmentRead])
def list_my_shifts(start_at: datetime | None = None, end_at: datetime | None = None, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    query = select(StaffShiftAssignment).where(
        StaffShiftAssignment.hospital_id == hospital_id,
        StaffShiftAssignment.staff_user_id == user.id,
    )
    if start_at is not None:
        if start_at.tzinfo is None:
            raise HTTPException(status_code=422, detail={"code": "start_at_must_be_timezone_aware"})
        query = query.where(StaffShiftAssignment.ends_at > start_at)
    if end_at is not None:
        if end_at.tzinfo is None:
            raise HTTPException(status_code=422, detail={"code": "end_at_must_be_timezone_aware"})
        query = query.where(StaffShiftAssignment.starts_at < end_at)
    return db.scalars(query.order_by(StaffShiftAssignment.starts_at).limit(500)).all()


@router.get("/shifts", response_model=list[ShiftAssignmentRead])
def list_shifts(start_at: datetime | None = None, end_at: datetime | None = None, department_id: UUID | None = None, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_manager(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    if manager_department_id is not None:
        if department_id is not None and department_id != manager_department_id:
            raise HTTPException(status_code=403, detail={"code": "department_schedule_scope_denied"})
        department_id = manager_department_id
    query = select(StaffShiftAssignment).where(StaffShiftAssignment.hospital_id == hospital_id)
    if department_id is not None:
        query = query.where(StaffShiftAssignment.department_id == department_id)
    if start_at is not None:
        if start_at.tzinfo is None:
            raise HTTPException(status_code=422, detail={"code": "start_at_must_be_timezone_aware"})
        query = query.where(StaffShiftAssignment.ends_at > start_at)
    if end_at is not None:
        if end_at.tzinfo is None:
            raise HTTPException(status_code=422, detail={"code": "end_at_must_be_timezone_aware"})
        query = query.where(StaffShiftAssignment.starts_at < end_at)
    return db.scalars(query.order_by(StaffShiftAssignment.starts_at).limit(1000)).all()


@router.patch("/shifts/{shift_id}", response_model=ShiftAssignmentRead)
def update_shift_assignment(shift_id: UUID, payload: ShiftAssignmentUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_manager(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    shift = _shift(db, hospital_id, shift_id, lock=True)
    _enforce_manager_department(manager_department_id, shift.department_id)
    if shift.status in ("completed", "cancelled"):
        raise HTTPException(status_code=409, detail={"code": "terminal_shift_status"})
    _ensure_no_attendance(db, hospital_id, shift.id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "shift_update_requires_changes"})
    for field in ("starts_at", "ends_at", "status"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail={"code": "shift_update_fields_cannot_be_null"})
    starts_at = changes.get("starts_at", shift.starts_at)
    ends_at = changes.get("ends_at", shift.ends_at)
    _validate_shift_times(starts_at, ends_at)
    if changes.get("status") == "cancelled":
        if not changes.get("note") or len(changes["note"].strip()) < 5:
            raise HTTPException(status_code=422, detail={"code": "shift_cancellation_note_required"})
        shift.status = "cancelled"
        changes.pop("status")
    elif changes.get("status") == "confirmed":
        shift.status = "confirmed"
        changes.pop("status")
    employee = _active_employee(db, hospital_id, shift.employee_profile_id, lock=True)
    _validate_employee_for_shift(db, hospital_id, employee, shift.department_id, starts_at, ends_at, exclude_shift_id=shift.id)
    shift.starts_at, shift.ends_at = starts_at, ends_at
    for key, value in changes.items():
        setattr(shift, key, value)
    event_type = "shift_cancelled" if shift.status == "cancelled" else "shift_updated"
    _event(db, hospital_id, user.id, event_type, "staff_shift_assignment", shift.id)
    _audit(db, hospital_id, user.id, "staff_scheduling.shift_updated", "staff_shift_assignment", shift.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(shift)
    return shift


@router.post("/shifts/{shift_id}/swap-requests", response_model=ShiftSwapRequestRead, status_code=status.HTTP_201_CREATED)
def create_shift_swap_request(shift_id: UUID, payload: ShiftSwapRequestCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    shift = _shift(db, hospital_id, shift_id, lock=True)
    if shift.staff_user_id != user.id or shift.status not in ("scheduled", "confirmed"):
        raise HTTPException(status_code=403, detail={"code": "only_assigned_staff_can_request_swap"})
    _ensure_no_attendance(db, hospital_id, shift.id)
    if payload.target_user_id == user.id:
        raise HTTPException(status_code=422, detail={"code": "shift_swap_target_must_be_another_staff_member"})
    target = db.scalar(select(EmployeeProfile).where(
        EmployeeProfile.hospital_id == hospital_id,
        EmployeeProfile.user_id == payload.target_user_id,
        EmployeeProfile.employment_status == "active",
    ).with_for_update())
    if target is None:
        raise HTTPException(status_code=404, detail={"code": "active_swap_target_not_found"})
    membership = db.scalar(select(HospitalMembership.id).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == target.user_id,
        HospitalMembership.status == "active",
    ).limit(1))
    if membership is None:
        raise HTTPException(status_code=403, detail={"code": "swap_target_active_membership_required"})
    if shift.department_id is not None and target.department_id is not None and shift.department_id != target.department_id:
        raise HTTPException(status_code=422, detail={"code": "swap_target_department_mismatch"})
    _validate_employee_for_shift(db, hospital_id, target, shift.department_id, shift.starts_at, shift.ends_at)
    request = StaffShiftSwapRequest(
        hospital_id=hospital_id, shift_assignment_id=shift.id,
        requester_user_id=user.id, target_user_id=target.user_id,
        reason=payload.reason, status="pending_target",
    )
    db.add(request)
    try:
        db.flush()
        _event(db, hospital_id, user.id, "swap_requested", "staff_shift_swap_request", request.id)
        _audit(db, hospital_id, user.id, "staff_scheduling.swap_requested", "staff_shift_swap_request", request.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "shift_swap_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.get("/swap-requests", response_model=list[ShiftSwapRequestRead])
def list_shift_swap_requests(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    query = select(StaffShiftSwapRequest).where(StaffShiftSwapRequest.hospital_id == hospital_id)
    if role in _MANAGER_ROLES:
        manager_department_id = _manager_department(db, user.id, hospital_id, role)
        if manager_department_id is not None:
            query = query.join(StaffShiftAssignment, and_(
                StaffShiftAssignment.hospital_id == StaffShiftSwapRequest.hospital_id,
                StaffShiftAssignment.id == StaffShiftSwapRequest.shift_assignment_id,
            )).where(StaffShiftAssignment.department_id == manager_department_id)
    else:
        query = query.where(or_(
            StaffShiftSwapRequest.requester_user_id == user.id,
            StaffShiftSwapRequest.target_user_id == user.id,
        ))
    return db.scalars(query.order_by(StaffShiftSwapRequest.created_at.desc()).limit(300)).all()


@router.post("/swap-requests/{request_id}/respond", response_model=ShiftSwapRequestRead)
def respond_to_shift_swap(request_id: UUID, payload: ShiftSwapResponse, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    request = db.scalar(select(StaffShiftSwapRequest).where(
        StaffShiftSwapRequest.id == request_id, StaffShiftSwapRequest.hospital_id == hospital_id,
    ).with_for_update())
    if request is None or request.status != "pending_target" or request.target_user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "pending_target_shift_swap_not_found"})
    shift = _shift(db, hospital_id, request.shift_assignment_id, lock=True)
    if shift.status not in ("scheduled", "confirmed"):
        raise HTTPException(status_code=409, detail={"code": "shift_not_swappable"})
    if payload.accept:
        target = db.scalar(select(EmployeeProfile).where(
            EmployeeProfile.hospital_id == hospital_id, EmployeeProfile.user_id == user.id,
            EmployeeProfile.employment_status == "active",
        ).with_for_update())
        if target is None:
            raise HTTPException(status_code=403, detail={"code": "active_employee_profile_required"})
        _validate_employee_for_shift(db, hospital_id, target, shift.department_id, shift.starts_at, shift.ends_at)
        request.status = "accepted"
        event_type = "swap_accepted"
    else:
        request.status = "declined"
        event_type = "swap_rejected"
    request.responded_by_user_id = user.id
    request.responded_at = datetime.now(timezone.utc)
    request.decision_note = payload.note
    _event(db, hospital_id, user.id, event_type, "staff_shift_swap_request", request.id)
    _audit(db, hospital_id, user.id, "staff_scheduling.swap_responded", "staff_shift_swap_request", request.id, {"accepted": payload.accept})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/swap-requests/{request_id}/decision", response_model=ShiftSwapRequestRead)
def decide_shift_swap(request_id: UUID, payload: ShiftSwapDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_manager(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    request = db.scalar(select(StaffShiftSwapRequest).where(
        StaffShiftSwapRequest.id == request_id, StaffShiftSwapRequest.hospital_id == hospital_id,
    ).with_for_update())
    if request is None or request.status != "accepted":
        raise HTTPException(status_code=404, detail={"code": "accepted_shift_swap_not_found"})
    shift = _shift(db, hospital_id, request.shift_assignment_id, lock=True)
    _enforce_manager_department(manager_department_id, shift.department_id)
    if shift.status not in ("scheduled", "confirmed") or shift.staff_user_id != request.requester_user_id:
        raise HTTPException(status_code=409, detail={"code": "shift_changed_since_swap_request"})
    if payload.decision == "approved":
        target = db.scalar(select(EmployeeProfile).where(
            EmployeeProfile.hospital_id == hospital_id, EmployeeProfile.user_id == request.target_user_id,
            EmployeeProfile.employment_status == "active",
        ).with_for_update())
        if target is None:
            raise HTTPException(status_code=409, detail={"code": "swap_target_no_longer_active"})
        _validate_employee_for_shift(db, hospital_id, target, shift.department_id, shift.starts_at, shift.ends_at)
        shift.employee_profile_id = target.id
        shift.staff_user_id = target.user_id
        request.status = "approved"
        event_type = "swap_approved"
    else:
        request.status = "rejected"
        event_type = "swap_rejected"
    request.decided_by_user_id = user.id
    request.decided_at = datetime.now(timezone.utc)
    request.decision_note = payload.note
    _event(db, hospital_id, user.id, event_type, "staff_shift_swap_request", request.id)
    _audit(db, hospital_id, user.id, "staff_scheduling.swap_decided", "staff_shift_swap_request", request.id, {"decision": payload.decision})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "shift_swap_approval_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(request)
    return request


@router.post("/shifts/{shift_id}/check-in", response_model=ShiftAttendanceRead, status_code=status.HTTP_201_CREATED)
def check_in_to_shift(shift_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    shift = _shift(db, hospital_id, shift_id, lock=True)
    if shift.staff_user_id != user.id or shift.status not in ("scheduled", "confirmed"):
        raise HTTPException(status_code=403, detail={"code": "assigned_active_shift_required"})
    now = datetime.now(timezone.utc)
    if now < shift.starts_at - timedelta(hours=2) or now > shift.ends_at:
        raise HTTPException(status_code=409, detail={"code": "outside_shift_check_in_window"})
    existing = db.scalar(select(StaffShiftAttendance.id).where(
        StaffShiftAttendance.hospital_id == hospital_id,
        StaffShiftAttendance.shift_assignment_id == shift.id,
    ).limit(1))
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "shift_attendance_already_exists"})
    attendance = StaffShiftAttendance(
        hospital_id=hospital_id, shift_assignment_id=shift.id, staff_user_id=user.id,
        check_in_at=now, source="manual", status="open",
    )
    db.add(attendance)
    try:
        db.flush()
        _event(db, hospital_id, user.id, "attendance_checked_in", "staff_shift_attendance", attendance.id)
        _audit(db, hospital_id, user.id, "staff_scheduling.attendance_checked_in", "staff_shift_attendance", attendance.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "shift_attendance_already_exists"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(attendance)
    return attendance


@router.post("/shifts/{shift_id}/check-out", response_model=ShiftAttendanceRead)
def check_out_of_shift(shift_id: UUID, payload: AttendanceCheckOut, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    attendance = db.scalar(select(StaffShiftAttendance).join(
        StaffShiftAssignment,
        and_(StaffShiftAssignment.hospital_id == StaffShiftAttendance.hospital_id,
             StaffShiftAssignment.id == StaffShiftAttendance.shift_assignment_id),
    ).where(
        StaffShiftAttendance.hospital_id == hospital_id,
        StaffShiftAttendance.shift_assignment_id == shift_id,
        StaffShiftAttendance.staff_user_id == user.id,
        StaffShiftAttendance.status == "open",
        StaffShiftAssignment.staff_user_id == user.id,
    ).with_for_update())
    if attendance is None:
        raise HTTPException(status_code=404, detail={"code": "open_shift_attendance_not_found"})
    now = datetime.now(timezone.utc)
    if now <= attendance.check_in_at:
        raise HTTPException(status_code=409, detail={"code": "check_out_must_follow_check_in"})
    attendance.check_out_at = now
    attendance.status = "submitted"
    attendance.note = payload.note
    _event(db, hospital_id, user.id, "attendance_checked_out", "staff_shift_attendance", attendance.id)
    _audit(db, hospital_id, user.id, "staff_scheduling.attendance_checked_out", "staff_shift_attendance", attendance.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(attendance)
    return attendance


@router.post("/attendance/{attendance_id}/decision", response_model=ShiftAttendanceRead)
def decide_shift_attendance(attendance_id: UUID, payload: AttendanceDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _require_manager(db, user.id, hospital_id)
    manager_department_id = _manager_department(db, user.id, hospital_id, role)
    attendance = db.scalar(select(StaffShiftAttendance).where(
        StaffShiftAttendance.id == attendance_id, StaffShiftAttendance.hospital_id == hospital_id,
    ).with_for_update())
    if attendance is None or attendance.status != "submitted":
        raise HTTPException(status_code=404, detail={"code": "submitted_attendance_not_found"})
    shift = _shift(db, hospital_id, attendance.shift_assignment_id, lock=True)
    _enforce_manager_department(manager_department_id, shift.department_id)
    if payload.decision == "rejected" and (not payload.note or len(payload.note.strip()) < 5):
        raise HTTPException(status_code=422, detail={"code": "attendance_rejection_note_required"})
    attendance.status = payload.decision
    attendance.decided_by_user_id = user.id
    attendance.decided_at = datetime.now(timezone.utc)
    attendance.decision_note = payload.note
    if payload.decision == "approved" and shift.ends_at <= datetime.now(timezone.utc):
        shift.status = "completed"
        event_type = "attendance_approved"
    else:
        event_type = "attendance_rejected" if payload.decision == "rejected" else "attendance_approved"
    _event(db, hospital_id, user.id, event_type, "staff_shift_attendance", attendance.id)
    _audit(db, hospital_id, user.id, "staff_scheduling.attendance_decided", "staff_shift_attendance", attendance.id, {"decision": payload.decision})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(attendance)
    return attendance


@router.post("/attendance/{attendance_id}/resubmit", response_model=ShiftAttendanceRead)
def resubmit_rejected_attendance(attendance_id: UUID, payload: AttendanceResubmission, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    attendance = db.scalar(select(StaffShiftAttendance).where(
        StaffShiftAttendance.id == attendance_id,
        StaffShiftAttendance.hospital_id == hospital_id,
        StaffShiftAttendance.staff_user_id == user.id,
        StaffShiftAttendance.status == "rejected",
    ).with_for_update())
    if attendance is None:
        raise HTTPException(status_code=404, detail={"code": "rejected_attendance_not_found"})
    if payload.check_in_at.tzinfo is None or payload.check_out_at.tzinfo is None or payload.check_out_at <= payload.check_in_at:
        raise HTTPException(status_code=422, detail={"code": "valid_timezone_aware_attendance_times_required"})
    attendance.check_in_at = payload.check_in_at
    attendance.check_out_at = payload.check_out_at
    attendance.note = payload.note
    attendance.status = "submitted"
    attendance.decided_by_user_id = None
    attendance.decided_at = None
    attendance.decision_note = None
    _event(db, hospital_id, user.id, "attendance_checked_out", "staff_shift_attendance", attendance.id, {"resubmitted": True})
    _audit(db, hospital_id, user.id, "staff_scheduling.attendance_resubmitted", "staff_shift_attendance", attendance.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(attendance)
    return attendance


@router.get("/dashboard")
def get_staff_scheduling_dashboard(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    if role not in _MANAGER_ROLES:
        return {
            "upcoming_shifts": db.scalar(select(func.count()).select_from(StaffShiftAssignment).where(
                StaffShiftAssignment.hospital_id == hospital_id,
                StaffShiftAssignment.staff_user_id == user.id,
                StaffShiftAssignment.status.in_(["scheduled", "confirmed"]),
                StaffShiftAssignment.starts_at >= datetime.now(timezone.utc),
            )) or 0,
            "pending_swap_responses": db.scalar(select(func.count()).select_from(StaffShiftSwapRequest).where(
                StaffShiftSwapRequest.hospital_id == hospital_id,
                StaffShiftSwapRequest.target_user_id == user.id,
                StaffShiftSwapRequest.status == "pending_target",
            )) or 0,
        }
    return {
        "upcoming_shifts": db.scalar(select(func.count()).select_from(StaffShiftAssignment).where(
            StaffShiftAssignment.hospital_id == hospital_id,
            StaffShiftAssignment.status.in_(["scheduled", "confirmed"]),
            StaffShiftAssignment.starts_at >= datetime.now(timezone.utc),
        )) or 0,
        "pending_swap_decisions": db.scalar(select(func.count()).select_from(StaffShiftSwapRequest).where(
            StaffShiftSwapRequest.hospital_id == hospital_id,
            StaffShiftSwapRequest.status == "accepted",
        )) or 0,
        "attendance_pending_review": db.scalar(select(func.count()).select_from(StaffShiftAttendance).where(
            StaffShiftAttendance.hospital_id == hospital_id,
            StaffShiftAttendance.status == "submitted",
        )) or 0,
    }
