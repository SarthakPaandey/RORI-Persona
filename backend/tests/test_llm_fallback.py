"""Tests for chat-model fallback behavior."""

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.config import Settings
from app.core.llm import (
    FallbackChatLLM,
    _is_provider_on_cooldown,
    _mark_provider_rate_limited,
    _provider_cooldowns,
    get_llm,
)


def _result(content):
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


class StubModel:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.error:
            raise self.error
        return self.result

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        if self.error:
            raise self.error
        return self.result


def test_fallback_uses_next_model_when_first_returns_empty_content():
    llm = FallbackChatLLM.construct(
        models=[
            StubModel(result=_result("")),
            StubModel(result=_result("fallback answer")),
        ]
    )

    result = llm._generate(messages=[])

    assert result.generations[0].message.content == "fallback answer"


@pytest.mark.asyncio
async def test_async_fallback_uses_next_model_when_first_returns_empty_content():
    llm = FallbackChatLLM.construct(
        models=[
            StubModel(result=_result("   ")),
            StubModel(result=_result("async fallback answer")),
        ]
    )

    result = await llm._agenerate(messages=[])

    assert result.generations[0].message.content == "async fallback answer"


def test_rate_limit_cooldown_isolated_per_api_key():
    _provider_cooldowns.clear()

    first = StubModel(result=_result("ok"))
    first.model_name = "llama-3.1-8b-instant"
    first.openai_api_base = "https://api.groq.com/openai/v1"
    first.openai_api_key = "gsk-primary-aaaaaaaa"

    second = StubModel(result=_result("ok"))
    second.model_name = "llama-3.1-8b-instant"
    second.openai_api_base = "https://api.groq.com/openai/v1"
    second.openai_api_key = "gsk-backup-bbbbbbbb"

    _mark_provider_rate_limited(first)

    assert _is_provider_on_cooldown(first) is True
    assert _is_provider_on_cooldown(second) is False


def test_get_llm_expands_groq_model_and_key_candidates():
    settings = Settings(
        pinecone_api_key="pcsk-test",
        calcom_api_key="cal-test",
        calcom_event_type_id="1",
        calcom_username="test-user",
        github_token="ghp_test",
        github_username="test-user",
        nvidia_embedding_api_key="nvapi-test",
        llm_provider_order="groq",
        groq_api_key="gsk-primary-11111111",
        groq_api_keys="gsk-backup-22222222,gsk-backup-33333333",
        groq_model="llama-3.1-8b-instant",
        groq_model_candidates="llama-3.3-70b-versatile",
    )

    llm = get_llm(settings)

    assert isinstance(llm, FallbackChatLLM)
    assert len(llm.models) == 6
    assert [m.model_name for m in llm.models[:3]] == ["llama-3.1-8b-instant"] * 3
    assert [m.model_name for m in llm.models[3:]] == ["llama-3.3-70b-versatile"] * 3
