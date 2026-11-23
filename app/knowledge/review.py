from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import AuditEvent, HospitalMembership
from app.models.knowledge import MedicalKnowledgeChunk, MedicalKnowledgeDocument, MedicalKnowledgeSource
from app.models.knowledge_ingestion import KnowledgeImportBatch, StagedKnowledgeDocument
from app.models.knowledge_review import ClinicalKnowledgeReviewerAuthorization, KnowledgeReviewEvent


def _require_reviewer(
    session: Session, *, user_id: UUID, hospital_id: UUID | None, scope: str
) -> ClinicalKnowledgeReviewerAuthorization:
    now = datetime.now(timezone.utc)
    query = select(ClinicalKnowledgeReviewerAuthorization).where(
        ClinicalKnowledgeReviewerAuthorization.user_id == user_id,
        ClinicalKnowledgeReviewerAuthorization.scope == scope,
        ClinicalKnowledgeReviewerAuthorization.status == "active",
        ClinicalKnowledgeReviewerAuthorization.verified_at <= now,
        (ClinicalKnowledgeReviewerAuthorization.expires_at.is_(None)
         | (ClinicalKnowledgeReviewerAuthorization.expires_at > now)),
    )
    if scope == "hospital":
        query = query.where(ClinicalKnowledgeReviewerAuthorization.hospital_id == hospital_id)
        membership = session.scalar(select(HospitalMembership).where(
            HospitalMembership.user_id == user_id,
            HospitalMembership.hospital_id == hospital_id,
            HospitalMembership.status == "active",
        ))
        if membership is None:
            raise PermissionError("active_hospital_membership_required")
    authorization = session.scalar(query)
    if authorization is None:
        raise PermissionError("verified_clinical_reviewer_authorization_required")
    return authorization


def approve_staged_document(
    session: Session, *, staged_document_id: UUID, reviewer_user_id: UUID,
    hospital_id: UUID | None, reason: str,
) -> StagedKnowledgeDocument:
    if not reason.strip():
        raise ValueError("review_reason_required")
    staged = session.scalar(
        select(StagedKnowledgeDocument)
        .where(StagedKnowledgeDocument.id == staged_document_id)
        .with_for_update()
    )
    if staged is None:
        raise LookupError("staged_document_not_found")
    batch = session.get(KnowledgeImportBatch, staged.batch_id)
    if batch is None or batch.status not in {"needs_review", "validating"}:
        raise ValueError("import_batch_not_reviewable")
    if staged.status not in {"pending_review", "staged"}:
        raise ValueError("staged_document_not_reviewable")
    if batch.submitted_by_user_id == reviewer_user_id:
        raise PermissionError("submitter_cannot_review_own_import")
    if batch.scope == "hospital" and batch.hospital_id != hospital_id:
        raise PermissionError("hospital_scope_mismatch")
    if batch.scope == "global" and hospital_id is not None:
        raise PermissionError("global_review_requires_platform_context")
    if not batch.license_verified or not (batch.declared_license or "").strip():
        raise ValueError("source_license_not_verified")
    authorization = _require_reviewer(
        session, user_id=reviewer_user_id, hospital_id=hospital_id, scope=batch.scope
    )
    source = session.get(MedicalKnowledgeSource, batch.source_id) if batch.source_id else None
    if source is None or source.status != "active":
        raise ValueError("active_governed_knowledge_source_required")
    if not source.license_name or not source.license_reference:
        raise ValueError("governed_source_license_metadata_required")
    staged.status = "approved"
    session.add(KnowledgeReviewEvent(
        staged_document_id=staged.id,
        actor_user_id=reviewer_user_id,
        reviewer_authorization_id=authorization.id,
        decision="approved",
        reason=reason.strip(),
        metadata_json={"source_id": str(source.id), "content_sha256": staged.content_sha256},
    ))
    session.commit()
    session.refresh(staged)
    return staged


def reject_staged_document(
    session: Session, *, staged_document_id: UUID, reviewer_user_id: UUID,
    hospital_id: UUID | None, reason: str,
) -> StagedKnowledgeDocument:
    if not reason.strip():
        raise ValueError("rejection_reason_required")
    staged = session.scalar(
        select(StagedKnowledgeDocument)
        .where(StagedKnowledgeDocument.id == staged_document_id)
        .with_for_update()
    )
    if staged is None:
        raise LookupError("staged_document_not_found")
    batch = session.get(KnowledgeImportBatch, staged.batch_id)
    if batch is None:
        raise LookupError("import_batch_not_found")
    if batch.submitted_by_user_id == reviewer_user_id:
        raise PermissionError("submitter_cannot_review_own_import")
    if batch.scope == "hospital" and batch.hospital_id != hospital_id:
        raise PermissionError("hospital_scope_mismatch")
    if batch.scope == "global" and hospital_id is not None:
        raise PermissionError("global_review_requires_platform_context")
    authorization = _require_reviewer(
        session, user_id=reviewer_user_id, hospital_id=hospital_id, scope=batch.scope
    )
    if staged.status not in {"pending_review", "staged"}:
        raise ValueError("staged_document_not_reviewable")
    staged.status = "rejected"
    session.add(KnowledgeReviewEvent(
        staged_document_id=staged.id, actor_user_id=reviewer_user_id,
        reviewer_authorization_id=authorization.id, decision="rejected",
        reason=reason.strip(), metadata_json={"content_sha256": staged.content_sha256},
    ))
    session.commit()
    session.refresh(staged)
    return staged


