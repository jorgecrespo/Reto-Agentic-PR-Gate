from pathlib import Path

import pytest

from pr_gate.infrastructure.config import load_policy


def test_loads_policy_with_checksum(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("""version: '1.0.0'
target_stage: QA
rules:
  - id: GATE-001
    description: x
    failure_status: INCONCLUSIVE
""")
    loaded = load_policy(path)
    assert loaded.policy.version == "1.0.0"
    assert len(loaded.checksum) == 64


def test_rejects_duplicate_policy_rule_ids(tmp_path: Path) -> None:
    path = tmp_path / "policy.yaml"
    path.write_text("""version: '1.0.0'
target_stage: QA
rules:
  - id: GATE-001
    description: x
    failure_status: INCONCLUSIVE
  - id: GATE-001
    description: y
    failure_status: INCONCLUSIVE
""")
    with pytest.raises(ValueError):
        load_policy(path)
