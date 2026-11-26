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
- [ ] Phase 3.10 laboratory catalog: hospital-scoped code uniqueness, active laboratory department, draft-only creation, independent approval, professional-registration presence, creator/approver separation, retirement reason/actor/timestamp consistency and no unapproved orderability.
- [ ] Laboratory order creation: active clinician role, in-progress encounter, active patient, exact patient/encounter/department assignment, active approved test definition, laboratory department routing and cross-hospital substitution denial.
- [ ] Laboratory queue and privacy: lab-department-only visibility, clinician assignment-only access, minimum patient identity, open-order default filter, explicit status filters, STAT/urgent priority ordering, deterministic pagination and access audit without result/clinical-indication content.
- [ ] Laboratory specimen lifecycle: accession uniqueness, catalog specimen-type binding, assigned ordering care-team or laboratory collector permissions, phlebotomist collection-only role, result-visibility restriction and processing denial, timezone-aware collection timestamp, collection-before-order rejection, collected → received → processing → completed transitions, invalid transition denial and concurrent transition locking.
- [ ] Laboratory specimen rejection/recollection: reason required, rejection timestamps, collected/received specimens rejectable by lab staff and processing specimens rejectable only by supervisors before result entry, one non-rejected specimen per order, multiple rejected specimens permitted, and order returns to ordered state for recollection.
- [ ] Laboratory result entry: exactly one text/numeric value, numeric unit must be nonblank and match catalog, result value bounds, abnormality enum, critical flag/note and exact critical-abnormality consistency, one result per specimen and no result before processing.
- [ ] Laboratory result verification: different verifier from entrant, permitted verifier role/department, professional-registration presence, preliminary → final transition, immutable final result, specimen completion and order completion timestamp.
- [ ] Laboratory critical result: manual-only critical classification, required critical note, no automated thresholds/notifications, assigned ordering clinician acknowledgement, duplicate acknowledgement denial and acknowledgement audit.
- [ ] Laboratory cancellation: order owner or lab verifier authorization, reason required, active specimen rejection before cancellation, no cancellation after final completion and concurrent cancel/collection conflict handling.
- [ ] Laboratory concurrency and locking: order → specimen → result lock order across collection, receipt, rejection, processing, result verification, acknowledgement and cancellation; no duplicate active specimen/result or deadlock.
- [ ] Laboratory tenant/privacy: RLS on catalog/order/specimen/result/acknowledgement tables, composite patient/encounter/department/test-definition FKs, audit metadata minimization and cross-hospital UUID substitution denial.
- [ ] Laboratory clinical safety: no seeded clinical test catalog, no automatic reference-range/abnormality interpretation, no analyzer ingestion, no autonomous critical alert, no diagnosis/treatment recommendation or clinical AI activation.
- [ ] Phase 3.11 imaging procedure catalog: hospital-scoped code uniqueness, modality/contrast/body-region constraints, active department, draft-only creation, independent approval, professional-registration presence, creator/approver separation, reasoned retirement and no unapproved orderability.
- [ ] Imaging order creation: active clinician role, in-progress encounter, active patient, exact patient/encounter/department assignment, active approved procedure definition, imaging department routing and cross-hospital substitution denial.
- [ ] Radiology queue and privacy: imaging-department-only visibility, clinician assignment-only access, minimum patient identity, open-order default, STAT/urgent priority ordering, deterministic pagination and audit metadata minimization.
- [ ] Imaging scheduling: timezone-aware future appointment, accession uniqueness, one study per order, order/study state synchronization, retired procedure schedule/start denial, duplicate schedule denial and concurrent schedule/cancel locking.
- [ ] Imaging acquisition: scheduled → in_progress → completed transitions, performing-user attribution, ownership checks, timestamps, invalid transition denial and order state consistency.
- [ ] Imaging PACS references: UID requires PACS system reference, opaque reference handling, no DICOM upload/retrieval claim and no PHI embedded in external reference fields.
- [ ] Imaging report entry: completed study required, radiologist/resident author roles, required findings/impression, critical flag/note consistency, one report per study and append-only preliminary report.
- [ ] Imaging report verification: registered verifier role, different verifier from author, preliminary → final transition, immutable final report and order completion timestamp.
- [ ] Imaging critical finding: manual-only critical flag, required note, no automated threshold/notification, assigned ordering clinician acknowledgement, duplicate acknowledgement denial and audit.
- [ ] Imaging cancellation: ordering clinician or radiology supervisor authorization, reason required, scheduled study cancellation, no cancellation after acquisition starts and concurrent start/cancel conflict handling.
- [ ] Imaging tenant/privacy: RLS on procedure/order/study/report/acknowledgement tables, composite patient/encounter/department/procedure FKs, minimum patient identity and cross-hospital UUID substitution denial.
- [ ] Imaging clinical safety: no seeded procedure catalog, no contrast prescribing/dosing, no automated image analysis or interpretation, no autonomous critical escalation and no AI activation outside central AI release gates.
- [ ] Phase 3.12 medication catalog: hospital-scoped code uniqueness, active pharmacy department, nonblank generic/ingredient/strength/form, valid default route, draft-only creation, independent registered pharmacist approval, reasoned retirement and no unapproved orderability.
- [ ] Medication order creation: active clinician role, in-progress encounter, active patient, exact patient/encounter/department assignment, active medication definition, pharmacy routing, dose/frequency text validation, catalog default-route enforcement and cross-hospital substitution denial.
- [ ] Pharmacy queue and privacy: pharmacy-department-only visibility, assigned ordering clinician access, minimum patient identity, open-order default/status filters, deterministic queue ordering and audit metadata minimization.
- [ ] Pharmacist review: nonblank registration, prescriber/reviewer separation, approved/on-hold/rejected state transitions, review note requirement, repeat review from hold, retired-medication denial and immutable review event history.
- [ ] Medication dispensing: pharmacist-only registered role, approved order required, quantity unit match, positive quantity with three-decimal precision and Numeric(12,3) upper bound, cumulative quantity cannot exceed prescription, exact full/partial status transitions, concurrent dispense locking and retired-medication denial, and fail-closed manual resolution when a partially dispensed prescription references a retired definition.
- [ ] Medication cancellation: prescribing clinician or registered pharmacy supervisor authorization, reason required, no cancellation after any dispense, cancelled state consistency and concurrent cancel/dispense conflict handling.
- [ ] Medication history integrity: database append-only triggers prevent update/delete of review events and dispense records; audit metadata excludes dose, frequency, instructions and clinical indication.
- [ ] Medication tenant/privacy: RLS on catalog/order/review/dispense tables, composite patient/encounter/department/medication-definition FKs and cross-hospital UUID substitution denial.
- [ ] Medication clinical safety: no seeded medication catalog/doses, no dose calculation or recommendation, no automated allergy/interaction/contraindication checking, no substitution, no stock deduction, no MAR/administration action and no AI treatment activation.
- [ ] Phase 3.13 billing service catalog: hospital/department scope, code uniqueness, nonnegative price, uppercase three-letter currency, draft-only creation, independent finance approval, reasoned retirement and retired service denial.
- [ ] Invoice creation: billing role/department, encounter and patient linkage, generated invoice-number uniqueness, explicit currency and cross-hospital UUID substitution denial.
- [ ] Invoice line entry: draft invoice only, active same-department service definition, currency match, positive quantity, Numeric(12,3) precision, unit-price snapshot, two-decimal ROUND_HALF_UP line total, Numeric(16,2) line/invoice overflow rejection and database-triggered subtotal aggregation.
- [ ] Invoice immutability: database trigger rejects line update/delete and line insertion after issue; issue requires positive total and a different finance issuer from creator.
- [ ] Invoice lifecycle: draft → issued → partially_paid → paid, void only from draft/issued with zero paid amount, pending payment must be failed before void and reason/actor/timestamp consistency.
- [ ] Payment recording: pending-only creation, supported method enum, currency match, optional external reference uniqueness, payment amount precision and no gateway call.
- [ ] Payment confirmation: separate creator/confirmer, invoice balance locking, concurrent confirmation, overpayment prevention, partial/full status transitions, currency check and immutable confirmed payment.
- [ ] Payment failure: pending → failed only, reason required, failed payment immutable, failed payments do not change invoice balance.
- [ ] Billing concurrency: invoice row locking across line insertion/issue, payment create/confirm/fail and void; no double subtotal, overpayment or pending-payment void race.
- [ ] Billing tenant/privacy: RLS on service catalog/invoice/line/payment tables, composite patient/encounter/department/service FKs, minimum patient identity and audit metadata minimization.
- [ ] Billing financial boundaries: no seeded prices/tax rules, no VAT/levy calculation, no insurance claim creation, no automated clinical charge capture, no refund/reversal/ledger, no gateway integration and no claim of actual external settlement.

