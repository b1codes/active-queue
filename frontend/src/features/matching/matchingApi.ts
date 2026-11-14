import { apiClient } from '@/core/api/apiClient';
import type { FeedItem } from '@/features/queue/types';

export interface Activity {
  id: string;
  name: string;
  category: string;
  tracker: string;
  min_duration_seconds: number;
  max_duration_seconds: number;
  default_duration_seconds: number;
  icon_name: string;
  is_active: boolean;
}

export interface TimeBlock {
  id: string;
  label: string;
  duration_seconds: number;
  description?: string | null;
}

export interface ContentMatchResult {
  content_id: string;
  duration_seconds: number;
  duration_label: string;
  matching_activities: Activity[];
  is_valid: boolean;
  rejection_reason: 'duration_out_of_range' | 'no_matching_activity' | null;
}

export interface TimeMatchResult {
  target_duration_seconds: number;
  target_duration_label: string;
  matched_items: FeedItem[];
  window_type: 'primary' | 'fallback' | null;
  is_valid: boolean;
  rejection_reason: 'no_content_in_window' | null;
}

export async function listActivities(): Promise<Activity[]> {
  const data = await apiClient<{ activities: Activity[] }>('/api/v1/activities');
  return data.activities;
}

export async function listTimeBlocks(): Promise<TimeBlock[]> {
  const data = await apiClient<{ time_blocks: TimeBlock[] }>('/api/v1/activities/time-blocks');
  return data.time_blocks;
}

/** Content-first: which catalog activities fit this item's duration (SPEC §5.2). */
export async function matchContent(contentId: string): Promise<ContentMatchResult> {
  return apiClient<ContentMatchResult>('/api/v1/content/match', {
    method: 'POST',
    body: JSON.stringify({ content_id: contentId }),
  });
}

/** Time-first: which queued items fit a time block (SPEC §5.3 asymmetric windows). */
export async function matchTimeBlock(targetSeconds: number): Promise<TimeMatchResult> {
  return apiClient<TimeMatchResult>('/api/v1/content/match-time', {
    method: 'POST',
    body: JSON.stringify({ target_duration_seconds: targetSeconds }),
  });
}
