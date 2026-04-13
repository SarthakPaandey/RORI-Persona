# Detailed Setup Instructions

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | python.org |
| Node.js | 20+ | nodejs.org |
| npm | 9+ | bundled with Node |

## Step-by-step

### 1. Clone and configure

```bash
git clone <your-repo-url> ai-persona
cd ai-persona
cp .env.example .env
```

Open `.env` and fill in every key. See the table below.

Latency tip: set `LLM_PROVIDER_ORDER=groq,nvidia,modelscope,openai` to try Groq first for faster chat generation.
For burst traffic/rate limits, set `GROQ_API_KEYS` (comma-separated backup keys) and
`GROQ_MODEL_CANDIDATES=llama-3.3-70b-versatile` while keeping
`GROQ_MODEL=llama-3.1-8b-instant` as the low-latency primary.
If streaming feels stuck before first token, set `LLM_STREAM_FIRST_TOKEN_TIMEOUT_SECONDS=6`
to fail over quickly to the next provider/model.

### 2. API Keys you need

**Stack option — Groq + ModelScope (no OpenAI):** set `GROQ_API_KEY`, `EMBEDDING_API_BASE`, `EMBEDDING_API_KEY`, `OPENAI_EMBEDDING_MODEL` (e.g. Qwen), and `PINECONE_EMBEDDING_DIMENSION` (e.g. 4096). Leave `OPENAI_API_KEY` empty.

| Key | Where to get it |
|-----|----------------|
| `OPENAI_API_KEY` | Optional if using Groq + ModelScope; otherwise platform.openai.com |
| `GROQ_API_KEY` | console.groq.com |
| `EMBEDDING_API_BASE` / `EMBEDDING_API_KEY` | ModelScope inference API (OpenAI-compatible embeddings) |
| `PINECONE_API_KEY` | app.pinecone.io → API Keys |
| `PINECONE_INDEX_NAME` | Choose any name, e.g. `ai-persona` |
| `VAPI_API_KEY` | dashboard.vapi.ai → API Keys |
| `VAPI_PHONE_NUMBER_ID` | Buy a number in Vapi dashboard |
| `CALCOM_API_KEY` | cal.com → Settings → Developer → API Keys |
| `CALCOM_EVENT_TYPE_ID` | Cal.com → Event Types → click your event → URL has the ID |
| `CALCOM_USERNAME` | Your cal.com username |
| `GITHUB_TOKEN` | github.com → Settings → Developer settings → Personal access tokens |
| `GITHUB_USERNAME` | Your GitHub username |
| `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API Key |
| `ELEVENLABS_VOICE_ID` | elevenlabs.io → Voices → click a voice → copy ID from URL |
| `CHAT_URL` | Your deployed frontend URL, used by the voice assistant sign-off |

### 3. Install dependencies

```bash
bash scripts/setup.sh
```

### 4. Place your resume

```
backend/data/resume.pdf   ← your actual resume
```

### 5. Run data ingestion

```bash
make ingest
# or: cd backend && python -m app.ingestion.run_ingestion
```

This parses your resume and fetches all your public GitHub repos,
then embeds them into Pinecone. Takes ~2 minutes on first run.

### 6. Start the application

```bash
# Option A: Docker (recommended)
docker-compose up --build

# Option B: Manual
make run-backend   # terminal 1
make run-frontend  # terminal 2
```

Visit http://localhost:3000 to test the chat interface.

### 7. Set up the voice agent

```bash
cd voice
python setup_vapi.py
```

This registers your assistant on Vapi and assigns it to your phone number.
The script templates the assistant name, role, voice ID, backend webhook URL,
and chat URL from your environment variables before creating the assistant.

### 8. Test everything

```bash
# Chat + booking tests
make eval

# Voice webhook tests
cd voice && python test_voice.py --url http://localhost:8000
```

## Deployment

```bash
bash scripts/deploy.sh
```

See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for infrastructure details.
