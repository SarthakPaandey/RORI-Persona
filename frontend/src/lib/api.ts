import {
  AvailabilityResponse,
  BookingRequest,
  BookingResponse,
  ChatRequest,
  ChatResponse,
  PersonaResponse,
} from './types';

/**
 * Base URL for the FastAPI backend.
 * - In local browser dev, prefer talking to FastAPI directly to avoid occasional
 *   Next.js dev proxy socket resets on long-running chat requests.
 * - Set `NEXT_PUBLIC_API_URL` to force a specific browser URL.
 * - On the server (SSR/tests), use `BACKEND_URL` or `NEXT_PUBLIC_API_URL` or localhost.
 * - In production browser usage, default to same-origin so deployed rewrites still work.
 */
function getLocalBrowserBackendUrl(): string {
  if (globalThis.window === undefined) return '';

  const hostname = globalThis.window.location.hostname;
  if (!['localhost', '127.0.0.1'].includes(hostname)) return '';

  const frontendPort = globalThis.window.location.port;
  const backendPort = frontendPort === '3001' ? '8001' : '8000';
  return `http://${hostname}:${backendPort}`;
}

function getApiBase(): string {
  const publicUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (globalThis.window !== undefined) {
    if (publicUrl) return publicUrl;
    if (process.env.NODE_ENV === 'development') {
      const localBackend = getLocalBrowserBackendUrl();
      if (localBackend) return localBackend;
    }
    return '';
  }
  return publicUrl || process.env.BACKEND_URL?.trim() || 'http://127.0.0.1:8000';
}

function getBrowserTimezone(): string {
  if (globalThis.window === undefined) return '';
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || '';
  } catch {
    return '';
  }
}

async function fetchJSON<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${getApiBase()}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

const CHAT_TIMEOUT_MS = 120_000;

export type ChatStreamEvent =
  | { type: 'token'; token: string }
  | { type: 'done'; response: ChatResponse }
  | { type: 'error'; error: string };

export async function sendChatMessage(
  payload: ChatRequest
): Promise<ChatResponse> {
  return fetchJSON<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(CHAT_TIMEOUT_MS),
  });
}

function parseStreamEventLine(line: string): ChatStreamEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed) as ChatStreamEvent;
  } catch {
    return null;
  }
}

export async function streamChatMessage(
  payload: ChatRequest,
  onEvent?: (event: ChatStreamEvent) => void
): Promise<ChatResponse> {
  const res = await fetch(`${getApiBase()}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(CHAT_TIMEOUT_MS),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }

  if (!res.body) {
    throw new Error('Streaming response body is unavailable');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse: ChatResponse | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    let newlineIndex = buffer.indexOf('\n');
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex);
      buffer = buffer.slice(newlineIndex + 1);

      const event = parseStreamEventLine(line);
      if (event) {
        onEvent?.(event);
        if (event.type === 'done') {
          finalResponse = event.response;
        }
        if (event.type === 'error') {
          throw new Error(event.error || 'Streaming chat failed');
        }
      }

      newlineIndex = buffer.indexOf('\n');
    }
  }

  const remaining = (buffer + decoder.decode()).trim();
  if (remaining) {
    const event = parseStreamEventLine(remaining);
    if (event) {
      onEvent?.(event);
      if (event.type === 'done') finalResponse = event.response;
      if (event.type === 'error') {
        throw new Error(event.error || 'Streaming chat failed');
      }
    }
  }

  if (!finalResponse) {
    throw new Error('Chat stream ended without a final response');
  }

  return finalResponse;
}

export async function getAvailability(): Promise<AvailabilityResponse> {
  const timezone = getBrowserTimezone();
  const query = timezone ? `?timezone=${encodeURIComponent(timezone)}` : '';
  return fetchJSON<AvailabilityResponse>(`/api/calendar/availability${query}`);
}

export async function bookMeeting(
  payload: BookingRequest
): Promise<BookingResponse> {
  const timezone = payload.timezone || getBrowserTimezone();
  return fetchJSON<BookingResponse>('/api/calendar/book', {
    method: 'POST',
    body: JSON.stringify({ ...payload, timezone: timezone || undefined }),
  });
}

export async function healthCheck(): Promise<{ status: string }> {
  return fetchJSON<{ status: string }>('/health');
}

export async function getPersona(): Promise<PersonaResponse> {
  return fetchJSON<PersonaResponse>('/api/persona');
}
