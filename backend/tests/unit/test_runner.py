from pathlib import Path

import pytest

from pr_gate.infrastructure import runner
from pr_gate.infrastructure.runner import (
    DockerRunner,
    classify_command_result,
    extract_pytest_tests,
)
from pr_gate.infrastructure.workspaces import WorkspaceError, WorkspaceManager


def test_classifies_functional_failure_separately_from_infrastructure() -> None:
    assert classify_command_result(1, "", "AssertionError: expected total") == "ASSERTION_FAILURE"
    assert (
        classify_command_result(None, "", "Docker daemon unavailable", True)
        == "INFRASTRUCTURE_ERROR"
    )
    assert classify_command_result(1, "", "ModuleNotFoundError: x") == "IMPORT_ERROR"


def test_extracts_pytest_executed_and_failed_tests() -> None:
    output = """
tests/test_orders.py::test_catalog_price FAILED                         [ 50%]
tests/test_orders.py::test_other PASSED                                  [100%]
FAILED tests/test_orders.py::test_catalog_price - AssertionError
"""

    tests = extract_pytest_tests(output, "")

    assert tests["executed_tests"] == ("test_catalog_price", "test_other")
    assert tests["failed_tests"] == ("test_catalog_price",)


@pytest.mark.asyncio
async def test_runner_reports_executor_launch_failure_as_infrastructure_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runner.shutil, "which", lambda _: "docker")

    async def raise_file_not_found(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", raise_file_not_found)

    result = await DockerRunner().run(Path.cwd(), "test", ("python", "-m", "pytest"))

    assert result.infrastructure_error
    assert result.classification == "INFRASTRUCTURE_ERROR"
    assert result.exit_code is None


@pytest.mark.asyncio
async def test_apply_patch_reports_missing_git_as_workspace_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    async def raise_file_not_found(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr(runner.asyncio, "create_subprocess_exec", raise_file_not_found)

    with pytest.raises(WorkspaceError, match="herramienta de aplicación"):
        await WorkspaceManager.apply_patch(tmp_path, "diff --git a/file b/file\n")


@pytest.mark.asyncio
async def test_apply_patch_recounts_invalid_hunk_metadata(tmp_path: Path) -> None:
    source = tmp_path / "orders.py"
    source.write_text("first\nold total\nlast\n")
    patch = """diff --git a/orders.py b/orders.py
--- a/orders.py
+++ b/orders.py
@@ -1,99 +1,99 @@
 first
-old total
+new total
 last
"""

    assert await WorkspaceManager.apply_patch(tmp_path, patch)
    assert source.read_text() == "first\nnew total\nlast\n"


@pytest.mark.asyncio
async def test_apply_patch_rejects_non_matching_content(tmp_path: Path) -> None:
    (tmp_path / "orders.py").write_text("first\nactual total\nlast\n")
    patch = """diff --git a/orders.py b/orders.py
--- a/orders.py
+++ b/orders.py
@@ -1,3 +1,3 @@
 first
-old total
+new total
 last
"""

    assert not await WorkspaceManager.apply_patch(tmp_path, patch)


@pytest.mark.asyncio
async def test_apply_patch_rebases_unambiguous_hunk_offset(tmp_path: Path) -> None:
    source = tmp_path / "orders.py"
    source.write_text("first\nsecond\nold total\nlast\n")
    patch = """diff --git a/orders.py b/orders.py
--- a/orders.py
+++ b/orders.py
@@ -1 +1 @@
-old total
+new total
"""

    assert await WorkspaceManager.apply_patch(tmp_path, patch)
    assert source.read_text() == "first\nsecond\nnew total\nlast\n"
