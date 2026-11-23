# Phase 2B.3 — Structured Clinical Knowledge Taxonomy

## Scope

This milestone adds schema and read-only lookup primitives for structured clinical concepts. It does not ship clinical recommendations, treatment pathways, drug doses, diagnostic rules, or populated clinical reference ranges.

## Structured entities

- Clinical concepts: disease, symptom, finding, procedure, laboratory test, imaging test, medication, anatomy, organism and other.
- Typed relationships: symptom/finding associations, differential relationships, investigations, treatments, contraindications, interactions, complications, anatomy, causation and general associations.
- Laboratory reference intervals: units, specimen, age range, sex, pregnancy, population, method, effective dates and interpretation notes.
- Medication safety rules: contraindication, interaction, caution, monitoring, pregnancy/lactation, renal/hepatic, dose-adjustment and severity.
- Emergency escalation rules: trigger concept, urgency, action, target service and context.

Every taxonomy row is linked to a governed medical knowledge document. Its clinical content becomes eligible for read paths only when the parent document is approved, has a named reviewer and review timestamp, has a future review deadline, is within its effective dates, and belongs to an active global source or the requesting hospital.

## Governance and boundaries

- No clinical dataset or reference range is seeded.
- Reference intervals are explicitly contextual, not universal normal ranges. Consumers must match units, specimen, method and relevant population context before interpreting results.
- Medication rules are reference material, not prescribing authority. The schema does not calculate doses or authorize medication orders.
- Emergency escalation definitions are clinician-governed reference material, not autonomous triage decisions.
- No ingestion, editing, approval or publication API is exposed. Reviewer authorization and professional credential verification are still prerequisites.
- Global knowledge is readable by tenant sessions but cannot be written by ordinary tenant sessions. Hospital-owned knowledge remains scoped to its hospital through PostgreSQL RLS.
- The taxonomy lookup is read-only and excludes unapproved, overdue-for-review, expired and foreign-hospital content.

## Next work

A later milestone should add a governed ingestion/import pipeline, clinical terminology adapters (for example SNOMED CT, ICD-10 and LOINC only under the appropriate licensing/usage terms), unit normalization, reference-range validation, medication knowledge source adapters, evidence citation persistence, and evaluation against clinician-reviewed test cases.