- [ ] Phase 3.14 insurer catalog: hospital-scoped code uniqueness, supported insurer type, draft-only creation, independent approval, retirement authorization and reason/actor/timestamp consistency.
- [ ] Patient coverage: patient/insurer tenant linkage, active insurer requirement, member/policy identifiers, date validity, reported-to-verified transition, verifier attribution and verification evidence reference handling.
- [ ] Insurance claim creation: verified same-patient coverage, issued same-patient/same-encounter invoice, currency consistency, claimed amount bounded by invoice total, hospital-scoped claim-number uniqueness and cross-hospital UUID substitution denial.
- [ ] Claim submission: draft-only transition, external claim reference uniqueness, submission actor/time, required partner reference and immutable submission history.
- [ ] Claim adjudication: submitted-only transition, authorized independent reviewer, accepted/partially-approved/rejected amount consistency, approval amount not exceeding claim amount and reasoned decision.
- [ ] Claim payments: adjudicated claim only, payment cannot exceed approved outstanding balance, concurrent payment locking, partial/full settlement transitions and immutable payment event history.
- [ ] Insurance tenant/privacy: RLS on insurer, coverage, claim and claim-event tables; composite hospital/patient/encounter/coverage/invoice foreign keys; audit metadata minimization and role separation.
- [ ] Insurance boundaries: no live SHA/private insurer API, eligibility verification, preauthorization, e-claim submission, adjudication, remittance, benefit-limit calculation or actual payment settlement until Phase 4 partner integration.
\n
- [ ] Phase 3.15 employee directory: one profile per hospital/user, employee-number uniqueness per hospital, active user requirement, department and manager same-hospital linkage, employment type/status/date constraints and cross-hospital ID substitution denial.
- [ ] HR authorization: only HR administrator roles create/update employee records; HR staff can list only their hospital; ordinary users cannot enumerate staff directory; role revocation takes effect immediately.
- [ ] Professional credentials: reported-only initial state, validity-date checks, independent reviewer requirement, reviewer/verification timestamp attribution, decision state transitions and sensitive credential/evidence data minimization in audit logs.
- [ ] Leave self-service: only active employee profiles submit; user can view own requests; HR staff can view hospital queue; non-HR users cannot view colleagues' requests; invalid/reversed date ranges rejected.
- [ ] Leave approval: only HR administrators decide pending requests; requester cannot approve own request; duplicate decisions and post-decision mutation rejected; decision actor/time/reason consistency enforced at database level.
- [ ] HR tenant isolation: RLS for employee profiles, credentials and leave requests; composite hospital-to-department/employee foreign keys; cross-hospital user, department, manager and employee identifiers rejected.
- [ ] HR privacy and scope: no payroll, tax, biometric, shift roster or automated regulator verification data is collected; audit events avoid credential numbers and evidence contents.


- [ ] Phase 3.16 vendor governance: hospital-scoped vendor-code uniqueness, supported vendor types, draft-only creation, independent approval, active-only PO selection and cross-hospital vendor ID substitution denial.
- [ ] Department requisitions: active department membership, same-hospital department linkage, required line items, positive quantities, date validation, currency/estimated-cost validation and unique requisition numbers.
- [ ] Requisition lifecycle: draft-only submission by requester, submitted-only decision, independent procurement approver, decision actor/time/note integrity, duplicate decision rejection and no mutation after submission.
- [ ] Purchase-order creation: approved requisition only, active same-hospital vendor, exactly one PO per requisition, one price for every requisition line, currency consistency, server-calculated line/order totals and nonnegative price limits.
- [ ] Purchase-order issuance: draft-only issue, independent authorized issuer, actor/time state integrity, no unauthorized issue or post-issue editing, unique order number and immutable procurement events.
- [ ] Procurement tenant/security: RLS across vendor/requisition/line/order/event tables; composite tenant foreign keys; department role boundaries; cross-hospital vendor, department, requisition and line identifier substitution denial.
- [ ] Procurement integration boundaries: no stock receipt, stock-on-hand, batch/lot tracking, budget ledger, tax calculation, supplier registry, banking or payment settlement until their planned modules/integrations.

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


