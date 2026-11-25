from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import (
    Department, Encounter, Hospital, HospitalMembership, Patient, Role,
)
from app.models.hospital_admin import (
    HospitalAdminProfile, HospitalOperationalSettings, HospitalOperatingHour, HospitalAdminEvent,
)
from app.models.inpatient import HospitalBed, InpatientAdmission, Ward
from app.models.hr import EmployeeProfile
from app.models.facilities import MaintenanceWorkOrder
from app.models.transport import TransportRequest
from app.schemas.hospital_admin import (
    HospitalProfileUpdate, HospitalProfileRead, HospitalOperationalSettingsUpdate,
    HospitalOperationalSettingsRead, OperatingHoursReplace, OperatingHourRead,
    DepartmentCreate, DepartmentUpdate, DepartmentRead,
)

router = APIRouter(prefix="/hospital-admin", tags=["hospital administration console"])
_ADMIN_ROLES = {"hospital_admin", "hospital_owner"}
_DEPARTMENT_MANAGER_ROLES = {"department_manager", "department_head", "hospital_admin"}


def _require_admin(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "hospital_admin_role_required"})


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _event(db: Session, hospital_id: UUID, user_id: UUID, event_type: str, resource_type: str, resource_id: UUID | None, metadata=None) -> None:
    db.add(HospitalAdminEvent(
        hospital_id=hospital_id, actor_user_id=user_id, event_type=event_type,
        resource_type=resource_type, resource_id=resource_id, event_metadata=metadata or {},
    ))


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, resource_id: UUID | None, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource, resource_id=str(resource_id) if resource_id else None,
        metadata=metadata or {},
    )


def _lock_hospital(db: Session, hospital_id: UUID):
    hospital = db.scalar(select(Hospital).where(Hospital.id == hospital_id).with_for_update())
    if hospital is None:
        raise HTTPException(status_code=404, detail={"code": "hospital_not_found"})
    return hospital


def _department(db: Session, department_id: UUID, hospital_id: UUID, *, lock: bool = False):
    query = select(Department).where(
        Department.id == department_id, Department.hospital_id == hospital_id,
    )
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "department_not_found"})
    return item


def _validate_department_manager(db: Session, hospital_id: UUID, manager_user_id: UUID | None) -> None:
    if manager_user_id is None:
        return
    membership = db.scalar(select(HospitalMembership).join(
        Role, Role.id == HospitalMembership.role_id,
    ).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == manager_user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    role_name = role.name.strip().casefold().replace(" ", "_") if role else ""
    if role_name not in _DEPARTMENT_MANAGER_ROLES:
        raise HTTPException(status_code=422, detail={"code": "active_department_manager_membership_required"})


def _validate_parent_department(db: Session, hospital_id: UUID, parent_id: UUID | None, department_id: UUID | None = None) -> None:
    if parent_id is None:
        return
    parent = db.scalar(select(Department).where(
        Department.id == parent_id, Department.hospital_id == hospital_id,
        Department.status == "active",
    ))
    if parent is None:
        raise HTTPException(status_code=422, detail={"code": "active_parent_department_required"})
    if department_id is not None:
        if parent_id == department_id:
            raise HTTPException(status_code=422, detail={"code": "department_cannot_parent_itself"})
        descendants = select(Department.id.label("id")).where(
            Department.hospital_id == hospital_id,
            Department.parent_department_id == department_id,
        ).cte(name="department_descendants", recursive=True)
        descendants = descendants.union_all(
            select(Department.id).join(
                descendants, Department.parent_department_id == descendants.c.id,
            ).where(Department.hospital_id == hospital_id)
        )
        if db.scalar(select(descendants.c.id).where(descendants.c.id == parent_id).limit(1)) is not None:
            raise HTTPException(status_code=409, detail={"code": "department_hierarchy_cycle"})


def _ensure_department_can_deactivate(db: Session, hospital_id: UUID, department_id: UUID) -> None:
    active_membership = db.scalar(select(HospitalMembership.id).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.department_id == department_id,
        HospitalMembership.status == "active",
    ).limit(1))
    active_child = db.scalar(select(Department.id).where(
        Department.hospital_id == hospital_id,
        Department.parent_department_id == department_id,
        Department.status == "active",
    ).limit(1))
    active_ward = db.scalar(select(Ward.id).where(
        Ward.hospital_id == hospital_id, Ward.department_id == department_id,
        Ward.status == "active",
    ).limit(1))
    active_encounter = db.scalar(select(Encounter.id).where(
        Encounter.hospital_id == hospital_id, Encounter.department_id == department_id,
        Encounter.status.in_(["scheduled", "in_progress"]),
    ).limit(1))
    if active_membership or active_child or active_ward or active_encounter:
        raise HTTPException(status_code=409, detail={"code": "department_has_active_staff_children_wards_or_encounters"})


