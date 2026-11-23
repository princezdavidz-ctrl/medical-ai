from uuid import UUID
from sqlalchemy.orm import Session
from app.models import AuditEvent

def write_audit_event(
    db: Session,
    *,
    hospital_id: UUID,
    actor_user_id: UUID,
    action: str,
    resource_type: str,
    resource_id: str | None,
    metadata: dict | None = None,
) -> None:
    """Append a minimal audit event; never include clinical note text or credentials."""
    db.add(
        AuditEvent(
            hospital_id=hospital_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome="success",
            metadata_json=metadata or {},
        )
    )
