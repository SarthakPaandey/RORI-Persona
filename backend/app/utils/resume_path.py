"""Resolve which PDF in ``data/`` is the resume."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import yaml

logger = structlog.get_logger()

DEFAULT_RESUME_NAME = "resume.pdf"
CONFIG_NAME = "persona_config.yaml"


def _resolve_data_dir(data_dir: str | Path) -> Path:
    """Resolve data directory independent of process working directory."""
    root = Path(data_dir)
    if root.is_absolute() or root.is_dir():
        return root

    backend_root = Path(__file__).resolve().parents[2]
    candidate = backend_root / root
    if candidate.is_dir():
        return candidate

    return root


def _load_yaml_config(data_dir: Path) -> dict[str, Any]:
    path = data_dir / CONFIG_NAME
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
            return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        logger.warning("Could not read persona config", path=str(path), error=str(exc))
        return {}


def resolve_resume_pdf_path(data_dir: str | Path = "data") -> Path | None:
    """
    Pick the resume PDF to use.

    1. ``resume_file`` in ``data/persona_config.yaml`` (filename under ``data/``)
    2. ``data/resume.pdf`` if it exists
    3. If exactly one ``*.pdf`` exists in ``data/``, use it
    4. If multiple PDFs exist and none of the above matched, return ``None``
    """
    root = _resolve_data_dir(data_dir)
    if not root.is_dir():
        return None

    cfg = _load_yaml_config(root)
    explicit = cfg.get("resume_file")
    if isinstance(explicit, str) and explicit.strip():
        candidate = root / explicit.strip()
        if candidate.is_file():
            return candidate
        logger.warning(
            "persona_config resume_file not found",
            resume_file=explicit,
            expected=str(candidate),
        )

    default = root / DEFAULT_RESUME_NAME
    if default.is_file():
        return default

    pdfs = sorted(root.glob("*.pdf"))
    if len(pdfs) == 1:
        logger.info("Using single PDF in data/ as resume", path=str(pdfs[0]))
        return pdfs[0]

    if len(pdfs) > 1:
        logger.warning(
            "Multiple PDFs in data/ — set resume_file in persona_config.yaml",
            files=[p.name for p in pdfs],
        )
    return None


def resume_is_configured(data_dir: str | Path = "data") -> bool:
    """Whether a resume PDF path can be resolved (file exists)."""
    p = resolve_resume_pdf_path(data_dir)
    return p is not None and p.is_file()
