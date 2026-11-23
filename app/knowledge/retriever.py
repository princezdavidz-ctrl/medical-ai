import re
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability, KnowledgeEvidence
from app.models.knowledge import MedicalKnowledgeChunk, MedicalKnowledgeDocument, MedicalKnowledgeSource


class SQLAlchemyKnowledgeRetriever:
    """Lexical retrieval restricted to approved, current, hospital-visible knowledge."""

    def __init__(self, session: Session, *, max_results: int = 6) -> None:
        self.session = session
        self.max_results = max_results

    def search(self, *, query: str, capability: AICapability, hospital_id: UUID) -> list[KnowledgeEvidence]:
        del capability  # Capability-specific taxonomies are a follow-on milestone.
        terms = list(dict.fromkeys(re.findall(r"[a-zA-Z0-9][a-zA-Z0-9-]{1,}", query.lower())))[:8]
        if not terms:
            return []

        matches = [
            or_(MedicalKnowledgeChunk.content.ilike(f"%{term}%"), MedicalKnowledgeDocument.title.ilike(f"%{term}%"))
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
                MedicalKnowledgeSource.jurisdiction,
                MedicalKnowledgeDocument.title,
                MedicalKnowledgeDocument.version,
                MedicalKnowledgeChunk.content,
            )
            .join(MedicalKnowledgeDocument, MedicalKnowledgeDocument.source_id == MedicalKnowledgeSource.id)
            .join(MedicalKnowledgeChunk, MedicalKnowledgeChunk.document_id == MedicalKnowledgeDocument.id)
            .where(
                MedicalKnowledgeSource.status == "active",
                or_(
                    MedicalKnowledgeSource.scope == "global",
                    and_(MedicalKnowledgeSource.scope == "hospital", MedicalKnowledgeSource.hospital_id == hospital_id),
                ),
                MedicalKnowledgeDocument.status == "approved",
                MedicalKnowledgeDocument.reviewed_by_user_id.is_not(None),
                MedicalKnowledgeDocument.reviewed_at.is_not(None),
                or_(MedicalKnowledgeDocument.effective_from.is_(None), MedicalKnowledgeDocument.effective_from <= func.now()),
                or_(MedicalKnowledgeDocument.effective_to.is_(None), MedicalKnowledgeDocument.effective_to > func.now()),
                MedicalKnowledgeDocument.next_review_at > func.now(),
                or_(*matches),
            )
            .order_by(rank.desc(), MedicalKnowledgeDocument.updated_at.desc())
            .limit(self.max_results)
        )
        rows = self.session.execute(statement).all()
        return [
            KnowledgeEvidence(
                source_id=str(row.source_id),
                title=row.title,
                excerpt=row.content[:1600],
                version=row.version,
                jurisdiction=row.jurisdiction,
            )
            for row in rows
        ]
