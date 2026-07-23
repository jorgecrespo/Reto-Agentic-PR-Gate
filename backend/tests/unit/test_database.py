from pathlib import Path

from pr_gate.infrastructure.database import AnalysisStore
from pr_gate.infrastructure.runner import CommandResult


def test_persists_validation_result(tmp_path: Path) -> None:
    store = AnalysisStore(f"sqlite:///{tmp_path / 'test.db'}")
    analysis = store.create("https://github.com/acme/shop/pull/1", "openai-small", "python-demo")
    store.save_validation(
        analysis.id,
        "suite",
        CommandResult("candidate-suite", 0, "passed", "", False, False),
    )
    assert store.get(analysis.id) is not None
