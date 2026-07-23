import pytest
from pydantic import ValidationError

from pr_gate.application.models import AnalysisOutput, AnalysisPrompt, FixPrompt
from pr_gate.infrastructure.llm import FakeLLMGateway, LLMError


def test_output_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AnalysisOutput.model_validate({"summary": "x", "findings": [], "decision": "READY"})


@pytest.mark.asyncio
async def test_fake_gateway_uses_structured_contract() -> None:
    output = AnalysisOutput(summary="ok", findings=[])
    gateway = FakeLLMGateway(output)
    assert (
        await gateway.analyze_change(
            AnalysisPrompt(prompt_version="analyze-change-v1", context="data")
        )
        == output
    )
    with pytest.raises(LLMError):
        await gateway.propose_fix_for(
            FixPrompt(prompt_version="propose-fix-v1", context="data", finding_index=0)
        )
