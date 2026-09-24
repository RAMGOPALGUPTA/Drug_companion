from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from io import BytesIO

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
    result = verify_packet_dict(evidence)
    return {
        **result,
        "valid": bool(result.get("chain_valid")) and result.get("source_image_hash_valid") is not False,
        "image_sha256": evidence.get("source_image_sha256"),
        "payload_sha256": evidence.get("chained_hash"),
    }


@router.get("/model")
def model_info() -> dict:
    from app.services.analysis_service import get_model_info
    return get_model_info()


@router.get("/storage")
def storage_info() -> dict:
    from app.services.analysis_service import get_storage_status
    return get_storage_status()


@router.get("/cases/{case_id}/report")
def case_report(case_id: str):
    from app.services.analysis_service import get_case
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    record = get_case(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 52

    def heading(text, size=18):
        nonlocal y
        pdf.setFont("Helvetica-Bold", size)
        pdf.drawString(42, y, text)
        y -= size + 12

    def field(label, value):
        nonlocal y
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(42, y, label.upper())
        pdf.setFont("Helvetica", 10)
        pdf.drawString(155, y, str(value)[:95])
        y -= 17

    pdf.setTitle(f"Drug Companion Case Report - {case_id}")
    heading("Drug Companion", 22)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(42, y, "Field Intelligence / Case Report")
    y -= 28
    heading("Case dossier", 16)

    field("Case ID", record.get("case_id", case_id))
    field("Result", str(record.get("result", "inconclusive")).upper())
    field("Model confidence", f"{float(record.get('confidence', 0) or 0) * 100:.1f}%")
    field("Officer", record.get("officer", "—"))
    field("Location", record.get("location", "Field capture"))
    field("Captured", record.get("time") or record.get("created_at") or "—")
    field("Storage", record.get("storage", "—"))

    y -= 8
    heading("Evidence integrity", 13)
    evidence = record.get("evidence", {}) or {}
    field("Image SHA-256", evidence.get("image_sha256", "—"))
    field("Payload SHA-256", evidence.get("payload_sha256", "—"))
    field("Integrity", evidence.get("integrity", "review"))

    y -= 8
    heading("Model and validation status", 13)
    model = record.get("model", {}) or {}
    field("Model", model.get("name", "MobileNetV3-Small"))
    field("Readiness", model.get("readiness_state", "BOOTSTRAP_READY"))
    field("Target validation", "VALIDATED" if model.get("target_validated") else "NOT VALIDATED")
    field("Forensic status", model.get("forensic_status", "NOT VALIDATED"))

    y -= 8
    heading("Decision trace", 13)
    for label, value in [
        ("Image quality gate", "PASS" if (record.get("quality") or {}).get("passed") else "REVIEW"),
        ("Reference normalization", "COMPLETE" if (record.get("calibration") or {}).get("passed") else "REVIEW"),
        ("ROI extraction", "DETECTED" if record.get("deltae") else "REVIEW"),
        ("Final decision", str(record.get("result", "inconclusive")).upper()),
    ]:
        field(label, value)

    y -= 12
    pdf.setFont("Helvetica", 7)
    pdf.drawString(42, 35, "Drug Companion — AI-assisted field screening prototype. Not a forensic or clinical identification report.")
    pdf.drawRightString(width - 42, 35, f"Case {case_id}")
    pdf.save()
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Drug-Companion-{case_id}.pdf"'},
    )
