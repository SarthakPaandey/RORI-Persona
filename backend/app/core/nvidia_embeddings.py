"""NVIDIA NIM NeMo Retriever embeddings (asymmetric query vs passage)."""

from __future__ import annotations

from typing import List

from langchain_core.embeddings import Embeddings
from openai import OpenAI


class NvidiaNimRetrieverEmbeddings(Embeddings):
    """
    OpenAI-compatible /v1/embeddings with required ``input_type`` for NeMo Retriever models.

    - Retrieval queries → ``input_type=query``
    - Documents / corpus chunks → ``input_type=passage``
    """

    def __init__(self, *, api_key: str, base_url: str, model: str):
        self._client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
        self._model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
            encoding_format="float",
            extra_body={"input_type": "passage"},
        )
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> List[float]:
        response = self._client.embeddings.create(
            model=self._model,
            input=text,
            encoding_format="float",
            extra_body={"input_type": "query"},
        )
        return response.data[0].embedding
