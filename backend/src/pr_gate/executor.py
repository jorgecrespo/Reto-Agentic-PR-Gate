from __future__ import annotations

import asyncio
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Header, HTTPException, Request

MAX_ARCHIVE_BYTES = 100_000_000
RUNNER_IMAGE = "pr-gate-runner:latest"


def _profiles() -> dict[str, dict[str, object]]:
    with Path("/app/config/validation-profiles.yaml").open() as profile_file:
        payload = yaml.safe_load(profile_file)
    profiles = payload.get("validation_profiles", []) if isinstance(payload, dict) else []
    return {
        str(profile["id"]): profile
        for profile in profiles
        if isinstance(profile, dict) and isinstance(profile.get("id"), str)
    }


def _command(profile: dict[str, object], phase: str) -> tuple[str, ...]:
    command_key = (
        "regression_test_command"
        if phase in {"baseline-regression", "candidate-regression"}
        else "test_command"
        if phase in {"pr-suite", "candidate-suite"}
        else "lint_command"
        if phase in {"pr-lint", "candidate-lint"}
        else None
    )
    command = profile.get(command_key) if command_key else None
    if not isinstance(command, list) or not all(
        isinstance(value, str) and value for value in command
    ):
        raise HTTPException(400, "Fase o perfil de validación inválido.")
    return tuple(command)


async def _run(*command: str, timeout_seconds: int = 30) -> tuple[int | None, str, str, bool]:
    try:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
    except FileNotFoundError:
        return None, "", "Docker no está disponible en el executor.", False
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except TimeoutError:
        process.kill()
        await process.wait()
        return None, "", "El comando excedió el timeout.", True
    return process.returncode, stdout.decode()[:8000], stderr.decode()[:8000], False


def _validate_archive(archive: Path) -> None:
    with zipfile.ZipFile(archive) as source:
        if sum(item.file_size for item in source.infolist()) > 250_000_000:
            raise HTTPException(413, "El archive excede el límite descomprimido.")
        for item in source.infolist():
            if Path(item.filename).is_absolute() or ".." in Path(item.filename).parts:
                raise HTTPException(400, "El archive contiene una ruta insegura.")


async def _execute(archive: Path, phase: str, profile_id: str) -> dict[str, Any]:
    profile = _profiles().get(profile_id)
    if profile is None:
        raise HTTPException(400, "Perfil de validación desconocido.")
    command = _command(profile, phase)
    timeout = profile.get("timeout_seconds")
    if not isinstance(timeout, int):
        raise HTTPException(400, "Timeout de perfil inválido.")
    suffix = uuid.uuid4().hex
    volume = f"pr-gate-{suffix}"
    staging = f"pr-gate-stage-{suffix}"
    created_volume = False
    try:
        code, _, stderr, timed_out = await _run("docker", "volume", "create", volume)
        if code != 0 or timed_out:
            return _result(phase, None, "", stderr, timed_out, True, command)
        created_volume = True
        extract_program = (
            "from pathlib import Path; import shutil, zipfile; "
            "source=Path('/tmp/source.zip'); destination=Path('/workspace'); "
            "zipfile.ZipFile(source).extractall('/tmp/extract'); "
            "roots=[p for p in Path('/tmp/extract').iterdir() if p.is_dir()]; "
            "assert len(roots) == 1; "
            "[shutil.move(str(p), destination / p.name) for p in roots[0].iterdir()]"
        )
        code, _, stderr, timed_out = await _run(
            "docker",
            "create",
            "--name",
            staging,
            "--user",
            "0:0",
            "--mount",
            f"type=volume,src={volume},dst=/workspace",
            RUNNER_IMAGE,
            "python",
            "-c",
            extract_program,
        )
        if code != 0 or timed_out:
            return _result(phase, None, "", stderr, timed_out, True, command)
        code, _, stderr, timed_out = await _run(
            "docker", "cp", str(archive), f"{staging}:/tmp/source.zip"
        )
        if code != 0 or timed_out:
            return _result(phase, None, "", stderr, timed_out, True, command)
        code, _, stderr, timed_out = await _run("docker", "start", "-a", staging)
        if code != 0 or timed_out:
            return _result(phase, None, "", stderr, timed_out, True, command)
        code, stdout, stderr, timed_out = await _run(
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--env",
            "RUFF_CACHE_DIR=/tmp/ruff-cache",
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
            f"type=volume,src={volume},dst=/workspace,readonly",
            RUNNER_IMAGE,
            *command,
            timeout_seconds=timeout,
        )
        return _result(phase, code, stdout, stderr, timed_out, code is None, command)
    finally:
        await _run("docker", "rm", "-f", staging)
        if created_volume:
            await _run("docker", "volume", "rm", "-f", volume)


def _result(
    phase: str,
    exit_code: int | None,
    stdout: str,
    stderr: str,
    timed_out: bool,
    infrastructure_error: bool,
    command: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    return {
        "command_name": phase,
        "command": list(command or ()),
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out,
        "infrastructure_error": infrastructure_error,
    }


app = FastAPI(title="PR Gate Executor")


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/execute")
async def execute(
    request: Request,
    x_validation_phase: str = Header(),
    x_validation_profile: str = Header(),
) -> dict[str, Any]:
    body = await request.body()
    if not body or len(body) > MAX_ARCHIVE_BYTES:
        raise HTTPException(413, "Archive de ejecución inválido o demasiado grande.")
    with tempfile.TemporaryDirectory(prefix="pr-gate-executor-") as temporary_directory:
        archive = Path(temporary_directory) / "source.zip"
        archive.write_bytes(body)
        try:
            _validate_archive(archive)
        except zipfile.BadZipFile as error:
            raise HTTPException(400, "Archive de ejecución inválido.") from error
        return await _execute(archive, x_validation_phase, x_validation_profile)
