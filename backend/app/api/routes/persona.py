"""Public persona metadata for the chat UI."""

from fastapi import APIRouter, Request

from app.models.schemas import PersonaResponse
from app.services.persona_service import PersonaService
from app.utils.resume_path import resume_is_configured

router = APIRouter()


@router.get("/persona", response_model=PersonaResponse)
async def get_persona(request: Request):
    """Return non-sensitive persona metadata for the frontend."""
    settings = request.app.state.settings
    persona = PersonaService()
    cfg = persona.config
    name = (cfg.get("name") or "").strip() or settings.persona_name
    role = (cfg.get("role") or "").strip() or settings.persona_role

    return PersonaResponse(
        name=name,
        role=role,
        booking_link=f"https://cal.com/{settings.calcom_username}",
        github_username=settings.github_username,
        resume_configured=resume_is_configured("data"),
        voice_enabled=bool(
            settings.vapi_api_key
            and settings.vapi_assistant_id
            and settings.vapi_phone_number_id
        ),
    )
