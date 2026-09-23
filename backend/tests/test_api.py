from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_model_endpoint():
    response = client.get("/api/v1/model")
    assert response.status_code == 200
    body = response.json()
    assert body["artifact"] == "mobilenetv3_small_int8.tflite"
    assert body["class_labels"] == ["negative", "positive", "invalid"]


def test_cases_empty_or_list():
    response = client.get("/api/v1/cases")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_summary():
    response = client.get("/api/v1/cases/summary")
    assert response.status_code == 200
    assert "total_cases" in response.json()
