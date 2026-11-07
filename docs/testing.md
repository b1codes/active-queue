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
| No source file with code left untested | `frontend/scripts/check-untested-files.js` | part of `make check` |
| Workflow lint | actionlint 1.7.11 (Docker) | part of `make check` |
| API contract: OpenAPI snapshot, interaction examples, error-code registry | `contracts/`, `backend/tests/contract/` | `make test-backend` |
| API contract: provider replay on the emulators | `backend/tests/emulator/test_contract_provider.py` | `make test-backend` |
| API contract: consumer replay + compile-time type check | `frontend/src/__tests__/contracts/` | `make test-frontend`, `make typecheck-frontend` |
| API breaking-change diff of `contracts/openapi.json` vs the PR base (oasdiff) | `api-breaking` job in `ci.yml` | CI only |
| Third-party contracts (YouTube, Firebase Auth) against recorded data, one `ContentProvider` contract for both providers | `contracts/third_party/`, `backend/tests/contract/`, `backend/tests/unit/providers/test_provider_contract.py` | `make test-backend` |
| Third-party contracts against the real services (nightly, about 8 YouTube quota units) | `.github/workflows/contracts-nightly.yml`, `backend/tests/contract/thirdparty/` | `LIVE_CONTRACTS=1 uv run pytest tests/contract/thirdparty` |
| Firestore security rules deny all client access (SPEC §4.9), one rules file in the repo | `firestore-rules/rules.test.mjs` | `make test-firestore-rules` |
| Terraform fmt / validate | `infra/` | CI only |

`CI Passed` is the single aggregate check to mark as required in branch protection.
`scripts/deploy.sh` refuses to deploy a commit without a successful CI run on a push.

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
