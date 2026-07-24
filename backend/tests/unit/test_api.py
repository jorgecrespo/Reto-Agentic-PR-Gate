import time

from fastapi.testclient import TestClient

import pr_gate.main as main_module
from pr_gate.infrastructure.llm import LLMError
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


def test_accepts_analysis_without_acceptance_criteria() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyses",
            json={
                "pull_request_url": "https://github.com/acme/shop/pull/1",
                "model_profile_id": "openai-small",
                "validation_profile_id": "python-demo",
            },
        )
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"


def test_exposes_only_safe_configuration() -> None:
    with TestClient(app) as client:
        models = client.get("/api/v1/config/models").json()
        profiles = client.get("/api/v1/config/validation-profiles").json()
        policy = client.get("/api/v1/config/policy").json()
    assert models["models"]
    assert "api_key_env" not in models["models"][0]
    assert models["models"][0]["id"] == "gemini-small"
    assert {item["id"] for item in models["models"]} == {"gemini-small", "openai-small"}
    assert profiles == {"validation_profiles": [{"id": "python-demo"}]}
    assert policy["version"] == "1.0.1"


def test_missing_analysis_uses_problem_details() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/analyses/missing")
    assert response.status_code == 404
    assert response.json()["detail"] == "Análisis no encontrado."


def test_llm_error_message_is_visible_in_report(monkeypatch) -> None:
    def raise_llm_error(*_: object, **__: object) -> None:
        raise LLMError(
            "GEMINI_API_KEY no está configurada para el perfil seleccionado.", "LLM_CREDENTIALS"
        )

    monkeypatch.setattr(main_module, "build_runtime_dependencies", raise_llm_error)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/analyses",
            json={
                "pull_request_url": "https://github.com/acme/shop/pull/1",
                "model_profile_id": "gemini-small",
                "validation_profile_id": "python-demo",
            },
        )
        analysis_id = created.json()["analysis_id"]
        for _ in range(20):
            analysis = client.get(f"/api/v1/analyses/{analysis_id}").json()
            if analysis["finished_at"] is not None:
                break
            time.sleep(0.05)
    assert analysis["status"] == "INCONCLUSIVE"
    assert analysis["error"] == "GEMINI_API_KEY no está configurada para el perfil seleccionado."
    assert (
        analysis["report"]["errors"][0]["message"]
        == "GEMINI_API_KEY no está configurada para el perfil seleccionado."
    )
