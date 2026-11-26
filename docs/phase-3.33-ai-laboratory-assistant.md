# Phase 3.33 — AI Laboratory Assistant

## Purpose
Provide a clinician-supervised, read-only interpretation review workflow bound to a specific patient, encounter, verified laboratory result set and exact evidence-grounded AI response.

## Source eligibility and binding
- The case must be created from an active patient-bound clinical AI session.
- The exact assistant message sequence, response digest and `LAB_INTERPRETATION` capability must match.
- Results must be final and independently verified; their specimens and orders must be completed and belong to the bound patient and encounter.
- Consent and care assignment are revalidated at case creation, read and clinician review.
- Duplicate result identifiers are rejected; snapshots are stored in deterministic order.

## Reference interval matching
A reference interval is included only when there is one unambiguous best match for the exact normalized laboratory test concept and result unit. Candidate intervals must also match the specimen, method, age range and administrative-sex context. The interval and its governing document must be effective now; the document must be approved, reviewed, within its review date and backed by an active global or same-hospital source.

Intervals that require pregnancy or population context are withheld because those contexts are not assumed. Missing or conflicting context results in no interval rather than a guessed range. The returned comparison is informational and cannot override the laboratory's verified abnormality or critical flags.

## Evidence provenance
The originating AI response stores citation identifiers and allow-listed citation metadata: source/document IDs, title, publisher, version, jurisdiction, evidence grade, review dates and canonical URL. Matched reference intervals expose their source title, publisher, document version, evidence grade, review dates and canonical URL. These details are immutable snapshots attached to the interpretation case.

## Clinician review
The case owner can record one review decision with private vault references. Review decisions and case creation are audited. The case does not modify source results, acknowledge critical findings, create diagnoses/orders/prescriptions, publish medical records or trigger autonomous clinical action.

## Security
- Hospital-scoped row-level security is enabled and forced.
- Composite foreign keys bind session, patient, encounter, consent and reviewer to the same hospital.
- Source response digest and capability are rechecked on case access.
- Vault reference formats and review decision values are constrained at both API and database layers.

## Phase 4 boundary
No external laboratory system, analyzer, HL7/FHIR interface, or external messaging integration is enabled by this module. Phase 4 will connect approved laboratory interfaces separately.

## Phase 5 verification
All backend security, authorization, context matching, citation provenance, lifecycle, migration and downgrade scenarios are recorded in `docs/TEST_REGISTER_PHASE_5.md`. Tests remain deferred to Phase 5 per project direction.
