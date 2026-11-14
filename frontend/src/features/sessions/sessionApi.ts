import { apiClient } from '../../core/api/apiClient';

export interface Session {
  id: string;
  user_id: string;
  activity_id: string;
  match_mode: 'content_first' | 'time_first';
  content_id?: string | null;
  duration_seconds: number;
  status: 'pending' | 'in_progress' | 'completed' | 'abandoned';
  checklist_completed: boolean;
  started_at?: string | null;
  completed_at?: string | null;
  abandoned_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateSessionInput {
  activity_id: string;
  match_mode: 'content_first' | 'time_first';
  content_id?: string | null;
  target_duration_seconds?: number | null;
}

export async function createSession(input: CreateSessionInput): Promise<Session> {
  return apiClient<Session>('/api/v1/sessions', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export async function startSession(sessionId: string): Promise<Session> {
  return apiClient<Session>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/start`, {
    method: 'POST',
  });
}

export async function getActiveSession(): Promise<Session | null> {
  return apiClient<Session | null>('/api/v1/sessions/active');
}

export interface SessionListResponse {
  items: Session[];
  next_cursor: string | null;
}

export async function completeSession(sessionId: string): Promise<Session> {
  return apiClient<Session>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/complete`, {
    method: 'POST',
  });
}

export async function abandonSession(sessionId: string): Promise<Session> {
  return apiClient<Session>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/abandon`, {
    method: 'POST',
  });
}

export async function discardSession(sessionId: string): Promise<void> {
  await apiClient(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' });
}

export async function listSessions(cursor?: string | null): Promise<SessionListResponse> {
  const query = cursor ? `&cursor=${encodeURIComponent(cursor)}` : '';
  return apiClient<SessionListResponse>(`/api/v1/sessions?limit=20${query}`);
}
