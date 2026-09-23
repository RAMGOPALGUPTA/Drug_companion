from fastapi import APIRouter, File, Header, HTTPException, UploadFile

router = APIRouter(prefix="/api/v1", tags=["analysis"])
MAX_IMAGE_BYTES = 12 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


@router.post("/analyze")
async def analyze(
    image: UploadFile = File(...),
    x_operator_id: str | None = Header(default=None),
    x_location: str | None = Header(default=None),
) -> dict:
    from app.services.analysis_service import analyze_bytes

    if image.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="Upload must be JPEG, PNG, or WEBP")
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 12 MB limit")
    try:
        return analyze_bytes(
            data, image.filename,
            officer=x_operator_id or "Field Operator",
            location=x_location or "Field capture",
            image_mime=image.content_type,
        )
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
    record = case_detail = None
    record = get_case(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return record


@router.get("/cases/{case_id}/analysis")
def case_analysis(case_id: str) -> dict:
    from app.services.analysis_service import get_case
    record = get_case(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {key: record[key] for key in ("case_id","quality","calibration","deltae","ml","resolved")}


@router.get("/cases/{case_id}/evidence")
def case_evidence(case_id: str) -> dict:
    from app.services.analysis_service import get_evidence
    evidence = get_evidence(case_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return evidence


@router.get("/cases/{case_id}/evidence/verify")
def verify_case_evidence(case_id: str) -> dict:
    from app.services.analysis_service import get_evidence
    from app.evidence.evidence_packet import verify_packet_dict
    evidence = get_evidence(case_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return verify_packet_dict(evidence)


@router.get("/model")
def model_info() -> dict:
    from app.services.analysis_service import get_model_info
    return get_model_info()


@router.get("/storage")
def storage_info() -> dict:
    from app.services.analysis_service import get_storage_status
    return get_storage_status()
