"""Transactional repository operations for hospital-scoped offline synchronization.

Callers must establish app.current_hospital_id from the authenticated facility context.
Functions intentionally leave commit/rollback to the caller so domain changes and
cursor advancement can be committed atomically.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.offline_packages import OfflineSyncCursor as CursorContract
from app.ai.offline_packages import OfflineSyncEvent as EventContract
from app.ai.offline_packages import classify_sync_event
from app.models.offline_sync import (
    OfflineDeliveryOutbox,
    OfflineSyncConflict,
    OfflineSyncCursor,
    OfflineSyncEvent,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OfflineSyncRejected(ValueError):
    """Raised when an event transition violates sync ordering or acknowledgement rules."""


def record_incoming_event(
    db: Session,
    *,
    hospital_id: UUID,
    source_node_id: str,
    stream_name: str,
    event_id: str,
    sequence_number: int,
    event_type: str,
    payload_sha256: str,
    encrypted_storage_ref: str | None = None,
) -> str:
    """Persist a new event or record a non-PHI conflict; never silently skip a gap."""
    if not _SHA256.fullmatch(payload_sha256):
        raise OfflineSyncRejected("invalid_payload_digest")
    if not all(value.strip() for value in (source_node_id, stream_name, event_id, event_type)):
        raise OfflineSyncRejected("sync_event_identity_missing")

    cursor = db.scalar(
        select(OfflineSyncCursor)
        .where(
            OfflineSyncCursor.hospital_id == hospital_id,
            OfflineSyncCursor.source_node_id == source_node_id,
            OfflineSyncCursor.stream_name == stream_name,
        )
        .with_for_update()
    )
    if cursor is None:
        cursor = OfflineSyncCursor(
            hospital_id=hospital_id,
            source_node_id=source_node_id,
            stream_name=stream_name,
            last_sequence=0,
        )
        db.add(cursor)
        db.flush()

    existing = db.scalar(
        select(OfflineSyncEvent).where(
            OfflineSyncEvent.hospital_id == hospital_id,
            OfflineSyncEvent.source_node_id == source_node_id,
            OfflineSyncEvent.stream_name == stream_name,
            OfflineSyncEvent.event_id == event_id,
        )
    )
    if existing is not None:
        if existing.payload_sha256 == payload_sha256 and existing.sequence_number == sequence_number:
            return "duplicate"
        db.add(OfflineSyncConflict(
            hospital_id=hospital_id,
            event_id=existing.id,
            source_node_id=source_node_id,
            stream_name=stream_name,
            incoming_event_id=event_id,
            incoming_sequence=sequence_number,
            conflict_code="event_identity_digest_or_sequence_mismatch",
            details_json={"stored_sequence": existing.sequence_number},
        ))
        return "conflict"

    sequence_collision = db.scalar(
        select(OfflineSyncEvent).where(
            OfflineSyncEvent.hospital_id == hospital_id,
            OfflineSyncEvent.source_node_id == source_node_id,
            OfflineSyncEvent.stream_name == stream_name,
            OfflineSyncEvent.sequence_number == sequence_number,
        )
    )
    if sequence_collision is not None:
        db.add(OfflineSyncConflict(
            hospital_id=hospital_id,
            event_id=sequence_collision.id,
            source_node_id=source_node_id,
            stream_name=stream_name,
            incoming_event_id=event_id,
            incoming_sequence=sequence_number,
            conflict_code="sequence_number_collision",
            details_json={"stored_event_id": sequence_collision.event_id},
        ))
        return "conflict"

    classification = classify_sync_event(
        cursor=CursorContract(
            sequence=cursor.last_sequence,
            last_event_id=cursor.last_event_id,
        ),
        event=EventContract(
            event_id=event_id,
            sequence=sequence_number,
            payload_sha256=payload_sha256,
        ),
    )
    if classification == "duplicate_or_stale":
        db.add(OfflineSyncConflict(
            hospital_id=hospital_id,
            event_id=None,
            source_node_id=source_node_id,
            stream_name=stream_name,
            incoming_event_id=event_id,
            incoming_sequence=sequence_number,
            conflict_code="stale_or_unrecognized_replay",
            details_json={"last_applied_sequence": cursor.last_sequence},
        ))
        return "conflict"
    if classification == "invalid":
        raise OfflineSyncRejected("invalid_sync_event")
    status = "queued" if classification == "ready" else "conflict"
    event = OfflineSyncEvent(
        hospital_id=hospital_id,
        source_node_id=source_node_id,
        stream_name=stream_name,
        event_id=event_id,
        sequence_number=sequence_number,
        event_type=event_type,
        payload_sha256=payload_sha256,
        encrypted_storage_ref=encrypted_storage_ref,
        status=status,
    )
    db.add(event)
    db.flush()
    if classification == "sequence_gap":
        db.add(OfflineSyncConflict(
            hospital_id=hospital_id,
            event_id=event.id,
            source_node_id=source_node_id,
            stream_name=stream_name,
            incoming_event_id=event_id,
            incoming_sequence=sequence_number,
            conflict_code="sequence_gap",
            details_json={"expected_sequence": cursor.last_sequence + 1},
        ))
        return "conflict"
    return "queued"


def apply_next_incoming_event(
    db: Session,
    *,
    hospital_id: UUID,
    event_id: UUID,
    apply_domain_change: Callable[[Session, OfflineSyncEvent], None],
    now: datetime | None = None,
) -> OfflineSyncEvent:
    """Apply exactly the next event and advance its cursor in the same transaction."""
    event = db.scalar(
        select(OfflineSyncEvent)
        .where(OfflineSyncEvent.id == event_id, OfflineSyncEvent.hospital_id == hospital_id)
        .with_for_update()
    )
    if event is None:
        raise OfflineSyncRejected("sync_event_not_found")
    if event.status != "queued":
        raise OfflineSyncRejected("sync_event_not_queued")

    cursor = db.scalar(
        select(OfflineSyncCursor)
        .where(
            OfflineSyncCursor.hospital_id == hospital_id,
            OfflineSyncCursor.source_node_id == event.source_node_id,
            OfflineSyncCursor.stream_name == event.stream_name,
        )
        .with_for_update()
    )
    if cursor is None or event.sequence_number != cursor.last_sequence + 1:
        raise OfflineSyncRejected("sync_cursor_order_violation")

    apply_domain_change(db, event)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise OfflineSyncRejected("timezone_required")
    event.status = "applied"
    event.applied_at = current
    cursor.last_sequence = event.sequence_number
    cursor.last_event_id = event.event_id
    return event


def acknowledge_incoming_event(
    db: Session, *, hospital_id: UUID, event_id: UUID, now: datetime | None = None
) -> OfflineSyncEvent:
    """Record inbound acknowledgement only after successful durable application."""
    event = db.scalar(
        select(OfflineSyncEvent)
        .where(OfflineSyncEvent.id == event_id, OfflineSyncEvent.hospital_id == hospital_id)
        .with_for_update()
    )
    if event is None or event.status != "applied":
        raise OfflineSyncRejected("only_applied_events_can_be_acknowledged")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise OfflineSyncRejected("timezone_required")
    event.status = "acknowledged"
    event.acknowledged_at = current
    return event


def enqueue_outbound_delivery(
    db: Session,
    *,
    hospital_id: UUID,
    destination_node_id: str,
    idempotency_key: str,
    event_type: str,
    payload_sha256: str,
    encrypted_storage_ref: str,
) -> OfflineDeliveryOutbox:
    """Create an idempotent outbound delivery record without storing raw payload data."""
    if not _SHA256.fullmatch(payload_sha256):
        raise OfflineSyncRejected("invalid_payload_digest")
    if not all(value.strip() for value in (
        destination_node_id, idempotency_key, event_type, encrypted_storage_ref
    )):
        raise OfflineSyncRejected("outbound_delivery_identity_missing")
    existing = db.scalar(
        select(OfflineDeliveryOutbox).where(
            OfflineDeliveryOutbox.hospital_id == hospital_id,
            OfflineDeliveryOutbox.destination_node_id == destination_node_id,
            OfflineDeliveryOutbox.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.payload_sha256 != payload_sha256:
            raise OfflineSyncRejected("idempotency_key_payload_mismatch")
        return existing
    item = OfflineDeliveryOutbox(
        hospital_id=hospital_id,
        destination_node_id=destination_node_id,
        idempotency_key=idempotency_key,
        event_type=event_type,
        payload_sha256=payload_sha256,
        encrypted_storage_ref=encrypted_storage_ref,
        status="queued",
        attempt_count=0,
    )
    db.add(item)
    db.flush()
    return item


def mark_outbound_delivered(
    db: Session,
    *,
    hospital_id: UUID,
    delivery_id: UUID,
    partner_ack_reference: str,
    now: datetime | None = None,
) -> OfflineDeliveryOutbox:
    """Mark delivery complete only when a verified partner acknowledgement is supplied."""
    if not partner_ack_reference.strip():
        raise OfflineSyncRejected("partner_acknowledgement_required")
    item = db.scalar(
        select(OfflineDeliveryOutbox)
        .where(
            OfflineDeliveryOutbox.id == delivery_id,
            OfflineDeliveryOutbox.hospital_id == hospital_id,
        )
        .with_for_update()
    )
    if item is None:
        raise OfflineSyncRejected("outbound_delivery_not_found")
    if item.status not in {"sending", "queued"}:
        raise OfflineSyncRejected("outbound_delivery_not_deliverable")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise OfflineSyncRejected("timezone_required")
    item.status = "delivered"
    item.partner_ack_reference = partner_ack_reference
    item.delivered_at = current
    return item

def claim_next_outbound_delivery(
    db: Session, *, hospital_id: UUID, now: datetime | None = None
) -> OfflineDeliveryOutbox | None:
    """Atomically claim one due delivery; concurrent workers skip already locked rows."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise OfflineSyncRejected("timezone_required")
    item = db.scalar(
        select(OfflineDeliveryOutbox)
        .where(
            OfflineDeliveryOutbox.hospital_id == hospital_id,
            OfflineDeliveryOutbox.status == "queued",
            (OfflineDeliveryOutbox.next_attempt_at.is_(None))
            | (OfflineDeliveryOutbox.next_attempt_at <= current),
        )
        .order_by(OfflineDeliveryOutbox.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if item is None:
        return None
    item.status = "sending"
    item.attempt_count += 1
    return item


def record_outbound_failure(
    db: Session,
    *,
    hospital_id: UUID,
    delivery_id: UUID,
    error_code: str,
    retry_delay: timedelta,
    maximum_attempts: int = 8,
    now: datetime | None = None,
) -> OfflineDeliveryOutbox:
    """Schedule bounded retry using a non-sensitive error code; no false delivery ack."""
    if not error_code.strip() or retry_delay.total_seconds() < 0 or maximum_attempts < 1:
        raise OfflineSyncRejected("invalid_delivery_retry_policy")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise OfflineSyncRejected("timezone_required")
    item = db.scalar(
        select(OfflineDeliveryOutbox)
        .where(
            OfflineDeliveryOutbox.id == delivery_id,
            OfflineDeliveryOutbox.hospital_id == hospital_id,
        )
        .with_for_update()
    )
    if item is None or item.status != "sending":
        raise OfflineSyncRejected("outbound_delivery_not_sending")
    item.last_error_code = error_code[:120]
    if item.attempt_count >= maximum_attempts:
        item.status = "failed"
        item.next_attempt_at = None
    else:
        item.status = "queued"
        item.next_attempt_at = current + retry_delay
    return item
