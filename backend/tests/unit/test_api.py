from fastapi.testclient import TestClient

from pr_gate.main import app


def test_health_endpoints() -> None:
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ok"}


def test_rejects_invalid_pull_request_url() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyses",
            json={
                "pull_request_url": "bad",
                "model_profile_id": "openai-small",
                "validation_profile_id": "python-demo",
            },
        )
    assert response.status_code == 422
