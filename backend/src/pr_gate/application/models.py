from __future__ import annotations

from pydantic import BaseModel, Field


class AcceptanceCriterionInput(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=1000)
    required: bool = True


class CreateAnalysisInput(BaseModel):
    pull_request_url: str
    model_profile_id: str
    validation_profile_id: str
    acceptance_criteria: list[AcceptanceCriterionInput] = Field(default_factory=list, max_length=20)


class FindingOutput(BaseModel):
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


class AnalysisOutput(BaseModel):
    summary: str
    findings: list[FindingOutput] = Field(default_factory=list, max_length=10)


class FixOutput(BaseModel):
    finding_index: int = Field(ge=0)
    summary: str
    patch: str
    regression_test_patch: str
    modified_paths: list[str] = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
