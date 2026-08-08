# Engineering Specification: ActiveQueue

**Status:** Draft v1
**Date:** 2026-08-08
**Derives from:** [CONCEPT.md](./CONCEPT.md)
**Entity:** B1Codes LLC Portfolio
**v1 Platform:** iOS first, Android-ready

---

## 1. Purpose & Scope

### 1.1 What this document is

`CONCEPT.md` describes *what* ActiveQueue is. This document describes *what gets built* — the API contracts, data model, state machines, error handling, and boundaries that an implementation plan can be written from directly without further design decisions.

Where `CONCEPT.md` is silent or ambiguous, this spec makes a decision and states it. Where it conflicts with the B1Codes house standards in `.claude/context/`, §14 records the resolution.

### 1.2 v1 scope

v1 is a **thin vertical slice**: one content provider, one verification method, one platform. The data model is designed to accommodate the deferred features without migration, but the deferred code is not written.

| Ref | Feature | v1 | v1.1 | v2 |
|-----|---------|:--:|:----:|:--:|
| A | Content-to-Cardio matcher — YouTube | ✅ | | |
| A | Content-to-Cardio matcher — Spotify | | ✅ | |
| A | Strength "Time Blocks" | ✅ | | |
| B | Orchestrator deep links (media + tracker) | ✅ | | |
| C | Manual completion ("Mark Complete") | ✅ | | |
| C | Apple HealthKit auto-verification | | ✅ | |
| C | External workout URL linking (Strava) | | ✅ | |
| D | Auto-hide on completion | ✅ | | |
| D | Manual swipe-to-hide | ✅ | | |
| E | Gym & Park finder (Google Places) | | | ✅ |

### 1.3 Explicit non-goals for v1

- **No rep/set/weight tracking.** ActiveQueue never becomes a workout logger. It orchestrates and verifies; other apps track.
- **No in-app media playback.** Playback happens in the native YouTube/Spotify app. See §6.1 for why.
- **No in-app workout timer running in background.** iOS background execution limits make a reliable long-running timer expensive and battery-hostile; the media app's own playback *is* the timer.
- **No social, sharing, streaks, or gamification.**
- **No push notifications.**
- **No offline write support.** The app requires network connectivity to create or complete a session.

### 1.4 Success criteria for v1

1. A signed-in user can connect a YouTube playlist and see their unconsumed items with accurate durations.
2. From a selected item, the user can start a session, be handed off to the YouTube app, and return to mark it complete.
3. A completed item never reappears in the feed.
4. p95 latency for `GET /api/v1/feed` ≤ 400 ms (warm), excluding provider sync.
5. All authenticated routes reject unverified, expired, or absent ID tokens.

---

## 2. System Architecture

### 2.1 Components

```
┌──────────────────────────────┐
│  ActiveQueue iOS app         │
│  React Native + Expo Router  │
│  • Firebase Auth SDK (GCIP)  │
│  • expo-linking (deep links) │
└──────────┬───────────────────┘
           │ HTTPS / TLS 1.3
           │ Authorization: Bearer <GCIP ID token>
           ▼
┌──────────────────────────────┐
│  ActiveQueue API             │
│  FastAPI on Cloud Run        │
│  • firebase-admin verify     │
│  • Firestore Admin SDK       │
└─────┬───────────────┬────────┘
      │               │
      ▼               ▼
┌───────────┐   ┌──────────────────┐
│ Firestore │   │ YouTube Data API │
│ (Native)  │   │ v3 (server-side) │
└───────────┘   └──────────────────┘
```

### 2.2 Non-negotiable boundaries

| Boundary | Rule |
|----------|------|
| **Client → Firestore** | Forbidden. The client never reads or writes Firestore directly. Security rules deny all client access (§4.6). All data flows through the API. |
| **Client → YouTube API** | Forbidden. The API key stays server-side; the client never holds a provider credential. |
| **Auth** | The client obtains an ID token from GCIP and does nothing else with it but attach it to requests. Every authorization decision happens server-side. |
| **Router → Service** | Routers contain no business logic. Services contain no HTTP types (no `Request`, `HTTPException`, no status codes). |
| **Service → Repository** | Services never touch the Firestore client directly. Repositories own all query construction. |

The third rule is what makes the service layer testable without a running emulator, and the fourth is what makes the Firestore→(anything else) swap a contained change.

### 2.3 Backend directory layout

Adapted from `.claude/context/003_directory-structure.md`, with SQLAlchemy/Alembic replaced by Firestore repositories (§14.1).

```
api/
├── pyproject.toml
├── Dockerfile
├── app/
│   ├── main.py                     # FastAPI instance, router mounts, lifespan
│   ├── core/
│   │   ├── config.py               # pydantic-settings Settings (single source of truth)
│   │   ├── firestore.py            # AsyncClient factory, emulator wiring
│   │   ├── dependencies.py         # get_current_user, get_db, pagination
│   │   ├── security.py             # verify_id_token wrapper, uid cache
│   │   ├── envelopes.py            # success/error envelope builders
│   │   └── errors.py               # AppError hierarchy + code registry
│   ├── features/
│   │   ├── users/                  # models, schemas, service, repository, router
│   │   ├── content/                # provider adapters, cache, feed
│   │   ├── sessions/
│   │   └── activities/             # static catalog, matching engine
│   ├── providers/
│   │   ├── base.py                 # ContentProvider protocol
│   │   └── youtube.py              # YouTube Data API v3 adapter
│   └── middleware/
│       ├── logging.py              # structlog JSON request logs
│       ├── ratelimit.py            # headers + instance-local limiter
│       └── errors.py               # AppError → error envelope
└── tests/
    ├── conftest.py
    ├── unit/features/…
    └── integration/features/…
```

`models.py` per feature holds Pydantic **domain** models (the Firestore document shape), `schemas.py` holds the **API** request/response shapes. They are deliberately separate types even when currently identical — it prevents a storage change from leaking into the public contract.

### 2.4 Mobile directory layout

Per `.claude/context/024_directory-structure.md` (Expo Router).

```
mobile/
├── app.json                        # incl. LSApplicationQueriesSchemes (§6.3)
├── app/
│   ├── _layout.tsx                 # providers, error boundary
│   ├── (auth)/
│   │   ├── _layout.tsx
│   │   └── sign-in.tsx
│   └── (app)/
│       ├── _layout.tsx             # tabs; redirects unauthenticated → /sign-in
│       ├── index.tsx               # Queue (feed)
│       ├── match/[contentId].tsx   # Activity picker for chosen content
│       ├── blocks.tsx              # Time Blocks entry (time-first matching)
│       ├── session/[id].tsx        # Handoff checklist + Mark Complete
│       ├── history.tsx
│       └── settings.tsx
└── src/
    ├── core/{components,hooks,theme,utils,constants}/
    └── features/
        ├── auth/                   # GCIP sign-in, token attachment
        ├── queue/                  # feed list, swipe-to-hide
        ├── matching/               # activity suggestions
        └── sessions/               # handoff orchestration, AppState tracking
```

---

## 3. Authentication & Authorization

Per `.claude/context/007_identity-platform-guide.md`.

### 3.1 Token flow

```
1. User signs in via @react-native-firebase/auth (Google, Apple).
   → iOS: refresh token persists in Keychain via the SDK's default. Do not override.
2. Client calls getIdToken() before each request (SDK returns cached token,
   auto-refreshing within 5 min of expiry).
3. Client sends: Authorization: Bearer <ID token>
4. Backend middleware calls firebase_admin.auth.verify_id_token(token).
   → Validates RS256 signature, iss, aud, exp. Never hand-rolled.
5. Backend extracts `sub` (the uid) and resolves authorization (§3.2).
6. On 401 with code AUTH_TOKEN_EXPIRED, the client force-refreshes
   (getIdToken(true)) and retries the request exactly once.
```

**Sign in with Apple is mandatory** for the iOS build (App Store requirement when any other social login is offered, and required by the house standard). All login flows route through the shared custom auth domain; `*.firebaseapp.com` must not appear in any production config.

### 3.2 Authorization resolution

The house standard requires a local `user_authorization` table separate from the identity provider. In Firestore this is a top-level collection keyed by `firebase_uid` (§4.4).

