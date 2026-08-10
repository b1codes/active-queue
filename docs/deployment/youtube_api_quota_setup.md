# YouTube Data API Key & Quota Management Guide

**ActiveQueue Infrastructure Specification §8.4, §10.3 & Risk #3**

---

## 1. Overview & Provider Architecture

ActiveQueue decouples content ingestion logic from content providers using the `ContentProvider` Python Protocol.

In development and local environments, ActiveQueue defaults to `CONTENT_PROVIDER="fixture"`.
In production environments, ActiveQueue sets `CONTENT_PROVIDER="youtube"`, fetching real YouTube metadata using the YouTube Data API v3.

---

## 2. GCP Secret Manager Configuration

The YouTube API Key is managed via GCP Secret Manager (`youtube-api-key-${env}`) and mounted directly into the Cloud Run v2 container environment as `YOUTUBE_API_KEY`:

```bash
# Provision or update the YouTube API key in Secret Manager
gcloud secrets versions add youtube-api-key-prod \
  --data-file=/path/to/youtube_api_key.txt \
  --project=activequeue-prod
```

Cloud Run automatically injects the secret into the container environment:

```hcl
env {
  name = "YOUTUBE_API_KEY"
  value_source {
    secret_key_ref {
      secret  = google_secret_manager_secret.youtube_api_key.secret_id
      version = "latest"
    }
  }
}
```

---

## 3. Production Quota Management & Extension Procedure

### A. Free Tier Quota Limits & Risk #3 Analysis
- Default GCP Free Tier Allocation: **10,000 units / day**.
- YouTube Data API v3 Costs:
  - `playlists.list`: 1 unit / call.
  - `playlistItems.list`: 1 unit / page (50 items / page).
  - `videos.list`: 1 unit / batch (50 video IDs / batch).
- For a 5,000-item playlist:
  - 100 pages of `playlistItems.list` = 100 units.
  - 100 batches of `videos.list` = 100 units.
  - Total per cold sync = **201 units**.
- **Free Tier Capacity**: ~50 cold syncs per day (suitable for private beta, insufficient for public launch).

### B. Quota Extension Request Step-by-Step
To scale past private beta, request a YouTube Data API quota increase via GCP Console:

1. Navigate to **GCP Console → APIs & Services → YouTube Data API v3 → Quotas**.
2. Click **EDIT QUOTAS** on `Queries per day`.
3. Fill out the **YouTube API Services Audit Form**:
   - Application Name: `ActiveQueue`
   - Use Case: Time-boxed activity queue content matching.
   - Requested Daily Quota: `1,000,000 units / day` (supports ~5,000 cold syncs / day).
   - Compliance: Explain ActiveQueue store-and-refresh caching model (`full_walk_interval_days = 7`), which minimizes API calls and respects YouTube Terms of Service.
4. Submit request (typical turnaround time: 3–5 business days).

---

## 4. Quota Exhaustion Degradation Behavior

Per **SPEC §8.3**, if the daily quota is exhausted (HTTP 403 `quotaExceeded`), ActiveQueue backend automatically gracefully degrades:
1. Sets source status to `quota_paused`.
2. Preserves the `next_page_token` cursor intact in Firestore.
3. Continues serving cached feed items to clients without error (`GET /feed` remains 100% operational).
4. Resumes background sync automatically on daily quota reset at 00:00 PST.