- [ ] Phase 3.17 inventory catalog: hospital-scoped item-code uniqueness, supported item types/tracking modes/status, nonnegative reorder threshold, active/inactive handling and cross-hospital identifier denial.
- [ ] Warehouse governance: hospital-scoped warehouse-code uniqueness, active-only goods receipt destination and cross-hospital warehouse substitution denial.
- [ ] Goods receipt creation: issued/partially-received PO only, exact same-PO purchase-order line binding, active inventory item, active warehouse, duplicate line rejection, positive quantity and nonnegative unit cost.
- [ ] Tracking metadata: serial-tracked receipt exactly one unit with serial, lot-tracked receipt batch requirement, rejection of incompatible metadata, duplicate serial prevention and expired-stock rejection.
- [ ] Goods receipt posting: draft-only posting, inventory-manager authorization, row locks, cumulative quantity cannot exceed PO line quantity, prior posted receipts counted, idempotent duplicate-post denial and atomic rollback on any failed line.
- [ ] Stock projection and ledger: one balance per hospital/warehouse/item, transactional on-hand increment, no negative quantity, immutable movement ledger at database level, no draft receipt stock effect and no cross-hospital movement visibility.
- [ ] Purchase-order synchronization: PO remains issued before receipt, becomes partially_received after partial receipt and received only when every PO line is fully received; cancellation and receipt race handling.
- [ ] Asset register: only active equipment/asset catalog items, active warehouse, hospital-unique asset tags and serials, warranty/acquisition date consistency, allowed lifecycle transitions and terminal retired/disposed behavior.
- [ ] Inventory authorization: role matrix for catalog, warehouse, draft receipt, posting, stock views and asset lifecycle; revoked memberships denied; ordinary clinical users denied.
- [ ] Inventory tenant/privacy: RLS on all seven inventory tables, composite hospital foreign keys for warehouse/item/receipt/PO/PO-line relationships and UUID substitution rejection.
- [ ] Inventory boundaries: no issue/reservation/transfer/adjustment/stocktake, no valuation/depreciation, no external ERP/device integration and no implied clinical device certification.


- [ ] Phase 3.18 facility location hierarchy: per-hospital code uniqueness, allowed location types/statuses, same-hospital active parent, self-parent/cycle prevention, cross-hospital parent rejection and location closure with active children/open work orders.
- [ ] Facilities authorization: active hospital membership and facilities role matrix for location management, request creation, approval/rejection/cancellation, assignment, start/completion and event visibility.
- [ ] Maintenance request integrity: unique work-order number per hospital, active location requirement, optional active same-hospital asset reference, category/priority bounds and description validation.
- [ ] Independent work-order decision: requester cannot approve or reject own request; non-manager denied; concurrent approval/rejection produces one valid terminal decision.
- [ ] Technician assignment: only active same-hospital maintenance technician/biomedical engineer or authorized facilities manager; inactive, wrong-role and cross-hospital user rejected; assignment only after approval.
- [ ] Work-order state machine: requested → approved → assigned → in_progress → completed; invalid transitions, repeated starts/completions, reassignment during work and terminal-state mutation denied.
- [ ] Work-order cancellation: only requested/approved/assigned; cancellation clears approval/assignment projection fields while preserving append-only history; in-progress/completed/rejected/cancelled cancellation denied.
- [ ] Work-order completion: assigned technician identity enforced; manager override policy, completion note required, completion actor/time recorded and no edit/delete after completion.
- [ ] Maintenance event ledger: every transition creates event and audit record; event update/delete rejected at DB level; event reads are tenant-scoped and do not expose another hospital's events.
- [ ] Facilities tenant isolation: RLS on all three facilities tables; composite hospital foreign keys for location parent, work-order location/asset and event/work-order; cross-hospital UUID substitution rejected.
- [ ] Facilities concurrency: simultaneous approvals, assignments, start/cancel, completion/cancel, location close versus new work-order creation and duplicate work-order numbers.
- [ ] Facilities safety boundary: no automatic medical-device certification, calibration approval, clinical equipment availability change, preventive maintenance scheduling, vendor dispatch or IoT/BMS action.


- [ ] Phase 3.19 transfer authorization: exact patient consent ID belongs to same hospital/patient, purpose is inter_hospital_transfer, granted/basis present, not withdrawn/expired, and scope contains identity + clinical_summary + transfer_of_care; wrong consent ID, withdrawn consent and expired consent denied.
- [ ] Transfer request integrity: active patient, matching active encounter, different active receiving hospital, interfacility-only type, unique transfer number, origin/destination descriptions and composite tenant/consent foreign keys.
- [ ] Receiving offer privacy: receiving hospital can list/read only minimized offer fields; patient ID, encounter ID, clinical reason, consent ID and patient demographics are not accessible through receiving APIs or RLS; origin hospital can reconcile offer status.
- [ ] Receiving bed acceptance: authorized receiving-hospital role only, offer belongs to current destination, bed reference required, duplicate acceptance denied, acceptance timestamp/actor persisted and append-only event emitted.
- [ ] Receiving rejection: authorized receiving role, reason required, only offered status, cross-hospital offer substitution denied, rejection visible to origin and immutable event/audit recorded.
- [ ] Ambulance fleet: vehicle-code and registration uniqueness per hospital, vehicle type/capacity/status constraints, cross-hospital vehicle denial, maintenance/out-of-service transitions and assigned/active-trip vehicle status lockout.
- [ ] Crew assignment: available origin-hospital vehicle, active same-hospital driver role, optional distinct active crew, wrong-role/inactive/cross-hospital crew rejected, concurrent vehicle double-assignment prevented.
- [ ] Dispatch: receiving bed acceptance required before vehicle assignment; vehicle assignment required before dispatch; duplicate dispatch and invalid status transitions denied.
- [ ] Tracking: assigned driver/crew only, en-route state only, paired latitude/longitude, coordinate bounds, note-only updates allowed, invalid coordinates denied and append-only event timeline.
- [ ] Arrival confirmation: receiving hospital role only, matching offer, bed-accepted state, one arrival confirmation, receiving actor/time persisted and origin event timeline updated without exposing patient records.
- [ ] Fleet release: origin fleet manager only, receiving arrival required, assigned vehicle status reconciled to available, transfer retains historical vehicle/crew references and repeated release denied.
- [ ] Cancellation: origin role only, only pre-dispatch states, assigned vehicle returned to available when applicable, receiving offer cancelled when still pending/accepted and cancellation after dispatch denied.
- [ ] Transport RLS: vehicles origin-hospital-only; transfer records origin-hospital-only; receiving offer visible only to origin and destination hospitals; event timeline visible only to transfer participants; cross-hospital UUID substitution denied.
- [ ] Transport event ledger: all state transitions and tracking events recorded; UPDATE/DELETE denied at DB trigger; actor attribution and audit metadata avoid patient clinical content.
- [ ] Transport concurrency: simultaneous receiving acceptance/rejection, vehicle assignment races, dispatch versus cancel, arrival versus duplicate confirmation, and release versus new assignment.
- [ ] Transport boundary: no actual inpatient bed reservation/occupancy, no automatic clinical fitness/triage decision, no patient record sharing, no live GPS/ETA/dispatch integration until Phase 4.

- [ ] Receiving offer progression: offered → bed_accepted → vehicle_assigned → en_route → arrived; receiving arrival confirmation before dispatch denied, rejected/cancelled offers cannot be assigned, and offer destination must match the transfer's receiving_hospital_id.

- [ ] Ambulance crew worklist: active assigned driver/crew only, origin-hospital scope, active trip statuses only, minimized route details and no patient/encounter IDs or clinical reason exposed.


