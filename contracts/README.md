# API contracts

The single source of truth for what the app and the API say to each other. Both sides test
against these files, so a change that breaks the other side fails CI.

| File | Written by | Checked by |
|------|------------|------------|
| `openapi.json` | generated from the FastAPI app (`make contracts`) | backend drift test, CI breaking-change diff against `main`, frontend generated types |
| `interactions/*.json` | hand-written requests, provider-recorded responses | backend provider replay (emulators), frontend consumer replay (Jest) |
| `third_party/youtube/*.schema.json` | the YouTube Data API v3 fields `YouTubeProvider` relies on | recorded fixtures on every PR; the real API nightly |
| `third_party/firebase/*.schema.json`, `examples/` | ID-token claims `get_current_user` relies on; signing-cert shape | claim examples and Auth-emulator tokens on every PR; Google's real signing certs nightly |

## Interaction format

```jsonc
{
  "id": "sessions.start",                      // unique, used in test names
  "description": "Start a pending session",
  "states": ["alice has a pending session"],   // provider setup, see test_contract_provider.py
  "request": {
    "method": "POST",
    "path": "/api/v1/sessions/sess_1/start",   // exactly as the app sends it, query included
    "auth": "alice",                           // alice (default) | none | invalid | expired
    "body": { }                                // omitted when the app sends no body
  },
  "response": { "status": 200, "headers": { }, "body": { "status": "success", "data": { } } },
  "dynamic": ["data.started_at"],              // values not compared (still schema-checked)
  "consumers": ["startSession"]                // app functions that handle this response
}
```

- **Placeholders.** `uid_alice`, `src_1` and `sess_1` stand for ids the provider generates.
  Provider states bind them to real values, so examples stay stable and readable.
- **Strictness.** The provider's real response must match the OpenAPI schema with no
  undeclared or missing fields, and equal the example everywhere except `dynamic` paths.
- **Consumers.** Names resolve to entries in
  `frontend/src/__tests__/contracts/consumer.test.ts`. An interaction with no consumers needs
  a `consumer_note` saying why, for example a server-only endpoint the app doesn't call yet.

## Changing the API

1. `make contracts` regenerates `openapi.json` and `frontend/src/__tests__/contracts/openapi.gen.ts`.
2. `UPDATE_CONTRACTS=1 make test-backend` re-records response examples from the real provider.
3. Review the diff, then run `make test-frontend`.

The `API breaking changes` CI job (oasdiff) diffs `openapi.json` against the PR's base and
fails on breaking changes: a removed or narrowed response field, a new required request
field, or a removed endpoint. The installed app can't be updated in lockstep with the API,
so prefer additive changes. When a break is intended and the app rollout is planned, label
the PR `api-breaking-ok` and re-run the job.

## Third-party contracts

The backend depends on two services it doesn't control. Their schemas list only the
fields the code relies on, and they allow extra fields, which those APIs add freely.

- **YouTube Data API v3** (`playlists.list`, `playlistItems.list`, `videos.list`, error
  envelope). On every PR, the recorded fixtures in `backend/tests/fixtures/youtube/` must
  satisfy the schemas. `YouTubeProvider`, fed those fixtures, must pass the same
  `ContentProvider` contract as `FixtureProvider`
  (`backend/tests/unit/providers/test_provider_contract.py`). Nightly, the real API must
  satisfy the same schemas, including the empty-items and `playlistNotFound` shapes the
  error mapping depends on. That run spends about 8 quota units.
- **Firebase Auth.** The claims schema is checked on every PR against hand-built
  Sign in with Apple and email/password examples, and against tokens the Auth emulator
  mints. Nightly, Google's production signing certificates (the URL `firebase_admin`
  fetches) must parse, be current, and carry a cache `max-age`.

The nightly workflow needs the `YOUTUBE_API_KEY` secret and the
`YOUTUBE_CONTRACT_PLAYLIST_ID` variable. Without them it skips YouTube with a notice.
