from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

import httpx

from pr_gate.infrastructure.runner import classify_command_result, extract_pytest_tests


class RemoteRunner:
    def __init__(self, executor_url: str, profile_id: str) -> None:
        self._executor_url = executor_url.rstrip("/")
        self._profile_id = profile_id

    async def run(self, workspace: str, phase: str) -> dict[str, Any]:
        try:
            archive = self._archive_workspace(Path(workspace))
            async with httpx.AsyncClient(timeout=130) as client:
                response = await client.post(
                    f"{self._executor_url}/v1/execute",
                    content=archive,
                    headers={
                        "X-Validation-Phase": phase,
                        "X-Validation-Profile": self._profile_id,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (OSError, httpx.HTTPError, ValueError) as error:
            return {
                "command_name": phase,
                "exit_code": None,
                "stdout": "",
                "stderr": f"Executor no disponible: {type(error).__name__}",
                "timed_out": False,
                "infrastructure_error": True,
            }
        exit_code = payload.get("exit_code")
        parsed_exit_code = exit_code if isinstance(exit_code, int) else None
        stdout = str(payload.get("stdout", ""))
        stderr = str(payload.get("stderr", ""))
        infrastructure_error = bool(payload.get("infrastructure_error", False))
        tests = extract_pytest_tests(stdout, stderr)
        return {
            "command_name": str(payload.get("command_name", phase)),
            "command": payload.get("command") if isinstance(payload.get("command"), list) else [],
            "exit_code": parsed_exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": bool(payload.get("timed_out", False)),
            "infrastructure_error": infrastructure_error,
            "classification": classify_command_result(
                parsed_exit_code, stdout, stderr, infrastructure_error
            ),
            "executed_tests": list(tests["executed_tests"]),
            "failed_tests": list(tests["failed_tests"]),
        }

    @staticmethod
    def _archive_workspace(workspace: Path) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in workspace.rglob("*"):
                if path.is_file() and path.name != ".pr-gate.patch":
                    archive.write(path, path.relative_to(workspace.parent))
        return output.getvalue()
