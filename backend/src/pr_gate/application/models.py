from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AcceptanceCriterionInput(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=1000)
    required: bool = True
    validation_tests: list[str] = Field(default_factory=list, max_length=20)


class CreateAnalysisInput(StrictModel):
    pull_request_url: str
    model_profile_id: str
    validation_profile_id: str
    acceptance_criteria: list[AcceptanceCriterionInput] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def require_verifiable_required_criteria(self) -> Self:
        required = [item for item in self.acceptance_criteria if item.required]
        if not required:
            raise ValueError("Debe existir al menos un criterio de aceptación obligatorio.")
        if any(not item.validation_tests for item in required):
            raise ValueError("Cada criterio obligatorio debe declarar al menos un validation_test.")
        return self


class FindingOutput(StrictModel):
    title: str
    category: str
    severity: str
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    evidence_excerpt: str = Field(min_length=1, max_length=2000)
    explanation: str = Field(min_length=1, max_length=4000)
    impact: str = Field(min_length=1, max_length=4000)
    recommended_action: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1)


class AnalysisOutput(StrictModel):
    summary: str
    findings: list[FindingOutput] = Field(default_factory=list, max_length=10)


class FixOutput(StrictModel):
    finding_index: int = Field(ge=0)
    summary: str
    patch: str
    regression_test_patch: str
    regression_test_name: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    modified_paths: list[str] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)


class AnalysisPrompt(StrictModel):
    prompt_version: str = Field(pattern=r"^analyze-change-v\d+$")
    context: str = Field(min_length=1, max_length=50_000)
    acceptance_criteria: list[AcceptanceCriterionInput] = Field(default_factory=list, max_length=20)


class FixPrompt(StrictModel):
    prompt_version: str = Field(pattern=r"^propose-fix-v\d+$")
    context: str = Field(min_length=1, max_length=50_000)
    finding_index: int = Field(ge=0)
