from app.ai.contracts import KnowledgeEvidence
from app.ai.evidence import (
    CitationValidationError,
    format_evidence_context,
    validate_response_citations,
)


def _evidence() -> KnowledgeEvidence:
    return KnowledgeEvidence(
        citation_id="K-0123456789-abcdef0123",
        document_id="01234567-89ab-cdef-0123-456789abcdef",
        chunk_id="abcdef01-2345-6789-abcd-ef0123456789",
        source_id="source-id",
        source_title="Synthetic guideline source",
        publisher="Synthetic publisher",
        canonical_url="https://example.invalid/synthetic",
        title="Synthetic clinical reference",
        excerpt="Synthetic evidence excerpt only.",
        version="fixture-v1",
        jurisdiction="KE",
        evidence_grade="synthetic",
        reviewed_at="2026-01-01T00:00:00+00:00",
        next_review_at="2027-01-01T00:00:00+00:00",
    )


def test_evidence_context_includes_provenance_and_citation_policy():
    context = format_evidence_context([_evidence()])
    assert "[K-0123456789-abcdef0123]" in context
    assert "Synthetic guideline source" in context
    assert "fixture-v1" in context
    assert "Never invent" in context


def test_response_citations_must_be_present_and_known():
    evidence = [_evidence()]
    valid = validate_response_citations(
        "This is a synthetic statement [K-0123456789-abcdef0123].", evidence
    )
    assert valid == ("K-0123456789-abcdef0123",)
    import pytest
    with pytest.raises(CitationValidationError):
        validate_response_citations("Uncited statement.", evidence)
    with pytest.raises(CitationValidationError):
        validate_response_citations("Claim [K-deadbeef00-badbadbad0].", evidence)
