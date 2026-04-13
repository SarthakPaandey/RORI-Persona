export type MessageRole = 'user' | 'assistant';

export interface Source {
  content: string;
  source: string;
  relevance_score: number;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  sources: Source[];
  bookingLink?: string;
  availableSlots?: TimeSlot[];
  timezone?: string;
  timestamp: Date;
}

export interface ConversationMessage {
  role: MessageRole;
  content: string;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  conversation_history?: ConversationMessage[];
  timezone?: string;
}

export interface ChatResponse {
  message: string;
  sources: Source[];
  conversation_id?: string;
  booking_link?: string;
  available_slots?: TimeSlot[];
  timezone?: string;
}

export interface TimeSlot {
  start: string;
  end: string;
  formatted: string;
}

export interface AvailabilityResponse {
  slots: TimeSlot[];
  booking_link: string;
  timezone: string;
}

export interface BookingRequest {
  name: string;
  email: string;
  start_time: string;
  timezone?: string;
  notes?: string;
}

export interface BookingResponse {
  success: boolean;
  booking_id?: string;
  confirmed_time?: string;
  message: string;
}

export interface PersonaResponse {
  name: string;
  role: string;
  booking_link: string;
  github_username: string;
  resume_configured: boolean;
  voice_enabled: boolean;
}