```
On each authenticated request:
  → verify_id_token → uid
  → Check in-process TTL cache (60 s, max 1000 entries) for uid
  → On miss: read user_authorization/{uid}
      → If absent: first-login provisioning —
          transactionally create user_authorization/{uid} (role="member",
          is_active=true) AND users/{uid} (empty preferences)
      → Cache the result
  → If is_active is false → 403 ACCOUNT_DISABLED
  → Attach AuthContext(uid, role, is_active) to request state
```

**Why the cache:** without it, every request pays an extra Firestore read (~5–15 ms and a billable operation) to fetch data that changes approximately never. The 60-second TTL bounds the staleness window for a deactivation, which is acceptable for v1's threat model. The cache is per-instance and is not a correctness dependency — a cold instance simply reads through.

Provisioning happens in the **backend**, not in a GCIP Blocking Function. Blocking functions must never write to application storage.

### 3.3 v1 role model

One role: `member`. The `role` field exists because the standard requires it and because admin tooling will need it, but v1 has no role-differentiated behavior. No roles or permissions are stored in GCIP custom claims.

### 3.4 Public routes

Only `GET /api/v1/healthz` is unauthenticated. Everything else requires a valid token.

---

## 4. Data Model (Firestore, Native mode)

### 4.1 Identifier conventions

Content IDs are **namespaced** so a second provider can be added without a migration:

```
yt:<youtube_video_id>       e.g. yt:dQw4w9WgXcQ
sp:<spotify_episode_id>     (v1.1, reserved)
```

The namespace prefix is parsed by `app/features/content/models.py` into `(provider, external_id)`. Nothing downstream of that parse may assume YouTube.

Session and source IDs are Firestore auto-IDs (20-char). All timestamps are Firestore `Timestamp`, serialized to ISO-8601 UTC with millisecond precision in API responses.

### 4.2 `users/{uid}`

Profile and preferences. Extends the `CONCEPT.md` schema.

| Field | Type | Notes |
|-------|------|-------|
| `uid` | string | Mirrors doc ID; the GCIP `sub` claim |
| `email` | string \| null | From the token, for support lookup only |
| `display_name` | string \| null | |
| `preferences` | map | See below |
| `saved_locations` | array\<string\> | Google Place IDs. **v2** — present but unused in v1 |
| `consumed_content_ids` | array\<string\> | Namespaced content IDs |
| `created_at` / `updated_at` | timestamp | |

`preferences` map:

| Key | Type | Default |
|-----|------|---------|
| `preferred_activity_types` | array\<string\> | `[]` (empty = suggest all) |
| `preferred_tracker_app` | string \| null | `null`. One of the §6.3 tracker keys |
| `default_time_block_seconds` | int | `2700` (45 min) |
| `hide_completed` | bool | `true` |

**`consumed_content_ids` size limit.** Firestore caps a document at 1 MiB. At ~16 bytes per entry, the array is safe to roughly 60,000 items, but a large array is rewritten in full on every `arrayUnion` and inflates every read of the user document. **Migration trigger: at 5,000 entries, move to a `users/{uid}/consumed/{contentId}` subcollection.** The repository must expose consumption checks behind `is_consumed(uid, content_id)` / `mark_consumed(uid, content_id)` so this move touches one file. v1 ships the array.

### 4.3 `sessions/{sessionId}`

Extends the `CONCEPT.md` schema with the fields the state machine (§7) requires.

| Field | Type | Notes |
|-------|------|-------|
| `session_id` | string | Mirrors doc ID |
| `user_id` | string | GCIP uid |
| `content_id` | string \| null | Namespaced. Null for a bare time block |
| `content_title` | string \| null | Denormalized at creation — the feed item may be gone later |
| `content_duration_seconds` | int | 300 ≤ n ≤ 10800 |
| `activity_type` | string | Key from the §5.1 catalog |
| `activity_label` | string | Denormalized display label |
| `tracker_app` | string \| null | Key from §6.3, captured at creation |
| `match_mode` | string | `content_first` \| `time_first` |
| `status` | string | `created` \| `in_progress` \| `completed` \| `abandoned` |
| `created_at` | timestamp | |
| `started_at` | timestamp \| null | Set when the first deep link fires |
| `completed_at` | timestamp \| null | Per `CONCEPT.md` |
| `external_workout_url` | string \| null | **v1.1.** Strava/Strong link |
| `healthkit_uuid` | string \| null | **v1.1.** Apple Health verification |
| `verification` | string | `manual` \| `healthkit` \| `external_url`. v1 always `manual` |

`external_workout_url`, `healthkit_uuid`, and the non-`manual` verification values are written into the schema now and rejected by the v1 API (`FEATURE_NOT_AVAILABLE`) so that v1.1 adds behavior without changing the document shape.

### 4.4 `user_authorization/{uid}`

Required by the house Identity Platform standard. Deliberately separate from `users/{uid}`: authorization is read on every request and must not be coupled to the churn of profile/preferences writes.

| Field | Type |
|-------|------|
| `firebase_uid` | string (mirrors doc ID) |
| `role` | string — v1 always `member` |
| `is_active` | bool — default `true` |
| `created_at` / `updated_at` | timestamp |

### 4.5 `content_sources/{sourceId}`

A user-registered content source. v1 supports exactly one type.

| Field | Type | Notes |
|-------|------|-------|
| `source_id` | string | |
| `user_id` | string | |
| `provider` | string | `youtube` |
| `source_type` | string | `playlist` |
| `external_id` | string | YouTube playlist ID |
| `title` | string | Fetched from the provider at registration |
| `item_count` | int | Last observed |
| `last_synced_at` | timestamp \| null | Last **completed** sync |
| `last_sync_status` | string | `ok` \| `partial` \| `failed` \| `in_progress` |
| `last_sync_error` | string \| null | |
| `last_full_walk_at` | timestamp \| null | Drives the 7-day forced full walk (§8.3) |
| `remote_item_count` | int \| null | `contentDetails.itemCount` at last preflight |
| `sync_page_token` | string \| null | Resume point for a chunked sync (§8.2); null when idle |
| `sync_items_processed` | int | Progress within the in-flight sync |
| `sync_started_at` | timestamp \| null | Start of the in-flight sync; used to expire a stalled one |
| `created_at` | timestamp | |

**Constraint: max 5 sources per user in v1.** Each sync costs YouTube API quota (§8.3); an unbounded count makes quota unpredictable.

The three `sync_*` fields exist because sync is **chunked and resumable** (§8.2) — the progress cursor has to survive both the end of an HTTP request and the app being backgrounded mid-sync.

### 4.6 `content_cache/{contentId}`

Provider metadata, keyed by namespaced content ID and **shared across all users**. A video's duration is immutable, so this is the single highest-leverage cache in the system.

| Field | Type | Notes |
|-------|------|-------|
| `content_id` | string | |
| `provider` / `external_id` | string | |
| `title`, `channel_title`, `thumbnail_url` | string | |
| `duration_seconds` | int | Parsed from ISO-8601 `PT#H#M#S` |
| `is_available` | bool | False when private/deleted/region-blocked |
| `fetched_at` | timestamp | |
| `ttl_expires_at` | timestamp | `fetched_at + 30d` |

Duration never changes, so an expired TTL only refreshes title/availability. A stale-but-present cache entry is always preferable to a failed request: on a provider error during refresh, serve the stale entry and log a warning.

### 4.7 `feed_items/{userId}_{contentId}`

The join between a user and a cached content item, denormalized so the feed can be served by a **single indexed query** with no fan-out reads. The deterministic composite doc ID makes upsert idempotent and re-sync cheap.

| Field | Type | Notes |
|-------|------|-------|
| `user_id` | string | |
| `content_id` | string | |
| `source_id` | string | Origin source |
| `duration_seconds` | int | Denormalized from cache — enables range queries |
| `title`, `thumbnail_url` | string | Denormalized for list rendering |
| `consumed` | bool | Set true on completion or manual hide |
| `consumed_at` | timestamp \| null | |
| `consumed_via` | string \| null | `session` \| `manual` |
| `added_at` | timestamp | |

