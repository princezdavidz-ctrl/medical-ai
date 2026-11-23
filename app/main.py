from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, health, patients
from app.core.config import get_settings
settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="Secure API foundation for a multi-hospital clinical and operations platform.", docs_url="/docs" if settings.environment != "production" else None, redoc_url="/redoc" if settings.environment != "production" else None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Hospital-ID", "Idempotency-Key"])
app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(patients.router, prefix=settings.api_v1_prefix)
@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "running"}
