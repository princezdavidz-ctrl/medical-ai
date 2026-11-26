import re
from datetime import datetime, timezone
from string import Formatter
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context, get_current_patient_context
from app.db.session import get_db
from app.models import Department, HospitalMembership, PatientConsent, Role, User
from app.models.notifications import NotificationEvent, NotificationIntent, NotificationPreference, NotificationTemplate
from app.models.patient_portal import PatientPortalLink
from app.models.hr import EmployeeProfile
from app.schemas.notifications import (
    NotificationEnqueue, NotificationIntentRead, NotificationPreferenceUpdate,
    NotificationTemplateCreate, NotificationTemplatePublish, NotificationTemplateRead,
    DepartmentNoticeCreate, DepartmentNoticeResult,
)

router = APIRouter(prefix="/notifications", tags=["communication and notifications"])
_ADMIN_ROLES = {"hospital_admin", "hospital_director", "hospital_owner", "communications_admin", "hospital_communications_manager"}
_SENSITIVE_PLACEHOLDERS = {"patient_name", "full_name", "date_of_birth", "medical_record_number", "phone", "email", "diagnosis", "medication", "lab_result", "clinical_note"}
_CHANNEL_PREF = {"in_app": "in_app_enabled", "email": "email_enabled", "sms": "sms_enabled", "push": "push_enabled"}


def _role(db: Session, user_id: UUID, hospital_id: UUID) -> str:
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == user_id,
        HospitalMembership.status == "active",
    ))
    role = db.get(Role, membership.role_id) if membership else None
    return role.name.strip().casefold().replace(" ", "_") if role else ""


