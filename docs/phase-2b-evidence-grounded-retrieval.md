# Phase 2B.6 — Evidence-grounded retrieval and citations

## Retrieval contract

The central knowledge retriever returns evidence only when all of the following are true:
- The source is active and is either global or owned by the requesting hospital.
- The document is approved, has a named reviewer and review timestamp, is inside its effective dates, and has a future review deadline.
- Its content type is permitted for the requested AI capability.
- The passage matches the bounded lexical query and is within the configured result/excerpt limits.

Capability filters currently use a conservative content-type allow-list:
- General medical information and clinical decision support: clinical references, guidelines and policies.
- Laboratory interpretation: lab catalogs, clinical references and guidelines.
- Medication safety: clinical references, guidelines and policies.
- Radiology support: clinical references, guidelines and policies.

These are coarse software filters, not clinical approval of an individual document. Source owners and clinical governance must verify that content is genuinely appropriate to each capability.

## Evidence provenance

Each result now carries:
- Stable citation token tied to the exact document and chunk IDs.
- Source ID, source title, publisher and canonical URL when available.
- Document title and version, jurisdiction and evidence grade.
- Reviewer timestamp and next review deadline.
- Bounded text excerpt.

The model request receives a formatted evidence context with explicit instructions to cite the supplied tokens, avoid invented citations, disclose insufficient/conflicting evidence and avoid converting evidence into autonomous orders.

## Output citation validation

The orchestrator rejects model responses that contain no recognized evidence citation or contain any citation token not present in the retrieved evidence set. This is a citation-integrity check, not a guarantee that every medical statement is factually correct or that the cited passage supports the claim. Clinical evaluation and human review remain mandatory.

## Limits and follow-on work

- Search remains lexical and primarily English-language; synonym expansion, multilingual terminology, hybrid vector search, reranking and capability-specific clinical taxonomies remain future work.
- Content-type allow-lists need review by clinical owners before enabling capabilities.
- No patient context is retrieved by this component.
- No clinical source data is bundled and no AI capability is enabled by this milestone.
- Citation validation does not replace factuality evaluation, subgroup testing, prompt-injection defenses or clinical sign-off.
