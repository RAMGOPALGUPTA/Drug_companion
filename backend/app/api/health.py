from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> dict:
    from app.services.analysis_service import get_model_info, get_storage_status

    model = get_model_info()
    storage = get_storage_status()
    return {
        "status": "ready" if model["model_available"] else "degraded",
        "model_available": model["model_available"],
        "database_available": storage["database_available"],
        "storage_backend": storage["backend"],
        "demo_only": not model["target_validated"],
    }