@router.get("/profile", response_model=HospitalProfileRead)
def get_hospital_profile(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    profile = db.scalar(select(HospitalAdminProfile).where(HospitalAdminProfile.hospital_id == hospital_id))
    if profile is None:
        raise HTTPException(status_code=404, detail={"code": "hospital_profile_not_configured"})
    return profile


@router.put("/profile", response_model=HospitalProfileRead)
def upsert_hospital_profile(payload: HospitalProfileUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    hospital = _lock_hospital(db, hospital_id)
    try:
        ZoneInfo(payload.timezone)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail={"code": "unknown_timezone"})
    hospital = _lock_hospital(db, hospital_id)
    profile = db.scalar(select(HospitalAdminProfile).where(
        HospitalAdminProfile.hospital_id == hospital_id,
    ).with_for_update())
    created = profile is None
    if profile is None:
        profile = HospitalAdminProfile(hospital_id=hospital_id, updated_by_user_id=user.id, **payload.model_dump())
        db.add(profile)
    else:
        for key, value in payload.model_dump().items():
            setattr(profile, key, value)
        profile.updated_by_user_id = user.id
    hospital.name = payload.display_name
    hospital.country_code = payload.country_code
    db.flush()
    _event(db, hospital_id, user.id, "profile_created" if created else "profile_updated", "hospital_profile", profile.id)
    _audit(db, hospital_id, user.id, "hospital_admin.profile_saved", "hospital_profile", profile.id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "hospital_profile_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(profile)
    return profile


@router.get("/settings", response_model=HospitalOperationalSettingsRead)
def get_hospital_settings(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    _lock_hospital(db, hospital_id)
    settings = db.scalar(select(HospitalOperationalSettings).where(
        HospitalOperationalSettings.hospital_id == hospital_id,
    ))
    if settings is None:
        return {
            "id": None, "hospital_id": hospital_id, "appointment_booking_enabled": True,
            "patient_self_registration_enabled": True, "public_directory_enabled": False,
            "default_appointment_duration_minutes": 20, "appointment_booking_advance_days": 60,
            "updated_by_user_id": user.id, "created_at": None, "updated_at": None,
        }
    return settings


@router.put("/settings", response_model=HospitalOperationalSettingsRead)
def upsert_hospital_settings(payload: HospitalOperationalSettingsUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    settings = db.scalar(select(HospitalOperationalSettings).where(
        HospitalOperationalSettings.hospital_id == hospital_id,
    ).with_for_update())
    if settings is None:
        settings = HospitalOperationalSettings(
            hospital_id=hospital_id, updated_by_user_id=user.id, **payload.model_dump(),
        )
        db.add(settings)
    else:
        for key, value in payload.model_dump().items():
            setattr(settings, key, value)
        settings.updated_by_user_id = user.id
    db.flush()
    _event(db, hospital_id, user.id, "settings_updated", "hospital_operational_settings", settings.id)
    _audit(db, hospital_id, user.id, "hospital_admin.settings_saved", "hospital_operational_settings", settings.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(settings)
    return settings


@router.get("/operating-hours", response_model=list[OperatingHourRead])
def get_operating_hours(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    return db.scalars(select(HospitalOperatingHour).where(
        HospitalOperatingHour.hospital_id == hospital_id,
    ).order_by(HospitalOperatingHour.day_of_week)).all()


@router.put("/operating-hours", response_model=list[OperatingHourRead])
def replace_operating_hours(payload: OperatingHoursReplace, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    _lock_hospital(db, hospital_id)
    days = [item.day_of_week for item in payload.hours]
    if set(days) != set(range(7)) or len(set(days)) != 7:
        raise HTTPException(status_code=422, detail={"code": "exactly_one_schedule_per_weekday_required"})
    for item in payload.hours:
        if item.is_closed:
            if item.opens_at is not None or item.closes_at is not None:
                raise HTTPException(status_code=422, detail={"code": "closed_day_must_not_have_hours"})
        elif item.opens_at is None or item.closes_at is None or item.opens_at >= item.closes_at:
            raise HTTPException(status_code=422, detail={"code": "valid_open_and_close_times_required"})
    db.execute(delete(HospitalOperatingHour).where(HospitalOperatingHour.hospital_id == hospital_id))
    rows = [HospitalOperatingHour(
        hospital_id=hospital_id, updated_by_user_id=user.id, **item.model_dump(),
    ) for item in payload.hours]
    db.add_all(rows)
    _event(db, hospital_id, user.id, "operating_hours_updated", "hospital_operating_hours", None, {"days_configured": 7})
    _audit(db, hospital_id, user.id, "hospital_admin.operating_hours_saved", "hospital_operating_hours", None)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    return db.scalars(select(HospitalOperatingHour).where(
        HospitalOperatingHour.hospital_id == hospital_id,
    ).order_by(HospitalOperatingHour.day_of_week)).all()


@router.get("/departments", response_model=list[DepartmentRead])
def list_departments(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    return db.scalars(select(Department).where(
        Department.hospital_id == hospital_id,
    ).order_by(Department.name)).all()


@router.post("/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    _lock_hospital(db, hospital_id)
    _validate_department_manager(db, hospital_id, payload.manager_user_id)
    _validate_parent_department(db, hospital_id, payload.parent_department_id)
    department = Department(hospital_id=hospital_id, status="active", **payload.model_dump())
    db.add(department)
    try:
        db.flush()
        _event(db, hospital_id, user.id, "department_created", "department", department.id)
        _audit(db, hospital_id, user.id, "hospital_admin.department_created", "department", department.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "department_code_or_parent_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(department)
    return department


@router.patch("/departments/{department_id}", response_model=DepartmentRead)
def update_department(department_id: UUID, payload: DepartmentUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    _lock_hospital(db, hospital_id)
    department = _department(db, department_id, hospital_id, lock=True)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail={"code": "department_update_requires_changes"})
    if any(changes.get(field) is None for field in ("name", "code", "status") if field in changes):
        raise HTTPException(status_code=422, detail={"code": "department_name_code_status_cannot_be_null"})
    if "manager_user_id" in changes:
        _validate_department_manager(db, hospital_id, changes["manager_user_id"])
    if "parent_department_id" in changes:
        _validate_parent_department(db, hospital_id, changes["parent_department_id"], department.id)
    if changes.get("status") == "inactive" and department.status != "inactive":
        _ensure_department_can_deactivate(db, hospital_id, department.id)
    for key, value in changes.items():
        setattr(department, key, value)
    event_type = "department_deactivated" if changes.get("status") == "inactive" else "department_updated"
    db.flush()
    _event(db, hospital_id, user.id, event_type, "department", department.id, {"changed_fields": sorted(changes.keys())})
    _audit(db, hospital_id, user.id, "hospital_admin.department_updated", "department", department.id, {"changed_fields": sorted(changes.keys())})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "department_update_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(department)
    return department


@router.get("/dashboard")
def hospital_admin_dashboard(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    def count(model, *conditions):
        return db.scalar(select(func.count()).select_from(model).where(model.hospital_id == hospital_id, *conditions)) or 0
    return {
        "patients": count(Patient),
        "departments_active": count(Department, Department.status == "active"),
        "beds_total": count(HospitalBed),
        "beds_available": count(HospitalBed, HospitalBed.status == "available"),
        "admissions_total": count(InpatientAdmission),
        "employees_active": count(EmployeeProfile, EmployeeProfile.employment_status == "active"),
        "maintenance_orders_open": count(MaintenanceWorkOrder, MaintenanceWorkOrder.status.in_(["requested", "approved", "assigned", "in_progress"])),
        "transport_requests_open": count(TransportRequest, TransportRequest.status.in_(["requested", "bed_accepted", "vehicle_assigned", "en_route"])),
    }


@router.get("/events")
def list_hospital_admin_events(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    rows = db.scalars(select(HospitalAdminEvent).where(
        HospitalAdminEvent.hospital_id == hospital_id,
    ).order_by(HospitalAdminEvent.created_at.desc()).limit(200)).all()
    return [{
        "id": row.id, "event_type": row.event_type, "actor_user_id": row.actor_user_id,
        "resource_type": row.resource_type, "resource_id": row.resource_id,
        "event_metadata": row.event_metadata, "created_at": row.created_at,
    } for row in rows]