**Why both `consumed` here and `consumed_content_ids` on the user:** Firestore cannot efficiently express "not in this array." Filtering the feed requires a boolean field on the queried document. The user-level array is the durable, source-independent record — if a user removes and re-adds a playlist, the array is what prevents already-watched items from resurfacing. `consumed` is a query-time projection of it, set at sync.

### 4.8 Composite indexes

Firestore requires these to be declared in `firestore.indexes.json`; a missing index is a runtime failure, not a slow query.

| Collection | Fields | Serves |
|------------|--------|--------|
| `feed_items` | `user_id` ASC, `consumed` ASC, `duration_seconds` ASC | Feed with duration range filter |
| `feed_items` | `user_id` ASC, `consumed` ASC, `added_at` DESC | Feed, default ordering |
| `sessions` | `user_id` ASC, `created_at` DESC | History |
| `sessions` | `user_id` ASC, `status` ASC, `created_at` DESC | Active-session lookup |
| `content_sources` | `user_id` ASC, `created_at` ASC | Source list |

### 4.9 Security rules

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
```

All access is server-side via the Admin SDK, which bypasses rules by design. Denying everything at the rules layer means a leaked client API key grants zero data access — it is the enforcement mechanism behind the §2.2 client→Firestore boundary, not a formality.

---

## 5. Matching Engine

### 5.1 Activity catalog

A **static, version-controlled catalog** in `app/features/activities/catalog.py` — not a Firestore collection. It is small, changes only with a release, and must be identical across environments. Putting it in the database would add a read, a cache, and an environment-drift failure mode for no benefit.

| `activity_type` | Label | Min | Max | Category |
|-----------------|-------|-----|-----|----------|
| `treadmill_walk` | Treadmill Walk | 600 | 10800 | cardio |
| `treadmill_run` | Treadmill Run | 900 | 7200 | cardio |
| `outdoor_walk` | Outdoor Walk | 600 | 10800 | cardio |
| `outdoor_run` | Outdoor Run | 900 | 7200 | cardio |
| `indoor_row` | Indoor Row | 600 | 5400 | cardio |
| `elliptical` | Elliptical | 600 | 5400 | cardio |
| `stationary_bike` | Stationary Bike | 600 | 7200 | cardio |
| `stair_climber` | Stair Climber | 600 | 3600 | cardio |
| `time_block_strength` | Strength Time Block | 900 | 5400 | strength |

Min/max are in seconds and encode "is this a sane duration for this activity," not a user preference. A 3-hour stair climb is a data-entry error, not a workout.

### 5.2 Content-first matching

Input: a `content_id`. Output: ranked candidate activities.

```
D = content_cache[content_id].duration_seconds

candidates = [a for a in catalog if a.min_seconds <= D <= a.max_seconds]

rank by:
  1. a.activity_type in user.preferences.preferred_activity_types  (desc)
  2. count of the user's completed sessions with this activity_type (desc)
  3. catalog declaration order                                     (asc, stable)
```

The session duration equals the content duration **exactly**. No warmup or cooldown padding is added — the entire premise is that the workout ends when the content ends, and padding breaks it. Users who want a warmup start the media late; that is their business, not the app's.

Two distinct empty results, because they need different copy:

| Condition | `reason` | Client message |
|-----------|----------|----------------|
| `D < 300` or `D > 10800` | `duration_out_of_range` | "This is too short/long to match a workout" |
| `D` in global range but no catalog activity's `[min, max]` contains it | `no_matching_activity` | "Nothing in your activity list fits 8:20 — try a Time Block" |

The second case is reachable: no catalog activity has a `min` below 600, so a 7-minute video is globally valid but matches nothing. Collapsing both into one message would tell a user their perfectly reasonable 7-minute video is "out of range," which is false.

### 5.3 Time-first matching (Time Blocks)

Input: a target block `B` from `{900, 1200, 1800, 2700, 3600, 4500, 5400}` seconds. Output: ranked feed items.

```
Primary window:   B <= duration_seconds <= B + 300
                  ranked ascending by duration (closest above the block first)

Fallback window:  B - 120 <= duration_seconds < B
                  used only when the primary window is empty
                  ranked descending by duration
```

**Why the asymmetry:** content slightly *longer* than the block means the workout ends with a little content left — harmless. Content *shorter* means silence during the last stretch, which is the failure mode the app exists to prevent. So overshoot is strongly preferred and undershoot is capped at 2 minutes.

Both windows are served by the `(user_id, consumed, duration_seconds)` index.

---

## 6. The Orchestrator Flow

### 6.1 The constraint this design exists to handle

When ActiveQueue opens another app via a deep link, **ActiveQueue is backgrounded and loses control**. It cannot launch a second app afterward, cannot run a reliable long-lived timer, and cannot observe what the user does in the other app. Any design that assumes "launch tracker, then launch media" in one tap is not implementable on iOS.

The consequence: the handoff is a **user-driven checklist with explicit returns**, not an automated sequence. This is the single most important behavioral decision in the spec, and the session screen is designed around it.

### 6.2 Handoff checklist

`app/(app)/session/[id].tsx` renders an ordered, resumable checklist. Each step is a button; each returns the user to ActiveQueue via the app switcher or the "back to ActiveQueue" affordance iOS renders in the status bar.

```
Step 1 — Start your tracker        [ Open Strava ]      (skippable)
Step 2 — Start your media          [ Open YouTube ]     (required)
Step 3 — Work out                  (passive; shows expected end time)
Step 4 — Mark complete             [ Mark Complete ]
```

- **Step 1 is skippable.** Tracker deep-link reliability is not guaranteed (§6.3), and a user tracking on an Apple Watch has no phone-side step at all. The flow must not dead-end on it.
- **Step 2 firing is what transitions the session to `in_progress`** and sets `started_at`. Step 1 does not — a user may open their tracker and abandon the session before ever starting the media.
- **Step 3 displays a computed end time** (`started_at + content_duration_seconds`) rendered client-side from the server's `started_at`. It is a label, not a timer: no background execution, no local notification, no wake locks.
- **Progress persists.** The checklist state is derived from the session's server-side `status` and `started_at`, so force-quitting the app mid-workout loses nothing.

An `AppState` listener detects the return to foreground and advances the visible step. This is a **convenience only** — every step is also manually tappable, because `AppState` transitions are not reliable enough to gate progress on.

### 6.3 Deep link registry

A static registry in `src/features/sessions/deepLinks.ts`. Each entry has a primary scheme and an HTTPS fallback.

| Key | Kind | Primary | Fallback |
|-----|------|---------|----------|
| `youtube` | media | `vnd.youtube://<videoId>` | `https://www.youtube.com/watch?v=<videoId>` |
| `strava` | tracker | `strava://` | `https://www.strava.com` |
| `strong` | tracker | `strong://` | App Store URL |
| `apple_fitness` | tracker | ⚠️ unverified — see below | Instruct: start from Apple Watch |

**Launch procedure:**

```
1. Linking.canOpenURL(primary)
2. If true  → Linking.openURL(primary)
3. If false → Linking.openURL(fallback), and surface a one-line notice
              ("YouTube isn't installed — opening in your browser")
4. If both throw → show an inline error with a Retry, and do NOT
                   transition the session state
```

`canOpenURL` requires every queried scheme to be declared in `LSApplicationQueriesSchemes` in `app.json`'s `ios.infoPlist`. **A scheme missing from that list returns `false` unconditionally, with no error** — it silently degrades to the fallback. This is the most likely source of a "works in dev, broken in TestFlight" bug in this app, and it must be covered by the §12.4 device matrix.

**⚠️ Apple Fitness has no publicly documented URL scheme.** This spec does not assert one. **Milestone 2 includes a spike** to determine on-device whether a working scheme exists. If it does not, `apple_fitness` ships with fallback behavior only (a note telling the user to start the workout from their Watch), and the registry entry records that. No shipped code may depend on an unverified scheme.

---

## 7. Session State Machine

