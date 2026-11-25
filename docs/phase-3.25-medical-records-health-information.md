# Phase 3.25 — Medical Records & Health Information

## Purpose and ownership

Create the hospital's health-information management layer: a searchable, governed index of record documents, controlled version history, release-of-information workflow and non-destructive amendment/addendum workflow.

This module does not replace source clinical records. OPD, Nursing, Inpatient, Emergency, ICU, Surgery, Maternity, Pediatrics, Laboratory, Radiology, Pharmacy, Billing and Insurance remain authoritative for their own clinical/operational records. Phase 4 adapters will publish their approved document metadata into this index.

## Capabilities

1. **Longitudinal document index** — hospital-scoped patient and encounter-linked document metadata, source module/record identifiers, document type/date, MIME type, SHA-256 checksum, version and opaque encrypted-vault reference.
2. **Independent document review** — records officers register documents; a different authorized records officer verifies or rejects each pending document. Rejection requires a reason.
3. **Immutable version history** — a replacement document must point to a verified prior version for the same patient and source record, and increment its version. Verification supersedes the old version atomically. Documents cannot be deleted or content-edited after registration.
4. **Purpose-specific release of information** — requests reference one exact, active patient authorization for record_sharing, the requested categories and the actual permitted use. A separate reviewer approves/rejects; a different records officer completes release with an opaque vault package reference. Consent is rechecked at approval and release.
5. **Record amendment requests** — scoped clinicians or records officers can request a correction. Independent review is required; approved corrections are fulfilled as a separate vault addendum, never by overwriting the original clinical record.
6. **Audit and event history** — patient-sensitive reads and workflow transitions are audited with minimal metadata; the patient record event ledger is hospital-scoped and append-only.

## Authorization

- Records management actions are limited to active employees with medical_records_officer, health_information_manager or medical_records_manager roles and active hospital membership.
- Hospital administrators/directors do not receive unrestricted chart/document access through this module.
- Clinical readers must have active hospital membership, active employee profile, active user account, independently verified clinical profile, unexpired license, active care-team assignment and the required record-type scope.
- Document list results are filtered per document type; a broad encounter scope cannot expose lab or medication documents.
- Release requests from treating providers require the same active scoped care-team access. External requester types must be registered by a records officer with an encrypted-vault evidence reference. Patient/proxy self-service is blocked until the portal identity and representative-verification workflow is connected.

## API

Base prefix: /api/v1/medical-records

| Method | Path | Purpose |
|---|---|---|
| POST | /documents | Register document metadata and vault reference |
| GET | /patients/{patient_id}/documents | Search/list the patient's authorized document index with type, source, title and date filters |
| GET | /documents/{document_id} | Read one authorized document metadata record |
| POST | /documents/{document_id}/decision | Independently verify or reject a document |
| POST | /release-requests | Create a consent-scoped release request |
| GET | /release-requests | List own requests or records-office queue |
| POST | /release-requests/{request_id}/cancel | Cancel own pending request |
| POST | /release-requests/{request_id}/decision | Approve/reject with independent review |
| POST | /release-requests/{request_id}/complete | Record completed release package reference |
| POST | /amendment-requests | Request a non-destructive correction/addendum |
| GET | /amendment-requests | List own requests or records-office queue |
| POST | /amendment-requests/{request_id}/cancel | Cancel own pending amendment |
| POST | /amendment-requests/{request_id}/decision | Approve/reject amendment request |
| POST | /amendment-requests/{request_id}/fulfil | Attach the separately stored amendment/addendum |

## Consent integration

The existing purpose-specific consent model now supports the explicit record_sharing purpose and permitted use. Release authorization checks the exact supplied consent record, granted state, lawful-basis declaration, expiry/withdrawal state, requested data categories and both record_sharing and the actual release purpose. The reusable patient-authorization service is also called; any missing or malformed scope fails closed.

The consent system records a declared basis and scope; it does not determine legal validity. Hospital legal/privacy governance must approve the applicable basis and purpose before production use.

## Storage and integration boundaries

- No raw file bytes, patient identifiers or document narrative are stored in the document metadata tables. Only opaque vault:// references and SHA-256 checksums are retained.
- The vault provider, object existence/checksum verification, malware scanning, encryption/key management, secure streaming and export packaging are not implemented in this module; they are Phase 4 integrations. Patient/proxy self-service export and portal identity verification are also deferred to Phase 4.
- No direct patient/proxy document upload or export is exposed until portal identity and representative authority are verified.
- Existing department modules are not rewritten to duplicate their records. Their document publication into this index is a Phase 4 integration.
- Retention schedules, legal holds, destruction approvals, national HIE/FHIR exchange and jurisdiction-specific disclosure automation remain later governance/integration work.

## Migration and verification

Migration: 0042_patient_records, after 0041_staff_scheduling. Four hospital-scoped tables enforce RLS. Document versions and event history have database immutability controls.

Backend tests were not run during development, per project direction. Migration, consent, authorization, immutability, versioning, release and amendment scenarios are registered in docs/TEST_REGISTER_PHASE_5.md.