- [ ] Phase 3.20 mortuary intake: patient/optional encounter same-hospital linkage, unique case/body references, death timestamp timezone/future validation, received actor/time and RLS.
- [ ] Mortuary authorization: allowed authority types, protected vault evidence reference, independent verifier (submitter cannot verify), rejected/revoked authority no longer permits release and cross-case authorization substitution denied.
- [ ] Mortuary custody: received/stored/relocated/release-pending/retained/released transitions, correct from/to locations, append-only movement ledger and concurrent movement serialization.
- [ ] Mortuary legal hold: hold blocks release-pending/release/transfer, manager-only application/lift, mandatory reason/authority reference, actor/time evidence, retained-by-authority state and audit evidence.
- [ ] Mortuary release: release-pending state, active verified authorization, no legal hold, recipient name/identity, manager authorization, personal-effects reconciliation, body released timestamp/actor and repeat release denial.
- [ ] Mortuary property: property inventory, sealed-state consistency, hospital-scoped references, independent release authority, recipient attribution and no release while legal hold is active.
- [ ] Pathology case integrity: patient/encounter tenant linkage, unique case number, allowed case types/statuses, autopsy authority required and forensic legal authority type restrictions.
- [ ] Pathology authority: independent pathology manager/admin verification, vault evidence required, rejected authority cancels case, unverified autopsy/forensic case cannot receive specimens or report.
- [ ] Pathology assignment: active same-hospital pathologist membership, manager-only assignment, assignment changes locked after finalization/closure/cancellation.
- [ ] Specimen accessioning: unique accession number, case/hospital binding, allowed condition, collected/received/processing/processed/archived/rejected transitions, received actor/time and invalid transition denial.
- [ ] Pathology reports: at least one processed/archived specimen, one draft at a time, version increments, report author/assigned pathologist controls, signed actor/time and manager override.
- [ ] Final pathology report immutability: UPDATE/DELETE denied after finalization; new version can be created while case remains open; closed case blocks additional versions.
- [ ] Pathology case lifecycle: opened/specimens_received/in_progress/report_draft/finalized/closed/cancelled transitions, no specimen mutation during reporting/finalized/closed states, audit and append-only pathology event history.
- [ ] Mortuary/pathology RLS: all eight tables hospital-isolated, composite patient/encounter/case foreign keys, cross-hospital UUID substitution denied and no cross-hospital report/authorization visibility.
- [ ] Mortuary/pathology privacy/safety: no automated cause-of-death determination, death certification, pathology diagnosis, AI image interpretation, external coroner/registrar exchange or unsupported legal sufficiency claim.


- [ ] Phase 3.21 administrator authorization: hospital_admin/hospital_owner active membership required; non-admin, revoked and cross-hospital memberships denied.
- [ ] Hospital profile: upsert and read, required legal/display name/address/contact fields, country/currency format, valid timezone, locale, facility type, URL/logo reference validation and synchronization with canonical hospital display name/country.
- [ ] Operational settings: default values, appointment duration bounds 5–240 minutes, advance-booking horizon 0–365 days, boolean flags and hospital tenant scope.
- [ ] Operating hours: exactly seven unique weekdays, Monday=0 through Sunday=6, closed days have no times, open days require valid ordered times, replacement is atomic and cross-hospital rows are inaccessible.
- [ ] Department create/update: hospital-scoped code uniqueness, required name/code, manager must be active same-hospital department manager/head/admin, parent must be active same-hospital department and self-parent denied.
- [ ] Department hierarchy: recursive parent cycle detection for ancestor/descendant changes, cross-hospital parent substitution denied, parent deactivation/child handling and concurrent hierarchy updates.
- [ ] Department deactivation: blocked while active memberships, active wards or scheduled/in-progress encounters remain; historical references preserved after deactivation.
- [ ] Hospital dashboard: aggregate counts match tenant-scoped source rows for patients, departments, beds, admissions, employees, maintenance and transport; no patient-level details returned.
- [ ] Hospital administration events: every profile/settings/hours/department change audited, event history is hospital-scoped and UPDATE/DELETE denied by database trigger.
- [ ] Hospital admin RLS: all four new administration tables isolated by hospital; existing department RLS remains effective; cross-hospital UUID substitution denied.
- [ ] Phase 4 enforcement dependency: appointment booking, self-registration and public-directory settings are connected to their respective workflows before enforcement is claimed; request-based consent-gated record sharing remains immutable.


- [ ] Phase 3.22 patient token: active user/password, active hospital, active verified patient link, hospital claim/header match, MFA-enabled account denied until challenge support, expired/revoked/pending link denied.
- [ ] Patient portal link creation: active same-hospital patient and user, one pending or active patient/user link, allowed nonempty access scopes only, self link cannot carry proxy authority, proxy link requires authority reference and timezone-aware future expiry.
- [ ] Independent identity verification: creator cannot verify own link, approved verification methods by relationship type, protected vault evidence required, proxy guardian/court authority verification and expiry.
- [ ] Patient portal revocation: active/pending link revocation, reason required, actor/time retained, immediate token/request denial, expired links inaccessible.
- [ ] Patient portal scopes: each profile/encounter/lab/medication/invoice/consent endpoint requires matching scope; proxy cannot exceed granted scope; cross-patient UUID substitution denied.
- [ ] Patient portal demographics/encounters: patient tenant binding, allowed fields only, no access without active link and corresponding scope.
- [ ] Patient portal laboratory results: final results only, correct patient through specimen/order joins, critical result withheld until clinician acknowledgement, tenant isolation and result ordering.
- [ ] Patient portal medications: correct patient and hospital, medication definition join, status/history visibility and no cross-patient medication leakage.
- [ ] Patient portal invoices: draft invoices hidden, totals/balance calculation correct, no cross-patient billing visibility.
- [ ] Patient portal consents: correct patient/hospital, consent status/scope fields, no ability for proxy link to silently grant or alter consent.
- [ ] Patient portal access audit: each sensitive read creates immutable event with correct link/user/patient/action/count, event rows are hospital-scoped and UPDATE/DELETE denied.
- [ ] Patient portal RLS: link and access-event tables hospital-isolated; composite link/patient FK integrity; patient record queries tenant filtered; no cross-hospital UUID substitution.
- [ ] Patient portal account boundaries: no implicit user signup, no MRN/DOB-only identity matching, no unsupported MFA bypass, no secure messaging/appointment/payment/record-sharing claims.

- [ ] Patient portal re-linking: one pending/active link per hospital-patient-user, duplicate open link denied, revoked link history retained and new request permitted after revocation.


