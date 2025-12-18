"""Health check endpoints."""

from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..database import get_db
from ..models.response import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check():
    """Check API and database health."""
    settings = get_settings()
    db = get_db()

    try:
        # Test database connection
        result = await db.execute("MATCH (n) RETURN count(n) as count LIMIT 1")
        node_count = result[0]["count"] if result else 0
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
        node_count = None

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version=settings.app_version,
        database=db_status,
        node_count=node_count,
    )


@router.get("/ready")
async def readiness_check():
    """Kubernetes-style readiness probe."""
    db = get_db()
    try:
        await db.execute("RETURN 1")
        return {"ready": True}
    except Exception:
        raise HTTPException(status_code=503, detail="Database not ready")


@router.get("/live")
async def liveness_check():
    """Kubernetes-style liveness probe."""
    return {"alive": True}
