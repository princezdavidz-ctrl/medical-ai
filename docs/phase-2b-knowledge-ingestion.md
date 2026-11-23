# Phase 2B.4 — Governed knowledge ingestion

## Scope

This milestone establishes a quarantine-first intake foundation. It does not import clinical reference content, expose an ingestion API, approve sources, or make staged material available to AI retrieval.

## Intake lifecycle

1. An import batch records tenant/global scope, submitter, source identity, license declaration and verification state.
2. A staged document stores source/version metadata, language, jurisdiction, content type, SHA-256 checksum and quarantined payload.
3. Validation checks required metadata, content presence, supported content types, language-tag shape and license verification.
4. Exact-content hashes support duplicate detection. Source identity plus external version are indexed to identify repeated releases. A duplicate is flagged; it is never silently overwritten.
5. Valid material remains staged for an authorized clinical review workflow. Promotion into the approved medical knowledge document/chunk tables is deliberately not implemented in this milestone.

## Terminology governance

- ICD-10 mappings retain jurisdiction and release version. Local national modifications must be treated as distinct releases.
- SNOMED CT and LOINC mappings require an explicit verified license state and license reference before a mapping can be accepted by the validation service. No terminology catalog, codes or descriptions are bundled.
- Terminology mappings are proposed until a separately authorized reviewer verifies them. No API or approval endpoint is exposed.
- Production adapters must load only a licensed package or use an authorized terminology service. License terms, territory, permitted use and redistribution rights must be checked before deployment.

## Laboratory units

The laboratory unit mapping table stores explicit source/canonical unit labels, specimen/method context, provenance and reviewer metadata. Optional factor/offset fields are data fields only: this milestone does not calculate conversions, infer dimensional equivalence, normalize results, or set reference intervals. A mapping requires a named reviewer and timestamp before it can be marked verified.

## Isolation and access

- Hospital import batches and their staged documents are tenant-scoped with PostgreSQL row-level security.
- Global import writes are reserved for a platform-controlled database identity that bypasses tenant RLS; no public route is provided.
- Terminology mappings inherit the scope of their governed clinical concept/document.
- Laboratory unit mappings are a platform-controlled shared catalog, readable to application roles but not writable through tenant sessions.
- The migration adds no API routes and no clinical content seeds.

## Deferred gates

Before any production ingestion or promotion workflow is enabled, implement and review: dedicated platform ingestion identity, role/department authorization, clinician credential verification, source/license verification evidence, malware and file-type scanning, size limits, safe parsing/sanitization, immutable import audit, approval/rejection workflow, supersession transaction rules, reviewer separation-of-duties, and clinical evaluation. Add format-specific parsers only after a source's license and schema are approved.

## Safety

Staged content is untrusted input and must never be passed to model prompts or retrieval. Only approved, current, reviewed MedicalKnowledgeDocument records are eligible for retrieval. No patient records, real medical reference data, medication doses, laboratory intervals, or clinical recommendations are seeded by this change.
