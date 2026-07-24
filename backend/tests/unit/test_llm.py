from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError
from pydantic import ValidationError

from pr_gate.application.models import AnalysisOutput, AnalysisPrompt, FixOutput, FixPrompt
from pr_gate.infrastructure.config import ModelProfile
from pr_gate.infrastructure.llm import (
    FakeLLMGateway,
    GeminiLLMGateway,
    LLMError,
    OpenAILLMGateway,
)


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


@pytest.mark.asyncio
async def test_openai_gateway_uses_sdk_pydantic_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    output = AnalysisOutput(summary="ok", findings=[])

    class Responses:
        async def parse(self, **kwargs: object) -> object:
            calls.update(kwargs)
            return SimpleNamespace(
                output_parsed=output,
                usage=SimpleNamespace(input_tokens=12, output_tokens=4),
            )

    client = SimpleNamespace(responses=Responses())
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("pr_gate.infrastructure.llm.AsyncOpenAI", lambda **_: client)

    gateway = OpenAILLMGateway()

    assert await gateway.analyze("safe context") == output
    assert calls["text_format"] is AnalysisOutput
    assert gateway.usage is not None
    assert gateway.usage.input_tokens == 12
    assert gateway.usage.output_tokens == 4


@pytest.mark.asyncio
async def test_gemini_gateway_uses_openai_compatible_chat_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    output = AnalysisOutput(summary="ok", findings=[])

    class ChatCompletions:
        async def create(self, **kwargs: object) -> object:
            calls.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"summary":"ok","findings":[]}')
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=8, completion_tokens=5),
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=ChatCompletions()))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("pr_gate.infrastructure.llm.AsyncOpenAI", lambda **kwargs: client)

    profile = ModelProfile(
        id="gemini-small",
        provider="gemini",
        model="gemini-2.0-flash",
        api_key_env="GEMINI_API_KEY",
        temperature=0,
        timeout_seconds=60,
        max_retries=2,
        enabled=True,
    )
    gateway = GeminiLLMGateway(profile)

    assert await gateway.analyze("safe context") == output
    assert calls["model"] == "gemini-2.0-flash"
    assert calls["temperature"] == 0
    assert calls["messages"][0]["role"] == "user"
    assert "untrusted_context" in calls["messages"][0]["content"]
    assert gateway.usage is not None
    assert gateway.usage.input_tokens == 8
    assert gateway.usage.output_tokens == 5


@pytest.mark.asyncio
async def test_gemini_rate_limit_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.com")
    response = httpx.Response(
        429, request=request, content=b'{"error":{"message":"quota exceeded"}}'
    )

    class ChatCompletions:
        async def create(self, **_: object) -> object:
            raise RateLimitError(
                "Error code: 429",
                response=response,
                body={"error": {"message": "quota exceeded"}},
            )

    client = SimpleNamespace(chat=SimpleNamespace(completions=ChatCompletions()))
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr("pr_gate.infrastructure.llm.AsyncOpenAI", lambda **kwargs: client)

    profile = ModelProfile(
        id="gemini-small",
        provider="gemini",
        model="gemini-2.0-flash",
        api_key_env="GEMINI_API_KEY",
        temperature=0,
        timeout_seconds=60,
        max_retries=0,
        enabled=True,
    )
    gateway = GeminiLLMGateway(profile)

    with pytest.raises(LLMError) as exc_info:
        await gateway.analyze("safe context")
    assert "429" in str(exc_info.value)
    assert exc_info.value.code == "LLM_RATE_LIMIT"


@pytest.mark.asyncio
async def test_fix_prompt_requires_complete_git_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    fix = FixOutput(
        finding_index=0,
        summary="fix",
        patch=(
            "diff --git a/app/orders.py b/app/orders.py\n--- a/app/orders.py\n+++ b/app/orders.py\n"
        ),
        regression_test_patch=(
            "diff --git a/tests/test_orders.py b/tests/test_orders.py\n"
            "--- a/tests/test_orders.py\n"
            "+++ b/tests/test_orders.py\n"
        ),
        modified_paths=["app/orders.py", "tests/test_orders.py"],
    )

    class Responses:
        async def parse(self, **kwargs: object) -> object:
            calls.update(kwargs)
            return SimpleNamespace(output_parsed=fix, usage=None)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "pr_gate.infrastructure.llm.AsyncOpenAI", lambda **_: SimpleNamespace(responses=Responses())
    )

    gateway = OpenAILLMGateway()
    assert await gateway.propose_fix("safe context") == fix
    assert "diff --git a/<path> b/<path>" in str(calls["input"])
    assert "do not invent classes" in str(calls["input"])
    assert "Set finding_index to 0" in str(calls["input"])
