from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context
from app.db.session import get_db
from app.models import Department, Encounter, Hospital, HospitalMembership, Patient, Role, User
from app.models.hospital_admin import HospitalAdminSettings
from app.schemas.hospital_admin import (
    HospitalSettingsUpdate, HospitalSettingsRead, DepartmentCreate,
    DepartmentUpdate, MembershipDecision,
)

router = APIRouter(prefix="/hospital-admin", tags=["hospital administration console"])
_ADMIN_ROLES = {"hospital_admin", "hospital_director"}


def _require_admin(db: Session, user_id: UUID, hospital_id: UUID) -> str:
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
    return role_name


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource: str, resource_id: UUID, metadata=None) -> None:
    write_audit_event(
        db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
        resource_type=resource, resource_id=str(resource_id), metadata=metadata or {},
    )


def _count(db: Session, model, hospital_id: UUID, *criteria) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(
        model.hospital_id == hospital_id, *criteria,
    )) or 0)


@router.get("/overview")
def get_overview(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    hospital = db.get(Hospital, hospital_id)
    return {
        "hospital": {"id": hospital.id, "name": hospital.name, "facility_code": hospital.facility_code,
                     "ownership_type": hospital.ownership_type, "country_code": hospital.country_code,
                     "status": hospital.status},
        "departments": {"total": _count(db, Department, hospital_id),
                        "active": _count(db, Department, hospital_id, Department.status == "active")},
        "staff": {"total_memberships": _count(db, HospitalMembership, hospital_id),
                  "active": _count(db, HospitalMembership, hospital_id, HospitalMembership.status == "active"),
                  "pending": _count(db, HospitalMembership, hospital_id, HospitalMembership.status == "pending"),
                  "suspended": _count(db, HospitalMembership, hospital_id, HospitalMembership.status == "suspended")},
        "patients": {"total": _count(db, Patient, hospital_id),
                     "active": _count(db, Patient, hospital_id, Patient.status == "active")},
        "encounters": {"total": _count(db, Encounter, hospital_id),
                       "open": _count(db, Encounter, hospital_id, Encounter.status == "in_progress")},
    }


@router.get("/settings", response_model=HospitalSettingsRead)
def get_settings(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    settings = db.scalar(select(HospitalAdminSettings).where(HospitalAdminSettings.hospital_id == hospital_id))
    if settings is None:
        hospital = db.get(Hospital, hospital_id)
        return {
            "address": None, "contact_email": None, "contact_phone": None, "website_url": None,
            "timezone_name": "Africa/Nairobi", "locale": "en-KE",
            "currency_code": "KES", "country_code": hospital.country_code,
            "updated_by_user_id": user.id, "updated_at": hospital.updated_at,
        }
    return settings


@router.put("/settings", response_model=HospitalSettingsRead)
def update_settings(payload: HospitalSettingsUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    values = payload.model_dump()
    email = values.get("contact_email")
    if email and ("@" not in email or "." not in email.rsplit("@", 1)[-1] or " " in email):
        raise HTTPException(status_code=422, detail={"code": "invalid_contact_email"})
    website = values.get("website_url")
    if website and not website.startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail={"code": "invalid_website_url"})
    values["currency_code"] = values["currency_code"].upper()
    values["country_code"] = values["country_code"].upper()
    hospital = db.get(Hospital, hospital_id)
    hospital.country_code = values["country_code"]
    settings = db.scalar(select(HospitalAdminSettings).where(
        HospitalAdminSettings.hospital_id == hospital_id,
    ).with_for_update())
    if settings is None:
        settings = HospitalAdminSettings(hospital_id=hospital_id, updated_by_user_id=user.id, **values)
        db.add(settings)
    else:
        for key, value in values.items():
            setattr(settings, key, value)
        settings.updated_by_user_id = user.id
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "hospital_admin.settings.updated", "hospital_admin_settings", settings.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "hospital_settings_constraint_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(settings)
    return settings


@router.get("/departments")
def list_departments(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    rows = db.scalars(select(Department).where(
        Department.hospital_id == hospital_id,
    ).order_by(Department.name)).all()
    return [{"id": row.id, "name": row.name, "code": row.code, "status": row.status,
             "created_at": row.created_at, "updated_at": row.updated_at} for row in rows]


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    department = Department(hospital_id=hospital_id, name=payload.name.strip(), code=payload.code.upper())
    db.add(department)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "hospital_admin.department.created", "department", department.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "department_code_conflict"})
    _restore_context(db, user.id, hospital_id)
    db.refresh(department)
    return {"id": department.id, "name": department.name, "code": department.code, "status": department.status}


@router.patch("/departments/{department_id}")
def update_department(department_id: UUID, payload: DepartmentUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    department = db.scalar(select(Department).where(
        Department.id == department_id, Department.hospital_id == hospital_id,
    ).with_for_update())
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "department_not_found"})
    if department.status == "inactive" and payload.status == "active":
        raise HTTPException(status_code=409, detail={"code": "inactive_department_reactivation_requires_governance_review"})
    if payload.status == "inactive":
        active_members = _count(db, HospitalMembership, hospital_id,
                                HospitalMembership.department_id == department.id,
                                HospitalMembership.status == "active")
        if active_members:
            raise HTTPException(status_code=409, detail={"code": "department_has_active_staff"})
    department.name = payload.name.strip()
    department.status = payload.status
    _audit(db, hospital_id, user.id, "hospital_admin.department.updated", "department", department.id, {"status": department.status})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(department)
    return {"id": department.id, "name": department.name, "code": department.code, "status": department.status}


