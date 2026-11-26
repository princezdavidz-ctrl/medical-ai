# Phase 3.34 — AI Radiology Assistant

## Objective
Offer clinicians a governed, read-only assistant for reviewing finalized radiology reports and associated study metadata. It is clinical decision support only and does not replace a radiologist or treating clinician.

## Eligible source data
- Same-hospital imaging order in a completed state.
- Completed imaging study linked to the order and the same patient/encounter.
- Final, verified, non-superseded report version.
- Active patient-bound clinical AI session using the dedicated radiology interpretation capability.
- Active care assignment and valid purpose-matched patient consent.

## Immutable case binding
Each case records the hospital, patient, encounter, order, study, report identifier and version, source report digest, assistant response sequence/digest, consent and assignment. The report is copied into a read-only snapshot. Any change to the source report or version makes the case stale and blocks review as current evidence.

## Clinical and privacy boundaries
- All interpretation is advisory and requires review by an authorized clinician.
- The assistant cannot amend or sign a radiology report, acknowledge critical findings, create diagnoses/orders/referrals/prescriptions or initiate treatment.
- Generic audit events contain no report text, patient identifiers, image data, prompts or generated interpretation.
- Patient and clinical record access is re-authorized on every read and review.
- Tenant boundaries are enforced by hospital RLS and composite foreign keys.

## Phase 3 exclusions
No raw DICOM/image upload, image blobs, PACS URLs, DICOMweb, PACS/RIS integration, image-model inference, external report publication or external provider credentials. These require separately approved Phase 4 integrations.

## Clinician review
Review decisions are immutable and auditable, with reviewer identity, timestamp and private vault references for any retained note. Review cannot change source report state.

## Phase 5 verification
Authorization, report eligibility, source digest/version binding, stale report handling, consent, RLS, immutable review history, migration and downgrade scenarios are listed in `docs/TEST_REGISTER_PHASE_5.md`. Backend tests remain deferred to Phase 5.
