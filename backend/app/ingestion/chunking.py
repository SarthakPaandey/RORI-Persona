"""Text chunking strategies for document ingestion."""

import structlog
from typing import List, Optional

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

logger = structlog.get_logger()


def chunk_text(
    text: str,
    source: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    metadata: Optional[dict] = None,
) -> List[Document]:
    """Split text into chunks suitable for embedding."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    base_metadata = {"source": source}
    if metadata:
        base_metadata.update(metadata)

    chunks = splitter.create_documents(
        texts=[text],
        metadatas=[base_metadata],
    )

    logger.info(
        "Text chunked",
        source=source,
        num_chunks=len(chunks),
        avg_chunk_size=sum(len(c.page_content) for c in chunks) / max(len(chunks), 1),
    )

    return chunks


def chunk_resume_sections(
    sections: List[dict],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> List[Document]:
    """Chunk resume sections individually for better retrieval."""
    all_chunks = []

    for section in sections:
        section_name = section["section"]
        content = section["content"]

        if len(content) < 50:
            continue

        chunks = chunk_text(
            text=content,
            source=f"resume:{section_name}",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            metadata={
                "document_type": "resume",
                "section": section_name,
            },
        )
        all_chunks.extend(chunks)

    logger.info("Resume sections chunked", total_chunks=len(all_chunks))
    return all_chunks
