"""LLM: NVIDIA NIM → ModelScope → Groq → OpenAI (fallback chain, OpenAI-compatible APIs)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, List, Sequence, Union

import structlog
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI

from app.config import Settings

logger = structlog.get_logger()
DEFAULT_PROVIDER_ORDER = ("nvidia", "modelscope", "groq", "openai")
RATE_LIMIT_COOLDOWN_SECONDS = 300
ALL_PROVIDERS_ON_COOLDOWN_ERROR = (
    "All configured LLM providers are on cooldown after rate limits."
)
_provider_cooldowns: dict[str, float] = {}


def _provider_id(model: BaseChatModel) -> str:
    """Build a stable provider/model identifier for cooldown tracking."""
    model_name = getattr(model, "model_name", getattr(model, "model", "unknown-model"))
    api_base = getattr(model, "openai_api_base", "")
    raw_key = getattr(model, "openai_api_key", "")
    key_getter = getattr(raw_key, "get_secret_value", None)
    api_key = ""
    if callable(key_getter):
        try:
            api_key = str(key_getter() or "")
        except Exception:
            api_key = ""
    else:
        api_key = str(raw_key or "")
    key_fingerprint = api_key[-8:] if api_key else "no-key"
    return f"{api_base}|{model_name}|{key_fingerprint}"


def _is_rate_limit_error(error: Exception) -> bool:
    """Detect provider-side throttling errors."""
    msg = str(error).lower()
    return "rate limit" in msg or "429" in msg or "too many requests" in msg


def _is_provider_on_cooldown(model: BaseChatModel) -> bool:
    """Return True when provider was recently rate-limited."""
    until = _provider_cooldowns.get(_provider_id(model), 0.0)
    return until > time.time()


def _mark_provider_rate_limited(model: BaseChatModel) -> None:
    """Temporarily deprioritize repeatedly rate-limited providers."""
    _provider_cooldowns[_provider_id(model)] = time.time() + RATE_LIMIT_COOLDOWN_SECONDS


def _nvidia_chat_api_key(settings: Settings) -> str:
    return (settings.nvidia_chat_api_key or settings.nvidia_embedding_api_key or "").strip()


def _modelscope_chat_key(settings: Settings) -> str:
    return (settings.modelscope_chat_api_key or settings.embedding_api_key or "").strip()


def _modelscope_chat_base(settings: Settings) -> str:
    return (settings.modelscope_chat_base or settings.embedding_api_base or "").strip()


def _openai_key_usable(settings: Settings) -> bool:
    k = settings.openai_api_key.strip()
    if not k:
        return False
    if k.startswith("sk-...") or k in ("sk-test", "sk-test-openai"):
        return False
    return len(k) > 20


def _content_to_text(content: object) -> str:
    """Normalize model content payloads (str or multimodal list) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


def _chat_result_text(result: ChatResult) -> str:
    """Extract a plain-text payload from a chat result."""
    if not result.generations:
        return ""

    generation = result.generations[0]
    message = getattr(generation, "message", None)
    content = getattr(message, "content", "")

    return _content_to_text(content)


def _provider_order(settings: Settings) -> list[str]:
    """Parse ordered provider list from env (comma-separated)."""
    raw = (settings.llm_provider_order or "").strip()
    if not raw:
        return list(DEFAULT_PROVIDER_ORDER)

    providers: list[str] = []
    for item in raw.split(","):
        provider = item.strip().lower()
        if not provider:
            continue
        if provider not in DEFAULT_PROVIDER_ORDER:
            logger.warning("llm_provider_unknown", provider=provider)
            continue
        if provider not in providers:
            providers.append(provider)

    return providers or list(DEFAULT_PROVIDER_ORDER)


