# Phase 5 — Central Test Register

This register collects verification work across all project phases. Development phases do not pause for test execution. Tests are run during the dedicated Phase 5 validation campaign, unless a safety-critical defect requires an immediate development correction.

## Current known CI finding

Source: GitHub Actions Backend CI run 45144650972 on commit 6307a0ec2b9ab969a926eeffd603cbb35a483af5.

- [ ] Re-run Ruff after the lint corrections in the Phase 2B.11 branch are merged.
- [ ] Confirm all lint checks are clean across app, tests and migrations.
- [ ] Run Alembic migrations from an empty PostgreSQL 16 database through head.
- [ ] Confirm the frozen 0001 Phase 1 baseline creates only its historical core tables and all later schemas are created exactly once by explicit revisions.
- [ ] Confirm the least-privileged application DB role can access only its intended tenant rows and cannot access governance tables.
- [ ] Execute the complete pytest suite. The run above stopped at lint, so migrations and pytest were skipped.
- [ ] Resolve any additional failures found after lint is clean.

The five lint findings were:
1. `app/ai/evaluation.py`: import `Mapping` from `collections.abc`.
2. `app/api/routes/ai.py`: remove unused `fastapi.status`.
3. `app/core/config.py`: combine nested production model validation conditions.
4. `app/models/__init__.py`: sort `__all__`.
5. `app/models/knowledge_ingestion.py`: remove unused `sqlalchemy.func`.

These corrections are included in the current development branch; they have not been re-validated.

## Backend and security

- [ ] Authentication, password hashing, JWT expiry, MFA enrollment/challenge/recovery and account recovery.
- [ ] Hospital and department RBAC, staff membership changes, role revocation and session expiry.
- [ ] PostgreSQL RLS tenant isolation for every tenant-owned table and bypass-resistance.
- [ ] Consent, purpose-of-use, emergency access, audit completeness and audit immutability.
- [ ] Encryption at rest/in transit, key rotation, secrets handling, backup restoration and disaster recovery.
- [ ] API rate limits, input validation, upload limits, dependency vulnerabilities and penetration testing.

## Central AI runtime

