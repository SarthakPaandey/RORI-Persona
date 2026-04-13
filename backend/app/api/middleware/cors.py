"""CORS configuration helpers.

The app applies CORS in ``app.main`` via FastAPI's ``CORSMiddleware``.
Use this module to centralize allowed-origin lists if you split configuration.
"""

from app.config import Settings


def build_cors_origins(settings: Settings) -> list[str]:
    """Return origins allowed for browser clients."""
    origins = {
        settings.frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    }
    return sorted(origin for origin in origins if origin)