def _require_admin(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    if _role(db, user_id, hospital_id) not in _ADMIN_ROLES:
        raise HTTPException(status_code=403, detail={"code": "communications_administrator_required"})


def _restore_context(db: Session, user_id: UUID, hospital_id: UUID) -> None:
    from sqlalchemy import text
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _audit(db: Session, hospital_id: UUID, user_id: UUID, action: str, resource_type: str, resource_id: UUID) -> None:
    write_audit_event(db, hospital_id=hospital_id, actor_user_id=user_id, action=action,
                      resource_type=resource_type, resource_id=str(resource_id), metadata={})


def _localized_template(db: Session, hospital_id: UUID, base: NotificationTemplate, locale: str) -> NotificationTemplate:
    if locale == base.locale:
        return base
    candidates = [locale] if locale else []
    if "en" not in candidates:
        candidates.append("en")
    for candidate_locale in candidates:
        localized = db.scalar(select(NotificationTemplate).where(
            NotificationTemplate.hospital_id == hospital_id,
            NotificationTemplate.template_code == base.template_code,
            NotificationTemplate.locale == candidate_locale,
            NotificationTemplate.channel == base.channel,
            NotificationTemplate.status == "published",
        ).order_by(NotificationTemplate.version.desc()).limit(1))
        if localized is None:
            continue
        required = _placeholders(localized.title_template, localized.body_template)
        if required.issubset(set(localized.allowed_placeholders)):
            return localized
    return base


def _placeholders(*templates: str) -> set[str]:
    found = set()
    try:
        for template in templates:
            for _, field, _, _ in Formatter().parse(template):
                if field:
                    if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", field):
                        raise ValueError("invalid_template_placeholder")
                    found.add(field)
    except ValueError:
        raise HTTPException(status_code=422, detail={"code": "invalid_template_placeholder"}) from None
    return found


@router.get("/preferences")
def get_notification_preferences(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    preference = db.scalar(select(NotificationPreference).where(
        NotificationPreference.hospital_id == hospital_id,
        NotificationPreference.user_id == user.id,
    ))
    if preference is None:
        return {
            "hospital_id": hospital_id, "user_id": user.id,
            "in_app_enabled": True, "email_enabled": False, "sms_enabled": False, "push_enabled": False,
            "locale": "en", "timezone_name": "Africa/Nairobi", "quiet_start": None, "quiet_end": None,
        }
    return preference


@router.put("/preferences")
def update_notification_preferences(payload: NotificationPreferenceUpdate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail={"code": "notification_preference_update_required"})
    if ("quiet_start" in values) != ("quiet_end" in values):
        raise HTTPException(status_code=422, detail={"code": "quiet_hours_must_be_updated_together"})
    preference = db.scalar(select(NotificationPreference).where(
        NotificationPreference.hospital_id == hospital_id,
        NotificationPreference.user_id == user.id,
    ).with_for_update())
    if preference is None:
        preference = NotificationPreference(hospital_id=hospital_id, user_id=user.id)
        db.add(preference)
    for key, value in values.items():
        setattr(preference, key, value)
    _audit(db, hospital_id, user.id, "notifications.preferences_updated", "notification_preference", preference.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(preference)
    return preference


@router.post("/templates", response_model=NotificationTemplateRead, status_code=status.HTTP_201_CREATED)
def create_notification_template(payload: NotificationTemplateCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    placeholders = _placeholders(payload.title_template, payload.body_template)
    if not placeholders.issubset(set(payload.allowed_placeholders)):
        raise HTTPException(status_code=422, detail={"code": "template_placeholder_not_allowlisted"})
    if placeholders & _SENSITIVE_PLACEHOLDERS and payload.content_classification != "sensitive":
        raise HTTPException(status_code=422, detail={"code": "sensitive_placeholder_requires_sensitive_classification"})
    latest = db.scalar(select(NotificationTemplate).where(
        NotificationTemplate.hospital_id == hospital_id,
        NotificationTemplate.template_code == payload.template_code,
        NotificationTemplate.locale == payload.locale,
    ).order_by(NotificationTemplate.version.desc()).limit(1))
    template = NotificationTemplate(
        hospital_id=hospital_id, version=(latest.version + 1 if latest else 1),
        created_by_user_id=user.id, **payload.model_dump(),
    )
    db.add(template)
    try:
        db.flush()
        _audit(db, hospital_id, user.id, "notifications.template_created", "notification_template", template.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail={"code": "notification_template_version_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(template)
    return template


@router.post("/templates/{template_id}/publish", response_model=NotificationTemplateRead)
def publish_notification_template(template_id: UUID, payload: NotificationTemplatePublish, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    template = db.scalar(select(NotificationTemplate).where(
        NotificationTemplate.hospital_id == hospital_id,
        NotificationTemplate.id == template_id,
    ).with_for_update())
    if template is None:
        raise HTTPException(status_code=404, detail={"code": "notification_template_not_found"})
    if template.status != "draft":
        raise HTTPException(status_code=409, detail={"code": "only_draft_templates_can_be_published"})
    if template.content_classification == "sensitive":
        if not payload.approve_sensitive or template.created_by_user_id == user.id:
            raise HTTPException(status_code=403, detail={"code": "independent_sensitive_template_approval_required"})
    template.status = "published"
    template.published_by_user_id = user.id
    template.published_at = datetime.now(timezone.utc)
    _audit(db, hospital_id, user.id, "notifications.template_published", "notification_template", template.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(template)
    return template


@router.post("/enqueue", response_model=NotificationIntentRead, status_code=status.HTTP_202_ACCEPTED)
def enqueue_notification(payload: NotificationEnqueue, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    existing = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.idempotency_key == payload.idempotency_key,
    ))
    if existing is not None:
        requested_template = db.scalar(select(NotificationTemplate).where(
            NotificationTemplate.hospital_id == hospital_id,
            NotificationTemplate.id == payload.template_id,
        ))
        existing_template = db.scalar(select(NotificationTemplate).where(
            NotificationTemplate.hospital_id == hospital_id,
            NotificationTemplate.id == existing.template_id,
        ))
        if (
            existing.recipient_user_id != payload.recipient_user_id
            or existing.patient_id != payload.patient_id
            or existing.consent_id != payload.consent_id
            or existing.purpose != payload.purpose
            or requested_template is None
            or existing_template is None
            or existing_template.template_code != requested_template.template_code
        ):
            raise HTTPException(status_code=409, detail={"code": "idempotency_key_reused_for_different_notification"})
        return existing
    template = db.scalar(select(NotificationTemplate).where(
        NotificationTemplate.hospital_id == hospital_id,
        NotificationTemplate.id == payload.template_id,
        NotificationTemplate.status == "published",
    ))
    if template is None:
        raise HTTPException(status_code=404, detail={"code": "published_notification_template_not_found"})
    preference = db.scalar(select(NotificationPreference).where(
        NotificationPreference.hospital_id == hospital_id,
        NotificationPreference.user_id == payload.recipient_user_id,
    ))
    template = _localized_template(db, hospital_id, template, preference.locale if preference else "en")
    required_placeholders = _placeholders(template.title_template, template.body_template)
    if not required_placeholders.issubset(set(template.allowed_placeholders)):
        raise HTTPException(status_code=422, detail={"code": "template_placeholder_configuration_invalid"})
    required = _placeholders(template.title_template, template.body_template)
    if set(payload.variables) != required or not set(payload.variables).issubset(set(template.allowed_placeholders)):
        raise HTTPException(status_code=422, detail={"code": "notification_variables_must_match_template"})
    membership = db.scalar(select(HospitalMembership).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.user_id == payload.recipient_user_id,
        HospitalMembership.status == "active",
    ))
    portal_link = None
    if payload.patient_id is not None:
        portal_link = db.scalar(select(PatientPortalLink).where(
            PatientPortalLink.hospital_id == hospital_id,
            PatientPortalLink.patient_id == payload.patient_id,
            PatientPortalLink.portal_user_id == payload.recipient_user_id,
            PatientPortalLink.status == "active",
            (PatientPortalLink.expires_at.is_(None) | (PatientPortalLink.expires_at > datetime.now(timezone.utc))),
        ))
    if membership is None and portal_link is None:
        raise HTTPException(status_code=404, detail={"code": "active_same_hospital_recipient_not_found"})
    if payload.patient_id is not None:
        consent = db.scalar(select(PatientConsent).where(
            PatientConsent.hospital_id == hospital_id,
            PatientConsent.id == payload.consent_id,
            PatientConsent.patient_id == payload.patient_id,
            PatientConsent.status == "granted",
            PatientConsent.purpose == payload.purpose,
        ))
        now = datetime.now(timezone.utc)
        if consent is None or (consent.expires_at is not None and consent.expires_at <= now):
            raise HTTPException(status_code=403, detail={"code": "active_purpose_matched_patient_consent_required"})
        allowed_channels = consent.scope.get("channels", []) if isinstance(consent.scope, dict) else []
        if template.channel not in allowed_channels:
            raise HTTPException(status_code=403, detail={"code": "patient_consent_does_not_cover_notification_channel"})
    elif payload.consent_id is not None:
        raise HTTPException(status_code=422, detail={"code": "consent_requires_patient_context"})
    enabled = preference is not None and getattr(preference, _CHANNEL_PREF[template.channel])
    if template.channel != "in_app" and not enabled:
        raise HTTPException(status_code=403, detail={"code": "recipient_channel_not_enabled"})
    if template.channel == "in_app" and preference is not None and not preference.in_app_enabled:
        raise HTTPException(status_code=403, detail={"code": "recipient_channel_opted_out"})
    try:
        title = template.title_template.format_map(payload.variables)
        body = template.body_template.format_map(payload.variables)
    except (KeyError, ValueError):
        raise HTTPException(status_code=422, detail={"code": "notification_template_render_failed"}) from None
    intent = NotificationIntent(
        hospital_id=hospital_id, recipient_user_id=payload.recipient_user_id,
        patient_id=payload.patient_id, consent_id=payload.consent_id, template_id=template.id,
        channel=template.channel, purpose=payload.purpose, idempotency_key=payload.idempotency_key,
        rendered_title=title, rendered_body=body, created_by_user_id=user.id,
    )
    db.add(intent)
    try:
        db.flush()
        db.add(NotificationEvent(hospital_id=hospital_id, intent_id=intent.id, actor_user_id=user.id,
                                 event_type="enqueued", event_metadata={"channel": template.channel}))
        _audit(db, hospital_id, user.id, "notifications.enqueued", "notification_intent", intent.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        duplicate = db.scalar(select(NotificationIntent).where(
            NotificationIntent.hospital_id == hospital_id,
            NotificationIntent.idempotency_key == payload.idempotency_key,
        ))
        if duplicate is not None:
            return duplicate
        raise HTTPException(status_code=409, detail={"code": "notification_enqueue_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    db.refresh(intent)
    return intent


@router.get("/inbox", response_model=list[NotificationIntentRead])
def get_notification_inbox(context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    return db.scalars(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.recipient_user_id == user.id,
        NotificationIntent.channel == "in_app",
    ).order_by(NotificationIntent.created_at.desc()).limit(100)).all()


@router.get("/my-notifications", response_model=list[NotificationIntentRead])
def get_staff_notifications(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    return db.scalars(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.recipient_user_id == user.id,
    ).order_by(NotificationIntent.created_at.desc()).limit(100)).all()


@router.get("/patient/preferences")
def get_patient_notification_preferences(context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    preference = db.scalar(select(NotificationPreference).where(
        NotificationPreference.hospital_id == hospital_id,
        NotificationPreference.user_id == user.id,
    ))
    if preference is None:
        return {
            "hospital_id": hospital_id, "user_id": user.id,
            "in_app_enabled": True, "email_enabled": False, "sms_enabled": False, "push_enabled": False,
            "locale": "en", "timezone_name": "Africa/Nairobi", "quiet_start": None, "quiet_end": None,
        }
    return preference


@router.put("/patient/preferences")
def update_patient_notification_preferences(payload: NotificationPreferenceUpdate, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail={"code": "notification_preference_update_required"})
    if ("quiet_start" in values) != ("quiet_end" in values):
        raise HTTPException(status_code=422, detail={"code": "quiet_hours_must_be_updated_together"})
    preference = db.scalar(select(NotificationPreference).where(
        NotificationPreference.hospital_id == hospital_id,
        NotificationPreference.user_id == user.id,
    ).with_for_update())
    if preference is None:
        preference = NotificationPreference(hospital_id=hospital_id, user_id=user.id)
        db.add(preference)
    for key, value in values.items():
        setattr(preference, key, value)
    _audit(db, hospital_id, user.id, "notifications.patient_preferences_updated", "notification_preference", preference.id)
    db.commit()
    from sqlalchemy import text
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user.id)})
    db.refresh(preference)
    return preference


@router.get("/templates", response_model=list[NotificationTemplateRead])
def list_notification_templates(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    return db.scalars(select(NotificationTemplate).where(
        NotificationTemplate.hospital_id == hospital_id,
    ).order_by(NotificationTemplate.template_code, NotificationTemplate.version.desc()).limit(300)).all()


@router.get("/queue", response_model=list[NotificationIntentRead])
def list_notification_queue(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    return db.scalars(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.status.in_(("queued", "processing", "retry_scheduled", "failed")),
    ).order_by(NotificationIntent.created_at.desc()).limit(300)).all()


@router.post("/{intent_id}/cancel", response_model=NotificationIntentRead)
def cancel_notification(intent_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    intent = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.id == intent_id,
    ).with_for_update())
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "notification_intent_not_found"})
    if intent.status not in ("queued", "retry_scheduled"):
        raise HTTPException(status_code=409, detail={"code": "only_queued_notifications_can_be_cancelled"})
    intent.status = "cancelled"
    db.add(NotificationEvent(
        hospital_id=hospital_id, intent_id=intent.id, actor_user_id=user.id,
        event_type="cancelled", event_metadata={"reason": "administrator_cancelled_before_dispatch"},
    ))
    _audit(db, hospital_id, user.id, "notifications.cancelled", "notification_intent", intent.id)
    db.commit()
    _restore_context(db, user.id, hospital_id)
    db.refresh(intent)
    return intent


@router.post("/department-notices", response_model=DepartmentNoticeResult, status_code=status.HTTP_202_ACCEPTED)
def create_department_notice(payload: DepartmentNoticeCreate, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    role = _role(db, user.id, hospital_id)
    manager_department_id = None
    if role in _ADMIN_ROLES:
        pass
    elif role in {"department_head", "nurse_manager"}:
        employee = db.scalar(select(EmployeeProfile).where(
            EmployeeProfile.hospital_id == hospital_id,
            EmployeeProfile.user_id == user.id,
            EmployeeProfile.employment_status == "active",
        ))
        if employee is None or employee.department_id is None:
            raise HTTPException(status_code=403, detail={"code": "active_department_manager_profile_required"})
        manager_department_id = employee.department_id
        if payload.department_id != manager_department_id:
            raise HTTPException(status_code=403, detail={"code": "department_notice_scope_denied"})
    else:
        raise HTTPException(status_code=403, detail={"code": "department_notice_publisher_role_required"})

    department = db.scalar(select(Department).where(
        Department.hospital_id == hospital_id,
        Department.id == payload.department_id,
        Department.status == "active",
    ))
    if department is None:
        raise HTTPException(status_code=404, detail={"code": "active_department_not_found"})
    template = db.scalar(select(NotificationTemplate).where(
        NotificationTemplate.hospital_id == hospital_id,
        NotificationTemplate.id == payload.template_id,
        NotificationTemplate.status == "published",
    ))
    if template is None:
        raise HTTPException(status_code=404, detail={"code": "published_notification_template_not_found"})
    required = _placeholders(template.title_template, template.body_template)
    if not required.issubset(set(template.allowed_placeholders)) or set(payload.variables) != required:
        raise HTTPException(status_code=422, detail={"code": "notification_variables_must_match_template"})
    query = select(HospitalMembership.user_id, Role.name).join(
        Role, Role.id == HospitalMembership.role_id,
    ).join(User, User.id == HospitalMembership.user_id).where(
        HospitalMembership.hospital_id == hospital_id,
        HospitalMembership.department_id == payload.department_id,
        HospitalMembership.status == "active",
        User.is_active.is_(True),
    )
    if payload.role_names:
        requested_roles = {name.strip().casefold().replace(" ", "_") for name in payload.role_names}
        query = query.where(func.lower(func.replace(Role.name, " ", "_")).in_(requested_roles))
    recipients = db.execute(query).all()
    if not recipients:
        raise HTTPException(status_code=409, detail={"code": "department_has_no_active_recipients"})

    queued_ids = []
    skipped = 0
    idempotency_keys = []
    for recipient_user_id, _role_name in recipients:
        key = f"{payload.idempotency_key}:{recipient_user_id}"
        idempotency_keys.append(key)
        existing = db.scalar(select(NotificationIntent.id).where(
            NotificationIntent.hospital_id == hospital_id,
            NotificationIntent.idempotency_key == key,
        ))
        if existing is not None:
            queued_ids.append(existing)
            continue
        preference = db.scalar(select(NotificationPreference).where(
            NotificationPreference.hospital_id == hospital_id,
            NotificationPreference.user_id == recipient_user_id,
        ))
        recipient_template = _localized_template(db, hospital_id, template, preference.locale if preference else "en")
        channel_field = _CHANNEL_PREF[recipient_template.channel]
        enabled = (recipient_template.channel == "in_app" and preference is None) or (
            preference is not None and getattr(preference, channel_field)
        )
        if not enabled:
            skipped += 1
            continue
        required_for_locale = _placeholders(recipient_template.title_template, recipient_template.body_template)
        if required_for_locale != set(payload.variables):
            recipient_template = _localized_template(db, hospital_id, template, "en")
        try:
            localized_title = recipient_template.title_template.format_map(payload.variables)
            localized_body = recipient_template.body_template.format_map(payload.variables)
        except (KeyError, ValueError):
            skipped += 1
            continue
        intent = NotificationIntent(
            hospital_id=hospital_id, recipient_user_id=recipient_user_id,
            template_id=recipient_template.id, channel=recipient_template.channel, purpose=payload.purpose,
            idempotency_key=key, rendered_title=localized_title, rendered_body=localized_body,
            created_by_user_id=user.id,
        )
        db.add(intent)
        db.flush()
        db.add(NotificationEvent(
            hospital_id=hospital_id, intent_id=intent.id, actor_user_id=user.id,
            event_type="enqueued", event_metadata={"channel": template.channel, "audience": "department"},
        ))
        queued_ids.append(intent.id)
    try:
        _audit(db, hospital_id, user.id, "notifications.department_notice_created", "department", department.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        _restore_context(db, user.id, hospital_id)
        existing_ids = db.scalars(select(NotificationIntent.id).where(
            NotificationIntent.hospital_id == hospital_id,
            NotificationIntent.idempotency_key.in_(idempotency_keys),
        )).all()
        if existing_ids:
            return DepartmentNoticeResult(
                department_id=department.id, recipients_queued=len(existing_ids),
                skipped_channel_opt_out=skipped, notification_ids=existing_ids,
            )
        raise HTTPException(status_code=409, detail={"code": "department_notice_enqueue_conflict"}) from None
    _restore_context(db, user.id, hospital_id)
    return DepartmentNoticeResult(
        department_id=department.id, recipients_queued=len(queued_ids),
        skipped_channel_opt_out=skipped, notification_ids=queued_ids,
    )


@router.get("/dashboard")
def get_notification_dashboard(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    _require_admin(db, user.id, hospital_id)
    status_rows = db.execute(select(
        NotificationIntent.status, func.count(NotificationIntent.id),
    ).where(NotificationIntent.hospital_id == hospital_id).group_by(NotificationIntent.status)).all()
    channel_rows = db.execute(select(
        NotificationIntent.channel, func.count(NotificationIntent.id),
    ).where(NotificationIntent.hospital_id == hospital_id).group_by(NotificationIntent.channel)).all()
    return {
        "hospital_id": hospital_id,
        "by_status": {state: count for state, count in status_rows},
        "by_channel": {channel: count for channel, count in channel_rows},
    }


@router.post("/my-notifications/{intent_id}/read", response_model=NotificationIntentRead)
def mark_staff_notification_read(intent_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    intent = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.id == intent_id,
        NotificationIntent.recipient_user_id == user.id,
    ).with_for_update())
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "notification_not_found"})
    if intent.read_at is None:
        intent.read_at = datetime.now(timezone.utc)
        _audit(db, hospital_id, user.id, "notifications.staff_notification_read", "notification_intent", intent.id)
        db.commit()
        _restore_context(db, user.id, hospital_id)
        db.refresh(intent)
    return intent


@router.post("/patient/inbox/{intent_id}/read", response_model=NotificationIntentRead)
def mark_patient_notification_read(intent_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    intent = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.id == intent_id,
        NotificationIntent.recipient_user_id == user.id,
        NotificationIntent.channel == "in_app",
    ).with_for_update())
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "notification_not_found"})
    if intent.read_at is None:
        intent.read_at = datetime.now(timezone.utc)
        _audit(db, hospital_id, user.id, "notifications.patient_notification_read", "notification_intent", intent.id)
        db.commit()
        from sqlalchemy import text
        db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
        db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user.id)})
        db.refresh(intent)
    return intent