- [ ] Phase 3.23 clinical profile submission: own active HR employee record, active clinical membership, unique hospital registration number, supported clinical role and timezone-aware future license expiry.
- [ ] Clinical credential verification: admin/medical director/HR role, independent verifier, vault evidence required for approval, rejection reason required, expired license cannot verify, suspension reason required, expired-license resubmission requires re-verification, suspended profile reinstatement requires a second independent administrator and new evidence, and suspended profile denied patient access/assignment.
- [ ] Care-team assignment: authorized assigner, active employee membership, verified clinical profile, unexpired license, same-hospital patient and department, care-role compatibility, no self-assignment and no duplicate active role assignment.
- [ ] Care-team renewal/expiry: expired assignment excluded from access, expired active row closed during renewal, future end time required, ended/revoked state actor/time/reason recorded and no reactivation through status mutation.
- [ ] Care-team access scope: only profile/encounters/lab_results/medications, profile scope mandatory, task types require their specific lab/medication/encounter scope, missing scope denied.
- [ ] Staff patient directory/overview: active employment and verified clinical profile rechecked, active care-team assignment required except clinical administrator access, no cross-patient or cross-hospital UUID substitution.
- [ ] Staff clinical overview: patient profile, encounter history, finalized laboratory results including critical results for authorized clinicians, medication history, scope-specific filtering and access event logging.
- [ ] Work queue creation: assigned staff has active hospital membership and employee record, patient-linked task requires assignee care-team assignment, encounter belongs to same patient/hospital, department is active and matches employee department.
- [ ] Work queue transitions: only assignee or clinical administrator can update, open to in-progress/completed/cancelled, completion actor/time, terminal completed/cancelled tasks cannot be reopened, no task delete endpoint.
- [ ] Staff portal dashboard: open task and active assigned-patient counts are scoped to current staff/hospital; no patient-level data in aggregate response.
- [ ] Staff portal events: credential, care-team, task and patient overview events recorded; event table hospital RLS and UPDATE/DELETE denied by append-only trigger.
- [ ] Staff portal tenant security: all four tables hospital RLS, composite patient/encounter/department/employee relationships, active membership checks and cross-hospital access denial.
- [ ] Phase 4 integration: existing clinical APIs enforce verified care-team assignments before universal care-team authorization is claimed; existing note/order/prescription workflows remain authoritative.

- [ ] Staff portal suspension cascade: suspending a verified clinical profile atomically revokes all active patient care-team assignments with actor, timestamp and reason; reinstatement does not reactivate old assignments.
- [ ] Patient-linked staff task read/update: task list and task status mutation require a current active care-team assignment and task-specific scope; expired, future-start, revoked or suspended-profile assignments block access.
- [ ] Staff worklist timing: assigned patient lists, care-team views and dashboard counts exclude future-start and expired assignments.
- [ ] Clinical admin patient privacy: hospital/HR/medical administrators may govern credential profiles but cannot browse arbitrary patient charts or patient worklists without verified active clinical assignment.

## Phase 3.24 — Staff Management & Scheduling

- [ ] Shift template CRUD: only roster managers create/update; template codes unique per hospital; active department and department manager scope enforced; inactive templates cannot receive assignments.
- [ ] Shift assignment authorization: assigned employee belongs to the same hospital, has active employment, active membership and active user account; department/template consistency enforced; cross-hospital IDs denied.
- [ ] Shift time validation: timezone-aware start/end, positive duration no longer than 24 hours, overnight shifts supported, invalid/equal timestamps rejected.
- [ ] Shift overlap prevention: overlapping scheduled/confirmed shifts rejected for the same employee; adjacent shifts allowed; completed/cancelled shifts do not block; concurrent create/update/swap operations serialize on employee row and cannot double-book.
- [ ] Leave conflict: approved leave blocks shift assignment/update; leave approval is rejected when an overlapping scheduled/confirmed shift exists; concurrent leave approval and shift assignment cannot bypass the employee lock.
- [ ] Department roster scope: department heads/nurse managers see and manage only their department; hospital/HR roster managers have authorized hospital-wide scope; explicit out-of-department IDs denied.
- [ ] Staff schedule visibility: employee sees only own shifts and own swap requests/responses; roster managers see only permitted department/hospital rosters; no cross-hospital records.
- [ ] Shift update lifecycle: terminal shifts cannot be changed; cancellation requires a reason; attendance prevents shift time reassignment/cancellation; all changes produce audit and immutable schedule events.
- [ ] Shift swap workflow: only assigned staff request; target must be active employee with active membership; target acceptance does not change assignment until independent manager approval; requester cancellation allowed only before final decision; rejected/declined/cancelled swaps are terminal.
- [ ] Shift swap concurrency: only one pending/accepted swap per shift; duplicate concurrent requests conflict safely; manager approval rechecks target employment, department, leave and overlapping shifts under lock.
- [ ] Attendance check-in: only assigned active employee; only within two hours before shift start through shift end; one attendance record per shift; duplicate check-in denied.
- [ ] Attendance check-out: only the assigned employee with an open attendance record; check-out strictly follows check-in; submitted attendance requires independent manager decision.
- [ ] Attendance review: department-scoped manager; rejection requires a reason; approved past shift closes as completed; rejected attendance can be resubmitted only with timezone-aware valid timestamps inside the scheduled shift window.
- [ ] Scheduling dashboard: staff receive own upcoming shifts/pending swap responses; managers receive scoped upcoming shifts, accepted swaps and attendance review counts; aggregate-only response contains no staff/patient-sensitive data.
- [ ] Event ledger: schedule events are hospital RLS protected and append-only; all template, assignment, swap and attendance transitions record actor, timestamp, resource and metadata.
- [ ] Migration: 0041 follows 0040; all five tables, indexes, constraints, RLS policies and immutable-event trigger create successfully; downgrade removes only Module 24 objects and leaves HR employee schema intact.
- [ ] HR integration: leave approval checks overlapping scheduled shifts; scheduling checks approved leave; employee deactivation blocks future shift actions and check-in; role changes and membership revocation are enforced.

## Phase 3.25 — Medical Records & Health Information