def publish_approved_document(
    session: Session, *, staged_document_id: UUID, publisher_user_id: UUID,
    hospital_id: UUID | None, next_review_at: datetime,
    supersedes_document_id: UUID | None = None,
) -> MedicalKnowledgeDocument:
    """Publish only after review, with a distinct authorized publisher identity."""
    staged = session.scalar(
        select(StagedKnowledgeDocument)
        .where(StagedKnowledgeDocument.id == staged_document_id)
        .with_for_update()
    )
    if staged is None:
        raise LookupError("staged_document_not_found")
    batch = session.get(KnowledgeImportBatch, staged.batch_id)
    if batch is None or staged.status != "approved":
        raise ValueError("document_requires_approved_review")
    if batch.submitted_by_user_id == publisher_user_id:
        raise PermissionError("submitter_cannot_publish_own_import")
    if batch.scope == "hospital" and batch.hospital_id != hospital_id:
        raise PermissionError("hospital_scope_mismatch")
    if batch.scope == "global" and hospital_id is not None:
        raise PermissionError("global_publication_requires_platform_context")
    if not batch.license_verified:
        raise ValueError("source_license_not_verified")
    authorization = _require_reviewer(
        session, user_id=publisher_user_id, hospital_id=hospital_id, scope=batch.scope
    )
    source = session.get(MedicalKnowledgeSource, batch.source_id) if batch.source_id else None
    if source is None or source.status != "active" or not source.license_name or not source.license_reference:
        raise ValueError("active_licensed_knowledge_source_required")
    if next_review_at.tzinfo is None or next_review_at <= datetime.now(timezone.utc):
        raise ValueError("future_timezone_aware_review_deadline_required")

    previous = None
    if supersedes_document_id is not None:
        previous = session.scalar(
            select(MedicalKnowledgeDocument)
            .where(MedicalKnowledgeDocument.id == supersedes_document_id)
            .with_for_update()
        )
        if previous is None or previous.source_id != source.id or previous.status != "approved":
            raise ValueError("superseded_document_must_be_approved_version_of_same_source")

    document = MedicalKnowledgeDocument(
        source_id=source.id,
        title=staged.title,
        version=staged.external_version or staged.content_sha256[:16],
        content_type=staged.content_type,
        summary=None,
        status="approved",
        reviewed_by_user_id=publisher_user_id,
        reviewed_at=datetime.now(timezone.utc),
        next_review_at=next_review_at,
        supersedes_document_id=supersedes_document_id,
    )
    session.add(document)
    session.flush()
    session.add(MedicalKnowledgeChunk(
        document_id=document.id,
        sequence=0,
        content=staged.payload_text,
        keywords=[],
        metadata_json={
            "source_identity": staged.source_identity,
            "external_document_id": staged.external_document_id,
            "external_version": staged.external_version,
            "jurisdiction": staged.jurisdiction,
            "language": staged.language,
            "content_sha256": staged.content_sha256,
            "ingestion_batch_id": str(batch.id),
        },
    ))
    if previous is not None:
        previous.status = "superseded"
        previous.effective_to = datetime.now(timezone.utc)
        session.add(KnowledgeReviewEvent(
            staged_document_id=staged.id,
            actor_user_id=publisher_user_id,
            reviewer_authorization_id=authorization.id,
            decision="superseded",
            reason="Replaced by a newly approved version",
            metadata_json={"superseded_document_id": str(previous.id)},
        ))
    staged.status = "promoted"
    session.add(KnowledgeReviewEvent(
        staged_document_id=staged.id,
        actor_user_id=publisher_user_id,
        reviewer_authorization_id=authorization.id,
        decision="published",
        reason="Published after independent clinical review",
        metadata_json={"knowledge_document_id": str(document.id), "content_sha256": staged.content_sha256},
    ))
    if batch.scope == "hospital" and batch.hospital_id:
        session.add(AuditEvent(
            hospital_id=batch.hospital_id,
            actor_user_id=publisher_user_id,
            action="knowledge.document.published",
            resource_type="medical_knowledge_document",
            resource_id=str(document.id),
            outcome="success",
            reason="Approved staged knowledge published",
            metadata_json={"source_id": str(source.id), "staged_document_id": str(staged.id)},
        ))
    session.commit()
    session.refresh(document)
    return document
