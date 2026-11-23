from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.clinical_taxonomy import ClinicalConcept
from app.models.knowledge import MedicalKnowledgeDocument, MedicalKnowledgeSource


class ClinicalTaxonomyRepository:
    """Read-only concept lookup; only current, clinically reviewed documents qualify."""

    def __init__(self, session: Session, *, max_results: int = 25) -> None:
        self.session = session
        self.max_results = max_results

    def search_concepts(
        self,
        *,
        query: str,
        hospital_id: UUID,
        concept_types: tuple[str, ...] = (),
    ) -> list[ClinicalConcept]:
        normalized = " ".join(query.casefold().split())
        if len(normalized) < 2:
            return []

        statement = (
            select(ClinicalConcept)
            .join(MedicalKnowledgeDocument, ClinicalConcept.document_id == MedicalKnowledgeDocument.id)
            .join(MedicalKnowledgeSource, MedicalKnowledgeDocument.source_id == MedicalKnowledgeSource.id)
            .where(
                MedicalKnowledgeSource.status == "active",
                or_(
                    MedicalKnowledgeSource.scope == "global",
                    and_(
                        MedicalKnowledgeSource.scope == "hospital",
                        MedicalKnowledgeSource.hospital_id == hospital_id,
                    ),
                ),
                MedicalKnowledgeDocument.status == "approved",
                MedicalKnowledgeDocument.reviewed_by_user_id.is_not(None),
                MedicalKnowledgeDocument.reviewed_at.is_not(None),
                MedicalKnowledgeDocument.next_review_at > func.now(),
                or_(MedicalKnowledgeDocument.effective_from.is_(None), MedicalKnowledgeDocument.effective_from <= func.now()),
                or_(MedicalKnowledgeDocument.effective_to.is_(None), MedicalKnowledgeDocument.effective_to > func.now()),
                ClinicalConcept.normalized_term.ilike(f"%{normalized}%"),
            )
            .order_by(ClinicalConcept.preferred_term.asc())
            .limit(self.max_results)
        )
        if concept_types:
            statement = statement.where(ClinicalConcept.concept_type.in_(concept_types))
        return list(self.session.scalars(statement).all())
