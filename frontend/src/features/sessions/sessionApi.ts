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
  return apiClient<Session>(`/api/v1/sessions/${sessionId}/start`, {
    method: 'POST',
  });
}