- [ ] Master execution gate and empty-by-default capability allow-list.
- [ ] Hospital AI emergency pause/resume, race handling, fail-closed behavior and audit attribution.
- [ ] Operations dashboard RBAC, tenant isolation, provider health timeout/failure handling and secret non-disclosure.
- [ ] Offline knowledge freshness calculations, inbound/outbound queue counts, open conflict visibility and dashboard audit events.
- [ ] Hosted/local provider routing, strict no-cross-class fallback and outage behavior.
- [ ] Hosted HTTPS-only endpoint, hostname allow-list, secret handling, model identity and timeout limits.
- [ ] Hosted transfer approval, public classification, identifier checks, and proof that patient context is never sent to hosted.
- [ ] Public/sensitive input classification enforcement for local and hosted providers, plus direct-identifier rejection across all request paths.
- [ ] Offline/degraded provider routing never invokes hosted, even during local runtime failure.
- [ ] Offline and degraded mode: no network dependency, no accidental hosted calls.
- [ ] Model identity/version/digest pinning and artifact attestation.
- [ ] Capability prompt version/digest stability, registry tampering detection and evaluation-to-prompt digest binding.
- [ ] Verify local and hosted providers receive identical capability-specific instructions, workflow contracts, response schemas and explicit tool allow-lists.
- [ ] Verify no unapproved tool can be invoked and tool permissions remain empty until separately approved.
- [ ] Validate response envelope against Pydantic schema and enforce clinical-use=false / clinician-review=true invariants.
- [ ] Verify prompt changes force a new evaluation and stale evaluation approvals cannot authorize changed prompts.
- [ ] Approved-evidence retrieval, source freshness, jurisdiction filtering and tenant scoping.
- [ ] Citation token validation, citation-to-source accuracy and unsupported-answer abstention.
- [ ] Prompt injection in user prompts, retrieved documents and tool outputs.
- [ ] Context limits, timeouts, cancellation, concurrency, resource exhaustion and malicious payloads.
- [ ] Patient-context authorization, consent, purpose limitation and minimum-necessary access.
- [ ] Patient assignment creation/revocation, role allow-list, consent expiry/withdrawal and same-hospital encounter enforcement.
- [ ] Confirm patient context is never queried without a registered local provider and never routed to hosted models.
- [ ] Verify no direct identifiers or unredacted free-text notes enter model context.
- [ ] Clinical capability evaluations by capability, model, prompt, dataset and operating mode.
- [ ] Red-flag sensitivity, false alarms, uncertainty calibration, omissions and subgroup analysis.
- [ ] Governance worker role isolation, approval separation, expiry, revocation and rollback.
- [ ] Signed offline package tampering, unknown keys, expired packages, stale packages and jurisdiction rejection.
- [ ] Offline sync replay, duplicate events, sequence gaps, conflict resolution and reconnect reconciliation.
- [ ] Offline cursor concurrency, atomic apply/cursor commit, first-cursor race retry and RLS isolation.
- [ ] Outbox idempotency, SKIP LOCKED worker concurrency, bounded retries and verified partner acknowledgement.
- [ ] AI session retention, access controls, deletion/export and audit privacy.
- [ ] AES-GCM round trip, ciphertext tampering, AAD binding, key rotation and missing-key behavior.
- [ ] Database RLS owner isolation, composite session/message ownership, cross-hospital access and deletion.
- [ ] Session expiry, scheduled purge, append-turn atomicity and no plaintext prompt/response persistence.
- [ ] Bounded history reconstruction, truncation signaling, prompt-injection isolation and local-only session routing.
- [ ] Usage metering accuracy, tenant quotas, billing aggregation and fail-safe behavior.
- [ ] Concurrent reservation race tests, policy lock behavior, request/token/cost quota boundaries and ambiguous-period policy rejection.
- [ ] Pricing snapshot, currency mismatch, unknown pricing with cost caps, cost rounding and historical rate stability.
- [ ] Provider-reported vs estimated token counts, citation-withheld usage settlement, failed provider charge and expired reservation cleanup.
- [ ] Hospital RLS, finance/admin-only dashboard access, append-only usage events and absence of prompt/PHI data in ledger.

## Clinical safety and interoperability

- [ ] Qualified clinical review of knowledge sources, reference ranges, medication safety rules and escalation rules.
- [ ] Validate that no unreviewed, expired or superseded knowledge is retrievable.
- [ ] Verify clinical decision support never represents itself as a diagnosis or autonomous order.
- [ ] Test emergency escalation, abstention and clinician handoff behavior.
- [ ] FHIR R4 conformance, partner identity matching, consent enforcement and request-based records exchange.
- [ ] Referral acceptance, bed confirmation, transport dispatch, arrival, handover and admission events.
- [ ] Offline facility queueing and reliable later synchronization.

## Hospital modules and integrations

