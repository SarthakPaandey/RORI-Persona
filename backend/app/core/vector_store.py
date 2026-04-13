"""Vector store management using Pinecone."""

import structlog
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from app.config import Settings
from app.core.embeddings import get_embeddings

logger = structlog.get_logger()


class VectorStoreManager:
    """Manages Pinecone vector store operations."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.embeddings = get_embeddings(settings)
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._ensure_index_exists()

    def _ensure_index_exists(self):
        """Create Pinecone index if it doesn't exist."""
        index_name = self.settings.pinecone_index_name
        existing_indexes = [idx.name for idx in self._pc.list_indexes()]

        if index_name not in existing_indexes:
            logger.info("Creating Pinecone index", name=index_name)
            self._pc.create_index(
                name=index_name,
                dimension=self.settings.pinecone_embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=self.settings.pinecone_environment,
                ),
            )
            logger.info("Pinecone index created", name=index_name)
        else:
            logger.info("Pinecone index already exists", name=index_name)

    def get_store(self) -> PineconeVectorStore:
        """Get the Pinecone vector store instance."""
        return PineconeVectorStore(
            index_name=self.settings.pinecone_index_name,
            embedding=self.embeddings,
            pinecone_api_key=self.settings.pinecone_api_key,
        )

    def add_documents(self, documents: list, namespace: str = ""):
        """Add documents to the vector store."""
        store = self.get_store()
        store.add_documents(documents, namespace=namespace)
        logger.info(
            "Documents added to vector store",
            count=len(documents),
            namespace=namespace,
        )

    def similarity_search(self, query: str, k: int = 5, namespace: str = "") -> list:
        """Perform similarity search."""
        store = self.get_store()
        return store.similarity_search_with_score(query, k=k, namespace=namespace)

    def delete_namespace(self, namespace: str):
        """Delete all vectors in a namespace."""
        index = self._pc.Index(self.settings.pinecone_index_name)
        index.delete(delete_all=True, namespace=namespace)
        logger.info("Namespace deleted", namespace=namespace)
