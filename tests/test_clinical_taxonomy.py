from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.knowledge.taxonomy import ClinicalTaxonomyRepository
from app.models.core import Hospital, Organization, User
from app.models.knowledge import MedicalKnowledgeDocument, MedicalKnowledgeSource
from app.models.clinical_taxonomy import ClinicalConcept


def test_taxonomy_search_excludes_unapproved_and_other_hospital_content() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        organization = Organization(legal_name="Synthetic taxonomy fixture")
        session.add(organization)
        session.flush()
        hospital = Hospital(
            organization_id=organization.id, name="Fixture Hospital",
            facility_code="TAX-001", ownership_type="private",
        )
        other_hospital = Hospital(
            organization_id=organization.id, name="Other Fixture Hospital",
            facility_code="TAX-002", ownership_type="public",
        )
        reviewer = User(
            email="taxonomy-reviewer@example.test", password_hash="not-a-real-hash",
            full_name="Synthetic Reviewer",
        )
        session.add_all([hospital, other_hospital, reviewer])
        session.flush()

        sources = [
            MedicalKnowledgeSource(
                scope="global", title="Synthetic global", publisher="Fixture",
                source_type="synthetic", jurisdiction="KE", status="active",
            ),
            MedicalKnowledgeSource(
                scope="hospital", hospital_id=hospital.id, title="Synthetic local",
                publisher="Fixture", source_type="synthetic", jurisdiction="KE", status="active",
            ),
            MedicalKnowledgeSource(
                scope="hospital", hospital_id=other_hospital.id, title="Synthetic foreign",
                publisher="Fixture", source_type="synthetic", jurisdiction="KE", status="active",
            ),
        ]
        session.add_all(sources)
        session.flush()
        now = datetime.now(timezone.utc)
        documents = [
            MedicalKnowledgeDocument(
                source_id=sources[0].id, title="Synthetic global concepts", version="test-1",
                status="approved", reviewed_by_user_id=reviewer.id, reviewed_at=now,
                next_review_at=now + timedelta(days=30),
            ),
            MedicalKnowledgeDocument(
                source_id=sources[1].id, title="Synthetic local concepts", version="test-1",
                status="approved", reviewed_by_user_id=reviewer.id, reviewed_at=now,
                next_review_at=now + timedelta(days=30),
            ),
            MedicalKnowledgeDocument(
                source_id=sources[2].id, title="Synthetic foreign concepts", version="test-1",
                status="approved", reviewed_by_user_id=reviewer.id, reviewed_at=now,
                next_review_at=now + timedelta(days=30),
            ),
            MedicalKnowledgeDocument(
                source_id=sources[0].id, title="Unapproved synthetic concepts",
                version="test-1", status="draft",
            ),
        ]
        session.add_all(documents)
        session.flush()
        session.add_all([
            ClinicalConcept(
                document_id=document.id, concept_type="disease",
                preferred_term=f"Synthetic fever concept {index}",
                normalized_term="synthetic fever", language="en",
            )
            for index, document in enumerate(documents)
        ])
        session.commit()

        results = ClinicalTaxonomyRepository(session).search_concepts(
            query="synthetic fever", hospital_id=hospital.id
        )
        assert len(results) == 2
        assert {concept.preferred_term for concept in results} == {
            "Synthetic fever concept 0", "Synthetic fever concept 1"
        }
