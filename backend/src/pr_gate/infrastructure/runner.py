from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    command_name: str
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    infrastructure_error: bool
    classification: str = "UNKNOWN"


class DockerRunner:
    """Runs only configuration-owned argv values; never model-generated commands."""

    def __init__(self, image: str = "pr-gate-runner:latest", timeout_seconds: int = 120) -> None:
        self._image = image
        self._timeout_seconds = timeout_seconds

    async def run(
        self, workspace: Path, command_name: str, command: tuple[str, ...]
    ) -> CommandResult:
        if not command or any(not value or "\x00" in value for value in command):
            return CommandResult(
                command_name,
                None,
                "",
                "Comando administrado inválido.",
                False,
                True,
                "INFRASTRUCTURE_ERROR",
            )
        if shutil.which("docker") is None:
            return CommandResult(command_name, None, "", "Docker no está disponible.", False, True)
        docker_command = (
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--pids-limit",
            "128",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--user",
            "65534:65534",
            "--workdir",
            "/workspace",
            "--mount",
            f"type=bind,src={workspace.resolve()},dst=/workspace,readonly",
            self._image,
            *command,
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *docker_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout_seconds
            )
        except FileNotFoundError:
            return CommandResult(
                command_name,
                None,
                "",
                "No se pudo iniciar el executor Docker.",
                False,
                True,
                "INFRASTRUCTURE_ERROR",
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            return CommandResult(
                command_name, None, "", "El comando excedió el timeout.", True, False, "TIMEOUT"
            )
        decoded_stdout = stdout.decode()[:8000]
        decoded_stderr = stderr.decode()[:8000]
        infrastructure_error = (
            process.returncode in {125, 126, 127} and "docker" in decoded_stderr.lower()
        )
        return CommandResult(
            command_name,
            process.returncode,
            decoded_stdout,
            decoded_stderr,
            False,
            infrastructure_error,
            classify_command_result(
                process.returncode, decoded_stdout, decoded_stderr, infrastructure_error
            ),
        )


def classify_command_result(
    exit_code: int | None, stdout: str, stderr: str, infrastructure_error: bool = False
) -> str:
    text = f"{stdout}\n{stderr}".lower()
    if infrastructure_error:
        return "INFRASTRUCTURE_ERROR"
    if exit_code == 0:
        return "PASSED"
    if "assertionerror" in text or "failed" in text and "error" not in text:
        return "ASSERTION_FAILURE"
    if "syntaxerror" in text:
        return "SYNTAX_ERROR"
    if "importerror" in text or "modulenotfounderror" in text:
        return "IMPORT_ERROR"
    if "no module named" in text or "not found" in text:
        return "DEPENDENCY_ERROR"
    return "FAILED"
