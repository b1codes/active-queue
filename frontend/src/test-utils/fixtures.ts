import type { FeedItem, Source } from '@/features/queue/types';
import type { Session } from '@/features/sessions/sessionApi';
import type { Activity, TimeBlock } from '@/features/matching/matchingApi';

export function feedItem(n: number, overrides: Partial<FeedItem> = {}): FeedItem {
  return {
    id: `u1_fx:fx_vid_${n}`,
    content_id: `fx:fx_vid_${n}`,
    source_id: 'u1_fixture_pl',
    title: `Fixture Workout Video #${n}`,
    provider: 'fixture',
    external_id: `fx_vid_${n}`,
    duration_seconds: 1500,
    duration_label: '25m 0s',
    published_at: '2026-01-01T00:00:00Z',
    thumbnail_url: null,
    video_url: `https://www.youtube.com/watch?v=fx_vid_${n}`,
    consumed: false,
    ...overrides,
  };
}

export function source(overrides: Partial<Source> = {}): Source {
  return {
    id: 'u1_fixture_pl',
    user_id: 'u1',
    provider: 'fixture',
    external_source_id: 'pl',
    title: 'Morning Runs',
    description: null,
    item_count: 14,
    thumbnail_url: null,
    status: 'active',
    last_sync_at: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

export function session(overrides: Partial<Session> = {}): Session {
  return {
    id: 's_0001',
    user_id: 'u1',
    activity_id: 'running',
    match_mode: 'content_first',
    content_id: 'yt:abc123',
    duration_seconds: 1800,
    status: 'pending',
    checklist_completed: false,
    started_at: null,
    completed_at: null,
    abandoned_at: null,
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
    ...overrides,
  };
}

export function activity(id: string, min = 300, max = 14400, name?: string): Activity {
  return {
    id,
    name: name ?? id[0].toUpperCase() + id.slice(1),
    category: 'cardio',
    tracker: 'apple_fitness',
    min_duration_seconds: min,
    max_duration_seconds: max,
    default_duration_seconds: 1800,
    icon_name: 'run',
    is_active: true,
  };
}

export const TIME_BLOCKS: TimeBlock[] = [900, 1200, 1800, 2700, 3600, 4500, 5400].map((s) => ({
  id: `tb_${s / 60}m`,
  label: `${s / 60} min`,
  duration_seconds: s,
  description: null,
}));
