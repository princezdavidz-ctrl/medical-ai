import re
from collections.abc import Sequence

from app.ai.contracts import KnowledgeEvidence


_CITATION_PATTERN = re.compile(r"\[(K-[a-f0-9]{10}-[a-f0-9]{10})\]")


class CitationValidationError(ValueError):
    pass


def format_evidence_context(evidence: Sequence[KnowledgeEvidence]) -> str:
    if not evidence:
        raise ValueError("approved_evidence_required")
    sections = [
        "MEDICAL EVIDENCE POLICY:",
        "- Use only the evidence items listed below for source-backed medical claims.",
        "- Cite factual claims with the exact citation token shown, such as [K-...].",
        "- Never invent, alter, or reuse a citation token for a different claim.",
        "- If the evidence is insufficient, conflicting, or outside its jurisdiction, say so clearly.",
        "- Do not treat this evidence as patient-specific diagnosis or an autonomous treatment order.",
        "",
    ]
    for item in evidence:
        sections.extend([
            f"{item.citation_label} {item.title} (version {item.version})",
            f"Source: {item.source_title} — {item.publisher}",
            f"Jurisdiction: {item.jurisdiction}; evidence grade: {item.evidence_grade or 'not specified'}",
            f"Reviewed: {item.reviewed_at}; review due: {item.next_review_at}",
            f"Document ID: {item.document_id}; chunk ID: {item.chunk_id}",
            f"Source URL: {item.canonical_url or 'not provided'}",
            f"Excerpt: {item.excerpt}",
            "",
        ])
    return "\n".join(sections)


def validate_response_citations(
    response_text: str, evidence: Sequence[KnowledgeEvidence]
) -> tuple[str, ...]:
    allowed = {item.citation_id for item in evidence}
    found = _CITATION_PATTERN.findall(response_text)
    if not found:
        raise CitationValidationError("response_contains_no_evidence_citations")
    unknown = tuple(sorted(set(found) - allowed))
    if unknown:
        raise CitationValidationError("response_contains_unknown_citation_ids")
    return tuple(dict.fromkeys(found))
