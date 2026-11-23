# Phase 2B.2 — Medical Knowledge Engine foundation

## Scope delivered

This milestone adds the governed data foundation and a read-only lexical retriever for the Central Medical AI. It does not load external clinical content, approve content, expose ingestion/review endpoints, or enable clinical AI capabilities.

## Knowledge registry

- Sources record publisher, source type, canonical reference, license name/reference, jurisdiction, language, active/retired status and ownership scope.
- Sources are either global shared references or hospital-owned protocols. Global sources have no hospital owner; hospital sources belong to exactly one hospital.
- Documents are versioned and carry publication/effective dates, clinical domain, evidence grade, reviewer, review timestamp, next-review date and supersession relationship.
- Document lifecycle: draft, pending_review, approved, rejected, superseded and archived.
- Chunks retain ordered text, keywords and extensible metadata. Each chunk is retrieved through its parent document and source.

## Retrieval rules

The internal SQLAlchemy retriever:
- Returns only active-source documents in approved state.
- Requires a recorded reviewer and review timestamp.
- Excludes content outside its effective window and content whose next review date has passed.
- Searches global knowledge plus the requesting hospital's own protocols only.
- Uses bounded lexical matching and returns source ID, title, version, jurisdiction and excerpt for downstream evidence citations.
- Does not ingest, approve, update, or delete content.

The current retriever is a conservative lexical baseline. Capability-specific taxonomies, synonym expansion, multilingual search, vector retrieval, ranking evaluation and evidence citation persistence are later milestones.

## Security and governance

PostgreSQL row-level security is enabled and forced on all three tables. Every tenant can read global knowledge and only its own hospital-scoped knowledge. Ordinary tenant sessions can write only hospital-owned knowledge. Global-source publication must use a separately governed privileged workflow; no such workflow or endpoint is included here.

There are deliberately no ingestion or approval APIs in this milestone. The platform's complete role/department authorization model and clinical reviewer credential workflow are not yet implemented, so exposing review operations to any authenticated staff member would be unsafe.

## Content and clinical safety

No medical reference text or third-party dataset is bundled. Before loading any source, record its provenance, applicable license/permission, jurisdiction, version and review schedule. Clinical content must be reviewed and approved by an appropriately credentialed clinical owner. Synthetic fixtures may be used for software tests only and must never be represented as clinical guidance.

The central AI remains fail-closed until an approved knowledge source is available and model/provider safety gates are met. This component is not a diagnostic device and is not approved for clinical use.
