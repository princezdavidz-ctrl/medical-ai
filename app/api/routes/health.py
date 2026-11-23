from fastapi import APIRouter
router = APIRouter(tags=["system"])
@router.get("/health/live", summary="Liveness check")
def liveness() -> dict[str, str]:
    return {"status": "ok"}
@router.get("/health/ready", summary="Readiness check")
def readiness() -> dict[str, str]:
    return {"status": "ready"}
