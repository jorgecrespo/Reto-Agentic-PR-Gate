import io
import zipfile

from fastapi.testclient import TestClient

from pr_gate import executor


def test_executor_accepts_archive_and_uses_profile_owned_phase(monkeypatch) -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as source:
        source.writestr("workspace/app.py", "print('ok')\n")
    received: dict[str, str] = {}

    async def fake_execute(path, phase: str, profile_id: str):
        received["phase"] = phase
        received["profile_id"] = profile_id
        assert path.name == "source.zip"
        return {
            "command_name": phase,
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
            "timed_out": False,
            "infrastructure_error": False,
        }

    monkeypatch.setattr(executor, "_execute", fake_execute)

    response = TestClient(executor.app).post(
        "/v1/execute",
        content=archive.getvalue(),
        headers={
            "X-Validation-Phase": "candidate-suite",
            "X-Validation-Profile": "python-demo",
        },
    )

    assert response.status_code == 200
    assert response.json()["exit_code"] == 0
    assert received == {"phase": "candidate-suite", "profile_id": "python-demo"}