- [ ] Record document registration: records officer only; same-hospital patient and optional encounter; vault reference format and SHA-256 checksum validated; no raw file bytes or direct identifiers accepted.
- [ ] Document version chain: first version has no predecessor; later version requires a verified predecessor for the same patient/source module/source record and exactly next version number; rejected versions do not block corrected re-registration; cross-patient/cross-hospital predecessor denied.
- [ ] Independent document verification: creator cannot verify/reject own document; rejection requires reason; pending to verified/rejected lifecycle enforced; superseded predecessor and verified replacement update atomically.
- [ ] Document immutability: no document delete endpoint; database trigger rejects delete and content mutation after registration; verified documents can only transition to superseded; event ledger rejects UPDATE/DELETE.
- [ ] Clinical document reads: require active employee, active hospital membership, active user, verified clinical profile, current patient care-team assignment and record-type-specific scope; expired/future/revoked assignments and expired licenses denied.
- [ ] Records officer boundaries: only active employees with medical_records_officer/health_information_manager/medical_records_manager roles and active hospital membership may register/review documents, approve release requests or fulfil amendments; hospital admins/directors cannot browse unrestricted patient documents.
- [ ] Document index minimum necessary: clinician listing returns only verified or superseded historical documents whose category maps to an active assignment scope; HIM queue may see pending/rejected documents; type/source/title/date filters do not bypass scope; cross-patient UUID substitution denied.
- [ ] Release authorization: request must reference the exact same-hospital patient consent, purpose record_sharing, granted state, non-expired/non-withdrawn basis, requested categories and record_sharing permitted use; service check and exact consent ID must agree.
- [ ] Release purpose scope: record-sharing consent must include both record_sharing and the actual use (care coordination/referral/patient portal/insurance claim/other); missing category or use denied; expired, withdrawn, rejected or unrelated consent denied.
- [ ] Release workflow: independent reviewer, requester cannot approve, rejection requires reason, consent rechecked at approval and release, release completion requires a different actor from reviewer and vault reference.
- [ ] Release requester controls: treating-provider requests require active scoped care-team access; external requester types may be registered only by HIM with a vault evidence reference; patient/proxy self-service remains denied until verified portal identity workflow is connected; requester can cancel only pending request.
- [ ] Amendment workflow: only scoped care-team staff or HIM can request; document must be verified and belong to same patient; amendment type requires matching scope; independent reviewer and rejection reason; fulfilment requires a different actor and vault addendum reference; original document remains unchanged.
- [ ] Amendment cancellation/listing: requester may cancel only own pending request; non-HIM staff see only own requests; HIM queues remain hospital-scoped.
- [ ] Record audit: document registration/review, document and release/amendment queue reads, release request/decision/release and amendment request/decision/fulfilment produce minimal audit metadata and patient-scoped immutable event history.
- [ ] Tenant security: all four tables enforce hospital RLS; composite patient/encounter/consent/document relationships prevent cross-hospital or mismatched-patient links; no cross-tenant UUID substitution.
- [ ] Migration: 0042 follows 0041; all four tables, indexes, constraints, RLS policies and immutable triggers create successfully; downgrade removes only Module 25 objects.
- [ ] Phase 4 integrations: clinical modules publish document metadata to the record index; encrypted vault adapter verifies object existence/checksum and streams authorized documents; patient/proxy identity and secure self-service export workflows are connected.

## Phase 3.26 — Telemedicine & Remote Care

- [ ] Scheduler authorization: telemedicine_coordinator/appointment_scheduler active employee roles and authorized hospital administrators can schedule; department heads/nurse managers are limited to their active department; revoked memberships and inactive users denied.
- [ ] Provider qualification: same-hospital active membership, active employee, active account, verified clinical profile, supported provider role and unexpired license required; suspended/rejected/expired credentials denied.
- [ ] Provider roster coverage: a scheduled/confirmed staff shift must cover the full telemedicine session in the correct department; cancelled, completed, too-short or cross-department shifts do not qualify.
- [ ] Telemedicine consent: exact same-hospital consent ID must be granted, purpose telemedicine, lawful basis declared, clinical_records category and telemedicine permitted use; expiry, withdrawal, wrong patient, wrong purpose or scope mismatch denied.
- [ ] Scheduling time validation: timezone-aware future start within 365 days, end after start, maximum two hours; patient and provider cannot have overlapping scheduled/patient-ready/in-progress sessions.
- [ ] Scheduling concurrency: concurrent sessions for the same patient or provider serialize using patient/employee row locks; no duplicate overlapping session can be created.
- [ ] Department boundaries: department head/nurse manager cannot create, list, view, mark ready, cancel or mark no-show for sessions outside their department; hospital-level scheduler scope remains tenant-bound.
- [ ] Patient readiness: readiness only within 15 minutes before start through 15 minutes after end; exact consent rechecked; encrypted location and emergency-contact references required; identity, privacy and emergency-plan acknowledgements all required.
- [ ] Session start: only assigned provider; patient-ready state; valid start window; consent rechecked; active roster coverage and active verified care-team assignment with encounters scope required; encounter created exactly once.
- [ ] Clinical note authorship: only assigned active provider can create signed notes for an in-progress session; DB composite FK binds author to assigned provider; note text minimum/maximum enforced; notes immutable.
- [ ] Note visibility: only assigned provider or active verified care-team members with encounters scope can read notes; schedulers and hospital administrators cannot read clinical note content.
- [ ] Session completion: requires at least one signed consultation or assessment note and active encounter; session and encounter close atomically with actor/time; duplicate completion and completion without note denied.
- [ ] Consent withdrawal after start: prevents new session start but does not block required note documentation or encounter closure for a consultation already in progress.
- [ ] Cancellation/no-show: cancellation only before start with reason; no-show only for scheduled session after scheduled end; terminal sessions cannot be restarted or modified.
- [ ] Event and audit controls: session lifecycle events append-only; notes append-only; session/note/list reads and state transitions create minimal audit records without note text, raw location or emergency contact.
- [ ] Tenant security: RLS on sessions, notes and events; composite patient/encounter/consent/provider links reject cross-hospital or mismatched-patient IDs.
- [ ] Migration: 0043 follows 0042; three tables, constraints, indexes, RLS and immutable triggers create/downgrade without affecting earlier modules.
- [ ] Phase 4 integrations: connect live video/audio provider, meeting link issuance, secure vault verification, patient-side booking/readiness, notifications, medical-record document indexing, prescribing, referrals and billing.


## Phase 3.27 — Communication & Notifications

- [ ] Notification preference authorization: users can read/update only their own preferences; administrators cannot silently override patient channel consent or opt-outs.
- [ ] Recipient resolution: same-hospital membership, active account, role/department audience scope and patient relationship are rechecked at enqueue and dispatch; cross-hospital recipients denied.
- [ ] Consent and purpose: patient-facing messages require a valid channel consent and declared purpose; withdrawn, expired, denied or mismatched consent blocks dispatch.
- [ ] Minimum necessary: templates reject direct identifiers and clinical narrative by default; sensitive content requires an explicitly approved template classification and authorized channel policy.
- [ ] Template governance: only authorized communications administrators publish templates; versions are immutable, placeholders are allow-listed and rendered output is bounded.
- [ ] Queue integrity: idempotency keys prevent duplicate logical notifications; concurrent enqueue attempts create one intent; tenant ownership is enforced by composite keys and RLS.
- [ ] Delivery lifecycle: queued, processing, delivered, retryable failure, terminal failure and cancelled transitions are valid and serialized; provider acknowledgement is required before delivered state.
- [ ] Retry safety: bounded exponential retry, maximum attempts, retry-after handling, dead-letter visibility and no retry after consent withdrawal or recipient deactivation.
- [ ] Quiet hours and timezone: local quiet-hour windows, daylight-saving/timezone boundaries and emergency bypass policy are enforced; no emergency bypass exists unless separately authorized.
- [ ] Provider boundary: Phase 3 records provider-neutral delivery attempts only; no real SMS/email/push network call or credential use occurs before Phase 4.
- [ ] Audit/privacy: enqueue, preference changes, template publication, dispatch attempts and delivery state changes are audited without message body, OTP, credentials or clinical content; event history is append-only.
- [ ] Tenant security: all notification tables enforce hospital RLS; composite recipient/template/intent/event relationships prevent cross-hospital UUID substitution.
- [ ] Access control: staff can inspect only authorized departmental or assigned notification queues; patient users see only their own notification history.
- [ ] Migration: 0044 follows 0043; constraints, indexes, RLS and immutable event triggers create/downgrade without affecting earlier modules.
- [ ] Phase 4 integrations: verified patient contact points, SMS/email/push gateways, in-app delivery, appointment/telemedicine event publishers, localization and delivery webhooks.