def _split_csv(raw: str) -> list[str]:
    """Split comma-separated env values into trimmed non-empty items."""
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _unique(values: Sequence[str]) -> list[str]:
    """Keep first occurrence order while removing duplicates/empties."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = (value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _groq_api_keys(settings: Settings) -> list[str]:
    """Primary + backup Groq keys (comma-separated in GROQ_API_KEYS)."""
    return _unique([settings.groq_api_key, *_split_csv(settings.groq_api_keys)])


def _groq_models(settings: Settings) -> list[str]:
    """Primary + backup Groq models (comma-separated in GROQ_MODEL_CANDIDATES)."""
    return _unique([settings.groq_model, *_split_csv(settings.groq_model_candidates)])


def _nvidia_chat_models(settings: Settings) -> list[str]:
    """Primary + fallback NVIDIA chat models (comma-separated candidates)."""
    return _unique(
        [settings.nvidia_chat_model, *_split_csv(settings.nvidia_chat_model_candidates)]
    )


class FallbackChatLLM(BaseChatModel):
    """Try chat models in order until one succeeds (rate limits, outages, etc.)."""

    models: List[ChatOpenAI]

    @property
    def _llm_type(self) -> str:
        return "fallback-chat-openai"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Union[List[str], None] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        last: Exception | None = None
        attempted = False
        for i, m in enumerate(self.models):
            if _is_provider_on_cooldown(m):
                logger.info("llm_provider_cooldown_skip", attempt=i + 1, provider=_provider_id(m))
                continue
            attempted = True
            try:
                result = m._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
                if _chat_result_text(result).strip():
                    return result
                raise ValueError("LLM returned empty content")
            except Exception as e:
                if _is_rate_limit_error(e):
                    _mark_provider_rate_limited(m)
                logger.warning("llm_fallback_invoke", attempt=i + 1, error=str(e)[:300])
                last = e
        if not attempted:
            raise RuntimeError(ALL_PROVIDERS_ON_COOLDOWN_ERROR)
        assert last is not None
        raise last

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Union[List[str], None] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        last: Exception | None = None
        attempted = False
        for i, m in enumerate(self.models):
            if _is_provider_on_cooldown(m):
                logger.info("llm_provider_cooldown_skip", attempt=i + 1, provider=_provider_id(m))
                continue
            attempted = True
            try:
                result = await m._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
                if _chat_result_text(result).strip():
                    return result
                raise ValueError("LLM returned empty content")
            except Exception as e:
                if _is_rate_limit_error(e):
                    _mark_provider_rate_limited(m)
                logger.warning("llm_fallback_ainvoke", attempt=i + 1, error=str(e)[:300])
                last = e
        if not attempted:
            raise RuntimeError(ALL_PROVIDERS_ON_COOLDOWN_ERROR)
        assert last is not None
        raise last

    def bind(self, **kwargs: Any) -> Any:
        """Delegate bind to the first underlying model (best-effort)."""
        return self.models[0].bind(**kwargs) if self.models else self


def get_llm(settings: Settings, temperature: float = 0.35) -> BaseChatModel:
    """Build LLM fallback chain in configured provider order."""
    models: List[ChatOpenAI] = []
    common = dict(
        temperature=temperature,
        max_tokens=int(settings.llm_max_tokens),
        request_timeout=int(settings.llm_request_timeout_seconds),
    )

    providers = _provider_order(settings)
    for provider in providers:
        if provider == "nvidia":
            nk = _nvidia_chat_api_key(settings)
            if not nk:
                continue
            for model_name in _nvidia_chat_models(settings):
                models.append(
                    ChatOpenAI(
                        model=model_name,
                        openai_api_key=nk,
                        openai_api_base=settings.nvidia_chat_base.rstrip("/"),
                        **common,
                    )
                )
            continue

        if provider == "modelscope":
            ms_key = _modelscope_chat_key(settings)
            ms_base = _modelscope_chat_base(settings)
            if not (ms_key and ms_base):
                continue
            models.append(
                ChatOpenAI(
                    model=settings.modelscope_chat_model,
                    openai_api_key=ms_key,
                    openai_api_base=ms_base.rstrip("/"),
                    **common,
                )
            )
            continue

        if provider == "groq":
            groq_keys = _groq_api_keys(settings)
            groq_models = _groq_models(settings)
            if not (groq_keys and groq_models):
                continue
            for model_name in groq_models:
                for key in groq_keys:
                    models.append(
                        ChatOpenAI(
                            model=model_name,
                            openai_api_key=key,
                            openai_api_base=settings.groq_api_base.rstrip("/"),
                            **common,
                        )
                    )
            continue

        if provider == "openai" and _openai_key_usable(settings):
            models.append(
                ChatOpenAI(
                    model=settings.openai_model,
                    openai_api_key=settings.openai_api_key,
                    **common,
                )
            )
            continue

    if not models:
        raise ValueError(
            "No LLM configured. Set NVIDIA (chat or embedding nvapi key), MODELSCOPE + EMBEDDING_API_KEY, "
            "GROQ_API_KEY, or a real OPENAI_API_KEY."
        )

    logger.info(
        "llm_chain_built",
        provider_order=providers,
        active_models=len(models),
        active_model_names=[getattr(m, "model_name", "unknown") for m in models],
    )

    if len(models) == 1:
        return models[0]

    return FallbackChatLLM(models=models)


async def stream_chat_tokens(
    llm: BaseChatModel,
    messages: Sequence[BaseMessage],
    first_token_timeout_seconds: int = 0,
    **kwargs: Any,
) -> AsyncIterator[str]:
    """Yield streamed token chunks, with fallback support before any token is emitted."""
    candidates: Sequence[BaseChatModel] = (
        llm.models if isinstance(llm, FallbackChatLLM) else [llm]
    )

    last_error: Exception | None = None
    attempted = False
    for idx, model in enumerate(candidates):
        if _is_provider_on_cooldown(model):
            logger.info(
                "llm_provider_cooldown_skip",
                attempt=idx + 1,
                provider=_provider_id(model),
            )
            continue
        attempted = True
        emitted = False
        try:
            async for token in _stream_tokens_with_first_token_timeout(
                model,
                messages,
                first_token_timeout_seconds=first_token_timeout_seconds,
                **kwargs,
            ):
                emitted = True
                yield token
            if emitted:
                return
            raise ValueError("LLM returned empty streamed content")
        except asyncio.TimeoutError as exc:
            _mark_provider_rate_limited(model)
            logger.warning(
                "llm_first_token_timeout",
                attempt=idx + 1,
                provider=_provider_id(model),
                timeout_seconds=first_token_timeout_seconds,
            )
            last_error = exc
        except Exception as exc:
            if _is_rate_limit_error(exc):
                _mark_provider_rate_limited(model)
            if emitted:
                logger.warning(
                    "llm_stream_interrupted",
                    attempt=idx + 1,
                    error=str(exc)[:300],
                )
                raise
            logger.warning("llm_fallback_astream", attempt=idx + 1, error=str(exc)[:300])
            last_error = exc

    if not attempted:
        raise RuntimeError(ALL_PROVIDERS_ON_COOLDOWN_ERROR)
    if last_error is not None:
        raise last_error
    raise ValueError("No streaming-capable LLM configured")


async def _stream_tokens_with_first_token_timeout(
    model: BaseChatModel,
    messages: Sequence[BaseMessage],
    first_token_timeout_seconds: int,
    **kwargs: Any,
) -> AsyncIterator[str]:
    """Stream tokens from one model with optional timeout for first token."""
    iterator = model.astream(messages, **kwargs).__aiter__()
    timeout_seconds = max(0, int(first_token_timeout_seconds))

    if timeout_seconds > 0:
        first_token = await asyncio.wait_for(
            _read_first_non_empty_token(iterator),
            timeout=timeout_seconds,
        )
    else:
        first_token = await _read_first_non_empty_token(iterator)

    yield first_token

    async for chunk in iterator:
        token = _content_to_text(getattr(chunk, "content", ""))
        if token:
            yield token


async def _read_first_non_empty_token(iterator: AsyncIterator[Any]) -> str:
    """Read the first non-empty token from a stream iterator."""
    async for chunk in iterator:
        token = _content_to_text(getattr(chunk, "content", ""))
        if token:
            return token
    raise ValueError("LLM returned empty streamed content")
