# API Reference

Base URL: `http://localhost:8000` (dev) or your Railway URL (prod)

---

## `GET /health`

Health check.

**Response**

```json
{ "status": "healthy", "service": "ai-persona-backend", "version": "1.0.0" }
```

---

## `POST /api/chat`

Send a message and receive a RAG-grounded response.

**Request**

```json
{
  "message": "Tell me about your RAG experience.",
  "conversation_id": "uuid-optional",
  "conversation_history": [
    { "role": "user", "content": "Hi" },
    { "role": "assistant", "content": "Hello! How can I help?" }
  ]
}
```

**Response**

```json
{
  "message": "I have X years of experience building RAG systems...",
  "sources": [
    {
      "content": "Resume excerpt...",
      "source": "resume:experience",
      "relevance_score": 0.87
    }
  ],
  "conversation_id": "uuid",
  "booking_link": "https://cal.com/username",
  "available_slots": [
    {
      "start": "2024-03-15T14:00:00Z",
      "end": "2024-03-15T14:30:00Z",
      "formatted": "Fri Mar 15 · 2:00 PM"
    }
  ],
  "timezone": "America/New_York"
}
```

---

## `POST /api/chat/stream`

Send a message and receive NDJSON events for token-by-token rendering.

**Request**

Same payload as `POST /api/chat`.

**Response (stream, `application/x-ndjson`)**

Each line is one JSON object:

```json
{ "type": "token", "token": "I" }
{ "type": "token", "token": " can" }
{ "type": "token", "token": " help" }
{ "type": "done", "response": { "message": "I can help...", "sources": [] } }
```

Possible event shapes:

- `{"type":"token","token":"..."}` incremental text chunk
- `{"type":"done","response":ChatResponse}` final structured payload (same shape as `/api/chat`)
- `{"type":"error","error":"..."}` streamed error detail

---

## `GET /api/calendar/availability`

Fetch available time slots for the next 7 days.

**Response**

```json
{
  "slots": [
    {
      "start": "2024-03-15T14:00:00Z",
      "end": "2024-03-15T14:30:00Z",
      "formatted": "Fri Mar 15 · 2:00 PM"
    }
  ],
  "booking_link": "https://cal.com/candidate",
  "timezone": "America/New_York"
}
```

---

## `GET /api/persona`

Return public persona metadata used by the chat frontend.

**Response**

```json
{
  "name": "Sarthak Pandey",
  "role": "AI Engineer",
  "booking_link": "https://cal.com/sarthak",
  "github_username": "sarthakpandey",
  "resume_configured": true,
  "voice_enabled": true
}
```

---

## `POST /api/calendar/book`

Book a meeting slot.

**Request**

```json
{
  "name": "Jane Smith",
  "email": "jane@example.com",
  "start_time": "2024-03-15T14:00:00Z",
  "notes": "Interview for AI Engineer role"
}
```

**Response**

```json
{
  "success": true,
  "booking_id": "cal_booking_123",
  "confirmed_time": "2024-03-15T14:00:00Z",
  "message": "Meeting booked! Confirmation sent to jane@example.com"
}
```

---

## `POST /api/voice/vapi/webhook`

Vapi webhook endpoint. Accepts function-call, assistant-request,
end-of-call-report, and status-update event types.
