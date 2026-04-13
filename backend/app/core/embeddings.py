"""Embeddings via OpenAI API or any OpenAI-compatible server (ModelScope, NVIDIA NIM, etc.)."""

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.config import Settings
from app.core.nvidia_embeddings import NvidiaNimRetrieverEmbeddings


def get_embeddings(settings: Settings) -> Embeddings:
    """Create embeddings client (OpenAI, ModelScope, NVIDIA NIM, or compatible base URL)."""
    # Priority: NVIDIA NIM > custom EMBEDDING_API_BASE > OpenAI
    if settings.nvidia_embedding_api_key.strip():
        return NvidiaNimRetrieverEmbeddings(
            api_key=settings.nvidia_embedding_api_key,
            base_url=settings.nvidia_embedding_base,
            model=settings.nvidia_embedding_model,
        )

    api_key = settings.embedding_api_key or settings.openai_api_key
    kwargs: dict = {
        "model": settings.openai_embedding_model,
        "openai_api_key": api_key,
    }
    if settings.embedding_api_base:
        kwargs["openai_api_base"] = settings.embedding_api_base.rstrip("/")
        kwargs["model_kwargs"] = {"encoding_format": "float"}
    return OpenAIEmbeddings(**kwargs)
