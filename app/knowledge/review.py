from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import AuditEvent, HospitalMembership
from app.models.knowledge import MedicalKnowledgeChunk, MedicalKnowledgeDocument, MedicalKnowledgeSource
from app.models.knowledge_ingestion import KnowledgeImportBatch, StagedKnowledgeDocument
from app.models.knowledge_review import ClinicalKnowledgeReviewerAuthorization, KnowledgeReviewEvent


def validate_review_separation(*, submitter_id: UUID, reviewer_id: UUID, publisher_id: UUID | None = None) -> None:
    if reviewer_id == submitter_id:
        raise PermissionError("submitter_cannot_review_own_import")
    if publisher_id is not None and publisher_id in {submitter_id, reviewer_id}:
        raise PermissionError("publisher_must_be_independent_of_submitter_and_reviewer")


def _authorization(session: Session, user_id: UUID, hospital_id: UUID | None, scope: str):
    now = datetime.now(timezone.utc)
    q = select(ClinicalKnowledgeReviewerAuthorization).where(
        ClinicalKnowledgeReviewerAuthorization.user_id == user_id,
        ClinicalKnowledgeReviewerAuthorization.scope == scope,
        ClinicalKnowledgeReviewerAuthorization.status == "active",
        ClinicalKnowledgeReviewerAuthorization.verified_at <= now,
        (ClinicalKnowledgeReviewerAuthorization.expires_at.is_(None) |
         (ClinicalKnowledgeReviewerAuthorization.expires_at > now)),
    )
    if scope == "hospital":
        q = q.where(ClinicalKnowledgeReviewerAuthorization.hospital_id == hospital_id)
        member = session.scalar(select(HospitalMembership).where(
            HospitalMembership.user_id == user_id,
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.status == "active",
        ))
        if member is None:
            raise PermissionError("active_hospital_membership_required")
    auth = session.scalar(q)
    if auth is None:
        raise PermissionError("verified_reviewer_authorization_required")
    return auth


def _get_staged(session: Session, staged_id: UUID):
    staged = session.scalar(select(StagedKnowledgeDocument).where(
        StagedKnowledgeDocument.id == staged_id
    ).with_for_update())
    if staged is None:
        raise LookupError("staged_document_not_found")
    batch = session.get(KnowledgeImportBatch, staged.batch_id)
    if batch is None:
        raise LookupError("import_batch_not_found")
    return staged, batch


def review_staged_document(
    session: Session, *, staged_document_id: UUID, reviewer_user_id: UUID,
    hospital_id: UUID | None, decision: str, reason: str,
) -> StagedKnowledgeDocument:
    if decision not in {"approved", "rejected"} or not reason.strip():
        raise ValueError("valid_review_decision_and_reason_required")
    staged, batch = _get_staged(session, staged_document_id)
    if staged.status not in {"staged", "pending_review"}:
        raise ValueError("staged_document_not_reviewable")
    validate_review_separation(submitter_id=batch.submitted_by_user_id, reviewer_id=reviewer_user_id)
    if batch.scope == "hospital" and batch.hospital_id != hospital_id:
        raise PermissionError("hospital_scope_mismatch")
    if batch.scope == "global" and hospital_id is not None:
        raise PermissionError("global_review_requires_platform_context")
    auth = _authorization(session, reviewer_user_id, hospital_id, batch.scope)
    if decision == "approved":
        source = session.get(MedicalKnowledgeSource, batch.source_id) if batch.source_id else None
        if (not batch.license_verified or not batch.declared_license or source is None
            or source.status != "active" or not source.license_name or not source.license_reference
            or source.scope != batch.scope or source.hospital_id != batch.hospital_id):
            raise ValueError("verified_active_licensed_source_required")
        staged.status = "approved"
    else:
        staged.status = "rejected"
    session.add(KnowledgeReviewEvent(
        staged_document_id=staged.id, actor_user_id=reviewer_user_id,
        reviewer_authorization_id=auth.id, decision=decision, reason=reason.strip(),
        metadata_json={"content_sha256": staged.content_sha256},
    ))
    session.commit()
    session.refresh(staged)
    return staged