@router.get("/roles")
def list_roles(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    rows = db.scalars(select(Role).where(Role.hospital_id == hospital_id).order_by(Role.name)).all()
    return [{"id": row.id, "name": row.name, "description": row.description} for row in rows]


@router.get("/memberships")
def list_memberships(status_filter: str | None = None, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    allowed = {"pending", "active", "suspended", "rejected"}
    if status_filter and status_filter not in allowed:
        raise HTTPException(status_code=422, detail={"code": "invalid_membership_status_filter"})
    query = select(HospitalMembership, User, Role, Department).join(
        User, User.id == HospitalMembership.user_id,
    ).join(Role, Role.id == HospitalMembership.role_id).outerjoin(
        Department, Department.id == HospitalMembership.department_id,
    ).where(HospitalMembership.hospital_id == hospital_id)
    if status_filter:
        query = query.where(HospitalMembership.status == status_filter)
    rows = db.execute(query.order_by(HospitalMembership.created_at.desc()).limit(500)).all()
    return [{
        "membership_id": membership.id, "user_id": member.id, "full_name": member.full_name,
        "email": member.email, "role": role.name, "role_id": role.id,
        "department": department.name if department else None,
        "department_id": department.id if department else None,
        "status": membership.status, "created_at": membership.created_at,
    } for membership, member, role, department in rows]


@router.post("/memberships/{membership_id}/decision")
def decide_membership(membership_id: UUID, payload: MembershipDecision, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.id == membership_id, HospitalMembership.hospital_id == hospital_id,
    ).with_for_update())
    if membership is None:
        raise HTTPException(status_code=404, detail={"code": "membership_not_found"})
    if membership.user_id == user.id:
        raise HTTPException(status_code=409, detail={"code": "cannot_change_own_membership"})
    if payload.decision == "activate":
        if membership.status != "pending" or payload.role_id is None:
            raise HTTPException(status_code=409, detail={"code": "pending_membership_and_role_required"})
        role = db.scalar(select(Role).where(Role.id == payload.role_id, Role.hospital_id == hospital_id))
        if role is None:
            raise HTTPException(status_code=422, detail={"code": "hospital_role_not_found"})
        if payload.department_id is not None:
            department = db.scalar(select(Department).where(
                Department.id == payload.department_id, Department.hospital_id == hospital_id,
                Department.status == "active",
            ))
            if department is None:
                raise HTTPException(status_code=422, detail={"code": "active_hospital_department_not_found"})
        membership.role_id = role.id
        membership.department_id = payload.department_id
        membership.status = "active"
    elif payload.decision == "reject":
        if membership.status != "pending":
            raise HTTPException(status_code=409, detail={"code": "pending_membership_required"})
        membership.status = "rejected"
    else:
        if membership.status != "active":
            raise HTTPException(status_code=409, detail={"code": "active_membership_required"})
        target_role = db.scalar(select(Role).where(Role.id == membership.role_id, Role.hospital_id == hospital_id))
        if target_role and target_role.name.strip().casefold().replace(" ", "_") in _ADMIN_ROLES:
            active_admins = db.scalar(select(func.count()).select_from(HospitalMembership).join(
                Role, Role.id == HospitalMembership.role_id,
            ).where(
                HospitalMembership.hospital_id == hospital_id,
                HospitalMembership.status == "active",
                Role.name.in_(list(_ADMIN_ROLES)),
            )) or 0
            if active_admins <= 1:
                raise HTTPException(status_code=409, detail={"code": "cannot_suspend_last_hospital_admin"})
        membership.status = "suspended"
    _audit(db, hospital_id, user.id, "hospital_admin.membership." + payload.decision,
           "hospital_membership", membership.id, {"target_user_id": str(membership.user_id)})
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(membership)
    return {"membership_id": membership.id, "user_id": membership.user_id, "status": membership.status}
