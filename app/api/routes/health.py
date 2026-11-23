from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["system"])

@router.get("/health/live", summary="Liveness check")
def liveness() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/health/ready", summary="Dependency readiness check")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        client = Redis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1)
        try:
            client.ping()
        finally:
            client.close()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A required backend dependency is unavailable",
        ) from None
    return {"status": "ready", "database": "ready", "redis": "ready"}
