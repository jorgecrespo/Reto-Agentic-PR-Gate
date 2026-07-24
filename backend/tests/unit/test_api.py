from fastapi.testclient import TestClient

from pr_gate.main import app


def test_health_endpoints() -> None:
    with TestClient(app) as client:
        live = client.get("/health/live", headers={"X-Correlation-ID": "test-correlation"})
        assert live.json() == {"status": "ok"}
        assert live.headers["X-Correlation-ID"] == "test-correlation"
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
    assert response.headers["content-type"].startswith("application/problem+json")


def test_exposes_only_safe_configuration() -> None:
    with TestClient(app) as client:
        models = client.get("/api/v1/config/models").json()
        profiles = client.get("/api/v1/config/validation-profiles").json()
        policy = client.get("/api/v1/config/policy").json()
    assert models["models"]
    assert "api_key_env" not in models["models"][0]
    assert profiles == {"validation_profiles": [{"id": "python-demo"}]}
    assert policy["version"] == "1.0.1"


def test_missing_analysis_uses_problem_details() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/analyses/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Análisis no encontrado."
