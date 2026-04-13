"""Resume path resolution."""

from pathlib import Path

import pytest

from app.utils.resume_path import resolve_resume_pdf_path, resume_is_configured


@pytest.fixture
def tmp_data(tmp_path: Path):
    d = tmp_path / "data"
    d.mkdir()
    return d


def test_resolve_explicit_resume_file(tmp_data, monkeypatch):
    (tmp_data / "a.pdf").write_bytes(b"%PDF-1.4")
    cfg = tmp_data / "persona_config.yaml"
    cfg.write_text('resume_file: "a.pdf"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_data.parent)
    p = resolve_resume_pdf_path(str(tmp_data))
    assert p is not None
    assert p.name == "a.pdf"


def test_resolve_default_resume_pdf(tmp_data, monkeypatch):
    (tmp_data / "resume.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.chdir(tmp_data.parent)
    p = resolve_resume_pdf_path(str(tmp_data))
    assert p is not None
    assert p.name == "resume.pdf"


def test_resolve_single_pdf_in_folder(tmp_data, monkeypatch):
    (tmp_data / "only.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.chdir(tmp_data.parent)
    p = resolve_resume_pdf_path(str(tmp_data))
    assert p is not None
    assert p.name == "only.pdf"


def test_resume_is_configured_true(tmp_data, monkeypatch):
    (tmp_data / "resume.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.chdir(tmp_data.parent)
    assert resume_is_configured(str(tmp_data)) is True
