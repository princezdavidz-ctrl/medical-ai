# Phase 3.1 — Patient Registration & Management

## Implemented registration workflow

### Patient record
- Hospital-scoped medical record number (MRN), enforced unique per hospital.
- Given, middle, preferred and family names.
- Date of birth, administrative sex, nationality and phone number.
- Existing patient status remains active/inactive/deceased for this milestone.
- Patient identity is never globally deduplicated across hospitals.

### Registration profile
- Email and alternate phone.
- Address lines, county, sub-county, country, postal code and preferred language.
- Registration source: walk-in, referral, transfer, portal or import.
- Registration actor and completion timestamp.

### Identity documents
- Supports Kenyan national ID, passport, birth certificate, alien ID, refugee document and other.
- API accepts only an opaque `vault://` reference to an encrypted-vault object, not raw identity numbers or document images.
- Optional identifier fingerprint field is reserved for a future trusted keyed-HMAC adapter; it is not accepted from the API.
- Verification is pending until a records verifier marks it verified/rejected using a controlled reason code; the database requires reviewer identity and timestamp for completed reviews.
- API responses never expose the encrypted vault reference or fingerprint.

### Next of kin
- Full name, relationship, phone and optional email.
- Contact permission is false by default.
- Allowing contact requires a documented basis: patient consent, legal guardian consent or another lawful basis; the database requires the basis and permission timestamp.
- The database enforces that a permission basis and timestamp exist whenever contact is allowed.

### Duplicate review
- Registration compares normalized name plus date of birth and/or exact phone number within the same hospital.
- A deterministic rule score and matching signals create a review case.
- The score is a candidate-ranking heuristic, not a probability or identity conclusion.
- A records verifier can mark a case not duplicate, confirmed duplicate or closed.
- No patient is automatically merged, overwritten or deleted. Completed duplicate decisions require reviewer identity and timestamp. A future merge workflow must require separate authorization, survivor selection, reference migration and immutable audit.

### Patient access
- Registration and medical-records roles may access hospital registration lists.
- Clinical roles may read only patients with a current active patient-care assignment that matches their hospital department when the assignment is department-scoped.
- Patient list/detail access is audited. Clinical staff can read only patients with an active, in-date care assignment; registration roles can access the hospital registration list.\n- Patient status changes use controlled reason codes; deceased is a terminal state in this workflow.
- Duplicate review, identity verification and status changes are restricted to records-verifier/admin roles.

## API routes

Base prefix: `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/patients` | Register patient with optional profile, identity-document references and next-of-kin contacts |
| GET | `/patients` | List patients within registration role scope or active care assignments |
| GET | `/patients/{patient_id}` | Read patient within role/assignment scope |
| GET | `/patients/{patient_id}/registration` | Read registration profile and safe document/contact metadata |
| PATCH | `/patients/{patient_id}` | Update patient demographics and re-run duplicate candidate detection |\n| PATCH | `/patients/{patient_id}/registration` | Update registration contact/address/language profile |
| GET | `/patients/{patient_id}/duplicate-cases` | List possible duplicate candidates for human review |
| PATCH | `/patients/duplicate-cases/{case_id}` | Record a human duplicate review decision; does not merge |
| PATCH | `/patients/{patient_id}/identity-documents/{document_id}/verification` | Verify/reject a pending identity document |
| PATCH | `/patients/{patient_id}/status` | Change patient active/inactive/deceased status |

## Role scope

Registration write and profile access: registration clerk, receptionist, medical records officer, hospital admin/director or system admin.

Identity verification, duplicate-case decisions and patient status changes: medical records officer, hospital admin/director or system admin.

Clinical read access: doctor/physician, medical officer, clinician, nurse, triage/emergency nurse, lab technician, radiologist, pharmacist, midwife, pediatrician, surgeon, anesthetist, dentist or therapist — only with an active patient-care assignment.

Role names must be provisioned consistently by hospital administration. Unknown roles are denied.

## Privacy and limitations

- No raw national ID, passport number or document image is accepted or returned by this API.
- Encrypted vault storage and the keyed HMAC fingerprint service are external integration prerequisites; this milestone accepts opaque references only.
- No automated identity match, cross-hospital patient matching or patient merge is performed.
- Consent records are not inferred from a next-of-kin record. A next-of-kin contact permission is separately recorded and is false by default.
- Full patient identity matching, document vault integration, portal registration, referral intake and HIE matching are later integration work.
- No real patient data is to be used in development.

## Phase 5 verification

All tests for duplicate detection, tenant boundaries, role/assignment access, consent basis, identity verification, status transitions, audit and migration integrity are recorded in `docs/TEST_REGISTER_PHASE_5.md`.
