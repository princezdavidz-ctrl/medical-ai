import hashlib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.knowledge_ingestion import StagedKnowledgeDocument


LICENSE_GATED_SYSTEMS = {"SNOMED-CT", "LOINC", "ICD-10"}
SUPPORTED_CODE_SYSTEMS = LICENSE_GATED_SYSTEMS | {"LOCAL", "OTHER"}


@dataclass(frozen=True)
class ImportValidation:
    content_sha256: str
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_import_payload(
    *,
    title: str,
    source_identity: str,
    jurisdiction: str,
    language: str,
    content_type: str,
    payload_text: str,
    declared_license: str | None,
    license_verified: bool,
) -> ImportValidation:
    """Validate intake metadata only; this never approves or publishes clinical content."""
    errors: list[str] = []
    if not title.strip():
        errors.append("title_required")
    if not source_identity.strip():
        errors.append("source_identity_required")
    if not jurisdiction.strip():
        errors.append("jurisdiction_required")
    if not re.fullmatch(r"[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})?", language):
        errors.append("language_tag_invalid")
    if content_type not in {"clinical_reference", "guideline", "terminology", "lab_catalog", "policy"}:
        errors.append("content_type_unsupported")
    if not payload_text.strip():
        errors.append("payload_empty")
    if not declared_license or not declared_license.strip():
        errors.append("license_declaration_required")
    if not license_verified:
        errors.append("license_not_verified")
    digest = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    return ImportValidation(content_sha256=digest, errors=tuple(errors))


def find_staged_duplicate(session: Session, *, content_sha256: str) -> StagedKnowledgeDocument | None:
    """Find exact-content duplicates across all staged batches visible to this DB session."""
    statement = (
        select(StagedKnowledgeDocument)
        .where(StagedKnowledgeDocument.content_sha256 == content_sha256)
        .order_by(StagedKnowledgeDocument.created_at.asc())
        .limit(1)
    )
    return session.scalar(statement)


def validate_terminology_mapping(
    *,
    code_system: str,
    code: str,
    release_version: str,
    jurisdiction: str,
    license_verified: bool,
    license_reference: str | None,
) -> tuple[str, ...]:
    errors: list[str] = []
    if code_system not in SUPPORTED_CODE_SYSTEMS:
        errors.append("terminology_system_unsupported")
    if not code.strip():
        errors.append("terminology_code_required")
    if not release_version.strip():
        errors.append("terminology_release_required")
    if not jurisdiction.strip():
        errors.append("terminology_jurisdiction_required")
    if code_system in LICENSE_GATED_SYSTEMS and not license_verified:
        errors.append("terminology_license_not_verified")
    if code_system in LICENSE_GATED_SYSTEMS and not (license_reference or "").strip():
        errors.append("terminology_license_reference_required")
    return tuple(errors)


def validate_unit_mapping(
    *,
    source_unit: str,
    canonical_unit: str,
    source_reference: str,
    reviewer_user_id: object | None,
    reviewed_at: object | None,
) -> tuple[str, ...]:
    """Require explicit review; deliberately does not infer dimensional conversions."""
    errors: list[str] = []
    if not source_unit.strip() or not canonical_unit.strip():
        errors.append("unit_labels_required")
    if not source_reference.strip():
        errors.append("unit_source_reference_required")
    if reviewer_user_id is None or reviewed_at is None:
        errors.append("unit_mapping_requires_named_reviewer_and_timestamp")
    return tuple(errors)
