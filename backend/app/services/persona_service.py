"""Persona configuration and context management."""

import structlog
import yaml
from pathlib import Path
from typing import Any, Dict

logger = structlog.get_logger()


class PersonaService:
    """Manages persona configuration and context."""

    def __init__(self, config_path: str = "data/persona_config.yaml"):
        self.config_path = self._resolve_config_path(config_path)
        self.config = self._load_config()

    @staticmethod
    def _resolve_config_path(config_path: str) -> Path:
        """Resolve config path independent of process working directory."""
        raw = Path(config_path)
        if raw.is_absolute() or raw.exists():
            return raw

        backend_root = Path(__file__).resolve().parents[2]
        candidate = backend_root / raw
        if candidate.exists():
            return candidate

        return raw

    def _load_config(self) -> Dict[str, Any]:
        """Load persona configuration from YAML."""
        if not self.config_path.exists():
            logger.warning("Persona config not found, using defaults")
            return self._default_config()

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        logger.info("Persona config loaded")
        return config

    def _default_config(self) -> Dict[str, Any]:
        """Default persona configuration."""
        return {
            "name": "Your Name",
            "role": "AI/ML Engineer",
            "personality": {
                "tone": "professional yet approachable",
                "style": "specific and detailed",
                "honesty": "always honest, never fabricates",
            },
            "key_strengths": [],
            "target_role": "AI Engineer",
        }

    def get_persona_context(self) -> str:
        """Get persona context string for prompts."""
        config = self.config
        return f"""
Persona: {config['name']}
Role: {config['role']}
Tone: {config['personality']['tone']}
Key Strengths: {', '.join(config.get('key_strengths', []))}
Target Role: {config.get('target_role', 'AI Engineer')}
"""
