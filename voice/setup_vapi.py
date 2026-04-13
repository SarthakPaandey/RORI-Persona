#!/usr/bin/env python3
"""
Creates or updates the Vapi assistant using the modern Tools API.
Run once to register tools, attach them to the assistant, and assign the phone number.

Usage:
    cd voice
    python setup_vapi.py
"""

import json
import os
import sys
import httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

VAPI_API_BASE = "https://api.vapi.ai"
VAPI_API_KEY = os.getenv("VAPI_API_KEY")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CHAT_URL = os.getenv("CHAT_URL", os.getenv("FRONTEND_URL", "http://localhost:3000"))
PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")
EXISTING_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "")
PERSONA_NAME = os.getenv("PERSONA_NAME", "AI Candidate")
PERSONA_ROLE = os.getenv("PERSONA_ROLE", "AI Engineer")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
VAPI_MODEL = os.getenv("VAPI_MODEL", "llama-3.1-8b-instant")

WEBHOOK_URL = f"{BACKEND_URL}/api/voice/vapi/webhook"

# ── Tool definitions (new Vapi Tools API format) ──────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_background_info",
            "description": (
                "Retrieve information about background, skills, experience, "
                "or specific GitHub projects. Use this whenever the caller asks "
                "about skills, projects, experience, education, or "
                "'why are you right for this role'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The caller's question, verbatim or paraphrased.",
                    }
                },
                "required": ["question"],
            },
        },
        "server": {"url": WEBHOOK_URL},
    },
    {
        "type": "function",
        "function": {
            "name": "get_availability",
            "description": (
                "Fetch real calendar availability for the next 7 days. "
                "Use this when the caller asks about scheduling, availability, "
                "or wants to book. Pass the caller's scheduling request verbatim "
                "in request so the backend can filter the options."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "request": {
                        "type": "string",
                        "description": (
                            "The caller's scheduling request in natural language, "
                            "for example 'after 5 PM on April fifteenth'."
                        ),
                    }
                },
            },
        },
        "server": {"url": WEBHOOK_URL},
    },
    {
        "type": "function",
        "function": {
            "name": "book_meeting",
            "description": (
                "Book a meeting on the calendar. Only call this after the caller "
                "confirms one exact slot from get_availability. Always pass the "
                "caller's exact confirmation words in selection. Do not invent a "
                "new date if the caller only repeats a time range."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "datetime": {
                        "type": "string",
                        "description": (
                            "ISO 8601 datetime string for the meeting start time, "
                            "but only when you are certain of the exact slot."
                        ),
                    },
                    "selection": {
                        "type": "string",
                        "description": (
                            "The caller's exact confirmation phrase, for example "
                            "'book it from 5:30 PM to 6 PM'."
                        ),
                    },
                },
            },
        },
        "server": {"url": WEBHOOK_URL},
    },
    {
        "type": "function",
        "function": {
            "name": "get_github_info",
            "description": (
                "Get detailed information about a specific GitHub repository — "
                "tech stack, purpose, architecture decisions, and tradeoffs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_name": {
                        "type": "string",
                        "description": "The repository name as it appears on GitHub.",
                    },
                    "question": {
                        "type": "string",
                        "description": "The specific question about the repo.",
                    },
                },
                "required": ["repo_name"],
            },
        },
        "server": {"url": WEBHOOK_URL},
    },
]


def get_headers():
    return {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json",
    }


def list_existing_tools(client: httpx.Client) -> list:
    """List all tools in the account."""
    res = client.get(f"{VAPI_API_BASE}/tool", headers=get_headers(), timeout=20)
    res.raise_for_status()
    return res.json()


def delete_tool(client: httpx.Client, tool_id: str):
    """Delete a tool by ID."""
    res = client.delete(
        f"{VAPI_API_BASE}/tool/{tool_id}", headers=get_headers(), timeout=20
    )
    res.raise_for_status()


def create_tool(client: httpx.Client, tool_def: dict) -> dict:
    """Create a new tool via the Vapi API."""
    res = client.post(
        f"{VAPI_API_BASE}/tool",
        headers=get_headers(),
        json=tool_def,
        timeout=20,
    )
    res.raise_for_status()
    return res.json()


def create_or_replace_tools(client: httpx.Client) -> list:
    """
    Delete any existing tools whose function name matches ours,
    then create fresh ones. Returns a list of tool IDs.
    """
    our_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}

    existing = list_existing_tools(client)
    for tool in existing:
        fn = tool.get("function", {})
        if fn.get("name") in our_names:
            print(f"  Deleting old tool: {fn['name']} ({tool['id']})")
            delete_tool(client, tool["id"])

    tool_ids = []
    for tool_def in TOOL_DEFINITIONS:
        created = create_tool(client, tool_def)
        fn_name = created.get("function", {}).get("name", "?")
        print(f"  Created tool: {fn_name} → {created['id']}")
        tool_ids.append(created["id"])

    return tool_ids