@router.get("/my-dashboard")
def get_my_notification_dashboard(context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    total = db.scalar(select(func.count(NotificationIntent.id)).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.recipient_user_id == user.id,
    )) or 0
    unread = db.scalar(select(func.count(NotificationIntent.id)).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.recipient_user_id == user.id,
        NotificationIntent.read_at.is_(None),
    )) or 0
    return {"total": total, "unread": unread}


@router.get("/patient/dashboard")
def get_patient_notification_dashboard(context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    total = db.scalar(select(func.count(NotificationIntent.id)).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.recipient_user_id == user.id,
        NotificationIntent.channel == "in_app",
    )) or 0
    unread = db.scalar(select(func.count(NotificationIntent.id)).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.recipient_user_id == user.id,
        NotificationIntent.channel == "in_app",
        NotificationIntent.read_at.is_(None),
    )) or 0
    return {"total": total, "unread": unread}


@router.get("/my-notifications/{intent_id}/events")
def get_staff_notification_events(intent_id: UUID, context: tuple = Depends(get_current_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    intent = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.id == intent_id,
        NotificationIntent.recipient_user_id == user.id,
    ))
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "notification_not_found"})
    events = db.scalars(select(NotificationEvent).where(
        NotificationEvent.hospital_id == hospital_id,
        NotificationEvent.intent_id == intent_id,
    ).order_by(NotificationEvent.created_at.asc()).limit(200)).all()
    return [{"id": event.id, "event_type": event.event_type, "created_at": event.created_at} for event in events]


@router.get("/patient/inbox/{intent_id}/events")
def get_patient_notification_events(intent_id: UUID, context: tuple = Depends(get_current_patient_context), db: Session = Depends(get_db)):
    user, hospital_id = context
    intent = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.id == intent_id,
        NotificationIntent.recipient_user_id == user.id,
        NotificationIntent.channel == "in_app",
    ))
    if intent is None:
        raise HTTPException(status_code=404, detail={"code": "notification_not_found"})
    events = db.scalars(select(NotificationEvent).where(
        NotificationEvent.hospital_id == hospital_id,
        NotificationEvent.intent_id == intent_id,
    ).order_by(NotificationEvent.created_at.asc()).limit(200)).all()
    return [{"id": event.id, "event_type": event.event_type, "created_at": event.created_at} for event in events]
