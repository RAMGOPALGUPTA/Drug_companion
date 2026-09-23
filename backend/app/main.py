from fastapi import FastAPI
from app.api.health import router as health_router

app = FastAPI(title="Drug Companion API", version="0.1.0")
app.include_router(health_router)

@app.get("/")
def root() -> dict[str, str]:
    return {"service": "drug-companion-api", "status": "ok"}