- [ ] Queue worker concurrency: parallel workers claim distinct rows using skip-locked semantics; stale processing claims are recovered without exceeding attempt limits.
- [ ] Provider idempotency: adapters use the stable intent ID as provider idempotency key so stale-claim recovery cannot create duplicate external sends.
- [ ] Dispatch revalidation: recipient active state, same-hospital membership or portal link, channel preference and unexpired purpose/channel-matched consent are rechecked immediately before dispatch.
- [ ] Quiet-hour scheduling: timezone-aware quiet windows defer dispatch and handle windows crossing midnight; invalid timezone configuration safely delays rather than bypasses quiet hours.
- [ ] Acknowledgement semantics: intent remains non-delivered until provider acknowledgement; retryable failures use bounded exponential backoff; exhausted attempts become terminal failure.

- [ ] Department notice publisher authorization: communications administrators may target any active department; department and nurse managers are restricted to their own active department.
- [ ] Department recipient resolution: only active same-hospital memberships and active users are included; role filters are normalized and cannot expand tenant scope.
- [ ] Department notice idempotency: repeat requests do not create duplicate intents for any recipient, including concurrent submissions.
- [ ] Department opt-outs: recipients with disabled channel preferences are skipped; in-app default behavior is explicit and external channels require opt-in.
- [ ] Notification dashboard: aggregate counts are hospital-scoped, expose no message body or direct patient identifiers, and are restricted to authorized communications administrators.

- [ ] Template locale validation: accept supported language/region format and reject malformed locale tags.
- [ ] Template version uniqueness: same code/version may exist for different locales, but duplicate versions within one locale are rejected.
- [ ] Locale resolution: recipient locale translation is preferred only when published and channel-compatible; fallback order is English then selected base template.
- [ ] Placeholder parity: localized templates render only with the supplied allow-listed variables; missing or extra placeholders fail safely or fall back without leaking raw template syntax.
- [ ] Department localization: each recipient receives the correct locale variant independently while retaining a stable recipient-specific idempotency key.
- [ ] Migration 0045: existing templates migrate to English; upgrade/downgrade preserves data and downgrade refuses unsafe localized-data loss.
- [ ] Quiet-hour database constraints: invalid hour/minute values are rejected by PostgreSQL check constraints.

- [ ] Notification content authorization: inbox title/body is visible only to the recipient and authorized communications administrators; cross-user and cross-hospital reads are denied.
- [ ] Read-state ownership: staff can mark only their own notifications read; patient portal users can mark only their own in-app notifications read.
- [ ] Read-state idempotency: repeated mark-read requests preserve the original read timestamp and do not create duplicate audit events.
- [ ] Dashboard counters: total and unread counts are scoped to the authenticated staff or patient portal identity and hospital.
- [ ] Migration 0046: read timestamp is nullable, backfills existing notifications as unread, and downgrade removes only the read-state column.


## Phase 3.28 — Quality Assurance & Patient Safety

- [ ] Incident creation: active hospital staff can report an incident; department, patient and encounter references must belong to the same hospital and patient.
- [ ] Confidential reporter: reporter identity is hidden from ordinary staff and department managers when confidentiality is enabled; safety officers have authorized access; reporters can access their own report.
- [ ] Incident visibility: ordinary staff see only their own reports; department/nurse managers see only their own department; safety officers see hospital-wide incidents.
- [ ] Triage: only safety officers and designated administrators can classify severity/harm; invalid or out-of-order transitions are rejected.
- [ ] Investigation assignment: only active same-hospital members can be assigned; one investigation per incident; assignment and re-assignment are audited.
- [ ] Investigation independence: assigned investigator can submit findings; a different authorized safety reviewer must approve/reject.
- [ ] CAPA ownership: CAPA owners must be active hospital members; owners can submit evidence only for their own actions.
- [ ] CAPA effectiveness: an authorized reviewer distinct from the owner must document effectiveness before completion.
- [ ] Incident closure: closure requires an approved investigation and no outstanding CAPA actions.
- [ ] Audit integrity: incident events are append-only; audit metadata excludes incident narratives and confidential reporter identity.
- [ ] Tenant isolation: RLS and composite foreign keys block cross-hospital patient, encounter, department, investigator and CAPA-owner references.
- [ ] Dashboard privacy: status/severity aggregates are hospital-wide for safety roles and department-scoped for department/nurse managers.
- [ ] Migration 0047: creates all four quality tables, RLS policies, indexes and immutable event trigger; downgrade removes only Phase 3.28 objects.

- [ ] Safety round creation: safety roles can create hospital or department rounds; department/nurse managers can create only for their own department.
- [ ] Round lead authorization: only the assigned lead or safety officer can start, add findings and complete a round.
- [ ] Finding ownership: findings are assigned only to active same-hospital members; only owner or safety officer can resolve with a documented note.
- [ ] Round completion gate: round cannot complete while any finding remains open or in progress.
- [ ] Indicator governance: only authorized safety roles create and activate versioned indicator definitions; active definitions are not silently overwritten.
- [ ] Measurement integrity: numerator is nonnegative, denominator positive, period timezone-aware and non-overlapping duplicates rejected; value calculation matches unit.
- [ ] Measurement provenance: source and source version are mandatory and retained with each measurement.
- [ ] Tenant isolation: RLS and composite keys prevent cross-hospital round leads, finding owners/resolvers, indicator definitions and measurement references.
- [ ] Department dashboard: department managers receive only their department's incident aggregates; indicator values remain hospital-scoped and contain no patient identifiers.
- [ ] Migration 0048: all four tables, indexes, RLS policies and composite references upgrade/downgrade cleanly.


## Phase 3.29 — Compliance & Security Management

- [ ] Policy governance: only authorized compliance roles create/publish policies; publisher must differ from author; published versions are immutable.
- [ ] Policy acknowledgements: only active same-hospital members acknowledge effective published policies; duplicate acknowledgement is idempotent; acknowledgement history is append-only.
- [ ] Confidential security incident: ordinary staff see only reports they filed or are assigned; reporter identity remains hidden from assignees unless they are the reporter or authorized security officer.
- [ ] Security incident triage: only compliance/security roles classify severity and breach assessment; invalid state transitions are rejected.
- [ ] Security incident assignment: only active same-hospital members can be assigned; cross-hospital assignment is rejected.
- [ ] Security incident lifecycle: containment precedes resolution; breach assessment must be completed before resolution/closure; event history is append-only.
- [ ] Risk scoring: inherent and residual scores equal likelihood × impact; values outside 1–5 are rejected by schema and database.
- [ ] Risk ownership/review: owners are active same-hospital members; independent compliance reviewer must differ from owner.
- [ ] Dashboard privacy: compliance dashboard aggregates only hospital-scoped counts and exposes no security incident narrative or reporter identity.
- [ ] Evidence privacy: policy documents use vault references only; no public URLs or credentials are stored.
- [ ] Migration 0049: RLS, composite membership references, immutable policy/acknowledgement/event triggers and downgrade behavior are verified.

