"""Tests for the ingestion pipeline."""

from app.ingestion.chunking import chunk_resume_sections, chunk_text


def test_chunk_text_produces_chunks():
    text = "This is a test document. " * 100
    chunks = chunk_text(text, source="test:doc", chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
    assert all(len(c.page_content) <= 250 for c in chunks)


def test_chunk_text_preserves_metadata():
    text = "Some content here."
    chunks = chunk_text(
        text,
        source="resume:experience",
        chunk_size=512,
        chunk_overlap=50,
        metadata={"section": "experience", "document_type": "resume"},
    )
    for chunk in chunks:
        assert chunk.metadata["source"] == "resume:experience"
        assert chunk.metadata["section"] == "experience"


def test_chunk_resume_sections_skips_short():
    sections = [
        {"section": "header", "content": "Hi"},
        {"section": "experience", "content": "Engineer at Company X. " * 30},
    ]
    chunks = chunk_resume_sections(sections, chunk_size=200, chunk_overlap=20)
    sources = [c.metadata["source"] for c in chunks]
    assert not any("header" in s for s in sources)
    assert any("experience" in s for s in sources)


def test_chunk_resume_sections_section_metadata():
    sections = [
        {
            "section": "skills",
            "content": "Python, TypeScript, LangChain, Pinecone. " * 10,
        },
    ]
    chunks = chunk_resume_sections(sections)
    assert all(c.metadata["document_type"] == "resume" for c in chunks)
