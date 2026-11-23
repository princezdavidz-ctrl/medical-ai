# Medical AI Hospital System

A secure, multi-hospital platform for clinical care, hospital operations, and controlled health-information exchange.

## Delivery phases

1. **Phase 1 — Backend foundation:** database, identity, tenant isolation, authorization, audit, core clinical APIs.
2. **Phase 2 — Central medical AI:** curated medical knowledge, evidence retrieval, consultation support, safety and clinician review.
3. **Phase 3 — Hospital modules:** clinical, diagnostics, pharmacy, inpatient, emergency, administration and other planned modules.
4. **Phase 4 — API integrations:** module APIs, external services and request-based hospital interoperability.
5. **Phase 5 — Testing:** security, clinical safety, integration, performance and user acceptance.

## Initial architecture

- Python 3.12+ and FastAPI
- PostgreSQL as the source of truth
- SQLAlchemy 2 and Alembic
- Redis for cache and background-work infrastructure
- Docker for reproducible local development
- HL7 FHIR interoperability planned for the integration phase

The backend is designed as a modular monolith initially. Hospital data is tenant-scoped; access is role- and department-scoped and audited.

## Clinical safety

The AI is decision support, not an autonomous clinician. It must communicate uncertainty, cite the approved knowledge sources used, flag emergency warning signs, and require qualified professional review for clinical decisions. It must not independently diagnose, prescribe, order treatment, or authorize disclosure of patient records.

## Development status

Repository initialized. Phase 1 backend foundation is under development. No production deployment or clinical-use approval is implied.