def build_assistant_config(tool_ids: list) -> dict:
    """Build the assistant JSON using the new toolIds model field."""
    profile_context = """
CAPTAIN SARTHAK PANDEY — FULL PROFILE (answer any question from this):

Role target: AI/ML Engineer (Scaler and similar AI-first companies)
Education: Bachelor of Science in CS, Scaler School Of Technology, enrolled 2023 (Scaler AI/ML Program)

TECHNICAL SKILLS:
- Languages: Python (production async typed), TypeScript, JavaScript
- AI/ML: RAG pipelines, LLM APIs (OpenAI, Groq, NVIDIA NIM), LangChain, LangGraph, LlamaIndex
- Voice AI: Vapi, ElevenLabs, Deepgram (built the voice assistant RORI — you)
- Vector DBs: Pinecone, Chroma, Weaviate
- Full-stack: FastAPI, Next.js, React, PostgreSQL, MongoDB
- Cloud/Infra: Railway, Vercel, Docker, GitHub Actions

KEY PROJECTS:
• FinTracker — AI personal finance app built with Next.js for tracking expenses and budgets with AI-driven insights
• SSTBORROWING — Unified campus booking system for facilities and equipment with QR-based check-ins and automated penalty management
• MrBully — Android accountability app using AI interventions and strict phrase-based unlocks to stop distractions
• Tradinguiz — Flutter-based mobile quiz application with a Golang backend for interactive multiple-choice quizzes
• StoryTeller — Interactive web-based storytelling game where AI generates stories and users choose options to progress
• AnonymChat — Real-time anonymous chat app built with React, MUI, and Firebase for secure, private communication
• portfolio — AI persona site with voice agent + RAG chatbot (this system you are running)

WHY HE IS THE RIGHT FIT:
• Shipped production AI agents to real users — not notebooks, real deployments
• Built complete RAG pipeline from scratch (Pinecone + LangChain + streaming)
• Built this voice AI system using Vapi + ElevenLabs + Deepgram — proof of skill
• Production-quality async Python — exactly what AI engineering roles need
• Hands-on with LLM APIs, function calling, context management, and cost optimization
• Experience with agentic systems: multi-step reasoning, tool calling, autonomous workflows
• Scaler AI/ML student — knows the platform, learner journey, and culture from the inside
• Ships fast under real constraints — this entire persona system is live in production today
"""

    system_prompt = (
        f"You are RORI, Captain {PERSONA_NAME}'s loyal ship AI.\n\n"
        f'If asked who you are, answer briefly: "I am RORI, Captain {PERSONA_NAME}\'s loyal ship AI."\n'
        "Do not repeat that line unless the caller explicitly asks your identity again.\n\n"
        "Keep responses to 2-3 sentences for voice. Be warm, specific, and confident.\n\n"
        + profile_context
        + "\n\nIMPORTANT RULES:\n"
        "1. You already have the profile above — answer directly from it for any basic question "
        "(skills, role fit, experience, general project overview). DO NOT call a tool for these.\n"
        "2. Only call get_background_info if the user asks a very specific detailed question "
        "not covered by the profile above (e.g. exact dates, a specific resume bullet).\n"
        "3. Only call get_github_info if the user asks for technical deep-dive on ONE specific repo.\n"
        "4. Only call get_availability or book_meeting for scheduling requests.\n"
        "5. NEVER call the same tool more than once per turn. One call to get_availability returns "
        "ALL available slots for 7 days — there is no reason to call it again. If a tool errors, "
        "answer from the profile or offer the cal.com link.\n"
        "6. CRITICAL: Call get_availability EXACTLY ONCE per scheduling request. It returns the "
        "full 7-day schedule. Pass the user's scheduling words in the request field so the backend "
        "can filter. Do NOT call it multiple times for different days or time ranges.\n"
        "7. For booking: call get_availability once, review the slots, suggest matching ones, "
        "and ask the caller to confirm one. When they confirm, pass their exact words in selection.\n"
        "8. Do not ask for caller contact details.\n"
        "9. If the user says vague time ranges like 'tomorrow after 3 PM', call get_availability "
        "ONCE, filter the results yourself, offer matching slots, and ask them to confirm one. "
        "Do NOT call book_meeting until the caller confirms a specific slot.\n"
        "10. Use 'he'/'his' for the Captain, never 'they'/'their'.\n"
        "11. Avoid repeating your identity sentence in normal replies.\n"
        "12. If an utterance sounds unclear or ambiguous, ask one short clarification question.\n"
        "13. Handle follow-ups naturally and conversationally, not as scripted Q&A.\n"
        "14. Never promise reminders, emails, or meeting links unless a tool explicitly returned that information.\n"
    )

    return {
        "name": f"AI Persona - {PERSONA_NAME}",
        "model": {
            "provider": "groq",
            "model": VAPI_MODEL,
            "temperature": 0.3,
            "systemPrompt": system_prompt,
            "toolIds": tool_ids,
        },
        "voice": {
            "provider": "11labs",
            "voiceId": ELEVENLABS_VOICE_ID,
            "model": "eleven_flash_v2_5",
            "stability": 0.5,
            "similarityBoost": 0.75,
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-3",
            "language": "en-IN",
        },
        "firstMessage": (
            f"I am RORI, Captain {PERSONA_NAME}'s loyal ship AI. "
            "Ask me about his skills, projects, why he is the right fit for your role, "
            "or let's schedule a meeting."
        ),
        "endCallMessage": (
            f"Thanks for the call! Follow up anytime at {CHAT_URL}. "
            "Have a great day."
        ),
        "endCallPhrases": ["goodbye", "bye", "talk later", "that's all", "thank you bye"],
        "recordingEnabled": True,
        "hipaaEnabled": False,
        "silenceTimeoutSeconds": 20,
        "maxDurationSeconds": 600,
        "backgroundSound": "off",
        "backchannelingEnabled": False,
        "serverUrl": WEBHOOK_URL,
        "analysisPlan": {
            "summaryPrompt": (
                "Summarize this call in 2-3 sentences. Note whether a booking "
                "was made and any key topics discussed."
            ),
            "successEvaluationPrompt": (
                "Did the call end with either (a) a confirmed booking or "
                "(b) the caller getting the information they needed? "
                "Answer 'success' or 'failure' with one sentence of reasoning."
            ),
            "successEvaluationRubric": "PassFail",
            "structuredDataSchema": {
                "type": "object",
                "properties": {
                    "booking_made": {"type": "boolean"},
                    "caller_name": {"type": "string"},
                    "caller_email": {"type": "string"},
                    "topics_discussed": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    }


def create_or_update_assistant(client: httpx.Client, config: dict) -> str:
    """Create or update the Vapi assistant."""
    if EXISTING_ASSISTANT_ID:
        print(f"Updating existing assistant: {EXISTING_ASSISTANT_ID}")
        res = client.patch(
            f"{VAPI_API_BASE}/assistant/{EXISTING_ASSISTANT_ID}",
            headers=get_headers(),
            json=config,
            timeout=20,
        )
    else:
        print("Creating new assistant...")
        res = client.post(
            f"{VAPI_API_BASE}/assistant",
            headers=get_headers(),
            json=config,
            timeout=20,
        )

    res.raise_for_status()
    assistant = res.json()
    assistant_id = assistant["id"]
    print(f"Assistant ID: {assistant_id}")
    return assistant_id


def assign_phone_number(client: httpx.Client, assistant_id: str):
    if not PHONE_NUMBER_ID:
        print("No VAPI_PHONE_NUMBER_ID set — skipping phone assignment.")
        return

    res = client.patch(
        f"{VAPI_API_BASE}/phone-number/{PHONE_NUMBER_ID}",
        headers=get_headers(),
        json={"assistantId": assistant_id},
        timeout=20,
    )
    res.raise_for_status()
    data = res.json()
    print(f"Phone number assigned: {data.get('number', 'unknown')}")


def list_phone_numbers(client: httpx.Client):
    res = client.get(f"{VAPI_API_BASE}/phone-number", headers=get_headers())
    res.raise_for_status()
    numbers = res.json()
    print("\nAvailable phone numbers:")
    for n in numbers:
        print(
            f"  ID: {n['id']}  Number: {n.get('number', 'N/A')}  "
            f"Assistant: {n.get('assistantId', 'unassigned')}"
        )


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not VAPI_API_KEY:
        print("ERROR: VAPI_API_KEY not set in .env")
        sys.exit(1)

    print(f"Backend webhook URL: {WEBHOOK_URL}\n")

    with httpx.Client() as client:
        print("1. Creating tools...")
        tool_ids = create_or_replace_tools(client)
        print(f"   Tool IDs: {tool_ids}\n")

        print("2. Building assistant config...")
        config = build_assistant_config(tool_ids)

        print("3. Pushing assistant to Vapi...")
        assistant_id = create_or_update_assistant(client, config)

        print("\n4. Assigning phone number...")
        assign_phone_number(client, assistant_id)

        list_phone_numbers(client)

    print("\n✅ Vapi setup complete!")
    print(f"   Add to your .env:  VAPI_ASSISTANT_ID={assistant_id}")
