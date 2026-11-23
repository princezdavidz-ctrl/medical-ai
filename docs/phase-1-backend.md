# Phase 1 — Backend foundation

## Initial scaffold
- FastAPI application and versioned API prefix.
- PostgreSQL configuration and SQLAlchemy 2 models.
- Organization, hospital, department, staff identity, role, membership, patient, encounter, consent and audit-event data models.
- Hospital-scoped staff authentication context.
- Hospital-filtered patient create/list/read endpoints.
- Argon2 password hashing and signed, expiring JWT access tokens.
- Docker Compose development services for API, PostgreSQL and Redis.
- Liveness endpoint and smoke test.

## Required before production
1. Add Alembic migrations, including PostgreSQL row-level security (RLS) policies for every tenant-owned table. Application-level hospital filters are necessary but not sufficient as the sole isolation boundary.
2. Complete role-permission enforcement, department scopes, MFA enrollment/challenge, account recovery and administrator provisioning.
3. Add immutable audit controls, tamper-evident retention and comprehensive access-event coverage.
4. Add patient identifiers, next-of-kin, allergies, conditions, observations, clinical notes, orders, results and document domains.
5. Add consent evidence, disclosure review, break-glass access and access revocation workflows.
6. Add encryption/key management for highly sensitive fields and secure object-storage integration.
7. Add rate limiting, security headers, request correlation, structured redacted logs and secret rotation.
8. Add readiness checks for database and Redis, backups, restore drills, monitoring and alerting.
9. Add API contract tests, tenant-isolation tests, authorization tests and migration tests.
10. Complete privacy impact assessment, threat model, clinical safety review and legal/regulatory review for each deployment jurisdiction.

## Tenant isolation rules
- Every hospital-owned record carries hospital_id.
- All patient queries are constrained by authenticated hospital context.
- A user's active hospital membership must be verified on every request.
- Cross-hospital record access is not implicit. It will be implemented only through Phase 4 request-based HIE workflows, with purpose limitation, lawful basis/consent, partner verification and audit.
- Ambiguous patient identities must not be auto-merged.

## Clinical safety boundary
This backend is infrastructure, not a validated clinical product. Clinical AI belongs to Phase 2 and must be evidence-grounded, versioned, evaluated and supervised by qualified clinicians. No autonomous diagnosis, prescribing, treatment authorization or emergency triage disposition is permitted.

## Local development
1. Copy .env.example to .env and replace SECRET_KEY with a random secret of at least 32 characters.
2. Run docker compose up --build.
3. Apply migrations once configured: alembic upgrade head.
4. Open localhost port 8000 at /docs in development mode.

Do not use sample Docker credentials or development configuration in production. No production deployment or clinical-use approval is implied.
