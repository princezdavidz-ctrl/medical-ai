# Backend architecture decisions

## Modular monolith
The initial backend is one FastAPI deployment organized by domain. This reduces operational overhead while keeping clear boundaries for later extraction if scale or regulatory needs require it.

## Data ownership
PostgreSQL is the authoritative store for structured records. Redis is disposable infrastructure for caching and asynchronous work; it is not a clinical record store. Object storage holds encrypted files and imaging objects; PostgreSQL stores their metadata and access controls.

## Multi-hospital tenancy
Each hospital is a tenant boundary. Hospital-owned rows include hospital_id, and request handlers derive that scope from a verified active staff membership. Cross-hospital access is denied by default and will be handled by explicit Phase 4 exchange requests.

Application-level tenant filters in the initial scaffold are not sufficient for production. PostgreSQL RLS policies, tenant-aware transaction context, isolation tests, and privileged-access controls are mandatory before production data is loaded.

## Clinical data integrity
Clinical records should be versioned and amended with authorship, timestamps and reasons. Avoid silent overwrites. Audit records must be protected from ordinary application-user modification and must record access as well as changes.

## AI data boundary
Phase 2 medical knowledge is a separately curated, versioned corpus with provenance, jurisdiction, publication date, review status and source licensing. Patient data must not be silently mixed into the general medical knowledge corpus or used for model training without a separately approved lawful basis and governance process.