```
            POST /sessions
                  │
                  ▼
             ┌─────────┐
             │ created │────────── DELETE /sessions/{id} ──────► (deleted)
             └────┬────┘
                  │ POST /sessions/{id}/start
                  │ (fired when the media deep link launches)
                  ▼
           ┌─────────────┐
           │ in_progress │
           └──────┬──────┘
                  │
      ┌───────────┴────────────┐
      │ POST …/complete        │ lazy sweep (§7.2)
      ▼                        ▼
┌───────────┐            ┌───────────┐
│ completed │            │ abandoned │
└───────────┘            └───────────┘
   (terminal)               (terminal)
```

### 7.1 Transition rules

| From | To | Trigger | Effects |
|------|----|---------|---------|
| — | `created` | `POST /sessions` | Validate duration bounds and activity catalog membership; snapshot content title/duration |
| `created` | `in_progress` | `POST /sessions/{id}/start` | Set `started_at = now()` |
| `created` | (deleted) | `DELETE /sessions/{id}` | Hard delete. Allowed only from `created` |
| `in_progress` | `completed` | `POST /sessions/{id}/complete` | Set `completed_at`, `verification="manual"`; **transactionally** set `feed_items.consumed=true` and `arrayUnion` the content ID onto the user |
| `created` \| `in_progress` | `abandoned` | Lazy sweep | Set `completed_at=null`; no consumption effects |

- **`complete` is idempotent.** Completing an already-`completed` session returns `200` with the unchanged session, not an error. Users double-tap; a network retry must not fail.
- **`start` is idempotent.** Re-firing preserves the original `started_at`.
- Completing from `created` (user never fired the media link but did the workout) returns `409 SESSION_NOT_STARTED`. The client's remedy is to show "Open media first, or discard this session" — silently back-dating a start time would corrupt the history.
- **Only one non-terminal session per user at a time.** Creating a second returns `409 ACTIVE_SESSION_EXISTS` with the existing session in `error.details`, letting the client offer "Resume" or "Discard and start new."

### 7.2 Abandonment

A session is abandoned when `now() > created_at + content_duration_seconds + 24h`.

This is evaluated **lazily on read** in the session service — no Cloud Scheduler job, no cron, no background worker in v1. The state is a pure function of stored timestamps, so computing it on read is always correct and costs nothing until someone looks. A scheduled sweep would be infrastructure carrying its own failure modes to produce an identical answer.

When a lazy read observes an abandoned session, it writes the `abandoned` status back so history queries stay consistent.

---

## 8. Content Ingestion

### 8.1 Provider interface

```python
# app/providers/base.py
class ContentProvider(Protocol):
    provider_key: str  # "youtube"

    async def fetch_source_metadata(self, external_id: str) -> SourceMetadata: ...
    async def list_source_items(
        self, external_id: str, page_token: str | None
    ) -> ItemPage: ...
    async def fetch_items(self, external_ids: Sequence[str]) -> list[ContentMetadata]: ...
```

Spotify (v1.1) implements the same protocol. Nothing outside `app/providers/` references YouTube by name.

### 8.2 Sync algorithm — chunked and resumable

Playlists are walked **in full**, to YouTube's own hard cap of 5,000 items per playlist (`MAX_ITEMS_PER_SOURCE = 5000`). There is no app-imposed item ceiling.

That decision forces the sync to be chunked. A cold 5,000-item walk is 100 `playlistItems` pages plus up to 100 `videos.list` batches — roughly 40–60 s of sequential network I/O. Three ways to handle a job that long:

| Approach | Why not |
|----------|---------|
| One long HTTP request | 60 s requests are hostile to clients and mobile radios, and any failure loses all progress |
| `BackgroundTasks` after responding | **Cloud Run throttles CPU once the response is sent** unless CPU-always-allocated is enabled. Background work silently stalls — the worst possible failure mode |
| Cloud Tasks + worker endpoint | Correct at scale, but new infra, new IAM, new failure modes, and it needs GCP set up |

**v1 uses client-driven chunking.** Each `POST /sources/{sourceId}/sync` processes a bounded slice and returns a progress record; the client loops until `complete: true`. Every request stays ~2–4 s, progress persists on the source document, and a sync interrupted by a crash, a backgrounded app, or a dropped connection resumes exactly where it stopped. No new infrastructure — which also means it works entirely against the local emulator (§10.4).

**Preflight (cheap change detection), runs only when `sync_page_token` is null:**

```
1. playlists.list(id=playlistId, part=contentDetails)          → 1 unit
2. If remote itemCount == source.remote_item_count
   AND now() - last_full_walk_at < 7 days
   → return { complete: true, skipped: true, reason: "unchanged" }
```

Two units to learn "nothing changed" instead of a hundred to re-walk. The heuristic has a known hole — one video added and one removed leaves `itemCount` identical — so a **full walk is forced every 7 days regardless**, and Settings offers a "Force full refresh" that skips the preflight entirely.

**Chunk (`PAGES_PER_CHUNK = 5`, so ≤250 items and ≤10 quota units per call):**

```
3. Repeat up to 5 times, or until no nextPageToken:
     playlistItems.list(playlistId, part=contentDetails,
                        maxResults=50, pageToken=sync_page_token)
4. Collect video IDs from this chunk. Select those missing from
   content_cache or with ttl_expires_at < now()
5. videos.list(id=<≤50 comma-separated>, part=contentDetails,snippet)
   → batched 50 at a time
6. Parse ISO-8601 durations (PT1H2M3S). Items absent from the response
   (private/deleted) or with P0D / no duration (live streams)
   → is_available = false, excluded from feed_items
7. Upsert content_cache      (batched writes, ≤500 ops per batch)
8. Upsert feed_items with consumed = is_consumed(uid, content_id)
9. Persist sync_page_token = nextPageToken, sync_items_processed += n
10. If no nextPageToken or items_processed >= MAX_ITEMS_PER_SOURCE:
      → clear sync_page_token, set last_synced_at, last_full_walk_at,
        remote_item_count, last_sync_status = ok|partial
      → return { complete: true }
    Else → return { complete: false, ... }
```

**Sync is idempotent at every level.** Deterministic doc IDs (§4.7) mean a re-run overwrites rather than duplicates, and the page token is only advanced *after* the chunk's writes land — so a chunk that fails mid-write is simply replayed. There is no compensating logic and no partial-state cleanup anywhere in this design; that is the whole reason for the deterministic-ID choice.

**A stalled sync expires.** If `sync_started_at` is older than 1 hour, the next sync request discards `sync_page_token` and restarts from the beginning. Otherwise a user who abandons a sync mid-walk leaves the source permanently pinned at a stale cursor.

**Partial failure** (some `videos.list` batches fail) writes what succeeded, records the error, and still advances the cursor — `last_sync_status = "partial"`. A partly-populated feed is more useful than none, and the next full walk repairs it.

**Items removed from the source playlist are left in `feed_items`.** Deleting them would resurface content the user had already dismissed and would make "I removed it from YouTube" silently destroy local state. Cleanup is deferred to v1.1.

### 8.3 Quota budget

YouTube Data API v3 default quota: **10,000 units/day, per project** — shared across every user of the app. This is the hardest scaling constraint in v1 and drives several decisions above.

| Call | Units | Notes |
|------|------:|-------|
| `playlistItems.list` | 1 | per page of 50 |
| `videos.list` | 1 | per batch of 50 |
| `search.list` | **100** | **Not used in v1** |
| `playlists.list` | 1 | Preflight change detection |

Cost per sync, now that playlists are walked in full:

| Scenario | Units | Syncs available per day |
|----------|------:|------------------------:|
| Preflight says unchanged | 1 | ~10,000 |
| 200-item playlist, cold (nothing cached) | ~9 | ~1,100 |
| 200-item playlist, warm (all cached) | ~5 | ~2,000 |
| 5,000-item playlist, cold | ~201 | ~50 |
| 5,000-item playlist, warm | ~101 | ~99 |

The warm numbers are the ones that matter in steady state, and they are much better than they look: `content_cache` is **shared across all users**, so a popular podcast episode is fetched once for the entire app. The marginal cost of the *n*-th user syncing the same playlist is just the `playlistItems` walk.

