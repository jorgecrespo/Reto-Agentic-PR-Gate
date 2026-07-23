from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class PolicyRuleConfig(BaseModel):
    id: str = Field(pattern=r"^GATE-\d{3}$")
    description: str = Field(min_length=1)
    failure_status: str = Field(pattern=r"^(READY|CONDITIONAL|BLOCKED|INCONCLUSIVE)$")


class PolicyConfig(BaseModel):
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    target_stage: str = Field(min_length=1)
    rules: list[PolicyRuleConfig]

    @field_validator("rules")
    @classmethod
    def unique_rule_ids(cls, rules: list[PolicyRuleConfig]) -> list[PolicyRuleConfig]:
        if len({rule.id for rule in rules}) != len(rules):
            raise ValueError("Los IDs de regla deben ser únicos.")
        return rules


class LoadedPolicy(BaseModel):
    policy: PolicyConfig
    checksum: str


def load_policy(path: Path) -> LoadedPolicy:
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    return LoadedPolicy(
        policy=PolicyConfig.model_validate(data),
        checksum=hashlib.sha256(raw).hexdigest(),
    )