- [ ] Compliance control governance: only compliance roles create/activate versioned controls; control owner must be an active same-hospital member.
- [ ] Control assessment: active controls only; assessor submits evidence/findings; an independent reviewer must finalize the assessment.
- [ ] Assessment evidence: vault reference format enforced; next review date must follow assessment date.
- [ ] Access review snapshot: campaign includes only active same-hospital memberships and active users, with role/department snapshot.
- [ ] Access review reviewer independence: reviewer cannot be the subject; approval must be performed by a different compliance officer from both reviewer and subject.
- [ ] Access review completion: campaign cannot complete until all items have approved decisions and justifications.
- [ ] Access review non-automation: keep/change/revoke are recorded recommendations only; no membership/role change occurs as a side effect.
- [ ] Access review idempotency and concurrency: duplicate campaign/item decisions cannot create inconsistent duplicate items or bypass independent approval.
- [ ] Tenant isolation: RLS and composite membership references prevent cross-hospital control owners, assessors, campaign subjects, reviewers and approvers.
- [ ] Migration 0050: four tables, RLS, constraints and indexes upgrade/downgrade cleanly.

- [ ] Retention policy governance: policy code/version uniqueness, domain/duration validation, and independent approver distinct from author.
- [ ] Retention eligibility: disposition cannot be requested before resource creation date plus active policy retention duration.
- [ ] Legal hold scope: only valid vault references are accepted; holds are hospital-scoped, auditable and released only with reason.
- [ ] Legal hold precedence: active, unexpired hold blocks disposition creation and is rechecked during review; a hold created after request still blocks approval.
- [ ] Disposition review: requester cannot approve own request; reviewer must be authorized; decision and review note are retained.
- [ ] No destructive side effects: approving a delete/archive request records approval only and does not delete, move or mutate source data in Phase 3.
- [ ] Expiry behavior: expired legal holds no longer block disposition; explicit release and automatic expiry remain distinguishable.
- [ ] Migration 0051: retention policy, legal hold and disposition tables have RLS and same-hospital issuer/approver/reviewer references.


## Phase 3.30 — Reports & Hospital Analytics

- [ ] Report definition: only approved report keys and matching data domains; reject raw SQL, query/table/join execution fields.
- [ ] Report publication: publisher differs from author; published definition is immutable and new versions are required for changes.
- [ ] Role authorization: finance, compliance, quality and clinical reports require the corresponding role; no cross-domain access through caller-supplied role lists.
- [ ] Department scope: department/nurse managers cannot request another department's metrics; department scope is derived from active membership.
- [ ] Metric correctness: aggregate calculations match source modules and date filters use timezone-aware boundaries.
- [ ] Currency integrity: billing summaries group by currency and never add unlike currencies.
- [ ] Small-cell privacy: counts below five and associated billing totals are suppressed; suppression is consistent across report types.
- [ ] Provenance: report run records definition version, calculation version, filters, source modules and expiry.
- [ ] Export privacy: only run owner or authorized hospital administrator can request export; exports remain queued until Phase 4 and never expose public URLs.
- [ ] Tenant isolation: RLS on definitions, runs and exports; cross-hospital definition/run references are rejected.
- [ ] Migration 0052: report catalog, run and export tables upgrade/downgrade cleanly; published-definition immutability trigger works.


## Phase 3.31 — AI Medical Assistant

- [ ] Clinical session creation: require active clinical role, active patient, in-progress encounter, current patient-care assignment and active purpose-bound consent.
- [ ] Session binding: a clinical AI session is bound to one patient/encounter/owner/hospital; switching patient or encounter in the same session is denied.
- [ ] Reauthorization: every AI request and clinician review revalidates the same consent and assignment; revoked/expired/changed authorization blocks further use.
- [ ] Local-only patient data: patient-context requests require approved local provider; hosted transfer is never attempted.
- [ ] Structured clinical response: prompt v2 includes required sections and distinguishes chart facts, user statements, inference, missing data and evidence limitations.
- [ ] Citation grounding: only approved current medical evidence citations are accepted; invalid or missing citations withhold output.
- [ ] Clinician review binding: review references an actual assistant message sequence and matching SHA-256 digest; tampered or stale digests are rejected.
- [ ] Review independence/ownership: only the session owner with current clinical authorization can record review; duplicate review of the same assistant response is rejected.
- [ ] Medical record boundary: review decision does not itself write a note or trigger orders/prescriptions; any note reference must be a private vault reference.
- [ ] Session privacy: conversation content remains encrypted at rest; review table stores digest/decision metadata, not plaintext response.
- [ ] Audit: session creation and review decisions are audited without prompt text, response content or direct identifiers.
- [ ] Offline/degraded behavior: no silent hosted fallback; runtime unavailability yields explicit safe failure and no patient data transfer.
- [ ] Migration 0053: patient-bound session and review tables enforce RLS and composite patient/encounter/consent/session ownership.

- [ ] Clinical response structure gate: clinical decision support output missing any required section is withheld and usage outcome is recorded as withheld.
- [ ] Clinical response digest: SHA-256 digest matches the exact encrypted assistant message and cannot be replayed against another sequence/session.

- [ ] Idempotency collision: reuse a key with a different recipient/patient/consent/purpose/template code returns HTTP 409; localized versions sharing the same template code remain equivalent.
- [ ] Patient portal expiry: an expired link cannot authorize enqueue or dispatch; active non-expired links remain eligible.
- [ ] Staff event history: only the authenticated recipient can read events for a staff notification; another user's intent returns 404.
- [ ] Patient event history: only the authenticated portal recipient can read events for their own in-app notification; staff or another patient's intent is not exposed.

- [ ] Compliance dashboard acknowledgement denominator: expected acknowledgements equal effective published policy versions multiplied by active same-hospital users; completed counts include only active users and active memberships.
- [ ] Compliance dashboard privacy: aggregate counts only; no incident summary, reporter identity, risk description, vault reference or personal access-review details.
- [ ] Compliance dashboard incident/risk states: unresolved incident and open-risk totals exclude only their terminal states and remain hospital-scoped.
- [ ] Control review metrics: pending-review assessments and overdue next-review dates are counted separately; null next-review dates are not treated as overdue.
- [ ] Access review metrics: open and overdue campaigns are counted separately; pending-review and awaiting-approval items remain distinct.
- [ ] Retention metrics: only active unexpired legal holds count; expired/released holds are excluded; pending disposition requests are counted without triggering destructive actions.
- [ ] Compliance dashboard authorization: only designated compliance/security roles can access aggregate governance metrics.