def publish_approved_document(
    session: Session, *, staged_document_id: UUID, publisher_user_id: UUID,
    hospital_id: UUID | None, next_review_at: datetime,
    supersedes_document_id: UUID | None = None,
) -> MedicalKnowledgeDocument:
    staged, batch = _get_staged(session, staged_document_id)
    if staged.status != "approved":
        raise ValueError("document_requires_approved_review")
    if batch.scope == "hospital" and batch.hospital_id != hospital_id:
        raise PermissionError("hospital_scope_mismatch")
    if batch.scope == "global" and hospital_id is not None:
        raise PermissionError("global_publication_requires_platform_context")
    publisher_auth = _authorization(session, publisher_user_id, hospital_id, batch.scope)
    approval = session.scalar(select(KnowledgeReviewEvent).where(
        KnowledgeReviewEvent.staged_document_id == staged.id,
        KnowledgeReviewEvent.decision == "approved",
    ).order_by(KnowledgeReviewEvent.occurred_at.desc()).limit(1))
    if approval is None:
        raise PermissionError("independent_clinical_approval_required")
    validate_review_separation(
        submitter_id=batch.submitted_by_user_id,
        reviewer_id=approval.actor_user_id,
        publisher_id=publisher_user_id,
    )
    if approval.reviewer_authorization_id is None:
        raise PermissionError("approval_requires_verified_reviewer")
    approval_auth = session.get(
        ClinicalKnowledgeReviewerAuthorization, approval.reviewer_authorization_id
    )
    if (approval_auth is None or approval_auth.user_id != approval.actor_user_id
        or approval_auth.status != "active"
        or (approval_auth.expires_at is not None
            and approval_auth.expires_at <= datetime.now(timezone.utc))):
        raise PermissionError("approving_clinician_authorization_not_current")
    source = session.get(MedicalKnowledgeSource, batch.source_id) if batch.source_id else None
    if (source is None or source.status != "active" or not source.license_name
        or not source.license_reference or source.scope != batch.scope
        or source.hospital_id != batch.hospital_id or not batch.license_verified):
        raise ValueError("active_licensed_knowledge_source_required")
    if next_review_at.tzinfo is None or next_review_at <= datetime.now(timezone.utc):
        raise ValueError("future_timezone_aware_review_deadline_required")
    if sha256(staged.payload_text.encode("utf-8")).hexdigest() != staged.content_sha256:
        raise ValueError("staged_content_integrity_check_failed")

    active_versions = session.scalars(select(MedicalKnowledgeDocument).where(
        MedicalKnowledgeDocument.source_id == source.id,
        MedicalKnowledgeDocument.status == "approved",
    ).with_for_update()).all()
    if active_versions:
        if len(active_versions) != 1 or supersedes_document_id != active_versions[0].id:
            raise ValueError("exactly_one_current_version_must_be_superseded")
    elif supersedes_document_id is not None:
        raise ValueError("no_current_approved_version_to_supersede")
    previous = active_versions[0] if active_versions else None

    now = datetime.now(timezone.utc)
    doc = MedicalKnowledgeDocument(
        source_id=source.id, title=staged.title,
        version=staged.external_version or staged.content_sha256[:16],
        content_type=staged.content_type, status="approved",
        reviewed_by_user_id=approval.actor_user_id, reviewed_at=approval.occurred_at,
        next_review_at=next_review_at, supersedes_document_id=supersedes_document_id,
    )
    session.add(doc)
    session.flush()
    session.add(MedicalKnowledgeChunk(
        document_id=doc.id, sequence=0, content=staged.payload_text, keywords=[],
        metadata_json={"source_identity": staged.source_identity,
            "external_document_id": staged.external_document_id,
            "external_version": staged.external_version,
            "jurisdiction": staged.jurisdiction, "language": staged.language,
            "content_sha256": staged.content_sha256, "ingestion_batch_id": str(batch.id)},
    ))
    if previous:
        previous.status = "superseded"
        previous.effective_to = now
        session.add(KnowledgeReviewEvent(
            staged_document_id=staged.id, actor_user_id=publisher_user_id,
            reviewer_authorization_id=publisher_auth.id, decision="superseded",
            reason="Replaced by a newly approved version",
            metadata_json={"superseded_document_id": str(previous.id)},
        ))
    staged.status = "promoted"
    session.add(KnowledgeReviewEvent(
        staged_document_id=staged.id, actor_user_id=publisher_user_id,
        reviewer_authorization_id=publisher_auth.id, decision="published",
        reason="Published after independent clinical review",
        metadata_json={"knowledge_document_id": str(doc.id)},
    ))
    if batch.scope == "hospital" and batch.hospital_id:
        session.add(AuditEvent(
            hospital_id=batch.hospital_id, actor_user_id=publisher_user_id,
            action="knowledge.document.published", resource_type="medical_knowledge_document",
            resource_id=str(doc.id), outcome="success",
            reason="Approved staged knowledge published",
            metadata_json={"source_id": str(source.id), "staged_document_id": str(staged.id)},
        ))
    session.commit()
    session.refresh(doc)
    return doc
