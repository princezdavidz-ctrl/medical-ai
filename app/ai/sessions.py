"""Hospital- and owner-scoped encrypted AI conversation persistence."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.session_crypto import SessionCipher, SessionEncryptionError
from app.models.ai_sessions import AISession, AISessionMessage


class AISessionUnavailable(PermissionError):
    pass


def _current_time(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise AISessionUnavailable("timezone_required")
    return current


def create_ai_session(
    db: Session,
    *,
    hospital_id: UUID,
    owner_user_id: UUID,
    retention_days: int,
    now: datetime | None = None,
) -> AISession:
    current = _current_time(now)
    if not 1 <= retention_days <= 3650:
        raise AISessionUnavailable("invalid_session_retention")
    session = AISession(
        hospital_id=hospital_id,
        owner_user_id=owner_user_id,
        status="active",
        message_count=0,
        expires_at=current + timedelta(days=retention_days),
    )
    db.add(session)
    db.flush()
    return session


def get_owned_ai_session(
    db: Session,
    *,
    hospital_id: UUID,
    owner_user_id: UUID,
    session_id: UUID,
    now: datetime | None = None,
    lock: bool = False,
) -> AISession:
    current = _current_time(now)
    query = select(AISession).where(
        AISession.id == session_id,
        AISession.hospital_id == hospital_id,
        AISession.owner_user_id == owner_user_id,
        AISession.status == "active",
        AISession.expires_at > current,
    )
    if lock:
        query = query.with_for_update()
    session = db.scalar(query)
    if session is None:
        raise AISessionUnavailable("ai_session_not_found")
    return session


def append_ai_session_turn(
    db: Session,
    *,
    hospital_id: UUID,
    owner_user_id: UUID,
    session_id: UUID,
    user_prompt: str,
    assistant_response: str,
    cipher: SessionCipher,
    assistant_metadata: dict,
    now: datetime | None = None,
) -> AISession:
    current = _current_time(now)
    session = get_owned_ai_session(
        db,
        hospital_id=hospital_id,
        owner_user_id=owner_user_id,
        session_id=session_id,
        now=current,
        lock=True,
    )
    entries = (
        ("user", user_prompt, {"kind": "request"}),
        ("assistant", assistant_response, assistant_metadata),
    )
    encrypted_entries = []
    for offset, (role, content, metadata) in enumerate(entries, start=1):
        sequence = session.message_count + offset
        key_version = cipher.active_key_version
        aad = cipher.associated_data(
            hospital_id=hospital_id,
            owner_user_id=owner_user_id,
            session_id=session.id,
            sequence_number=sequence,
            role=role,
            key_version=key_version,
        )
        ciphertext, nonce, key_version = cipher.encrypt(content, associated_data=aad)
        encrypted_entries.append((sequence, role, ciphertext, nonce, key_version, metadata))
    for sequence, role, ciphertext, nonce, key_version, metadata in encrypted_entries:
        db.add(AISessionMessage(
            hospital_id=hospital_id,
            session_id=session.id,
            sequence_number=sequence,
            role=role,
            ciphertext=ciphertext,
            nonce=nonce,
            key_version=key_version,
            metadata_json=metadata,
        ))
    session.message_count += 2
    session.last_message_at = current
    db.flush()
    return session


def list_owned_ai_sessions(
    db: Session,
    *,
    hospital_id: UUID,
    owner_user_id: UUID,
    now: datetime | None = None,
) -> list[AISession]:
    current = _current_time(now)
    return list(db.scalars(
        select(AISession)
        .where(
            AISession.hospital_id == hospital_id,
            AISession.owner_user_id == owner_user_id,
            AISession.status == "active",
            AISession.expires_at > current,
        )
        .order_by(AISession.last_message_at.desc().nullslast(), AISession.created_at.desc())
    ).all())


def read_owned_ai_session(
    db: Session,
    *,
    hospital_id: UUID,
    owner_user_id: UUID,
    session_id: UUID,
    cipher: SessionCipher,
    now: datetime | None = None,
) -> tuple[AISession, list[dict]]:
    session = get_owned_ai_session(
        db,
        hospital_id=hospital_id,
        owner_user_id=owner_user_id,
        session_id=session_id,
        now=now,
    )
    messages = db.scalars(
        select(AISessionMessage)
        .where(
            AISessionMessage.hospital_id == hospital_id,
            AISessionMessage.session_id == session.id,
        )
        .order_by(AISessionMessage.sequence_number)
    ).all()
    output: list[dict] = []
    for message in messages:
        aad = cipher.associated_data(
            hospital_id=hospital_id,
            session_id=session.id,
            sequence_number=message.sequence_number,
            role=message.role,
            key_version=message.key_version,
        )
        try:
            content = cipher.decrypt(
                message.ciphertext,
                nonce=message.nonce,
                key_version=message.key_version,
                associated_data=aad,
            )
        except SessionEncryptionError:
            raise
        output.append({
            "sequence": message.sequence_number,
            "role": message.role,
            "content": content,
            "metadata": message.metadata_json,
            "created_at": message.created_at,
        })
    return session, output


def delete_owned_ai_session(
    db: Session,
    *,
    hospital_id: UUID,
    owner_user_id: UUID,
    session_id: UUID,
    now: datetime | None = None,
) -> None:
    current = _current_time(now)
    session = get_owned_ai_session(
        db,
        hospital_id=hospital_id,
        owner_user_id=owner_user_id,
        session_id=session_id,
        now=current,
        lock=True,
    )
    db.execute(
        delete(AISessionMessage).where(
            AISessionMessage.hospital_id == hospital_id,
            AISessionMessage.session_id == session.id,
        )
    )
    session.status = "deleted"
    session.deleted_at = current
    session.message_count = 0
    session.last_message_at = None
    db.flush()

def purge_expired_ai_sessions(
    db: Session,
    *,
    hospital_id: UUID,
    owner_user_id: UUID,
    now: datetime | None = None,
    batch_size: int = 100,
) -> int:
    """Purge one owner's expired messages in bounded batches; caller commits."""
    current = _current_time(now)
    if not 1 <= batch_size <= 1000:
        raise AISessionUnavailable("invalid_session_purge_batch_size")
    expired = db.scalars(
        select(AISession)
        .where(
            AISession.hospital_id == hospital_id,
            AISession.owner_user_id == owner_user_id,
            AISession.status == "active",
            AISession.expires_at <= current,
        )
        .order_by(AISession.expires_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    for session in expired:
        db.execute(
            delete(AISessionMessage).where(
                AISessionMessage.hospital_id == session.hospital_id,
                AISessionMessage.session_id == session.id,
            )
        )
        session.status = "expired"
        session.deleted_at = current
        session.message_count = 0
        session.last_message_at = None
    db.flush()
    return len(expired)
