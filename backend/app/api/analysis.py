from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analyze")
async def analyze(image: UploadFile = File(...)) -> dict:
    from app.services.analysis_service import analyze_bytes
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload must be an image")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds 12 MB limit")
    try:
        return analyze_bytes(data, image.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis pipeline failed: {exc}") from exc


@router.get("/cases")
def cases() -> list[dict]:
    from app.services.analysis_service import list_cases
    return list_cases()


@router.get("/cases/summary")
def cases_summary() -> dict:
    from app.services.analysis_service import get_summary
    return get_summary()


@router.get("/cases/{case_id}")
def case_detail(case_id: str) -> dict:
    from app.services.analysis_service import get_case
    record = case_detail_lookup(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return record


@router.get("/cases/{case_id}/analysis")
def case_analysis(case_id: str) -> dict:
    from app.services.analysis_service import get_case
    record = case_analysis_lookup(case_id, get_case)
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {k: record[k] for k in ("case_id", "quality", "calibration", "deltae", "ml", "resolved")}


@router.get("/cases/{case_id}/evidence")
def case_evidence(case_id: str) -> dict:
    from app.services.analysis_service import get_evidence
    evidence = get_evidence(case_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return evidence


@router.get("/model")
def model_info() -> dict:
    from app.services.analysis_service import get_model_info
    return get_model_info()


def case_detail_lookup(case_id: str):
    from app.services.analysis_service import get_case
    return get_case(case_id)


def case_analysis_lookup(case_id: str, getter):
    return getter(case_id)
