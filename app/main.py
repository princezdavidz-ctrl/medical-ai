from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.runtime import build_model_gateway
from app.api.routes import ai_laboratory, ai_radiology, diagnostic_support, reports, compliance, quality, notifications, ai, auth, billing, emergency, facilities, health, hr, hospital_admin, icu, inpatient, insurance, inventory, laboratory, mortuary_pathology, patient_portal, medical_records, procurement, maternity, nursing, opd, patients, pediatrics, pharmacy, radiology, staff_portal, staff_scheduling, telemedicine, surgery, transport
from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    gateway = build_model_gateway(settings)
    application.state.ai_gateway = gateway
    try:
        yield
    finally:
        gateway.close()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Secure API foundation for a multi-hospital clinical and operations platform.",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Hospital-ID", "Idempotency-Key"],
)
app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(patients.router, prefix=settings.api_v1_prefix)
app.include_router(opd.router, prefix=settings.api_v1_prefix)
app.include_router(nursing.router, prefix=settings.api_v1_prefix)
app.include_router(inpatient.router, prefix=settings.api_v1_prefix)
app.include_router(emergency.router, prefix=settings.api_v1_prefix)
app.include_router(icu.router, prefix=settings.api_v1_prefix)
app.include_router(surgery.router, prefix=settings.api_v1_prefix)
app.include_router(maternity.router, prefix=settings.api_v1_prefix)
app.include_router(pediatrics.router, prefix=settings.api_v1_prefix)
app.include_router(laboratory.router, prefix=settings.api_v1_prefix)
app.include_router(radiology.router, prefix=settings.api_v1_prefix)
app.include_router(pharmacy.router, prefix=settings.api_v1_prefix)
app.include_router(billing.router, prefix=settings.api_v1_prefix)
app.include_router(insurance.router, prefix=settings.api_v1_prefix)
app.include_router(hr.router, prefix=settings.api_v1_prefix)
app.include_router(procurement.router, prefix=settings.api_v1_prefix)
app.include_router(inventory.router, prefix=settings.api_v1_prefix)
app.include_router(facilities.router, prefix=settings.api_v1_prefix)
app.include_router(transport.router, prefix=settings.api_v1_prefix)
app.include_router(mortuary_pathology.router, prefix=settings.api_v1_prefix)
app.include_router(hospital_admin.router, prefix=settings.api_v1_prefix)
app.include_router(patient_portal.router, prefix=settings.api_v1_prefix)
app.include_router(medical_records.router, prefix=settings.api_v1_prefix)
app.include_router(staff_portal.router, prefix=settings.api_v1_prefix)
app.include_router(staff_scheduling.router, prefix=settings.api_v1_prefix)
app.include_router(telemedicine.router, prefix=settings.api_v1_prefix)
app.include_router(notifications.router, prefix=settings.api_v1_prefix)
app.include_router(quality.router, prefix=settings.api_v1_prefix)
app.include_router(compliance.router, prefix=settings.api_v1_prefix)
app.include_router(reports.router, prefix=settings.api_v1_prefix)
app.include_router(ai.router, prefix=settings.api_v1_prefix)
app.include_router(diagnostic_support.router, prefix=settings.api_v1_prefix)
app.include_router(ai_laboratory.router, prefix=settings.api_v1_prefix)
app.include_router(ai_radiology.router, prefix=settings.api_v1_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}
