"""HTTP API for the SIH field-test companion.

The API stores a chain-of-custody record, not the image itself. Images remain on
the device; their SHA-256 digest lets a stored record be checked later.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from typing import Iterator, Literal
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://sih:sih_dev@localhost:5432/sih")
API_PREFIX = "/api/v1"
Classification = Literal["positive", "negative", "inconclusive"]


class CaseIn(BaseModel):
    """A complete, replay-safe field capture record."""

    id: UUID | None = None
    operator_id: str = Field(default="demo-operator", min_length=1, max_length=120)
    classification: Classification
    confidence: float = Field(ge=0, le=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    captured_at: datetime
    model_version: str = Field(min_length=1, max_length=120)
    app_version: str = Field(min_length=1, max_length=120)
    image_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("captured_at")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("image_sha256")
    @classmethod
    def normalize_digest(cls, value: str) -> str:
        return value.lower()


class CaseOut(BaseModel):
    id: UUID
    operator_id: str
    classification: Classification
    confidence: float
    latitude: float | None
    longitude: float | None
    captured_at: datetime
    model_version: str
    app_version: str


class CaseSummary(BaseModel):
    total: int
    positive: int
    negative: int
    inconclusive: int
    average_confidence: float


def canonical(case: CaseIn) -> str:
    """Return a deterministic serialization for the evidence-record digest."""
    document = {
        "id": str(case.id),
        "operator_id": case.operator_id,
        "classification": case.classification,
        "confidence": case.confidence,
        "latitude": case.latitude,
        "longitude": case.longitude,
        "captured_at": case.captured_at.isoformat(),
        "model_version": case.model_version,
        "app_version": case.app_version,
        "image_sha256": case.image_sha256,
    }
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def digest(case: CaseIn) -> str:
    return hashlib.sha256(canonical(case).encode("utf-8")).hexdigest()


@contextmanager
def connection() -> Iterator[psycopg.Connection]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as database:
        yield database


app = FastAPI(
    title="SIH Field Testing API",
    version="1.1.0",
    description="Offline-capable evidence record synchronization for presumptive field tests.",
)

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def unavailable(error: Exception) -> HTTPException:
    logger.warning("Database request failed: %s", error)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database_unavailable")


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with connection() as database:
            database.execute("SELECT 1")
    except psycopg.Error as error:
        raise unavailable(error) from error
    return {"status": "ok", "service": "sih-field-testing-api"}


@app.get(f"{API_PREFIX}/cases", response_model=list[CaseOut])
def list_cases(
    limit: int = Query(default=50, ge=1, le=200),
    classification: Classification | None = None,
) -> list[dict]:
    query = """
        SELECT id, operator_id, classification, confidence, latitude, longitude,
               captured_at, model_version, app_version
        FROM cases
    """
    parameters: tuple[object, ...] = ()
    if classification is not None:
        query += " WHERE classification = %s"
        parameters = (classification,)
    query += " ORDER BY captured_at DESC LIMIT %s"
    parameters += (limit,)
    try:
        with connection() as database:
            return list(database.execute(query, parameters).fetchall())
    except psycopg.Error as error:
        raise unavailable(error) from error


@app.get(f"{API_PREFIX}/cases/summary", response_model=CaseSummary)
def case_summary() -> dict:
    query = """
        SELECT COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE classification = 'positive')::int AS positive,
               COUNT(*) FILTER (WHERE classification = 'negative')::int AS negative,
               COUNT(*) FILTER (WHERE classification = 'inconclusive')::int AS inconclusive,
               COALESCE(AVG(confidence), 0)::double precision AS average_confidence
        FROM cases
    """
    try:
        with connection() as database:
            return database.execute(query).fetchone()
    except psycopg.Error as error:
        raise unavailable(error) from error


@app.post(f"{API_PREFIX}/cases", status_code=status.HTTP_201_CREATED)
def create_case(case: CaseIn) -> dict[str, str]:
    """Create a record or safely accept a replay sent by an offline device."""
    case.id = case.id or uuid4()
    payload_sha256 = digest(case)
    try:
        with connection() as database:
            operator = database.execute("SELECT id FROM operators WHERE id = %s", (case.operator_id,)).fetchone()
            if operator is None:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown_operator")
            inserted = database.execute(
                """
                INSERT INTO cases (
                    id, operator_id, classification, confidence, latitude, longitude,
                    captured_at, model_version, app_version
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                RETURNING id
                """,
                (case.id, case.operator_id, case.classification, case.confidence,
                 case.latitude, case.longitude, case.captured_at, case.model_version,
                 case.app_version),
            ).fetchone()
            if inserted is None:
                existing = database.execute(
                    "SELECT payload_sha256 FROM evidence WHERE case_id = %s", (case.id,)
                ).fetchone()
                if existing is None or existing["payload_sha256"] != payload_sha256:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="case_id_payload_mismatch",
                    )
                return {"id": str(case.id), "payload_sha256": payload_sha256, "status": "already_recorded"}
            database.execute(
                """
                INSERT INTO evidence (case_id, image_sha256, payload_sha256)
                VALUES (%s, %s, %s)
                ON CONFLICT (case_id) DO NOTHING
                """,
                (case.id, case.image_sha256, payload_sha256),
            )
            database.execute(
                """
                INSERT INTO audit_log (case_id, operator_id, action, details)
                VALUES (%s, %s, %s, %s)
                """,
                (case.id, case.operator_id, "case_received", json.dumps({"classification": case.classification})),
            )
    except HTTPException:
        raise
    except psycopg.Error as error:
        raise unavailable(error) from error
    return {"id": str(case.id), "payload_sha256": payload_sha256, "status": "created"}


@app.get(f"{API_PREFIX}/cases/{{case_id}}/verify")
def verify(case_id: UUID) -> dict[str, str | bool]:
    try:
        with connection() as database:
            row = database.execute(
                """
                SELECT c.id, c.operator_id, c.classification, c.confidence, c.latitude,
                       c.longitude, c.captured_at, c.model_version, c.app_version,
                       e.image_sha256, e.payload_sha256
                FROM cases AS c JOIN evidence AS e ON e.case_id = c.id
                WHERE c.id = %s
                """,
                (case_id,),
            ).fetchone()
    except psycopg.Error as error:
        raise unavailable(error) from error
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case_not_found")

    recorded_digest = row.pop("payload_sha256")
    image_sha256 = row["image_sha256"]
    candidate = CaseIn(**row)
    computed_digest = digest(candidate)
    return {
        "case_id": str(case_id),
        "valid": computed_digest == recorded_digest,
        "recorded_payload_sha256": recorded_digest,
        "computed_payload_sha256": computed_digest,
        "image_sha256": image_sha256,
    }
