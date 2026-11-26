import re
import uuid
from datetime import datetime, timezone
from string import Formatter
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.audit import write_audit_event
from app.api.deps import get_current_context, get_current_patient_context
from app.db.session import get_db
from app.models import HospitalMembership, PatientConsent, Role
from app.models.notifications import NotificationEvent, NotificationIntent, NotificationPreference, NotificationTemplate
from app.models.patient_portal import PatientPortalLink
from app.schemas.notifications import (
    NotificationEnqueue, NotificationIntentRead, NotificationPreferenceUpdate,
    NotificationTemplateCreate, NotificationTemplatePublish, NotificationTemplateRead,
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
        if (
            existing.recipient_user_id != payload.recipient_user_id
            or existing.template_id != payload.template_id
            or existing.patient_id != payload.patient_id
            or existing.consent_id != payload.consent_id
            or existing.purpose != payload.purpose
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
    preference = db.scalar(select(NotificationPreference).where(
        NotificationPreference.hospital_id == hospital_id,
        NotificationPreference.user_id == payload.recipient_user_id,
    ))
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
