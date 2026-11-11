# Testing & CI gates

Run `make check` before pushing. It runs the same gates as CI (`.github/workflows/ci.yml`).

| Gate | Where it's defined | Local command |
|------|--------------------|---------------|
| Ruff lint + format (incl. bandit, pytest, async, datetime rules) | `backend/pyproject.toml` `[tool.ruff]` | `make lint-backend` |
| mypy --strict | `backend/pyproject.toml` `[tool.mypy]` | `make typecheck-backend` |
| Backend tests: unit, mocked integration, **emulator tier**, random order | `backend/tests/` | `make test-backend` |
| Backend coverage: **95% branch over all of `app/`** (single source of truth) | `backend/pyproject.toml` `[tool.coverage.report] fail_under` | `make test-backend` |
| ESLint 9 flat config + typescript-eslint strict, zero warnings | `frontend/eslint.config.js` | `make lint-frontend` |
| tsc --noEmit | `frontend/tsconfig.json` | `make typecheck-frontend` |
| Jest, random order, coverage over every file in `src/` + `app/` | `frontend/jest.config.js` `coverageThreshold` | `make test-frontend` |
| Accessibility audit of every story and every screen state, iOS settings (Reduce Transparency/Motion), contrast of every theme token, modal focus | `frontend/src/__tests__/a11y/`, `frontend/src/test-utils/a11y.ts` | `make test-frontend` |
| Text comes only from `@/core/components/Text` (Dynamic Type ceiling) | `no-restricted-imports` in `frontend/eslint.config.js` | `make lint-frontend` |
| Release build config: production `eas.json` sets every variable the app reads and none it doesn't, HTTPS API, Terraform's prod project and auth domain; `app.json` declares every scheme `canOpenURL` probes, installed plugins, existing assets | `frontend/src/__tests__/config/buildConfig.test.ts` | `make test-frontend` |
| expo-doctor (SDK-compatible versions, config) | `frontend` job in `ci.yml` | part of `make check` |
| No source file with code left untested | `frontend/scripts/check-untested-files.js` | part of `make check` |
| Workflow lint | actionlint 1.7.11 (Docker) | part of `make check` |
| API contract: OpenAPI snapshot, interaction examples, error-code registry | `contracts/`, `backend/tests/contract/` | `make test-backend` |
| API contract: provider replay on the emulators | `backend/tests/emulator/test_contract_provider.py` | `make test-backend` |
| API contract: consumer replay + compile-time type check | `frontend/src/__tests__/contracts/` | `make test-frontend`, `make typecheck-frontend` |
| API breaking-change diff of `contracts/openapi.json` vs the PR base (oasdiff) | `api-breaking` job in `ci.yml` | CI only |
| Third-party contracts (YouTube, Firebase Auth) against recorded data, one `ContentProvider` contract for both providers | `contracts/third_party/`, `backend/tests/contract/`, `backend/tests/unit/providers/test_provider_contract.py` | `make test-backend` |
| Third-party contracts against the real services (nightly, about 8 YouTube quota units) | `.github/workflows/contracts-nightly.yml`, `backend/tests/contract/thirdparty/` | `LIVE_CONTRACTS=1 uv run pytest tests/contract/thirdparty` |
| Firestore security rules deny all client access (SPEC §4.9), one rules file in the repo | `firestore-rules/rules.test.mjs` | `make test-firestore-rules` |
| Every query the emulator tier runs is served by an index in `firestore.indexes.json` (the emulator never enforces this, production does), every declared index is used, one indexes file in the repo | `backend/tests/firestore_indexes.py`, `backend/tests/emulator/conftest.py`, `backend/tests/unit/test_firestore_indexes.py` | `make test-backend` |
| API image: hadolint (every Dockerfile), Trivy (fixable HIGH/CRITICAL fail), non-root user, then started **read-only** against the emulators and smoke-checked | `container` job in `ci.yml`, `.hadolint.yaml`, `scripts/container-smoke.sh`, `scripts/smoke_test.py` | `make test-container` |
| Terraform: fmt, `validate` of every environment root (locked providers), tflint (Google ruleset), Trivy config scan of Terraform and Dockerfiles | `terraform` job in `ci.yml`, `infra/.tflint.hcl` | CI only |
| `scripts/deploy.sh` decisions with gcloud/terraform stubbed: deploys the built digest via a reviewed plan, refuses unsafe states before changing anything, rolls back on a failed smoke check; and `scripts/smoke_test.py` fails for each fault it targets | `scripts/tests/` | `python3 -m unittest discover -s scripts/tests` |
| Terraform module behavior with a mocked Google provider: the deployed image is the one passed in and pinned by digest, public invoker, least-privilege IAM, no emulator/DEBUG env, startup probe, scaling, real OAuth credentials | `infra/modules/activequeue_app/tests/` | `cd infra/modules/activequeue_app && terraform init -backend=false && terraform test` |
| Dependency audit (pip-audit, pnpm audit at high+) and gitleaks over full history | `security-scans` job in `ci.yml` | see [Security tests](#security-tests) |
| CodeQL (Python, TypeScript, Actions; security-extended) | `.github/workflows/codeql.yml` | CI only |
| OWASP ZAP API scan against staging (nightly) | `.github/workflows/security-nightly.yml` | CI only |
| API fuzzing: Schemathesis over every operation in `contracts/openapi.json` on the emulators (25 derandomized examples per operation per PR, 1000 with a fresh logged seed nightly) | `backend/tests/emulator/test_schemathesis_emulator.py`, `.github/workflows/fuzz-nightly.yml` | `make test-backend`, `make fuzz-api SEED=<n>` |
| App monkey: seeded random walks over every screen against a stateful fake API, healthy and flaky (fixed seeds per PR, 25 fresh seeds nightly), plus gesture races (double taps, back mid-request, backgrounding mid-sync) | `frontend/src/__tests__/fuzz/`, `frontend/src/test-utils/monkey.tsx`, `frontend/src/test-utils/fakeBackend.ts` | `make test-frontend`, `MONKEY_SEED=<n> pnpm test -- monkey` |
| Render budgets: a 1,000-item feed mounts at most 20 rows, sync ticks and banners re-render no row, nothing animates on the JS thread; every test holds the 2-layer GPU blur budget | `frontend/src/__tests__/perf/`, `frontend/src/core/perf/glassBudget.ts`, `frontend/jest.setup.ts` | `make test-frontend` |
| Production iOS bundle at most 6.5 MiB (startup) and free of Storybook and test code | `frontend/scripts/check-bundle.js`, `frontend` job in `ci.yml` | part of `make check` |
| Visual regression: every Storybook story screenshotted on the Tier 1 and Tier 3 glass on a pinned iOS simulator, diffed against baselines; light mode changes nothing | `frontend/.rnstorybook/screenshots/`, `frontend/scripts/screenshots/`, `frontend/screenshots/baselines/`, `screenshots` job in `ci.yml` | `make test-screenshots` (macOS) |
| E2E journeys: the Release app on a fresh iOS simulator, driven by Maestro, against the real API (fixture provider) on empty Firebase emulators. Sign in and out, add a source and watch it sync, hide a feed item, time block to completed session, match from the queue and abandon, two accounts on one device. No journey may cause a 5xx. | `e2e/`, `e2e` job in `ci.yml` | `make e2e` (macOS) |
| Firestore reads and writes per request, as a heavy user (4 sources, 1,200-item feed, 30 sessions), each endpoint held to a budget from what bounds it | `backend/tests/emulator/test_read_budgets_emulator.py`, `backend/tests/firestore_meter.py` | `make test-backend` |
| Sync cost at the 5,000-item cap: YouTube quota units (cold, warm, throttled, unchanged, capped), Firestore writes, wall time | `backend/tests/emulator/test_sync_cost_emulator.py` | `make test-backend` |
| API image under Cloud Run's 1 vCPU / 512 MiB: cold start, first signed-in request, peak memory, plus the 45 s k6 load smoke against it | `container` job in `ci.yml`, `scripts/container-perf.sh`, `loadtest/api.js` | `make test-container` |
| k6 API load: 20 users for 3 min with p95 budgets per endpoint, no 5xx, no throttled legitimate user, abuser and IP flood limited (nightly, emulator stack and staging) | `.github/workflows/perf-nightly.yml`, `loadtest/` | `make load-test` |

`CI Passed` is the single aggregate check to mark as required in branch protection.
`scripts/deploy.sh` refuses to deploy a commit without a successful CI run on a push, applies
only a reviewed plan, and smoke-checks the result with rollback (see
[the deployment guide](deployment/cloud_run_deployment.md#3-deploying)).

The emulator tier uses `firebase.test.json` (Firestore 9190, Auth 9199), so it never wipes
the dev emulators. It needs Java 21. `make test-emulator` runs them in the foreground.
Without the emulators the tier is skipped locally. With `REQUIRE_EMULATOR=1` (as in CI)
it fails instead.

## API contract tests

`contracts/` is the shared contract between the app and the API (see `contracts/README.md`):

- `openapi.json` is generated from the FastAPI app and committed. Every API change shows up
  as a diff.
- `interactions/*.json` hold recorded request/response pairs. The backend replays each one
  against the real app on the emulators (provider). Jest replays each one through the app
  code that consumes it (consumer).
- `frontend/src/__tests__/contracts/openapi.gen.ts` is generated from `openapi.json`.
  `types.contract.ts` fails to compile when the app's hand-written API types drift from it.

After an intentional API change:

1. `make contracts` regenerates `openapi.json` and the frontend types.
2. `UPDATE_CONTRACTS=1 make test-backend` re-records the interaction examples. Values at
   `dynamic` paths and placeholders (`uid_alice`, `src_1`, `sess_1`) are preserved.
3. Review the diff, then run `make test-frontend`. If the app can't handle the new response,
   the consumer suite fails here, before a user sees it.

## Accessibility tests

`frontend/src/test-utils/a11y.ts` walks a rendered tree and fails on what VoiceOver, Dynamic
Type and low-vision users would hit. Call `expectAccessible()` after rendering anything:

| Rule | Fails when |
|------|------------|
| `role`, `name` | a pressable has no `accessibilityRole`, or nothing to announce |
| `state` | a radio/checkbox/switch has no `checked`, a tab no `selected`, or a button shows a spinner without `busy` |
| `nested` | a control sits inside an `accessible` element. iOS exposes only the outer one, so VoiceOver can't reach the control. |
| `input-label` | a `TextInput` relies on its placeholder |
| `target` | a declared size is under 44pt, `hitSlop` included (SPEC §11.4) |
| `font-cap` | text has no `maxFontSizeMultiplier`, one above `fontScale.max`, or `allowFontScaling={false}` |
| `clip` | at its ceiling, text no longer fits a fixed-`height` box around it |
| `decorative` | a lone icon or emoji isn't hidden from VoiceOver |
| `contrast` | text is under 4.5:1 (3:1 at 24pt, or 18.66pt bold), or an icon under 3:1, against the composited background. Disabled controls are exempt. |

Each rule has a self-test that fails on a known-bad tree (`a11y/auditor.test.tsx`). The
sweeps:

- `stories.a11y.test.tsx` renders every Storybook story inside its own and its meta's
  decorators (as the screenshot harness does, so contrast is checked against the real
  backdrop). New stories are picked up automatically.
- `screens.a11y.test.tsx` renders every route in its loaded, empty, error and in-flight
  states.
- `settings.a11y.test.tsx` covers:
  - Reduce Transparency on both glass tiers
  - the Tier 3 header over white, Ink, Heat Core and Signal Verified content
  - every text token on every ground
  - a source check that no animation escapes Reduce Motion: Reanimated's
    `ReduceMotion.System` default is what keeps ThermalGlow still
- `focus.a11y.test.tsx` checks the add-source sheet's reading order, Modal containment,
  escape gesture and error announcement.

All text renders through `@/core/components/Text`, which defaults `maxFontSizeMultiplier` to
`fontScale.max` (2.0). Use `fontScale.compact` (1.5) only for chrome in fixed-height rows.
When `clip` fires, prefer `minHeight` over a lower cap.

The checks read declared props and styles, not native layout. Spatial VoiceOver order, real
line wrapping and Tier 1 vibrancy are in [manual-qa.md](manual-qa.md#accessibility).

## Fuzz and monkey tests

**API: Schemathesis** (`backend/tests/emulator/test_schemathesis_emulator.py`) generates valid and
invalid requests from the committed contract and sends them, as a signed-in user, to the real
app under uvicorn on the emulators. A response fails when it:

- is a 5xx,
- uses a status code, content type, header or body the contract doesn't document,
- rejects input the contract allows, or accepts input it forbids,
- still answers when Schemathesis resends the request without the token or with a bad one,
- answers an undeclared method without a 405 and an accurate `Allow` header.

Exemptions sit at the top of the file, each with its reason. When a failure is the contract
being vague, fix the contract (for example, the ID `pattern`) rather than adding an exemption.

**App: monkey** (`frontend/src/__tests__/fuzz/monkey.test.tsx`) mounts each screen and takes
seeded random actions: taps, double taps, two-finger taps, long presses, VoiceOver actions,
scrolls, pull to refresh, typing, toggles, alert answers, swipe back, and background and
return. `router.push`/`replace`/`back` really change screens. The API is
`src/test-utils/fakeBackend.ts`, an in-memory server that keeps the session state machine,
chunked syncs and the real error codes. In flaky mode, 15% of requests fail. A run fails on:

- a crash,
- a `console.error`,
- an unhandled rejection (Jest fails the test),
- rendered `undefined`/`NaN`/`[object Object]`,
- a request to a route the API doesn't have,
- a screen left with nothing to tap and nowhere to go back to.

`monkey.selftest.test.tsx` proves each of these is caught, and that the same seed replays the
same walk.

**Gesture races** (`gestureRaces.test.tsx`) press twice in one frame, before the first press
can re-render a button disabled. So guard an action where it starts (the store function or a
ref), not with `disabled` alone. After an `await`, navigate only if the screen is still
mounted (`useIsMounted`).

Replaying a nightly failure: the run's summary prints the seed and the command.

```sh
make fuzz-api SEED=<seed> FUZZ_MAX_EXAMPLES=1000                       # API
cd frontend && MONKEY_SEED=<seed> MONKEY_RUNS=25 MONKEY_STEPS=300 pnpm test -- monkey   # app
MONKEY_LOG=1 ...   # print each walk
```

The monkey drives React through Jest, so native gesture recognition, real multi-touch and
iOS's own crash reporting are outside it. The E2E journeys exercise native gestures on
the simulator (see [E2E tests](#e2e-tests)). A seeded random walk there is a follow-up.

## Performance and load tests

**Firestore cost per request.** Firestore bills per document, so reads are both a
request's cost and most of its latency. `tests/firestore_meter.py` wraps the SDK's gRPC
client and counts what Firestore bills: one read per document a query returns (one if it
returns none), one per document a get asks for, one per 1,000 entries a `count()` matches,
one write per write in a commit. `test_read_budgets_emulator.py` runs every endpoint as a
heavy user and holds each to a budget derived from what bounds it: a page size, the
5-source cap, `TIME_MATCH_RESULT_LIMIT`. A new query whose reads grow with the user's data
fails here. `pytest -s` prints the whole table.

**Sync cost.** `test_sync_cost_emulator.py` runs the real `YouTubeProvider` against a fake
Data API that bills each call, and holds SPEC §8.3's scenarios to their budgets at the
5,000-item cap:

| Scenario | Units |
|----------|------:|
| cold (nothing cached) | 201 |
| warm (another user already synced it) | 101 |
| start within 15 minutes of the last | 0 |
| unchanged since the last walk | 1 |

It also checks that a walk stops at `max_items_per_source`, that cache entries older than
30 days are fetched again, and the writes and wall time of a cold sync.

**Load (k6).** `loadtest/api.js` has three scenarios:

- `journey`: each virtual user is one app user (feed, match-time, match, create, start,
  complete or abandon, history), with think time and a staggered start.
- `abuser`: one user at 4 requests a second.
- `flood`: one address at 15 requests a second with no token.

A run fails on any 5xx, any 429 to a journey user, an abuser or flood that is never
limited, a 429 without `Retry-After`, or a p95 over budget. `loadtest/run.sh` mints the
tokens, wipes the test emulators and runs k6 from a pinned image.

| Profile | Where | Duration | Latency budgets |
|---------|-------|----------|-----------------|
| `smoke` | every PR, against the built image (`container` job) | 45 s | 10x `local`: catches pathological regressions only |
| `local` | nightly, uvicorn on the emulators | 3 min | regression tripwires |
| `staging` | nightly, when its variables are set (see the workflow header) | 3 min | SPEC §1.4: feed p95 ≤ 400 ms |

Locally, each user gets its own client address through `X-Forwarded-For` with
`TRUSTED_PROXY_HOPS=1`, as Cloud Run's front end provides. On staging every user shares
the runner's address, so the run stays under the 300/min per-IP guard and has no flood
scenario. The limiter is per instance (SPEC §10.2), so staging doesn't require the abuser
to be limited.

Two things to know when reading the numbers:

- The emulator has no indexes and scans a collection per query, so the `local` budgets
  are regression tripwires, not targets. They sit at about 4x what 20 users measure on a
  GitHub ubuntu runner (feed p95 ~37 ms). On macOS, Docker Desktop and the emulator run
  about 10x slower, so `run.sh` multiplies them by `LOAD_LATENCY_FACTOR` (10 on macOS, 1
  elsewhere). The read budgets above cover cost at scale.
- The limiter's windows are fixed to the minute. A short run can split a client's requests
  across two windows, so the smoke rates are set to exceed each limit in half the run.

```sh
make load-test                    # nightly profile, results in loadtest/out/
make load-test PROFILE=smoke      # the per-PR version
make test-container               # cold start, memory and the smoke run against the image
```

Cold start and memory: `scripts/container-perf.sh` starts the image read-only with
`--cpus 1 --memory 512m`. It times `docker run` to the first `/healthz` 200 (budget 4 s)
and the first signed-in request (1.5 s), samples memory during the smoke run (budget
256 MiB, half the limit), and fails on an OOM kill. On staging, the nightly job times the
first request of the night, normally a cold start (budget 6 s).

**App.** Jest can't measure frames, but it can count the work that costs them, the
same way every time:

- `src/__tests__/perf/renderBudgets.test.tsx` mounts a 1,000-item feed and fails if
  more than 20 rows mount. It also fails if 20 sync-progress ticks, or a banner change
  above the list, re-render any row. It counts `FeedCard` through a wrapper that keeps its
  memo comparison, so a parent passing a fresh callback fails. A source check fails on
  `requestAnimationFrame`, `setInterval`, core `Animated` or `LayoutAnimation` in app code:
  animation runs as Reanimated worklets on the UI thread.
- The GPU blur budget (at most 2 concurrent glass layers, `src/core/perf/glassBudget.ts`)
  is checked after every test by `jest.setup.ts`, across every story, screen state and
  monkey walk.
- Startup: Hermes maps the whole bundle at launch. `scripts/check-bundle.js` fails a
  production iOS export over 6.5 MiB (5.70 MiB in Nov 2026), or one that contains
  Storybook (+2.9 MiB) or test code.

Real frame rate, launch time on a device, and how the blur feels while scrolling are in
[manual-qa.md](manual-qa.md#performance).

## Visual regression tests

Every Storybook story is screenshotted on a pinned iOS simulator, on both glass tiers, and
compared with `frontend/screenshots/baselines/`. CI runs it on every PR
(the `screenshots` job).

**How a capture is made.**
- `scripts/ios-sim-build.sh screenshots` builds a Release simulator app whose JS entry is
  the harness (`.rnstorybook/screenshots/`), not expo-router. It renders one story full
  screen, inside its own, its meta's and `preview.tsx`'s decorators.
- `scripts/screenshots/capture.js` boots a new simulator for each run. It launches the app
  once per story and tier, choosing the story with launch arguments (`-vrStory <id>
  -vrTier <1|3>`). A deep link would stop at iOS's "Open in ActiveQueue?" prompt.
- Once the story has mounted, the harness pings a localhost server the script runs. Only
  then does capturing start. A slow cold launch leaves the home screen or splash still for
  seconds, and that would otherwise pass for a settled story.
- It saves a screenshot once two frames in a row are identical, then compares it with the
  baseline.

**Comparing.** A pixel has changed when any channel moved by more than 3 of 255
(`channelTolerance` in `reference.json`), and a capture fails on any changed pixel. The
tolerance absorbs the 1 to 2 levels of dithering the Tier 1 material shows from one
launch to the next. A layout shift, a new string or a changed color token moves far more.

`reference.json` also lists masked rectangles. Today that's only the Dynamic Island,
which iOS sometimes draws into a simulator screenshot around a launch.

The diff image marks changed pixels in red over a faded copy of the capture.

**What's held still.**
- The clock is frozen at 2026-11-03 09:41 UTC.
- Reduce Motion is on, which stills ChromaticPulse, ThermalGlow and the skeletons at
  their first frame.
- `ActivityIndicator` is swapped for a stopped one that stays visible: UIKit's spinner
  ignores Reduce Motion.
- Remote images are replaced with a bundled thumbnail.
- Each capture is a fresh launch with the status bar hidden, in en_US at the default text
  size.

Two full runs on fresh simulators matched on all 101 captures before the baselines were
committed.

**Glass tiers.** `overrideGlassTier()` renders every surface through Tier 1 (the native
iOS 26 material) or Tier 3 (the Skia fallback), so a regression in either tier shows up.

**Dark only.** `app.json` sets `userInterfaceStyle: "dark"`, so light mode must change
nothing. The run re-captures three stories in light mode and fails if any pixel differs.

**The reference platform** is pinned in `frontend/screenshots/reference.json`:

| Setting | Value |
|---------|-------|
| Runner | GitHub's `macos-26` |
| Xcode | 26.6 |
| Simulator | iPhone 17 Pro, iOS 26.5 |

An app linked against another Xcode SDK can render differently even on the same
simulator. So `capture.js` reads the Xcode that built the app (`DTXcode`), and compares
against baselines only when it matches. Elsewhere:

- `--off-reference` checks that every story renders and settles, and reports diffs
  without failing on them.
- `--baselines <dir>` compares two local runs with each other, to check that rendering is
  deterministic on your machine.

**Changing how something looks.**

1. Push. The `screenshots` job fails and uploads the `screenshots` artifact: `actual/`,
   `diff/` (changed pixels in red) and `report.json`.
2. Review the diffs. Every changed story should be one you meant to change.
3. Run `make screenshots RUN=<run-id>`. It takes that run's captures as the baselines,
   including adding new stories and dropping removed ones. Commit the result.

A new story needs a baseline before CI passes. Jest's `visual/catalog.test.tsx` fails on
any story without a baseline on both tiers, and on any baseline without a story.

```sh
make test-screenshots                                   # build + capture + diff (reference Xcode)
make test-screenshots SCREENSHOT_ARGS=--off-reference   # on another Xcode: harness check only
make screenshots RUN=<ci-run-id>                        # accept a CI run's captures
cd frontend && node scripts/screenshots/capture.js --off-reference --only feedcard   # a subset
```

Not covered here: how the Tier 1 material moves and refracts as content scrolls under it
(a still can't show that), and real devices. See
[manual-qa.md](manual-qa.md#visual-settings).

## E2E tests

`e2e/run.sh` runs the journeys in `e2e/flows/` against the whole stack:

- **The app:** a Release simulator build (`frontend/scripts/ios-sim-build.sh e2e`) with
  the emulator settings inlined: API on `127.0.0.1:8090`, Auth emulator on 9199.
- **The API:** the real FastAPI app under uvicorn, on the test emulators (Firestore 9190,
  Auth 9199). Both are emptied at the start of every run.
- **Content:** the fixture provider stands in for YouTube. `FIXTURE_PAGE_LATENCY_MS=200`
  gives each playlist page a real Data API round trip, so a 1,200-item sync takes a few
  seconds and its progress can be watched.
- **The simulator:** a new iPhone 17 Pro on iOS 26.5 each run, with an English-only
  keyboard and no autocorrect, predictions or swipe typing. XCTest types key by key, and
  those features rewrite or swallow keys.

Each journey creates its own Auth-emulator account (`common/create-account.js`) and signs
in through the real sign-in screen. No journey depends on another's data, so they can run
in any order or alone. The runner also fails if any request in the API log got a 5xx.

| Journey | What it proves |
|---------|----------------|
| `sign-in-out` | A wrong password is refused with the plain-language message (and VoiceOver hears the same). Sign-in survives a relaunch; sign-out does too. |
| `add-source-sync` | An unknown playlist is refused with a reason. A 1,200-item playlist syncs in chunks with visible progress and fills the queue (count badge 1.2k). |
| `hide-feed-item` | Hiding from the options menu removes the card, and it stays hidden after a relaunch. |
| `time-block-complete` | Time first (SPEC §5.3: a block B takes B to B+5 min, else B−2 min to B). 60 min has no match, 45 min matches a 45:00 video. Start, hand off to the media, come back, complete. History shows it. |
| `match-abandon` | Content first: pick a queued 15:00 video, pick an activity, start, hand off, abandon. No active session is left, and History shows the abandon. |
| `multi-account` | After Alice signs out, Bob sees none of her sources, queue or history. Alice's data is there when she signs back in. |
| `change-preferences` | Skipped (`tags: [skip]`): the app has no preferences screen yet (ClickUp 86bcyn043). |

The media hand-off opens the video in Safari, since the simulator has no YouTube app.
The journey then brings the app back. Real YouTube, Apple Fitness and tracker apps, and
Sign in with Apple, stay in [manual-qa.md](manual-qa.md#platform-hand-offs).

Selectors are accessibility labels where the app has them, which keeps them honest: a
label VoiceOver can't use is one a journey can't either. Text inputs have `testID`s,
because a label also matches the field's visible caption. Taps that can land mid-animation
(the keyboard coming up) are verified and retried: `common/sign-in.yaml` checks each
field's value after typing.

```sh
make e2e MAESTRO=<path to maestro>                         # build, then every journey
make e2e MAESTRO=... FLOWS=e2e/flows/hide-feed-item.yaml   # one journey
```

Results land in `frontend/build/e2e/`: `report.xml` (JUnit), each flow's screenshots and
view hierarchy on failure (`artifacts/`), and `api.log`. CI uploads them as the `e2e`
artifact. Maestro is pinned in `ci.yml` (`MAESTRO_VERSION`, checked by SHA-256).

## Security tests

| What | Where |
|------|-------|
| Every operation (from the OpenAPI inventory) needs a token. A second user gets 404 on every owned ID and never sees the first user's identifiers. The first user's documents stay unchanged. Unclassified new routes fail. | `backend/tests/emulator/test_authz_matrix.py` |
| ID tokens checked by the Admin SDK in production mode with locally signed tokens: expired, wrong aud/iss, alg=none, HS256 key confusion, wrong or unknown key, tampered payload, future iat, bad sub, non-Bearer credentials | `backend/tests/integration/test_token_verification.py` |
| Revoked tokens and deleted users get 401, Firebase-disabled users get 403 (cached per uid for 60 s). Run against real Auth-emulator accounts. | `backend/tests/emulator/test_auth_emulator.py`, `test_token_verification.py` |
| Deployed envs refuse emulator hosts, and only `local` defaults to them | `backend/tests/unit/test_config.py` |
| Rate limits keyed on verified uids. Forged tokens can't dodge a limit, drain a victim's budget, or raise their tier. Per-IP flood guard, X-Forwarded-For hop trust, burst behavior. | `backend/tests/integration/test_ratelimit_middleware.py` |
| Hypothesis fuzzing of the sanitizers, request models and provider models (unit), plus hostile path IDs, source URLs and preference bodies through the API (emulators) | `backend/tests/unit/test_sanitizer_properties.py`, `backend/tests/emulator/test_input_fuzz_emulator.py` |
| Firestore rules deny every client operation, and only one rules file exists | `firestore-rules/rules.test.mjs` |

Running the scans locally:

```sh
# Python dependencies
cd backend && uv export --frozen --no-emit-project --format requirements-txt -o /tmp/req.txt \
  && uvx pip-audit@2.10.0 -r /tmp/req.txt --require-hashes --disable-pip
# npm dependencies (no install needed; reads the lockfile)
(cd frontend && pnpm audit --audit-level high) && (cd firestore-rules && pnpm audit --audit-level high)
# Secrets, whole history
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 git /repo --config /repo/.gitleaks.toml --redact
```

Exceptions are reviewed, kept next to what they exempt, and need a written reason:
`auditConfig.ignoreGhsas` in `frontend/pnpm-workspace.yaml`, `[[allowlists]]` in
`.gitleaks.toml`, and `.zap/api-scan-rules.tsv`. Dependabot (`.github/dependabot.yml`)
opens grouped weekly updates. Expo SDK packages are excluded because they move together
via `npx expo install --fix`.
