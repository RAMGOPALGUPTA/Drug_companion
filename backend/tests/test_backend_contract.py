from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_model_contract():
    response = client.get("/api/v1/model")
    assert response.status_code == 200
    body = response.json()
    assert body["artifact"] == "mobilenetv3_small_int8.tflite"
    assert body["model_available"] is True
    assert body["runtime"] == "ai_edge_litert"
    assert body["target_validated"] is False


def test_storage_contract():
    response = client.get("/api/v1/storage")
    assert response.status_code == 200
    body = response.json()
    assert body["backend"] in {"postgresql", "process_memory"}
    assert body["fallback_enabled"] is True


def test_rejects_non_image():
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("payload.txt", b"not an image", "text/plain")},
    )
    assert response.status_code == 415


def test_rejects_empty_image():
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
