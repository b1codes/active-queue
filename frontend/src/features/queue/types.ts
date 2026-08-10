export interface FeedItem {
  id: string;
  content_id: string;
  source_id: string;
  title: string;
  provider: string;
  external_id: string;
  duration_seconds: number;
  duration_label: string;
  published_at: string;
  thumbnail_url: string | null;
  video_url: string | null;
  consumed: boolean;
}

export interface FeedResponse {
  items: FeedItem[];
  next_cursor: string | null;
  total_unconsumed: number | null;
}

export interface Source {
  id: string;
  user_id: string;
  provider: string;
  external_source_id: string;
  title: string;
  description: string | null;
  item_count: number | null;
  thumbnail_url: string | null;
  status: string;
  last_sync_at: string | null;
  created_at: string;
}

export interface SyncChunkResponse {
  source_id: string;
  status: string;
  items_synced: number;
  has_more: boolean;
  next_page_token: string | null;
  message: string | null;
}

export interface SyncProgressState {
  isSyncing: boolean;
  sourceId: string | null;
  itemsSyncedTotal: number;
  estimatedTotal: number | null;
  iterationCount: number;
  isCancelled: boolean;
  error: string | null;
}