Enforced controls:
- **`search.list` is forbidden in v1.** At 100 units it would exhaust the daily quota in 100 calls. Users add playlists by ID or URL (§9.3).
- **Preflight before every walk** (§8.2) — 1 unit to avoid up to 200.
- **Forced full walk at most every 7 days per source**, to bound the cost of the `itemCount` heuristic's blind spot.
- **Sync throttle: one sync *start* per source per 15 minutes.** Continuation chunks are exempt — throttling them would make a large playlist mathematically unable to finish. A start request inside the window returns the last result with `throttled: true` rather than an error.
- **Client auto-sync only on foreground when `last_synced_at` is older than 6 hours.**
- **Quota-exceeded (HTTP 403, reason `quotaExceeded`) is a first-class state**: return `503 PROVIDER_QUOTA_EXCEEDED` and serve the existing cached feed. A partially-walked source keeps its cursor and resumes tomorrow. The app must remain usable on already-synced content.

**Before public launch, request a quota increase.** At 5,000-item playlists the free tier supports ~50 cold syncs/day, which is a beta-sized budget, not a launch-sized one.

### 8.4 Fixture provider (development without a Google account)

`ContentProvider` (§8.1) has a second implementation: `FixtureProvider`, selected by `content_provider = "fixture"` in config (§10.3).

It serves recorded YouTube API responses from `tests/fixtures/youtube/` — several playlists of varying size (including one over 250 items, to exercise chunking), plus the awkward cases: private videos, deleted videos, live streams, and a `quotaExceeded` response triggered by a magic playlist ID.

This is not only a test double. It means **the entire application — feed, matching, sessions, completion, the whole client — can be built and demoed with no Google account, no API key, and no GCP project.** Swapping to the real provider is one config value. Given that GCP isn't set up yet (§10.4), this is what keeps Milestones 2–5 unblocked, and the same fixtures back the §12.3 provider tests, so it costs nothing extra to maintain.

---

## 9. API Surface

Base path `/api/v1`. TLS 1.3 only. All responses use the house envelopes from `.claude/context/006_api-health-guide.md`.

**Success:**
```json
{ "status": "success", "data": { }, "error": null }
```

**Error:**
```json
{ "status": "error", "data": null,
  "error": { "code": "ERROR_CODE", "message": "Human-readable description.", "details": [] } }
```

All authenticated responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.

### 9.1 Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Health contract (§9.8). Unauthenticated |
| GET | `/me` | Current user profile + preferences |
| PATCH | `/me/preferences` | Partial preferences update |
| GET | `/sources` | List content sources |
| POST | `/sources` | Register a YouTube playlist by URL **or** ID (§9.3) |
| DELETE | `/sources/{sourceId}` | Remove a source (leaves `feed_items`) |
| POST | `/sources/{sourceId}/sync` | Process one sync chunk; call in a loop (§9.4) |
| GET | `/feed` | Paged, filtered feed |
| POST | `/feed/{contentId}/hide` | Manual hide (swipe-to-complete) |
| GET | `/activities` | Static catalog + time blocks |
| GET | `/activities/match` | Content-first suggestions (§5.2) |
| GET | `/sessions` | Session history |
| POST | `/sessions` | Create session |
| GET | `/sessions/{id}` | Fetch one |
| POST | `/sessions/{id}/start` | Transition to `in_progress` |
| POST | `/sessions/{id}/complete` | Transition to `completed` |
| DELETE | `/sessions/{id}` | Discard a `created` session |

### 9.2 `GET /feed`

Query: `duration_min` (int, ≥300), `duration_max` (int, ≤10800), `include_consumed` (bool, default false), `cursor` (opaque), `limit` (int, 1–50, default 20).

```json
{
  "status": "success",
  "data": {
    "items": [
      { "content_id": "yt:dQw4w9WgXcQ",
        "title": "Deep Work — Episode 12",
        "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg",
        "duration_seconds": 2712,
        "duration_label": "45:12",
        "source_id": "a1B2c3D4e5F6g7H8i9J0",
        "consumed": false,
        "added_at": "2026-08-08T14:02:11.482Z" }
    ],
    "next_cursor": "eyJhZGRlZF9hdCI6…",
    "total_unconsumed": 47
  },
  "error": null
}
```

Cursor pagination, not offset — Firestore has no efficient offset, and the feed mutates underneath the user as sessions complete. The cursor is a base64-encoded `startAfter` key.

`duration_label` is server-formatted so the two clients cannot disagree about how to render `2712`.

`total_unconsumed` uses a Firestore `count()` aggregation query, which is billed per-index-entry-read rather than per-document and does not fetch the documents. It is computed only on the first page (when `cursor` is absent) and returned as `null` on subsequent pages.

### 9.3 `POST /sources`

Accepts **either** a raw playlist ID or a pasted URL. Exactly one of `external_id` or `url` must be present.

```json
{ "provider": "youtube", "url": "https://www.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx" }
```

Accepted URL forms, all parsed to the `list` parameter by `app/providers/youtube.py`:

| Form | Example |
|------|---------|
| Playlist page | `youtube.com/playlist?list=<ID>` |
| Mobile / no-www | `m.youtube.com/…`, `youtube.com/…` |
| Watch URL carrying a playlist | `youtube.com/watch?v=<VID>&list=<ID>` |
| Short share link | `youtu.be/<VID>?list=<ID>` |
| Raw ID | `PLxxxxxxxxxxxxxxxx` |

URL parsing is ~10 lines and raw IDs are user-hostile — nobody knows where to find one. Supporting both costs almost nothing and removes the most likely first-run dead end.

**Rejected with specific, explanatory errors:**