- [ ] Each of the 40 modules: permissions, workflow, data integrity, audit, accessibility and usability.
- [ ] Phase 3.1 patient registration: duplicate candidate detection, human-reviewed identity matching, no automatic merge, consent/lawful basis, next-of-kin access, patient status transitions and audit history.
- [ ] Phase 3.2 OPD: visit registration, queue token uniqueness/collision retry, one active visit per patient, arrival and valid state transitions.
- [ ] OPD role scope: registration-wide queue, triage-nurse department open queue, clinician active encounter assignment, department mismatch and inactive membership denial.
- [ ] OPD tenant isolation: composite hospital/patient/encounter/department FKs, RLS on all OPD tables, cross-hospital UUID substitution and audit attribution.
- [ ] OPD triage: vital-sign numeric bounds, systolic/diastolic consistency, red-flag note requirement, red-flag urgency floor, one triage record per visit and no automated scoring.
- [ ] OPD consultation: assigned clinician only, start/complete state transitions, one signed note per visit, required assessment/plan, no edit/delete path and post-closure access expiry.
- [ ] OPD diagnosis: active consultation requirement, primary diagnosis uniqueness under concurrent writes, certainty states and approved/current knowledge concept validation.
- [ ] OPD disposition: discharged/admission-requested/referred/transfer-requested only after consultation completion; left-without-being-seen only before consultation; no false bed/referral/transfer completion.
- [ ] OPD assignment expiry and cancellation: encounter-scoped assignments, 24-hour review window, expired assignment denial and cancellation before arrival.
- [ ] OPD audit and privacy: audit every transition without duplicating complaint, consultation text, vitals or other clinical narrative into audit metadata.
- [ ] OPD queue ordering and pagination under concurrent arrival/triage updates; timezone-aware local visit date and token uniqueness.
- [ ] Phase 3.3 Nursing: active nursing role, department membership and exact active patient-care assignment required for every read/write; cross-hospital and unassigned encounter denial.
- [ ] Nursing tenant integrity: RLS on all nursing tables, patient/encounter/hospital composite foreign keys, mismatched patient-to-encounter rejection and care-plan review tenant binding.
- [ ] Nursing assessment: allowed assessment types, pain score bounds, fall/pressure-injury risk categories, optional fields and audit metadata privacy.
- [ ] Nursing observations: vital bounds, blood pressure ordering, timestamp handling, at least one measurement, intake/output bounds and append-only history.
- [ ] Nursing notes: note type validation, whitespace normalization, signing identity/time, no update/delete path and correction/addendum governance.
- [ ] Nursing care plans: diagnosis/goals/interventions required, valid lifecycle transitions, assigned nurse only, concurrent review/close behavior and review history.
- [ ] Nursing care-plan reviews: outcome categories, evaluation text, achieved outcome completion, escalated outcome remains active and no cross-tenant review attachment.
- [ ] Nursing encounter record view: assignment expiry, closed encounter read-only behavior, pagination limits and audit on every access.
- [ ] Nursing medication safety boundary: no MAR write or administration event until a verified pharmacy order and medication safety workflow exist.
- [ ] Phase 3.4 Inpatient: ward create/list authorization, department scope, active department validation, ward code uniqueness and tenant isolation.
- [ ] Inpatient bed inventory: bed create/list, bed number uniqueness per ward, valid bed types/statuses, cross-hospital ward substitution and RLS.
- [ ] Admission request: active source encounter assignment, eligible source encounter states, patient status, destination ward scope and duplicate active admission prevention under concurrency.
- [ ] Admission acceptance: only a destination-department clinician, no bed occupancy before assignment, duplicate acceptance denial and accepting-clinician assignment.
- [ ] Bed assignment: accepted admission only, available bed only, same-ward enforcement, ICU/maternity/pediatric compatibility, concurrent double-booking prevention and rollback consistency.
- [ ] Care-team assignment: active admission only, valid same-hospital staff, destination department match, clinician/nurse role allow-list and duplicate assignment handling.
- [ ] Admission cancellation: requested/accepted only, no cancellation after admitted, encounter cancellation, care-assignment expiry and active-admission uniqueness release.
- [ ] Discharge: assigned clinician only, active bed assignment required, discharge summary required, bed release, cleaning state, encounter closure and assignment expiry window.
- [ ] Bed readiness: cleaning-only transition, no active bed assignment, ward manager authorization and bed availability restoration.
- [ ] Inpatient read/list: ward admin visibility, assigned clinician/nurse visibility, department isolation, cross-hospital IDs and audit events.
- [ ] Inpatient lifecycle concurrency: simultaneous admission requests, bed assignment races, cancellation versus acceptance, discharge versus bed allocation and partial unique index enforcement.
- [ ] Inpatient audit/privacy: no clinical reason, discharge narrative or patient identifiers copied into generic audit metadata; all transition actors and resource IDs recorded.
- [ ] Phase 3.5 Emergency: arrival registration, patient active status, duplicate open emergency visit prevention, department scope and arrival-mode validation.
- [ ] Emergency triage: role/department access, initial triage state, revision sequencing under concurrent reassessment, red-flag note requirement, acuity floor and vital/BP validation.
- [ ] Emergency queue: manual acuity ordering, untriaged ordering, nurse open-queue scope, clinician assignment-only visibility, registration/admin visibility and pagination.
- [ ] Emergency clinical detail: registration-only roles denied triage/event/note detail; nursing requires same-department open case; clinicians require active assignment; hospital admins remain audited.
- [ ] Emergency treatment: clinician role only, waiting-to-treatment transition, assigned clinician ownership, assignment creation and competing clinician race.
- [ ] Emergency care events: active assignment requirement, event type, timestamp timezone/future bounds, event chronology and append-only record history.
- [ ] Emergency notes: active assignment requirement, note type, signature actor/time, no update/delete route and privacy-safe audit.
- [ ] Emergency disposition: clinician-only discharge/admission/referral/transfer request after treatment, nurse-only left-without-being-seen before treatment, encounter status mapping and assignment expiry.
- [ ] Emergency-to-inpatient handoff: admission_requested source encounter eligibility, active clinician assignment, duplicate inpatient admission protection and no false bed confirmation.
- [ ] Emergency tenant integrity: RLS on all emergency tables, composite patient/encounter/department foreign keys, cross-hospital ID substitution and audit attribution.
- [ ] Emergency clinical safety: no automated triage scoring, diagnosis, treatment recommendation, medication administration, referral acceptance, ambulance dispatch or clinical AI activation.
- [ ] Phase 3.6 ICU: start only from admitted inpatient with active occupied bed assignment in an active ICU ward and matching inpatient encounter/department.
- [ ] ICU authorization: ICU clinician/nurse role, active hospital membership, ICU department membership and active encounter assignment; no unassigned or cross-hospital access.
- [ ] ICU concurrency: duplicate active ICU stay per admission, concurrent start versus discharge, stepdown versus close, observation writes versus close and partial unique index behavior.
- [ ] ICU observations: vital numeric bounds, blood pressure ordering, pain score, separate GCS component bounds, fluid intake/output/urine output bounds, timezone/future timestamps and observation chronology.
- [ ] ICU care events: event type, assigned staff, event timestamps, chronology and append-only behavior.
- [ ] ICU progress notes: allowed note types, assigned staff, signature actor/time, no edit/delete route and clinical narrative privacy in audit.
- [ ] ICU stepdown: clinician-only request, reason required, status transition, no false transfer completion, no premature bed release and active ICU stay uniqueness retained.
- [ ] ICU closure: inpatient discharge must be completed first, assigned ICU clinician only, closure timestamp/actor and post-closure write denial.
- [ ] ICU detail/list: assigned staff scope, administrator read access, pagination limits, RLS and audit on access.
- [ ] ICU clinical safety: no automated APACHE/SOFA or GCS score calculation, alarms, diagnosis, prognosis, ventilator control, medication dosing, vasopressor orders or AI activation.
- [ ] Phase 3.7 Surgery: theatre room create/list permissions, department scope, active department validation, code uniqueness and tenant isolation.
- [ ] Surgical scheduling: surgeon role/assignment, active encounter, cross-department theatre access, timezone-aware schedule, end-after-start, maximum duration, past-time validation and assignment validity through case/recovery.
- [ ] Lead surgeon assignment: theatre-manager-only assignment to active encounter, valid surgeon membership, cross-department patient assignment, duplicate assignment prevention, 30-day preassignment expiry and extension through scheduled case end plus recovery window.
- [ ] Theatre conflict prevention: overlapping theatre, surgeon or patient schedules; simultaneous case creation; active case overruns; cancellation freeing schedule; completed case no longer blocking.
- [ ] Surgical team assignment: lead surgeon/theatre manager authority, same-hospital staff, cross-department assignment, allowed surgeon/anesthesia/theatre nurse roles, active encounter assignment and duplicate prevention.
- [ ] Surgical detail access: assigned team and hospital administrators can read clinical case detail; theatre managers are department-scoped for operations and cannot read clinical notes without assignment.
- [ ] Surgical safety checklists: sign-in/time-out/sign-out phase state, revision ordering, failed checks retained, latest revision gates, not-applicable site/count handling and concurrent revisions.
- [ ] Anesthesia record: assigned anesthetist role, single record per case, ASA class 1–6, timestamp bounds, assessment required, no medication dose fields and end-time validation.
- [ ] Surgical case start: lead surgeon only, passing latest sign-in and time-out checklists, valid anesthesia record from an active assigned anesthesia provider, correct scheduled state and concurrent start denial.
- [ ] Surgical events: assigned team only, in-progress case only, event type, timestamp after actual start, append-only history and audit privacy.
- [ ] Surgical notes: assigned team only, operative note only during surgery, post-op note only during recovery, signing identity/time and no edit/delete path.
- [ ] Procedure completion: lead surgeon only, passing sign-out checklist, signed operative note, anesthesia end timestamp and transition to recovery.
- [ ] Recovery completion: lead surgeon only, signed post-op/handover note required, completed-state immutability and no implied bed transfer/discharge.
- [ ] Surgical cancellation: scheduled-only cancellation, lead surgeon/theatre manager permissions, reason required, no cancellation after procedure start and schedule conflict release.
- [ ] Surgery tenant/privacy: RLS on all surgery tables, composite patient/encounter/theatre/case FKs, cross-hospital substitution and audit records without clinical narrative.
- [ ] Surgery clinical safety: no automatic procedure selection, ASA scoring, anesthesia dosing, medication orders, blood product orders, device control or clinical AI activation.
- [ ] Phase 3.8 maternity episode: active patient, same-patient in-progress encounter, active maternity department, assigned clinician, gravida/para, LMP/EDD validation, pregnancy number uniqueness and one active episode per patient.
- [ ] Maternity role/access: midwife/obstetrician/maternity nurse/neonatal roles, cross-department team assignment, same-hospital membership, encounter assignment, department boundaries and admin access.
- [ ] Maternity antenatal visits: gestational age bounds, maternal BP consistency, weight/fundal height/FHR bounds, timestamp timezone/future/episode chronology and append-only history.
- [ ] Labor start: assigned midwife/obstetrician, one labor record per episode, pregnancy state transition, start timestamp and concurrent duplicate labor creation.
- [ ] Labor observations: labor stage, cervical dilation, FHR, contraction frequency/duration, maternal vitals, membrane status, timestamp ordering, stage history and no automated partograph/alert scoring.
- [ ] Delivery from labor: allowed labor states, same mother/episode, delivery timestamp, placenta timestamp, blood-loss bounds, one delivery per episode and labor end-state consistency.
- [ ] Planned cesarean without labor: cesarean-only route, matching same-patient/same-encounter surgical case, surgical case active/recovery/completed state and no duplicate delivery.
- [ ] Cesarean linkage integrity: database composite FK to surgical case patient, one delivery per surgical case, no surgical-case link for vaginal/assisted delivery and required link for cesarean.
- [ ] Newborn records: multiple birth orders, sex/outcome values, birth chronology, weight/length/head circumference bounds, manual Apgar 0–10 at 1/5/10 minutes and resuscitation flag.
- [ ] Newborn outcome rules: stillbirth cannot link to a patient; neonatal-death and live-birth record handling; no newborn observation for stillbirth or recorded neonatal death.
- [ ] Newborn patient linking: registration role, same-hospital active patient, DOB match, sex consistency, one patient linked to one newborn record and concurrent duplicate link protection.
- [ ] Newborn observations: assigned neonatal role, live-birth only, observation after birth, temperature/HR/RR/SpO2 bounds, feeding/urine/stool values and append-only history.
- [ ] Maternal postpartum observations: postpartum state only, observation after delivery, BP consistency, maternal vitals/blood-loss bounds, uterine tone/lochia values and meaningful observation requirement.
- [ ] Pregnancy ending: obstetrician-only permission, reason enum, note required, active labor closure, no delivery record and ended pregnancy closed-state constraints.
- [ ] Maternity episode closure: postpartum-only closure, reason required/persisted, labor delivered before closure and denial of later clinical writes.
- [ ] Maternity concurrency and lock ordering: concurrent labor observation/delivery/pregnancy-ending/episode-close requests acquire episode before labor, preserve state invariants, avoid deadlocks and reject duplicate terminal transitions.
- [ ] Maternity timestamp chronology: reject future or out-of-order antenatal, labor, delivery, newborn and postpartum events; verify timezone-aware comparisons and audit timestamps.
- [ ] Maternity privacy/audit: RLS across all maternity tables, cross-hospital UUID substitution, composite mother/delivery/newborn FKs, assignment expiry/revocation and no clinical narrative in audit metadata.
- [ ] Maternity clinical safety: no automatic gestational age/EDD, partograph scoring, fetal interpretation, obstetric risk score, Apgar calculation, medication dosing, resuscitation device control or clinical AI activation.
- [ ] Phase 3.9 pediatric record creation: active patient, valid DOB, age under 18 at record opening, exact 18th-birthday boundary, leap-day DOB, in-progress same-patient encounter, active pediatric department, assigned staff member and concurrent duplicate encounter prevention.
- [ ] Pediatric access control: pediatric role allow-list, active hospital membership, department match, exact patient/encounter care assignment, assignment expiry/revocation and cross-hospital UUID substitution denial.
- [ ] Pediatric growth observations: numeric bounds, database-enforced at-least-one-measurement rule, measured/reported provenance, timezone-aware observation chronology, pre-birth and future timestamp rejection and append-only history.
- [ ] Pediatric developmental screening: instrument name/version, domain/outcome constraints, database-enforced referral outcome consistency, timezone-aware screening timestamps, manual-only entry, no system scoring and immutable screening history.
- [ ] Pediatric immunization history: status/source combinations, database-enforced administered timestamp and caregiver-reported provenance, timezone-aware administered timestamps, pre-birth/future timestamp rejection, batch reference handling and no vaccine order/administration action.
- [ ] Pediatric notes: role/assignment enforcement, required note content, signature timestamp, immutable note history and no edit/delete route.
- [ ] Pediatric record closure: linked encounter must no longer be in progress, assignment required, closure timestamp/audit, database closure-state consistency and denial of all subsequent clinical writes while preserving read access.
- [ ] Pediatric tenant/privacy: RLS on all pediatric tables, composite patient/encounter/department relationships, minimal audit metadata and no guardian access without separately authorized proxy/consent workflows.
- [ ] Pediatric clinical safety: no BMI/growth percentile/z-score or growth-trajectory calculation, no developmental instrument scoring/diagnosis, no vaccine schedule/due-date automation, no medication dosing or AI treatment advice.
- [ ] Patient MRN uniqueness per hospital and composite foreign-key tenant isolation across registration profile, identity documents, next of kin and duplicate cases.
- [ ] Patient create/list/read/update RBAC: registration-role access, active care-assignment-only clinical reads, assignment expiry/revocation, department matching and cross-hospital denial.
- [ ] Patient demographic updates: required-name null rejection, immutable MRN, future DOB rejection, duplicate re-detection and no duplicate-case duplication.
- [ ] Duplicate candidate rules: normalized names, date-of-birth and phone matches; heuristic score interpretation; same-hospital-only matching; concurrent duplicate case creation.
- [ ] Human duplicate review state transitions, reviewer attribution, no automatic merge/delete, and immutable audit evidence.
- [ ] Identity document API accepts only opaque encrypted-vault references, never returns vault references/fingerprints, and enforces pending-to-verified/rejected review with controlled reason codes.
- [ ] Next-of-kin contact permission defaults false; database rejects contact permission without a lawful-basis code and timestamp.
- [ ] Patient status transitions, deceased terminal status, reason/audit attribution and unauthorized role denial.
- [ ] Patient processing lawful-basis and consent workflow: legal-basis review, scoped grant, evidence reference, expiry, withdrawal, emergency exceptions and no implied consent.
- [ ] Consent request lifecycle: pending → granted/rejected → withdrawn, terminal-state enforcement, reviewer/requester attribution and no re-grant after rejection/withdrawal.
- [ ] Declared basis-to-method consistency, purpose included in permitted uses, category/use scope subset checks and timezone-aware expiry.
- [ ] Evidence reference accepts only opaque vault UUIDs; evidence material is never returned or copied into audit metadata.
- [ ] Active authorization service rejects pending, rejected, withdrawn, expired, wrong-purpose, missing-category, wrong-use and malformed-scope records.
- [ ] Consent RLS and composite patient/hospital foreign key prevent cross-hospital access or linkage.
- [ ] Legal counsel review of basis codes, processing purposes, retention, minors/guardian consent and lawful exceptions before production use.
- [ ] Patient registration migration from an empty PostgreSQL database and upgrade from the previous schema head.
- [ ] Phase 2 closeout: deploy migrations through head, verify operator runbook against deployed configuration, validate API contracts against OpenAPI, and verify all external release prerequisites are tracked.
- [ ] Phase 3.10 laboratory catalog: hospital-scoped code uniqueness, active laboratory department, draft-only creation, independent approval, professional-registration presence, creator/approver separation, retirement and no unapproved orderability.
- [ ] Laboratory order creation: active clinician role, in-progress encounter, active patient, exact patient/encounter/department assignment, active approved test definition, laboratory department routing and cross-hospital substitution denial.
- [ ] Laboratory queue and privacy: lab-department-only visibility, clinician assignment-only access, minimum patient identity, status filters, priority ordering, pagination and access audit without result/clinical-indication content.
- [ ] Laboratory specimen lifecycle: accession uniqueness, catalog specimen-type binding, timezone-aware collection timestamp, collection-before-order rejection, collected → received → processing → completed transitions, invalid transition denial and concurrent transition locking.
- [ ] Laboratory specimen rejection/recollection: reason required, rejection timestamps, only collected/received specimens rejectable, one non-rejected specimen per order, multiple rejected specimens permitted, and order returns to ordered state for recollection.
- [ ] Laboratory result entry: exactly one text/numeric value, numeric unit must match catalog, result value bounds, abnormality enum, critical flag/note consistency, one result per specimen and no result before processing.
- [ ] Laboratory result verification: different verifier from entrant, permitted verifier role/department, professional-registration presence, preliminary → final transition, immutable final result, specimen completion and order completion timestamp.
- [ ] Laboratory critical result: manual-only critical classification, required critical note, no automated thresholds/notifications, assigned ordering clinician acknowledgement, duplicate acknowledgement denial and acknowledgement audit.
- [ ] Laboratory cancellation: order owner or lab verifier authorization, reason required, active specimen rejection before cancellation, no cancellation after final completion and concurrent cancel/collection conflict handling.
- [ ] Laboratory tenant/privacy: RLS on catalog/order/specimen/result/acknowledgement tables, composite patient/encounter/department/test-definition FKs, audit metadata minimization and cross-hospital UUID substitution denial.
- [ ] Laboratory clinical safety: no seeded clinical test catalog, no automatic reference-range/abnormality interpretation, no analyzer ingestion, no autonomous critical alert, no diagnosis/treatment recommendation or clinical AI activation.
- [ ] Module-to-API integration and cross-module workflows.
- [ ] Kenya SHA and private insurer claims workflows.
- [ ] Pharmacy, laboratory, radiology, medical devices, messaging and payment integrations.
- [ ] Performance/load, resilience, failover, backup restore and multi-hospital scale.

## Release readiness

- [ ] Privacy impact assessment, threat model, penetration test and remediation.
- [ ] Kenyan legal/regulatory review and applicable health-data compliance.
- [ ] Independent clinical safety case and signed release approvals.
- [ ] Disaster recovery and incident response exercise.
- [ ] Staged deployment, monitoring, rollback and operational sign-off.
- [ ] Explicit approval before any patient data or clinical AI is used in live care.

No item is considered passed until evidence, environment, build SHA, reviewer and execution date are recorded.
