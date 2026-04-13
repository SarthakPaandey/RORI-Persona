"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "AI Persona"
    environment: str = "development"
    log_level: str = "INFO"
    backend_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # OpenAI — chat + default embeddings when no custom embedding endpoint is set.
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # OpenAI-compatible embeddings (e.g. ModelScope inference API). When set, embeddings use this base URL + key.
    embedding_api_base: str = ""
    embedding_api_key: str = ""

    # NVIDIA NIM (OpenAI-compatible). If set, takes precedence over EMBEDDING_API_BASE / ModelScope.
    # https://docs.api.nvidia.com/nim — use a Pinecone index whose dimension matches the model (2048 for NeMo 300M embed v1).
    nvidia_embedding_api_key: str = ""
    nvidia_embedding_base: str = "https://integrate.api.nvidia.com/v1"
    nvidia_embedding_model: str = "nvidia/llama-3.2-nemoretriever-300m-embed-v1"

    # Must match the embedding model output size (1536 for text-embedding-3-small, 4096 for Qwen3-Embedding-8B, 2048 for NVIDIA NeMo 300M embed v1, etc.).
    pinecone_embedding_dimension: int = 1536

    # Groq — chat LLM fallback (OpenAI-compatible). Default model can be overridden (e.g. qwen/qwen3-32b).
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3-32b"
    groq_api_base: str = "https://api.groq.com/openai/v1"
    # Optional comma-separated backup Groq keys for automatic rotation on 429/rate limits.
    groq_api_keys: str = ""
    # Optional comma-separated fallback Groq models (tried after GROQ_MODEL).
    groq_model_candidates: str = ""

    # NVIDIA NIM chat (OpenAI-compatible /v1/chat/completions). Uses same nvapi key as embeddings if nvidia_chat_api_key empty.
    nvidia_chat_api_key: str = ""
    nvidia_chat_base: str = "https://integrate.api.nvidia.com/v1"
    nvidia_chat_model: str = "meta/llama-3.1-70b-instruct"
    # Optional comma-separated NVIDIA chat fallback models (for example: google/gemma-2-9b-it).
    nvidia_chat_model_candidates: str = ""

    # ModelScope chat fallback (e.g. stepfun-ai/Step-3.5-Flash). Reuses embedding token/base if these are empty.
    modelscope_chat_api_key: str = ""
    modelscope_chat_base: str = ""
    modelscope_chat_model: str = "stepfun-ai/Step-3.5-Flash"

    # Pinecone
    pinecone_api_key: str
    pinecone_index_name: str = "ai-persona"
    pinecone_environment: str = "us-east-1"

    # Vapi
    vapi_api_key: str = ""
    vapi_phone_number_id: str = ""
    vapi_assistant_id: str = ""

    # Cal.com
    calcom_api_key: str
    calcom_event_type_id: str
    calcom_username: str
    calcom_timezone: str = "Asia/Kolkata"

    # GitHub
    github_token: str
    github_username: str

    # ElevenLabs
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""

    # Persona
    persona_name: str = "Your Name"
    persona_role: str = "AI/ML Engineer"

    # LLM runtime
    # Completion token budget for chat responses. Increase if you see responses ending mid-sentence
    # with finish_reason="length".
    llm_max_tokens: int = 1200
    llm_request_timeout_seconds: int = 20
    llm_stream_first_token_timeout_seconds: int = 6
    # Ordered chat provider chain (comma-separated): nvidia, modelscope, groq, openai
    # Example for low latency: "groq,nvidia,modelscope,openai" or "groq".
    llm_provider_order: str = "nvidia,modelscope,groq,openai"

    # RAG Config
    chunk_size: int = 512
    chunk_overlap: int = 50
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.7
    rag_max_context_docs: int = 6
    rag_max_chars_per_doc: int = 1200
    rag_retrieval_timeout_seconds: float = 8.0

    @model_validator(mode="after")
    def validate_llm_and_embedding_keys(self):
        """Ensure at least one LLM path and one embedding path are configured."""
        nv_chat = (
            (self.nvidia_chat_api_key or self.nvidia_embedding_api_key or "").strip()
        )
        ms_chat_key = (self.modelscope_chat_api_key or self.embedding_api_key or "").strip()
        ms_chat_base = (self.modelscope_chat_base or self.embedding_api_base or "").strip()
        groq_extra_keys = [k.strip() for k in (self.groq_api_keys or "").split(",") if k.strip()]
        oa = (self.openai_api_key or "").strip()
        oa_ok = bool(oa and not oa.startswith("sk-...") and len(oa) > 12)
        has_llm = bool(
            (self.groq_api_key or "").strip()
            or groq_extra_keys
            or oa_ok
            or nv_chat
            or (ms_chat_key and ms_chat_base)
        )
        if not has_llm:
            raise ValueError(
                "Set at least one chat LLM: GROQ_API_KEY, NVIDIA (nvapi) chat/embedding key, "
                "ModelScope chat (EMBEDDING_API_KEY + EMBEDDING_API_BASE), or a real OPENAI_API_KEY."
            )
        use_nvidia = bool(self.nvidia_embedding_api_key.strip())
        use_custom_embed = bool(self.embedding_api_base.strip())

        if use_nvidia:
            return self

        emb_key = self.embedding_api_key or self.openai_api_key
        if use_custom_embed:
            if not emb_key:
                raise ValueError(
                    "When EMBEDDING_API_BASE is set, set EMBEDDING_API_KEY (ModelScope token) "
                    "or OPENAI_API_KEY for embeddings."
                )
        elif not self.openai_api_key:
            raise ValueError(
                "Set OPENAI_API_KEY for OpenAI embeddings, or set NVIDIA_EMBEDDING_API_KEY, "
                "or set EMBEDDING_API_BASE + EMBEDDING_API_KEY (e.g. Groq + ModelScope)."
            )
        if self.llm_max_tokens > 2048:
            self.llm_max_tokens = 2048

        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
