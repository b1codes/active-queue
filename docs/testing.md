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
| Terraform fmt / validate | `infra/` | CI only |

`CI Passed` is the single aggregate check to mark as required in branch protection.
`scripts/deploy.sh` refuses to deploy a commit without a successful CI run on a push.

The emulator tier uses `firebase.test.json` (Firestore 9190, Auth 9199), so it never wipes
the dev emulators. It needs Java 21. `make test-emulator` runs them in the foreground.
Without the emulators the tier is skipped locally. With `REQUIRE_EMULATOR=1` (as in CI)
it fails instead.
