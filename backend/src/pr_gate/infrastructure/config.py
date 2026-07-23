from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key_env: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    temperature: float = Field(ge=0, le=1)
    timeout_seconds: int = Field(ge=1, le=300)
    max_retries: int = Field(ge=0, le=3)
    enabled: bool


class ModelProfiles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    models: list[ModelProfile]

    @field_validator("models")
    @classmethod
    def unique_ids(cls, profiles: list[ModelProfile]) -> list[ModelProfile]:
        if len({profile.id for profile in profiles}) != len(profiles):
            raise ValueError("Los IDs de modelo deben ser únicos.")
        return profiles


def load_model_profiles(path: Path) -> ModelProfiles:
    data = yaml.safe_load(path.read_bytes())
    return ModelProfiles.model_validate(data)
