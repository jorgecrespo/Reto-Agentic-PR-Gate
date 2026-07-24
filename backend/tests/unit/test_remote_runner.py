import io
import zipfile

from pr_gate.infrastructure.remote_runner import RemoteRunner


def test_archives_workspace_under_a_single_root_directory(tmp_path) -> None:
    workspace = tmp_path / "candidate"
    workspace.mkdir()
    (workspace / "app.py").write_text("print('ok')\n")

    archive = RemoteRunner._archive_workspace(workspace)

    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        assert source.namelist() == ["candidate/app.py"]
