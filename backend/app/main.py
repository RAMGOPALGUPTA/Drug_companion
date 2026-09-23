from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analysis import router as analysis_router
from app.api.health import router as health_router

app = FastAPI(title="Drug Companion API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
@app.on_event("startup")
def ensure_dev_schema_compatibility() -> None:
    # The canonical schema creates this column; this guard upgrades an existing
    # local development database created before location persistence was added.
    try:
        from app.db.repository import ensure_schema_compatibility
        ensure_schema_compatibility()
    except Exception:
        # Readiness still reports database state; analysis has a process-memory fallback.
        pass


app.include_router(analysis_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "drug-companion-api", "status": "ok", "version": app.version}
