from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pr_gate.infrastructure.database import AnalysisStore, ValidationRecord
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


def test_migrates_complete_schema_from_zero(tmp_path: Path) -> None:
    store = AnalysisStore(f"sqlite:///{tmp_path / 'migrated.db'}")
    assert {
        "pull_requests",
        "pr_snapshots",
        "analysis_runs",
        "findings",
        "candidate_fixes",
        "validation_runs",
        "acceptance_evaluations",
        "gate_decisions",
        "run_events",
    } <= set(inspect(store._engine).get_table_names())  # noqa: SLF001


def test_persists_incremental_report_entities(tmp_path: Path) -> None:
    store = AnalysisStore(f"sqlite:///{tmp_path / 'report.db'}")
    analysis = store.create("https://github.com/acme/shop/pull/1", "openai-small", "python-demo")
    store.save_snapshot(
        analysis.id,
        "acme",
        "shop",
        1,
        analysis.pull_request_url,
        "a" * 40,
        "b" * 40,
        False,
        {"files": []},
    )
    finding_id = store.save_finding(
        analysis.id,
        {
            "category": "security",
            "severity": "critical",
            "title": "Client price",
            "file_path": "app/orders.py",
            "start_line": 1,
            "end_line": 1,
            "evidence_excerpt": "unit_price",
            "explanation": "Client input is trusted.",
            "impact": "Price manipulation.",
            "recommended_action": "Use catalog price.",
            "confidence": 0.9,
        },
    )
    store.save_candidate_fix(finding_id, "diff", "test diff", "c" * 64, "APPLICABLE")
    store.save_acceptance_evaluation(analysis.id, "AC-1", "Use catalog price", True, "PASSED", [])
    report = store.report(analysis.id)
    assert report is not None
    assert report["findings"] == [
        {
            "id": finding_id,
            "severity": "critical",
            "title": "Client price",
            "file_path": "app/orders.py",
        }
    ]
    assert report["acceptance_criteria"] == [{"id": "AC-1", "status": "PASSED", "evidence": []}]


def test_redacts_secrets_from_persisted_report(tmp_path: Path) -> None:
    store = AnalysisStore(f"sqlite:///{tmp_path / 'redacted.db'}")
    analysis = store.create("https://github.com/acme/shop/pull/1", "openai-small", "python-demo")
    store.finish(analysis.id, "INCONCLUSIVE", {"output": "api_key=abcdefghijklmnop"})
    saved = store.get(analysis.id)
    assert saved is not None
    assert "abcdefghijklmnop" not in saved.report_json
    assert "[REDACTED_SECRET]" in saved.report_json


def test_foreign_key_failure_rolls_back_validation(tmp_path: Path) -> None:
    store = AnalysisStore(f"sqlite:///{tmp_path / 'rollback.db'}")
    with pytest.raises(IntegrityError):
        store.save_validation("missing", "suite", CommandResult("suite", 0, "", "", False, False))
    with Session(store._engine) as session:  # noqa: SLF001
        assert list(session.scalars(select(ValidationRecord))) == []


def test_history_survives_store_recreation_and_paginates(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'history.db'}"
    store = AnalysisStore(database_url)
    first = store.create("https://github.com/acme/shop/pull/1", "openai-small", "python-demo")
    second = store.create("https://github.com/acme/shop/pull/2", "openai-small", "python-demo")
    restored_store = AnalysisStore(database_url)
    first_page = restored_store.list(limit=1)
    second_page = restored_store.list(limit=1, offset=1)
    assert {record.id for record in first_page + second_page} == {first.id, second.id}


def test_finds_active_runs_and_marks_orphans_inconclusive(tmp_path: Path) -> None:
    store = AnalysisStore(f"sqlite:///{tmp_path / 'active.db'}")
    pending = store.create("https://github.com/acme/shop/pull/1", "openai-small", "python-demo")
    assert store.find_active(pending.pull_request_url, "openai-small", "python-demo") is not None
    store.mark_running(pending.id)
    assert store.mark_orphaned() == 1
    recovered = store.get(pending.id)
    assert recovered is not None
    assert recovered.status == "INCONCLUSIVE"
    assert recovered.error_message is not None
