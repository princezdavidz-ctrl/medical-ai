from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.contracts import AICapability
from app.db.base import Base
from app.knowledge.retriever import SQLAlchemyKnowledgeRetriever
from app.models.core import Hospital, Organization, User
from app.models.knowledge import MedicalKnowledgeChunk, MedicalKnowledgeDocument, MedicalKnowledgeSource


def test_retriever_returns_only_approved_visible_knowledge() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        organization = Organization(legal_name="Fixture Organization")
        session.add(organization)
        session.flush()
        hospital = Hospital(
            organization_id=organization.id, name="Fixture Hospital",
            facility_code="FIXTURE-001", ownership_type="private",
        )
        other_hospital = Hospital(
            organization_id=organization.id, name="Other Fixture Hospital",
            facility_code="FIXTURE-002", ownership_type="public",
        )
        reviewer = User(
            email="reviewer@example.test", password_hash="not-a-real-hash",
            full_name="Fixture Reviewer",
        )
        session.add_all([hospital, other_hospital, reviewer])
        session.flush()

        global_source = MedicalKnowledgeSource(
            scope="global", title="Synthetic source", publisher="Test fixture",
            source_type="synthetic", jurisdiction="KE", status="active",
        )
        local_source = MedicalKnowledgeSource(
            scope="hospital", hospital_id=hospital.id, title="Local protocol",
            publisher="Test fixture", source_type="synthetic", jurisdiction="KE",
            status="active",
        )
        foreign_source = MedicalKnowledgeSource(
            scope="hospital", hospital_id=other_hospital.id, title="Other protocol",
            publisher="Test fixture", source_type="synthetic", jurisdiction="KE",
            status="active",
        )
        session.add_all([global_source, local_source, foreign_source])
        session.flush()

        docs = [
            MedicalKnowledgeDocument(
                source_id=global_source.id, title="Synthetic fever reference",
                version="test-1", status="approved", reviewed_by_user_id=reviewer.id,
                reviewed_at=datetime.now(timezone.utc), next_review_at=datetime.now(timezone.utc) + timedelta(days=90),
            ),
            MedicalKnowledgeDocument(
                source_id=local_source.id, title="Local fever pathway",
                version="test-1", status="approved", reviewed_by_user_id=reviewer.id,
                reviewed_at=datetime.now(timezone.utc), next_review_at=datetime.now(timezone.utc) + timedelta(days=90),
            ),
            MedicalKnowledgeDocument(
                source_id=foreign_source.id, title="Foreign fever pathway",
                version="test-1", status="approved", reviewed_by_user_id=reviewer.id,
                reviewed_at=datetime.now(timezone.utc), next_review_at=datetime.now(timezone.utc) + timedelta(days=90),
            ),
            MedicalKnowledgeDocument(
                source_id=global_source.id, title="Draft fever notes",
                version="test-3", status="draft",
            ),
            MedicalKnowledgeDocument(
                source_id=global_source.id, title="Synthetic fever lab catalog",
                version="test-2", content_type="lab_catalog", status="approved",
                reviewed_by_user_id=reviewer.id, reviewed_at=datetime.now(timezone.utc),
                next_review_at=datetime.now(timezone.utc) + timedelta(days=90),
            ),
        ]
        session.add_all(docs)
        session.flush()
        session.add_all([
            MedicalKnowledgeChunk(
                document_id=doc.id, sequence=0,
                content=f"Synthetic fever content {index}.",
            )
            for index, doc in enumerate(docs)
        ])
        session.commit()

        results = SQLAlchemyKnowledgeRetriever(session).search(
            query="fever", capability=AICapability.MEDICAL_INFORMATION, hospital_id=hospital.id
        )
        assert {item.title for item in results} == {
            "Synthetic fever reference", "Local fever pathway"
        }
        assert all(item.version == "test-1" for item in results)
        assert all(item.citation_id.startswith("K-") for item in results)
        assert all(item.document_id and item.chunk_id and item.source_title for item in results)
        assert all(item.reviewed_at and item.next_review_at for item in results)

        lab_results = SQLAlchemyKnowledgeRetriever(session).search(
            query="fever", capability=AICapability.LAB_INTERPRETATION, hospital_id=hospital.id
        )
        assert "Synthetic fever lab catalog" in {item.title for item in lab_results}