| Input | Code | Why |
|-------|------|-----|
| `WL` | `SOURCE_UNSUPPORTED` | Watch Later. The API returns no items for it (Risk #1) |
| `LL` | `SOURCE_UNSUPPORTED` | Liked Videos — same restriction |
| `HL` | `SOURCE_UNSUPPORTED` | History — same restriction |
| Unparseable string | `SOURCE_URL_UNPARSEABLE` | |
| Private / nonexistent playlist | `SOURCE_NOT_ACCESSIBLE` | Verified by a `playlists.list` call at registration |
| Already registered | `SOURCE_ALREADY_ADDED` | Returns the existing source |

**`WL` deserves its own error, not a generic failure.** "Watch Later" is the first thing a user will try to add, it is the single most-requested thing the app cannot do, and a vague error here reads as a bug rather than a platform limitation. The message must say so directly and point at creating a normal playlist instead.

Registration performs one `playlists.list` call (1 unit) to verify accessibility and capture the title and `itemCount`. It does **not** sync — the client calls §9.4 afterward.

### 9.4 `POST /sources/{sourceId}/sync`

Processes one chunk (§8.2) and returns progress. Always `200`; `complete` is the loop condition, not the status code.

```json
{ "status": "success",
  "data": { "source_id": "a1B2c3D4e5F6g7H8i9J0",
            "complete": false,
            "skipped": false,
            "throttled": false,
            "sync_status": "in_progress",
            "items_processed": 250,
            "items_total_estimate": 1284,
            "new_items": 37,
            "error": null },
  "error": null }
```

**Client loop:**

```
do {
  r = POST /sources/{id}/sync
  render progress (items_processed / items_total_estimate)
} while (!r.complete && iterations < 40)
```

- `items_total_estimate` comes from the preflight `itemCount` and is an estimate — private and deleted entries still count toward it upstream, so the bar may finish slightly short of 100%. The client renders "250 of ~1,284."
- **The 40-iteration guard is required**, not defensive decoration: 40 × 250 items covers the 5,000-item cap with margin, and without it a server bug that never sets `complete` becomes an infinite client loop burning quota.
- The loop is cancellable. Abandoning it mid-way is safe and resumable — that is the entire point of persisting the cursor (§4.5).
- `throttled: true` with `complete: true` means a start request arrived inside the 15-minute window; the client shows the last sync's result rather than an error.
- `skipped: true` means the preflight found no change.

### 9.5 `POST /sessions`

```json
{ "content_id": "yt:dQw4w9WgXcQ",
  "activity_type": "treadmill_walk",
  "tracker_app": "strava",
  "match_mode": "content_first" }
```

For a bare time block (strength training with no content attached), omit `content_id` and send `duration_seconds`. That value must be **one of the seven enumerated blocks in §5.3** — it is validated against an allowlist, not a range, so the "duration always comes from a trusted source" rule below holds in both paths.

`201`:
```json
{ "status": "success",
  "data": { "session_id": "s1B2c3D4e5F6g7H8i9J0",
            "status": "created",
            "content_id": "yt:dQw4w9WgXcQ",
            "content_title": "Deep Work — Episode 12",
            "content_duration_seconds": 2712,
            "activity_type": "treadmill_walk",
            "activity_label": "Treadmill Walk",
            "tracker_app": "strava",
            "created_at": "2026-08-08T14:05:00.000Z",
            "started_at": null,
            "completed_at": null },
  "error": null }
```

Server-side validation (never trusting client validation, per the house standard):
- `content_id` must exist in `content_cache` and belong to a `feed_item` owned by the caller.
- `content_duration_seconds` is read **from `content_cache`, never from the request body.** A client-supplied duration is an integrity hole — it would let a client log a 3-hour session for a 3-minute video. (The bare-time-block path has no content to read from, which is why its `duration_seconds` is allowlisted rather than range-checked.)
- `activity_type` must be in the catalog and its `[min, max]` must contain the duration.
- No non-terminal session may already exist for the user.

### 9.6 `POST /sessions/{id}/complete`

Empty body in v1. `external_workout_url` and `healthkit_uuid` are rejected with `FEATURE_NOT_AVAILABLE` until v1.1.

Effects run in a **single Firestore transaction**: update the session, set `feed_items.consumed`, and `arrayUnion` the content ID onto the user. Partial application here is the one inconsistency users would actually notice — a completed session whose content is still in the queue.

### 9.7 Error code registry

| HTTP | Code | Meaning |
|-----:|------|---------|
| 400 | `VALIDATION_FAILED` | DTO validation failed; `details[]` carries field/issue pairs |
| 401 | `AUTH_TOKEN_MISSING` | No `Authorization` header |
| 401 | `AUTH_TOKEN_INVALID` | Signature, `iss`, or `aud` check failed |
| 401 | `AUTH_TOKEN_EXPIRED` | `exp` passed — client refreshes and retries once |
| 403 | `ACCOUNT_DISABLED` | `user_authorization.is_active == false` |
| 404 | `SESSION_NOT_FOUND` | Also returned when the session belongs to another user |
| 404 | `CONTENT_NOT_FOUND` | Not in cache, or no feed item for this user |
| 404 | `SOURCE_NOT_FOUND` | |
| 422 | `SOURCE_URL_UNPARSEABLE` | No playlist ID found in the supplied URL (§9.3) |
| 422 | `SOURCE_UNSUPPORTED` | `WL` / `LL` / `HL` — not exposed by the Data API (§9.3) |
| 404 | `SOURCE_NOT_ACCESSIBLE` | Playlist is private or does not exist |
| 409 | `SOURCE_ALREADY_ADDED` | Existing source returned in `error.details` |
| 409 | `ACTIVE_SESSION_EXISTS` | A non-terminal session already exists |
| 409 | `SESSION_NOT_STARTED` | `complete` attempted from `created` |
| 409 | `SESSION_ALREADY_TERMINAL` | Transition attempted from `completed`/`abandoned` |
| 422 | `DURATION_OUT_OF_RANGE` | Outside [300, 10800] |
| 422 | `ACTIVITY_DURATION_MISMATCH` | Duration outside the activity's `[min, max]` |
| 422 | `SOURCE_LIMIT_REACHED` | Already at 5 sources |
| 429 | `RATE_LIMITED` | Per-user request limit exceeded |
| 501 | `FEATURE_NOT_AVAILABLE` | A v1.1/v2 field was supplied |
| 503 | `PROVIDER_QUOTA_EXCEEDED` | YouTube daily quota exhausted |
| 503 | `PROVIDER_UNAVAILABLE` | Provider 5xx or timeout |
| 500 | `INTERNAL_ERROR` | Never leaks an exception message or stack trace |

`SESSION_NOT_FOUND` is deliberately returned for another user's session rather than `403`. A `403` would confirm the ID exists — an enumeration oracle.

### 9.8 `GET /healthz`

Per the house contract, adapted to this stack (§14.3):

| Check | Critical | Method |
|-------|:--------:|--------|
| Firestore | ✅ | Read a sentinel document; record round-trip latency |
| YouTube Data API | ❌ | Cached reachability, refreshed at most once per minute |
| Process | ❌ | Uptime, in-flight request count |

`200` when Firestore is reachable; `503` otherwise. The YouTube check reports `degraded` in the body but never fails the check — the app serves cached content fine without the provider, and failing health here would cause Cloud Run to cycle healthy instances during a provider outage, converting a partial degradation into a full one.

No cache or disk checks: this service has neither.

---

## 10. Cross-Cutting Concerns

### 10.1 Logging

`structlog` with `JSONRenderer` to stdout (Cloud Run ingests stdout into Cloud Logging). Every entry carries the house fields — `timestamp` (ISO-8601, ms), `level`, `component`, `message`, `latency_ms` for HTTP — plus:

| Field | Purpose |
|-------|---------|
| `request_id` | UUID v4 per request; echoed as `X-Request-ID` |
| `trace` | `logging.googleapis.com/trace`, from `X-Cloud-Trace-Context`, for Cloud Trace correlation |
| `uid` | Authenticated user, when present |

**Never logged:** ID tokens, refresh tokens, `Authorization` header values, the YouTube API key, or email addresses outside of `ERROR` records. A redacting `structlog` processor enforces this by key name rather than relying on call-site discipline.

### 10.2 Rate limiting

Per-user limits: **60 requests/minute** general, **10/minute** on `POST /sources/{id}/sync`.

v1 uses an **instance-local** fixed-window limiter. Cloud Run runs multiple instances, so the effective limit is `instances × 60` — the headers are therefore approximate. This is a documented v1 compromise (§14.4): an accurate distributed limiter needs a Firestore or Redis counter write per request, which would roughly double the cost and latency of every call to protect against a threat v1 does not yet face. Cloud Armor edge rate limiting is the v1.1 hardening.

### 10.3 Configuration

`pydantic-settings` `Settings` in `app/core/config.py` is the single source of truth; no module reads `os.environ` directly.

| Setting | Source | Default / placeholder |
|---------|--------|-----------------------|
| `env` | Env | `local` \| `dev` \| `staging` \| `prod` |
| `gcp_project_id` | Env | `activequeue-local` (placeholder until GCP exists) |
| `firestore_emulator_host` | Env; **non-prod only** | `localhost:8080` |
| `firebase_auth_emulator_host` | Env; **non-prod only** | `localhost:9099` |
| `content_provider` | Env | `fixture` \| `youtube` — see §8.4 |
| `youtube_api_key` | Secret Manager → env at deploy | unset while `content_provider="fixture"` |
| `max_items_per_source` | Default | `5000` (YouTube's own playlist cap) |
| `pages_per_chunk` | Default | `5` (≤250 items, ≤10 quota units per call) |
| `sync_throttle_seconds` | Default | `900` — applies to sync *starts* only |
| `sync_stall_timeout_seconds` | Default | `3600` |
| `full_walk_interval_days` | Default | `7` |
| `auth_cache_ttl_seconds` | Default | `60` |

Startup asserts that **both emulator hosts are unset when `env == "prod"`.** A `FIRESTORE_EMULATOR_HOST` leaking into production would silently point the service at a nonexistent database and return empty results rather than errors — a failure mode that looks exactly like data loss. A leaked `FIREBASE_AUTH_EMULATOR_HOST` is worse: the Admin SDK stops verifying token signatures, so **any forged token is accepted**. That one is a full authentication bypass, and it is the single most important assertion in the codebase.

### 10.4 Local development without GCP

GCP is not provisioned yet, and the spec is deliberately arranged so that this blocks almost nothing. Everything except real federated sign-in and deployment can be built and run locally.

| Concern | Local substitute | Fidelity |
|---------|------------------|----------|
| Firestore | Firebase Firestore emulator | High — same SDK, same queries, **enforces composite indexes**, same transactions |
| Auth | Firebase Auth emulator | High for the token flow; the Admin SDK verifies emulator tokens through the same code path |
| YouTube Data API | `FixtureProvider` (§8.4) | High for shapes and failures; no real quota behavior |
| Cloud Run | `uvicorn` locally, plus `docker build` in CI | Medium — no cold starts, no CPU throttling |
| Secret Manager | `.env` (gitignored) | Sufficient |
| Terraform | `fmt` + `validate` in CI, no `apply` | Config is written and checked but never applied |

**Placeholder values** used throughout until the real project exists, all sourced from config so the swap is a `.env` change and never a code change:

```
GCP_PROJECT_ID=activequeue-local
FIRESTORE_EMULATOR_HOST=localhost:8080
FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
CONTENT_PROVIDER=fixture
API_BASE_URL=http://localhost:8000/api/v1
AUTH_DOMAIN=localhost                 # → auth.<domain> when GCP lands
```

**What genuinely requires GCP, and when:**

| Needs | Milestone | Note |
|-------|-----------|------|
| A free Google Cloud project + YouTube Data API v3 key | M2 (optional) | **No billing account required** — the 10,000 unit/day quota is free tier. This is a ~5-minute task, far smaller than full GCP setup, and `FixtureProvider` means M2 does not wait on it |
| Identity Platform with real Google/Apple providers | M6 | The Auth emulator covers the token flow; only the real OAuth handshake is deferred |
| Custom auth domain | M6 | Required for production Sign in with Apple. Prod cannot ship without it |
| Cloud Run, Firestore (real), Secret Manager, Artifact Registry | M6 | |

The Apple Developer account is in hand, so no Apple-side work is blocked — but the Services/Team/Key IDs can only be wired into Identity Platform once the GCP project exists, which is why real Apple sign-in sits in M6 rather than M1.

### 10.5 Infrastructure (Terraform)

Three isolated GCP projects (`dev`, `staging`, `prod`) per the house standard, each provisioning: Cloud Run service, Firestore database + indexes + rules, Secret Manager secrets, service account with least-privilege IAM (`roles/datastore.user` only), Artifact Registry, and `google_identity_platform_config` with its OAuth clients. No `gcloud identity-platform` CLI is used — it does not exist.

Cloud Run: `min_instances = 0` in dev/staging, `1` in prod (cold start on a Python container is 2–4 s, which is visible on app launch), `max_instances = 10`, concurrency 80.

---

## 11. Client Behavior

### 11.1 State and data fetching

TanStack Query for server state; Zustand for local UI state only. Auth state lives in `src/features/auth/store/authStore.ts` and is the sole gate in `app/(app)/_layout.tsx`.

Cache policy: feed `staleTime` 5 min, session detail 0 (always fresh — it drives the handoff checklist), activities catalog 24 h.

### 11.2 API client

A single `apiClient` in `src/core/api/` owns: base URL from config, token attachment via `getIdToken()`, the one-shot 401 refresh-and-retry (§3.1), envelope unwrapping, and mapping the §9.7 codes to typed errors. **No feature calls `fetch` directly.** The 401 retry in particular must exist in exactly one place or it becomes an infinite-loop bug.

### 11.3 Required empty and error states

Each of these is a designed screen, not a spinner or a toast. They are the states a first-run or degraded user actually sees.

| State | Trigger | Content |
|-------|---------|---------|
| No sources | Zero `content_sources` | What a playlist is, how to add one, why Watch Later can't be used (§13) |
| Empty feed | Sources exist, no unconsumed items | Offer sync, or "you're all caught up" |
| No duration match | Match returns zero candidates | The content's length and why nothing fits |
| Provider quota | `PROVIDER_QUOTA_EXCEEDED` | Cached feed still browsable; banner explains new items are paused |
| Offline | Network unavailable | Read-only cached feed; session actions disabled with a reason |
| Deep link failed | Both primary and fallback failed | Inline retry; session state unchanged |
| Active session | A non-terminal session exists | Resume banner on the queue screen |
| Sync in progress | `complete: false` from §9.4 | Determinate progress ("250 of ~1,284"), cancellable, non-blocking — the existing feed stays browsable |
| Sync resumable | `sync_page_token` present on app launch | "Finish syncing <playlist>" prompt; never auto-resumes without a tap |
| Watch Later rejected | `SOURCE_UNSUPPORTED` | Explains the platform limitation and offers "create a playlist instead" — see §9.3 |

### 11.4 Accessibility

Dynamic Type support throughout; minimum 44×44 pt touch targets; VoiceOver labels on every checklist step and swipe action; swipe-to-hide has an equivalent long-press menu action, since swipe alone is not operable with VoiceOver.

---

## 12. Testing Strategy

### 12.1 Backend unit tests

`pytest` + `pytest-asyncio`. Services are tested against **in-memory fake repositories**, not the emulator — this is the payoff for the §2.2 service→repository boundary and keeps the matching engine, state machine, and validation suites fast.

Required coverage:
- Matching engine: every window boundary in §5.2 and §5.3, including the fallback-window asymmetry.
- State machine: every legal transition, every illegal transition, both idempotency guarantees.
- ISO-8601 duration parsing: `PT45M`, `PT1H2M3S`, `PT10S`, `P0D` (live), absent.
- Content ID namespace parse/format round-trip.
- Playlist URL parsing: all five accepted forms in §9.3, plus `WL`/`LL`/`HL` rejection and unparseable input.
- Sync chunking: cursor advance, resume from a mid-walk token, stall expiry past `sync_stall_timeout_seconds`, completion at `MAX_ITEMS_PER_SOURCE`, and preflight skip when `itemCount` is unchanged.

### 12.2 Backend integration tests

Against the **Firestore emulator** (`firebase emulators:start`), via `httpx.AsyncClient` with ASGI transport. `firebase_admin.auth.verify_id_token` is patched to return a fixture claim set — the emulator's auth is not the system under test.

Required coverage: envelope shape on success and error, every §9.7 code reachable from a request, transactional completion (session + feed item + user array all applied or none), composite-index-dependent queries actually running, first-login provisioning, cross-user access returning 404.

### 12.3 Provider tests

`respx` to mock the YouTube HTTP layer against **recorded real fixtures** — the same corpus `FixtureProvider` (§8.4) serves, so the fixtures earn their keep twice. Required shapes: `quotaExceeded` 403, private video (item absent from the response rather than an error), deleted video, live stream (`P0D`), a playlist paginating across three pages, and one playlist over 250 items so the chunk boundary is actually crossed.

The "private video is silently absent from `videos.list` rather than an error" case is the one most likely to be missed and produces a feed item with a null duration if unhandled.

A **contract test runs the identical suite against both `FixtureProvider` and the `respx`-mocked real provider.** Without it the fixture double drifts from the thing it doubles, and the local-first development path (§10.4) quietly stops being evidence of anything.

### 12.4 Client tests

Jest + React Native Testing Library with MSW for API mocking. Unit tests for the checklist step-derivation logic and the duration formatter.

**Deep linking cannot be meaningfully tested in CI** — it requires other apps installed on a real device. It is covered by a manual device matrix executed before each TestFlight build:

| Case | Expected |
|------|----------|
| YouTube installed | Opens native app to the video |
| YouTube not installed | Opens Safari; notice shown |
| Scheme missing from `LSApplicationQueriesSchemes` | Falls back silently — **must be caught here** |
| Strava installed / not installed | Opens app / opens web |
| Force-quit mid-session, relaunch | Checklist resumes at the correct step |
| Airplane mode during session | Actions disabled with a reason; no state corruption |

### 12.5 CI gates

Backend: `ruff` (lint + format), `mypy --strict` on `app/`, `pytest` with unit + integration, coverage floor 80% on `app/features/`. Client: `eslint`, `tsc --noEmit`, `jest`.

Terraform: `fmt -check` and `validate` only until M6 — `plan` needs real credentials against a real project, so it joins CI when GCP does. Integration tests run against emulators started by the CI job, so **no CI stage requires a Google account before M6.**

---

## 13. Known Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | **YouTube Watch Later and History are not accessible via the Data API.** Google removed programmatic access. | High — this is most users' actual queue, and the obvious first expectation. | Users register their own playlists by ID/URL. The no-sources empty state explains this directly (§11.3). Accepted product limitation, not a bug to fix. |
| 2 | **Apple Fitness has no documented URL scheme** (§6.3). | Medium | Milestone 2 spike; ship fallback-only if unverified. No code depends on an unverified scheme. |
| 3 | **10,000 units/day is a project-wide quota**, not per-user — and full playlist walks make it tighter (~50 cold 5,000-item syncs/day). | High at scale | §8.3 controls: preflight change detection, 7-day walk interval, shared `content_cache`, start-only throttling. Quota exhaustion degrades to cached content and a resumable cursor rather than failing. **Quota increase required before public launch.** |
| 4 | **The handoff requires the user to leave and return** (§6.1). | High — it is the core UX risk. | Explicit checklist; server-derived resumable state; every step manually tappable. Validate with real users in Milestone 3. |
| 5 | Manual completion is unverified — users can mark complete without working out. | Low for v1 | Accepted. HealthKit verification in v1.1 is the answer. |
| 6 | `consumed_content_ids` array growth (§4.2). | Low near-term | 5,000-entry migration trigger; repository interface isolates the change. |
| 7 | Instance-local rate limiting is approximate (§10.2). | Low | Documented; Cloud Armor in v1.1. |
| 8 | Cold start latency on Cloud Run. | Medium | `min_instances = 1` in prod; lazy provider client init. |
| 9 | **GCP is not provisioned.** Real federated sign-in, the custom auth domain, and deployment are unexercised until M6. | Medium | §10.4 local-first path keeps M0–M5 unblocked on emulators, placeholders, and `FixtureProvider`. The residual risk is real: emulator auth cannot surface Apple Services-ID or domain-verification misconfiguration, so **M6 must budget time for first-time OAuth setup**, not treat it as a deploy step. |
| 10 | The `itemCount` change-detection heuristic (§8.2) misses an equal add+remove. | Low | Forced full walk every 7 days; manual "Force full refresh" in Settings. Worst case is a stale feed entry for up to a week, not data loss. |
| 11 | The client-driven sync loop puts pacing in the client (§9.4). A buggy or hostile client could hammer it. | Low | 40-iteration client guard, server-side start throttle, per-user rate limit, and quota exhaustion degrading safely. No single control is sufficient alone; the stack is. |

---

## 14. Deviations from House Context Files

These are conscious departures, recorded so a future reader does not mistake them for oversights.

### 14.1 `003_directory-structure.md` — no SQLAlchemy, no Alembic

The file prescribes SQLAlchemy ORM models, an async engine, and Alembic migrations. `CONCEPT.md` specifies Firestore, a schemaless document store with no migration concept.

**Retained:** the feature-module pattern (`models` / `schemas` / `service` / `router`), the strict no-layer-skipping rule, `app/core/config.py` as the single settings source, and the test layout.

**Replaced:** `models.py` holds Pydantic domain models instead of ORM models; `repository.py` replaces the session/engine layer; `firestore.indexes.json` and `firestore.rules` replace `alembic/`. The SQLi guidance in `006` is not applicable — Firestore has no query string to inject into — but the DTO validation, length/range bounds, and never-trust-the-client rules apply in full and are enforced in §9.5.

### 14.2 `007_identity-platform-guide.md` — `user_authorization` as a collection

The standard specifies a SQL table. §4.4 implements it as a Firestore collection with identical fields and semantics. First-login provisioning stays in the backend, and Blocking Functions still write nothing. §3.2's in-process cache is an addition, not a deviation.

### 14.3 `006_api-health-guide.md` — reduced `/healthz` checks

The standard lists database, cache, storage, and resource checks. This service has no cache and no disk. §9.8 implements Firestore (critical) and provider reachability (non-critical) only. The envelope, rate-limit headers, path versioning, TLS 1.3, and validation requirements are followed exactly.

### 14.4 `006_api-health-guide.md` — approximate rate-limit headers

Headers are emitted per §10.2 but reflect an instance-local budget. Rationale and remediation path in §10.2.

---

## 15. Milestones

**M0–M5 run entirely on local emulators and placeholder config** (§10.4). GCP provisioning is deferred to M6 rather than gating M0, because there is no reason for infrastructure that doesn't exist yet to block application work that doesn't depend on it.

| # | Milestone | Delivers | Done when | GCP |
|---|-----------|----------|-----------|:---:|
| 0 | Local foundations | `api/` + `mobile/` scaffolds, FastAPI skeleton, envelopes, error middleware, structlog, Firestore emulator wiring, `/healthz`, CI | `/healthz` returns 200 against the emulator; CI green | — |
| 1 | Auth (emulated) | Auth emulator wiring, `verify_id_token` middleware, `user_authorization` + first-login provisioning, `GET /me`, RN sign-in, `apiClient` with 401 retry | A new emulator user signs in and both documents are created | — |
| 2 | Content ingestion | Provider protocol, **`FixtureProvider`**, `content_cache`, `feed_items`, sources CRUD with URL parsing, chunked sync + client loop, `GET /feed`; **Apple Fitness scheme spike** | A 1,000+ item fixture playlist syncs to completion across multiple chunks and yields an accurate, correctly-paged feed | optional¹ |
| 3 | Matching + orchestration | Activity catalog, both match modes, session create/start, handoff checklist, deep link registry | End-to-end on a device: pick content → open YouTube → return to app | — |
| 4 | Completion + hide | `complete` transaction, auto-hide, swipe-to-hide, history, lazy abandonment | A completed item never reappears; device matrix (§12.4) passes | — |
| 5 | Hardening | Empty/error states, accessibility, rate limiting, quota degradation, full test suite, Terraform written and `validate`-clean | Full §12 suite passes; Terraform validates but is not applied | — |
| 6 | GCP + ship | Three projects via Terraform, real Firestore + indexes + rules, Identity Platform with Google + Apple, custom auth domain, real YouTube key, Cloud Run deploy, TestFlight | Real Apple sign-in works on a physical device against prod | **yes** |

¹ M2 can optionally use a real YouTube key from a free Google Cloud project (no billing account needed). `FixtureProvider` means it does not wait on one.

**Two schedule notes:**

- **The Apple Fitness spike sits in M2 deliberately.** It needs a physical device and the Apple Developer account — both of which you have — but not GCP. If Fitness has no usable scheme, M3's checklist copy and tracker registry change, and that is far cheaper to learn before the screen is built than after.
- **M6 is not a deploy step.** First-time Identity Platform setup, Apple Services/Team/Key ID wiring, and custom-domain verification are the parts of this project most likely to consume an unplanned day. Risk #9 exists to keep that from being a surprise.

---

## 16. Resolved Decisions

All open questions were resolved on **2026-08-08**. Recorded here with their consequences so the reasoning survives.

| # | Question | Decision | Consequence |
|---|----------|----------|-------------|
| 1 | Paid Apple Developer account provisioned? | **Yes** | Sign in with Apple is in scope. The Services/Team/Key IDs can only be wired into Identity Platform once GCP exists, so real Apple sign-in lands in M6 (§15), not M1 |
| 2 | Custom auth domain registered? | **No — arrives with GCP** | M0–M5 use `AUTH_DOMAIN=localhost` against the Auth emulator (§10.4). Production still cannot ship without it; tracked in M6 and Risk #9 |
| 3 | Playlists by URL as well as raw ID? | **Both** | §9.3 parses five URL forms plus raw IDs, and rejects `WL`/`LL`/`HL` with a specific explanatory error rather than a generic failure |
| 4 | Is 200 items/source the right ceiling? | **No — page fully** | Ceiling raised to YouTube's own 5,000-item cap. This forced the redesign of sync into a chunked, resumable, client-driven loop (§8.2, §9.4), added five progress/change-detection fields to `content_sources` (§4.5), and required preflight change detection to keep quota viable (§8.3). **The largest structural change from this round.** |
| 5 | Are the seven time blocks right? | **Ship as listed, revisit in testing** | §5.3 unchanged. Revisit is a v1.1 input, not a v1 task |
| 6 | Soft-delete discarded sessions for analytics? | **Hard delete** | §7.1 unchanged. Add an analytics path when there is an analytics consumer — not before |

**Still outstanding, deferred rather than answered:** whether a GCP quota increase will be granted before public launch (Risk #3), and whether Apple Fitness exposes a usable URL scheme (Risk #2, resolved by the M2 spike).
