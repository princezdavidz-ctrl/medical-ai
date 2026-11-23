"""Purpose- and scope-limited patient authorization checks for module services."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PatientConsent


def has_active_patient_authorization(
    db: Session,
    *,
    hospital_id: UUID,
    patient_id: UUID,
    purpose: str,
    data_categories: set[str],
    permitted_use: str,
    now: datetime | None = None,
) -> bool:
    """Return true only when one current granted record covers the entire requested scope."""
    current = now or datetime.now(timezone.utc)
    records = db.scalars(
        select(PatientConsent).where(
            PatientConsent.hospital_id == hospital_id,
            PatientConsent.patient_id == patient_id,
            PatientConsent.purpose == purpose,
            PatientConsent.status == "granted",
            PatientConsent.basis_code.is_not(None),
            PatientConsent.granted_at.is_not(None),
            PatientConsent.granted_at <= current,
            PatientConsent.withdrawn_at.is_(None),
        )
    ).all()
    for record in records:
        if record.expires_at is not None and record.expires_at <= current:
            continue
        scope = record.scope if isinstance(record.scope, dict) else {}
        categories = set(scope.get("data_categories", []))
        uses = set(scope.get("permitted_uses", []))
        if data_categories.issubset(categories) and permitted_use in uses:
            return True
    return False
