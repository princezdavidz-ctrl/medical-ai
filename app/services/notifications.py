from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import HospitalMembership, PatientConsent, User
from app.models.notifications import (
    NotificationDeliveryAttempt, NotificationEvent, NotificationIntent, NotificationPreference,
)
from app.models.patient_portal import PatientPortalLink


def _restore_tenant(db: Session, hospital_id: UUID, user_id: UUID) -> None:
    db.execute(text("SELECT set_config('app.current_hospital_id', :v, true)"), {"v": str(hospital_id)})
    db.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user_id)})


def _recipient_is_active(db: Session, intent: NotificationIntent) -> bool:
    user = db.scalar(select(User).where(User.id == intent.recipient_user_id, User.is_active.is_(True)))
    if user is None:
        return False
    membership = db.scalar(select(HospitalMembership.id).where(
        HospitalMembership.hospital_id == intent.hospital_id,
        HospitalMembership.user_id == intent.recipient_user_id,
        HospitalMembership.status == "active",
    ))
    if membership is not None:
        return True
    if intent.patient_id is None:
        return False
    link = db.scalar(select(PatientPortalLink.id).where(
        PatientPortalLink.hospital_id == intent.hospital_id,
        PatientPortalLink.patient_id == intent.patient_id,
        PatientPortalLink.portal_user_id == intent.recipient_user_id,
        PatientPortalLink.status == "active",
    ))
    return link is not None


def _consent_is_active(db: Session, intent: NotificationIntent, now: datetime) -> bool:
    if intent.patient_id is None:
        return intent.consent_id is None
    consent = db.scalar(select(PatientConsent).where(
        PatientConsent.hospital_id == intent.hospital_id,
        PatientConsent.id == intent.consent_id,
        PatientConsent.patient_id == intent.patient_id,
        PatientConsent.status == "granted",
        PatientConsent.purpose == intent.purpose,
    ))
    if consent is None or (consent.expires_at is not None and consent.expires_at <= now):
        return False
    channels = consent.scope.get("channels", []) if isinstance(consent.scope, dict) else []
    return intent.channel in channels


def _quiet_until(preference: NotificationPreference | None, now: datetime) -> datetime | None:
    if preference is None or preference.quiet_start is None or preference.quiet_end is None:
        return None
    try:
        zone = ZoneInfo(preference.timezone_name)
    except ZoneInfoNotFoundError:
        return now + timedelta(minutes=15)
    local_now = now.astimezone(zone)
    current = local_now.timetz().replace(tzinfo=None)
    start = time.fromisoformat(preference.quiet_start)
    end = time.fromisoformat(preference.quiet_end)
    if start == end:
        return None
    quiet = start <= current < end if start < end else current >= start or current < end
    if not quiet:
        return None
    end_date = local_now.date()
    if start > end and current >= start:
        end_date += timedelta(days=1)
    local_end = datetime.combine(end_date, end).replace(tzinfo=zone)
    return local_end.astimezone(timezone.utc)


def claim_next_notification(db: Session, *, hospital_id: UUID, worker_user_id: UUID) -> NotificationIntent | None:
    """Claim one due intent. Caller must commit before calling an external adapter."""
    _restore_tenant(db, hospital_id, worker_user_id)
    now = datetime.now(timezone.utc)
    intent = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.status.in_(("queued", "retry_scheduled")),
        NotificationIntent.next_attempt_at <= now,
    ).order_by(NotificationIntent.next_attempt_at, NotificationIntent.created_at).with_for_update(skip_locked=True).limit(1))
    if intent is None:
        return None

    preference = db.scalar(select(NotificationPreference).where(
        NotificationPreference.hospital_id == hospital_id,
        NotificationPreference.user_id == intent.recipient_user_id,
    ))
    enabled_by_default = intent.channel == "in_app" and preference is None
    channel_enabled = enabled_by_default or (preference is not None and getattr(
        preference, {"in_app": "in_app_enabled", "email": "email_enabled", "sms": "sms_enabled", "push": "push_enabled"}[intent.channel]
    ))
    if not _recipient_is_active(db, intent) or not _consent_is_active(db, intent, now) or not channel_enabled:
        intent.status = "cancelled"
        db.add(NotificationEvent(
            hospital_id=hospital_id, intent_id=intent.id, actor_user_id=worker_user_id,
            event_type="cancelled", event_metadata={"reason_code": "recipient_or_consent_no_longer_eligible"},
        ))
        db.commit()
        _restore_tenant(db, hospital_id, worker_user_id)
        return None

    quiet_until = _quiet_until(preference, now)
    if quiet_until is not None:
        intent.status = "retry_scheduled"
        intent.next_attempt_at = quiet_until
        db.add(NotificationEvent(
            hospital_id=hospital_id, intent_id=intent.id, actor_user_id=worker_user_id,
            event_type="retry_scheduled", event_metadata={"reason_code": "recipient_quiet_hours"},
        ))
        db.commit()
        _restore_tenant(db, hospital_id, worker_user_id)
        return None

    intent.status = "processing"
    intent.attempt_count += 1
    db.add(NotificationEvent(
        hospital_id=hospital_id, intent_id=intent.id, actor_user_id=worker_user_id,
        event_type="dispatch_started", event_metadata={"attempt_number": intent.attempt_count},
    ))
    db.commit()
    _restore_tenant(db, hospital_id, worker_user_id)
    db.refresh(intent)
    return intent


def record_notification_result(
    db: Session, *, hospital_id: UUID, worker_user_id: UUID, intent_id: UUID,
    provider_name: str, accepted: bool, provider_reference: str | None = None,
    retryable: bool = True, error_code: str | None = None,
) -> NotificationIntent:
    """Persist an adapter result. accepted=True must mean the provider acknowledged acceptance."""
    _restore_tenant(db, hospital_id, worker_user_id)
    intent = db.scalar(select(NotificationIntent).where(
        NotificationIntent.hospital_id == hospital_id,
        NotificationIntent.id == intent_id,
    ).with_for_update())
    if intent is None:
        raise ValueError("notification_intent_not_found")
    if intent.status != "processing":
        raise ValueError("notification_intent_not_processing")

    now = datetime.now(timezone.utc)
    attempt_number = intent.attempt_count
    if accepted:
        outcome = "accepted"
        intent.status = "delivered"
        event_type = "delivery_accepted"
    elif retryable and attempt_number < intent.max_attempts:
        outcome = "retryable_failure"
        intent.status = "retry_scheduled"
        intent.next_attempt_at = now + timedelta(seconds=min(3600, 30 * (2 ** max(0, attempt_number - 1))))
        event_type = "retry_scheduled"
    else:
        outcome = "terminal_failure"
        intent.status = "failed"
        event_type = "delivery_failed"

    db.add(NotificationDeliveryAttempt(
        hospital_id=hospital_id, intent_id=intent.id, attempt_number=attempt_number,
        provider_name=provider_name, provider_reference=provider_reference,
        outcome=outcome, error_code=error_code,
    ))
    db.add(NotificationEvent(
        hospital_id=hospital_id, intent_id=intent.id, actor_user_id=worker_user_id,
        event_type=event_type, event_metadata={
            "attempt_number": attempt_number, "provider": provider_name,
            "provider_acknowledged": accepted, "error_code": error_code,
        },
    ))
    db.commit()
    _restore_tenant(db, hospital_id, worker_user_id)
    db.refresh(intent)
    return intent
