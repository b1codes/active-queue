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
| Every query the emulator tier runs is served by an index in `firestore.indexes.json` (the emulator never enforces this, production does), every declared index is used, one indexes file in the repo | `backend/tests/firestore_indexes.py`, `backend/tests/emulator/conftest.py`, `backend/tests/unit/test_firestore_indexes.py` | `make test-backend` |
| API image: hadolint (every Dockerfile), Trivy (fixable HIGH/CRITICAL fail), non-root user, then started **read-only** against the emulators and smoke-checked | `container` job in `ci.yml`, `.hadolint.yaml`, `scripts/container-smoke.sh`, `scripts/smoke_test.py` | `make test-container` |
| Terraform: fmt, `validate` of every environment root (locked providers), tflint (Google ruleset), Trivy config scan of Terraform and Dockerfiles | `terraform` job in `ci.yml`, `infra/.tflint.hcl` | CI only |
| Terraform module behavior with a mocked Google provider: the deployed image is the one passed in and pinned by digest, public invoker, least-privilege IAM, no emulator/DEBUG env, startup probe, scaling, real OAuth credentials | `infra/modules/activequeue_app/tests/` | `cd infra/modules/activequeue_app && terraform init -backend=false && terraform test` |
| Dependency audit (pip-audit, pnpm audit at high+) and gitleaks over full history | `security-scans` job in `ci.yml` | see [Security tests](#security-tests) |
| CodeQL (Python, TypeScript, Actions; security-extended) | `.github/workflows/codeql.yml` | CI only |
| OWASP ZAP API scan against staging (nightly) | `.github/workflows/security-nightly.yml` | CI only |

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
