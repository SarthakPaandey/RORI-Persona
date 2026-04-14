"""RAG (Retrieval-Augmented Generation) engine."""

from __future__ import annotations

import asyncio
import structlog
from dataclasses import dataclass, field
from typing import AsyncIterator, List

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_pinecone import PineconeVectorStore

from app.config import Settings
from app.core.llm import get_llm, stream_chat_tokens
from app.core.prompt_templates import format_chat_prompt
from app.models.schemas import ConversationMessage
from app.services.persona_service import PersonaService

logger = structlog.get_logger()


def _aimessage_content_to_str(content: object) -> str:
    """Normalize LangChain AIMessage content (str or multimodal list) to a plain string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text") or block.get("content") or ""))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content)


@dataclass
class RAGResult:
    """Result from a RAG query."""

    answer: str
    source_documents: List[Document] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class RAGStreamResult:
    """Prepared stream response with token iterator and grounding metadata."""

    token_stream: AsyncIterator[str]
    source_documents: List[Document] = field(default_factory=list)
    confidence: float = 0.0


class RAGEngine:
    """
    RAG pipeline that retrieves relevant documents from the vector store
    and generates grounded responses using GPT-4o.
    """

    def __init__(self, settings: Settings, vector_store: PineconeVectorStore):
        self.settings = settings
        self.vector_store = vector_store
        self.llm = get_llm(settings)
        self._persona = PersonaService()

    async def query(
        self,
        query: str,
        conversation_history: List[ConversationMessage],
        additional_context: str = "",
    ) -> RAGResult:
        """Process a query through the RAG pipeline."""
        logger.info("RAG query", query=query[:100])

        messages, retrieved_docs = await self._prepare_messages(
            query=query,
            conversation_history=conversation_history,
            additional_context=additional_context,
        )

        response = await self.llm.ainvoke(messages)

        confidence = self._calculate_confidence(retrieved_docs)

        logger.info(
            "RAG response generated",
            query=query[:50],
            num_sources=len(retrieved_docs),
            confidence=confidence,
        )

        source_docs = self._build_source_documents(retrieved_docs)

        return RAGResult(
            answer=_aimessage_content_to_str(getattr(response, "content", None)),
            source_documents=source_docs,
            confidence=confidence,
        )

    async def stream_query(
        self,
        query: str,
        conversation_history: List[ConversationMessage],
        additional_context: str = "",
    ) -> RAGStreamResult:
        """Prepare a streamed RAG response for incremental UI rendering."""
        logger.info("RAG stream query", query=query[:100])

        messages, retrieved_docs = await self._prepare_messages(
            query=query,
            conversation_history=conversation_history,
            additional_context=additional_context,
        )
        confidence = self._calculate_confidence(retrieved_docs)
        source_docs = self._build_source_documents(retrieved_docs)

        async def _token_stream() -> AsyncIterator[str]:
            async for token in stream_chat_tokens(
                self.llm,
                messages,
                first_token_timeout_seconds=int(
                    getattr(self.settings, "llm_stream_first_token_timeout_seconds", 0)
                ),
            ):
                yield token

        return RAGStreamResult(
            token_stream=_token_stream(),
            source_documents=source_docs,
            confidence=confidence,
        )

    async def _prepare_messages(
        self,
        query: str,
        conversation_history: List[ConversationMessage],
        additional_context: str,
    ) -> tuple[List[SystemMessage | HumanMessage], List[tuple]]:
        """Build model messages and retrieval context once for sync and streaming modes."""
        retrieved_docs = await self._retrieve(query)
        retrieved_docs = self._filter_excluded_github(retrieved_docs, query)
        context = self._format_context(retrieved_docs)
        history_str = self._format_history(conversation_history)

        cfg = self._persona.config
        role_req = cfg.get("target_role_requirements") or ""
        if not isinstance(role_req, str):
            role_req = ""
        bg_notes = cfg.get("background_notes") or ""
        if not isinstance(bg_notes, str):
            bg_notes = ""

        display_name = (cfg.get("name") or "").strip() or self.settings.persona_name
        display_role = (cfg.get("role") or "").strip() or self.settings.persona_role

        raw_show = cfg.get("github_showcase_repos") or []
        showcase_str = (
            ", ".join(str(x).strip() for x in raw_show if x)
            if isinstance(raw_show, list)
            else ""
        )

        system_prompt = format_chat_prompt(
            persona_name=display_name,
            persona_role=display_role,
            context=context,
            conversation_history=history_str,
            additional_context=additional_context,
            role_requirements=role_req,
            background_notes=bg_notes,
            github_showcase_repos=showcase_str,
        )

        messages: List[SystemMessage | HumanMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]
        return messages, retrieved_docs

    def _build_source_documents(self, docs_with_scores: List[tuple]) -> List[Document]:
        """Attach retrieval score metadata to source docs."""
        source_docs: List[Document] = []
        for doc, score in docs_with_scores:
            merged = Document(
                page_content=doc.page_content,
                metadata={**doc.metadata, "score": float(score)},
            )
            source_docs.append(merged)
        return source_docs

    def _is_project_query(self, query: str) -> bool:
        q = query.lower()
        return any(
            w in q
            for w in (
                "github",
                "git hub",
                "repository",
                "repo",
                "project",
                "portfolio",
                "open source",
                "code",
                "build",
            )
        )

    def _retrieve_k(self, query: str) -> int:
        """Use a moderately larger top-k for project queries without exploding prompt size."""
        k = self.settings.retrieval_top_k
        if self._is_project_query(query):
            return min(8, k + 3)
        return k

    def _retrieval_timeout_seconds(self) -> float:
        """Clamp vector retrieval timeout to a sane positive value."""
        raw = getattr(self.settings, "rag_retrieval_timeout_seconds", 5.0) or 5.0
        return max(1.0, float(raw))

    async def _similarity_search_with_score(self, query: str, k: int) -> List[tuple]:
        """Run vector search off the event loop and fail fast on provider stalls."""
        timeout_seconds = self._retrieval_timeout_seconds()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self.vector_store.similarity_search_with_score,
                    query,
                    k,
                ),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "vector_search_timeout",
                query=query[:100],
                k=k,
                timeout_seconds=timeout_seconds,
            )
            return []

    async def _merge_showcase_boost(self, query: str, docs_with_scores: List[tuple]) -> List[tuple]:
        """
        Pure vector search can surface unrelated small repos. Merge in a second retrieval biased toward
        AI/ML + flagship repo names, then rank showcase repos first.
        For 'latest/recent' queries, do an extra-wide retrieval to ensure recently-pushed repos surface.
        """
        raw = self._persona.config.get("github_showcase_repos") or []
        if not isinstance(raw, list) or not raw:
            return docs_with_scores
        showcase = {str(x).strip() for x in raw if x}
        if not showcase or not self._is_project_query(query):
            return docs_with_scores

        q_lower = query.lower()
        is_recent = any(w in q_lower for w in ("recent", "latest", "newest", "current", "last updated"))

        # For recency queries, search for each showcase repo by name so they
        # are guaranteed to enter the candidate pool (similarity search for
        # "latest github projects" won't match them by content).
        extra: List[tuple] = []
        if is_recent:
            for repo_name in sorted(showcase):
                try:
                    hits = await self._similarity_search_with_score(
                        f"GitHub Repository: {repo_name}",
                        2,
                    )
                    extra.extend(hits)
                except Exception:
                    pass
        else:
            bias_q = (
                f"{query} artificial intelligence machine learning LLM RAG agents "
                f"embeddings Pinecone LangChain production {' '.join(sorted(showcase))}"
            )
            try:
                extra = await self._similarity_search_with_score(
                    bias_q,
                    min(6, len(showcase) + 2),
                )
            except Exception as e:
                logger.warning("showcase boost search failed", error=str(e))
                extra = []

        def doc_key(doc: Document) -> tuple:
            return (doc.metadata.get("source", ""), doc.page_content[:160])

        best: dict = {}
        for doc, score in docs_with_scores + extra:
            if score < self.settings.similarity_threshold:
                continue
            k = doc_key(doc)
            if k not in best or score > best[k][1]:
                best[k] = (doc, score)

        if not best:
            for doc, score in docs_with_scores + extra:
                k = doc_key(doc)
                if k not in best or score > best[k][1]:
                    best[k] = (doc, score)

        items = list(best.values())

        def rank(item: tuple) -> tuple:
            doc, score = item
            repo = (doc.metadata.get("repo_name") or "").strip()
            pri = 1 if repo in showcase else 0

            if is_recent:
                # For "latest" queries, date is the PRIMARY sort key so the
                # most recently pushed repos always surface first.
                date_str = doc.metadata.get("pushed_at") or doc.metadata.get("last_updated", "1970-01-01")
                return (date_str, pri, score)

            return (pri, score)

        items.sort(key=rank, reverse=True)
        max_docs = max(1, int(getattr(self.settings, "rag_max_context_docs", 6) or 6))
        return items[:max_docs]

    def _filter_excluded_github(
        self, docs_with_scores: List[tuple], query: str
    ) -> List[tuple]:
        """Drop low-signal GitHub repos listed in persona_config (e.g. profile readme only)."""
        raw = self._persona.config.get("github_exclude_repos") or []
        if not isinstance(raw, list) or not raw:
            return docs_with_scores
        excluded = {str(x).strip() for x in raw if x}
        if not excluded:
            return docs_with_scores

        q = query.lower()
        project_like = any(
            w in q for w in ("github", "repo", "project", "portfolio", "code", "build")
        )
        if not project_like:
            return docs_with_scores

        filtered = []
        for doc, score in docs_with_scores:
            repo = doc.metadata.get("repo_name") or ""
            src = doc.metadata.get("source", "")
            if src.startswith("github:") and repo in excluded:
                continue
            filtered.append((doc, score))

        return filtered if filtered else docs_with_scores[:5]

    async def _retrieve(self, query: str) -> List[tuple]:
        """Retrieve relevant documents from vector store."""
        try:
            k = self._retrieve_k(query)

            # Run primary search first
            results = await self._similarity_search_with_score(query, k)

            filtered = [
                (doc, score)
                for doc, score in results
                if score >= self.settings.similarity_threshold
            ]

            logger.info(
                "Documents retrieved",
                total=len(results),
                after_filter=len(filtered),
            )

            max_docs = max(1, int(getattr(self.settings, "rag_max_context_docs", 6) or 6))
            base = filtered if filtered else (results[:max_docs] if results else [])

            # Skip showcase boost if primary search returned nothing
            # (embedding API is likely stalling — boost will also time out)
            if not results:
                logger.info("Skipping showcase boost — primary search returned empty")
                return base

            merged = await self._merge_showcase_boost(query, base)
            return merged if merged else base

        except Exception as e:
            logger.error("Retrieval failed", error=str(e))
            return []

    def _format_context(self, docs_with_scores: List[tuple]) -> str:
        """Format retrieved documents into context string."""
        if not docs_with_scores:
            return "No relevant documents found in the knowledge base."

        max_docs = max(1, int(getattr(self.settings, "rag_max_context_docs", 6) or 6))
        max_chars = max(200, int(getattr(self.settings, "rag_max_chars_per_doc", 1200) or 1200))

        context_parts = []
        for i, (doc, score) in enumerate(docs_with_scores[:max_docs], 1):
            source = doc.metadata.get("source", "unknown")
            snippet = doc.page_content
            if len(snippet) > max_chars:
                snippet = snippet[:max_chars].rstrip() + "..."
            context_parts.append(
                f"[Source {i}: {source} (relevance: {score:.2f})]\n{snippet}"
            )

        return "\n\n---\n\n".join(context_parts)

    def _format_history(self, history: List[ConversationMessage]) -> str:
        """Format conversation history."""
        if not history:
            return "No previous conversation."

        formatted = []
        for msg in history[-10:]:
            role = "User" if msg.role == "user" else "Assistant"
            formatted.append(f"{role}: {msg.content}")

        return "\n".join(formatted)

    def _calculate_confidence(self, docs_with_scores: List[tuple]) -> float:
        """Calculate confidence score based on retrieval quality."""
        if not docs_with_scores:
            return 0.0

        scores = [score for _, score in docs_with_scores]
        avg_score = sum(scores) / len(scores)
        return min(avg_score, 1.0)
