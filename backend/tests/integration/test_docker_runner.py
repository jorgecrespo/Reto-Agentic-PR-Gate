from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pr_gate.infrastructure.runner import DockerRunner


def _docker_is_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return (
        subprocess.run(
            ("docker", "info"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        ).returncode
        == 0
    )


pytestmark = pytest.mark.skipif(not _docker_is_available(), reason="Docker no está operativo")


@pytest.mark.asyncio
async def test_runner_executes_innocuous_command_in_sandbox() -> None:
    result = await DockerRunner(image="python:3.12-slim", timeout_seconds=30).run(
        Path.cwd(), "smoke", ("python", "-c", "print('sandbox-ok')")
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == "sandbox-ok"
    assert not result.infrastructure_error


@pytest.mark.asyncio
async def test_runner_disables_network() -> None:
    result = await DockerRunner(image="python:3.12-slim", timeout_seconds=30).run(
        Path.cwd(),
        "network-denied",
        (
            "python",
            "-c",
            "import socket; socket.create_connection(('1.1.1.1', 443), timeout=2)",
        ),
    )
    assert result.exit_code != 0
    assert not result.infrastructure_error
