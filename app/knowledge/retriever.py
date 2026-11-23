import re
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability, KnowledgeEvidence
from app.models.knowledge import MedicalKnowledgeChunk, MedicalKnowledgeDocument, MedicalKnowledgeSource


CAPABILITY_CONTENT_TYPES: dict[AICapability, tuple[str, ...]] = {
    AICapability.MEDICAL_INFORMATION: ("clinical_reference", "guideline", "policy"),
    AICapability.CLINICAL_DECISION_SUPPORT: ("clinical_reference", "guideline", "policy"),
    AICapability.LAB_INTERPRETATION: ("lab_catalog", "clinical_reference", "guideline"),
    AICapability.MEDICATION_SAFETY: ("clinical_reference", "guideline", "policy"),
    AICapability.RADIOLOGY_SUPPORT: ("clinical_reference", "guideline", "policy"),
}


class SQLAlchemyKnowledgeRetriever:
    """Capability-filtered retrieval from approved, current, hospital-visible knowledge."""

    def __init__(self, session: Session, *, max_results: int = 6, max_excerpt_chars: int = 1600) -> None:
        if not 1 <= max_results <= 20:
            raise ValueError("max_results_must_be_between_1_and_20")
        if not 200 <= max_excerpt_chars <= 4000:
            raise ValueError("max_excerpt_chars_must_be_between_200_and_4000")
        self.session = session
        self.max_results = max_results
        self.max_excerpt_chars = max_excerpt_chars

    def search(
        self, *, query: str, capability: AICapability, hospital_id: UUID
    ) -> list[KnowledgeEvidence]:
        allowed_types = CAPABILITY_CONTENT_TYPES.get(capability)
        if not allowed_types:
            return []
        terms = list(dict.fromkeys(
            re.findall(r"[a-zA-Z0-9][a-zA-Z0-9-]{1,}", query.lower())
        ))[:8]
        if not terms:
            return []

        matches = [
            or_(
                MedicalKnowledgeChunk.content.ilike(f"%{term}%"),
                MedicalKnowledgeDocument.title.ilike(f"%{term}%"),
            )
            for term in terms
        ]
        rank = sum(
            case((MedicalKnowledgeChunk.content.ilike(f"%{term}%"), 2), else_=0)
            + case((MedicalKnowledgeDocument.title.ilike(f"%{term}%"), 3), else_=0)
            for term in terms
        )
        statement = (
            select(
                MedicalKnowledgeSource.id.label("source_id"),
                MedicalKnowledgeSource.title.label("source_title"),
                MedicalKnowledgeSource.publisher,
                MedicalKnowledgeSource.canonical_url,
                MedicalKnowledgeSource.jurisdiction,
                MedicalKnowledgeDocument.id.label("document_id"),
                MedicalKnowledgeDocument.title,
                MedicalKnowledgeDocument.version,
                MedicalKnowledgeDocument.evidence_grade,
                MedicalKnowledgeDocument.reviewed_at,
                MedicalKnowledgeDocument.next_review_at,
                MedicalKnowledgeChunk.id.label("chunk_id"),
                MedicalKnowledgeChunk.content,
            )
            .join(
                MedicalKnowledgeDocument,
                MedicalKnowledgeDocument.source_id == MedicalKnowledgeSource.id,
            )
            .join(
                MedicalKnowledgeChunk,
                MedicalKnowledgeChunk.document_id == MedicalKnowledgeDocument.id,
            )
            .where(
                MedicalKnowledgeSource.status == "active",
                or_(
                    MedicalKnowledgeSource.scope == "global",
                    and_(
                        MedicalKnowledgeSource.scope == "hospital",
                        MedicalKnowledgeSource.hospital_id == hospital_id,
                    ),
                ),
                MedicalKnowledgeDocument.content_type.in_(allowed_types),
                MedicalKnowledgeDocument.status == "approved",
                MedicalKnowledgeDocument.reviewed_by_user_id.is_not(None),
                MedicalKnowledgeDocument.reviewed_at.is_not(None),
                or_(
                    MedicalKnowledgeDocument.effective_from.is_(None),
                    MedicalKnowledgeDocument.effective_from <= func.now(),
                ),
                or_(
                    MedicalKnowledgeDocument.effective_to.is_(None),
                    MedicalKnowledgeDocument.effective_to > func.now(),
                ),
                MedicalKnowledgeDocument.next_review_at > func.now(),
                or_(*matches),
            )
            .order_by(
                rank.desc(),
                MedicalKnowledgeDocument.updated_at.desc(),
                MedicalKnowledgeChunk.sequence.asc(),
            )
            .limit(self.max_results)
        )
        rows = self.session.execute(statement).all()
        results: list[KnowledgeEvidence] = []
        for row in rows:
            doc_token = row.document_id.hex[:10]
            chunk_token = row.chunk_id.hex[:10]
            results.append(KnowledgeEvidence(
                citation_id=f"K-{doc_token}-{chunk_token}",
                document_id=str(row.document_id),
                chunk_id=str(row.chunk_id),
                source_id=str(row.source_id),
                source_title=row.source_title,
                publisher=row.publisher,
                canonical_url=row.canonical_url,
                title=row.title,
                excerpt=row.content[: self.max_excerpt_chars],
                version=row.version,
                jurisdiction=row.jurisdiction,
                evidence_grade=row.evidence_grade,
                reviewed_at=row.reviewed_at.isoformat(),
                next_review_at=row.next_review_at.isoformat(),
            ))
        return results
