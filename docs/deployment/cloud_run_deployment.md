# Cloud Run & Firestore Infrastructure Deployment Guide

**ActiveQueue Infrastructure Specification §4.9, §10.5 & Milestone 6 Subtask 5**

---

## 1. Overview & Security Boundaries

ActiveQueue deploys a containerized Python 3.12 FastAPI backend to Google Cloud Run v2 with native Firestore database storage and Secret Manager secrets.

### Key Security Boundaries (SPEC §4.9 & §10.3)
1. **Client Never Touches Firestore Directly**: All database access flows through the FastAPI backend using the `google-cloud-firestore` AsyncClient / Firebase Admin SDK.
2. **Deny-All Client Rules**: [`firestore.rules`](../../firestore.rules), the file `firebase.json` deploys, denies every client read and write. The Admin SDK bypasses security rules server-side, so even if the client Firebase API keys leak, raw Firestore access yields zero data. `make test-firestore-rules` proves this on the emulator, and fails if a second rules file appears in the repo.
3. **Emulator Host Unset Assertion**: [`backend/app/core/config.py`](../../backend/app/core/config.py) asserts that both `FIRESTORE_EMULATOR_HOST` and `FIREBASE_AUTH_EMULATOR_HOST` are unset in every deployed env (`dev`, `staging`, `prod`) to prevent auth bypass vulnerabilities.

---

## 2. Environment Deployment Architecture

ActiveQueue isolates infrastructure across three GCP projects:

| Environment | GCP Project ID | Cloud Run Service | Min Instances | Content Provider |
| :--- | :--- | :--- | :--- | :--- |
| **Dev** | `activequeue-dev` | `activequeue-api-dev` | `0` | `fixture` / `youtube` |
| **Staging** | `activequeue-staging` | `activequeue-api-staging` | `0` | `youtube` |
| **Prod** | `activequeue-prod` | `activequeue-api-prod` | `1` (0-cold-start) | `youtube` |

---

## 3. Deploying

```bash
scripts/deploy.sh dev      # or staging, prod
```

The script stops before changing anything if:

- the working tree is dirty, or the commit has no successful `CI` run on a push
- `FIREBASE_WEB_API_KEY` or `TF_VAR_google_oauth_client_id` isn't set
- an OAuth client secret is neither in `TF_VAR_*` nor in Secret Manager
- `youtube-api-key-<env>` has no enabled version (Cloud Run can't start a revision whose secret has no version)
- you can't sign JWTs as the smoke-test service account

Then it:

1. Builds `backend/` with Cloud Build as `…/api:<commit sha>` and deploys the image **by digest** (`…/api@sha256:…`). Terraform rejects a mutable tag such as `:latest`.
2. Deploys Firestore rules and indexes, before the new revision, so the indexes its queries need are already building.
3. Runs `terraform plan -out`, prints the plan, and applies **that saved plan** only after you type the environment name. There is no `-auto-approve`.
4. Runs `scripts/smoke_test.py` against the service URL:
   - `GET /health` (Cloud Run never routes `/healthz`)
   - 401 without a token
   - sign-in as `smoke-test-<env>` through a custom token signed by `activequeue-smoke-<env>@…`
   - `GET /users/me` and `GET /activities`
   - a forged token for that user must get 401
5. **If the smoke check fails**, it sends 100% of traffic back to the revision that was serving before and exits non-zero. The module declares 100% to the latest revision, so the next deploy's plan moves traffic forward again.

Cloud Run's startup probe hits `/healthz`, so a revision that can't reach Firestore never becomes ready and never takes traffic, even before the smoke check runs.

### Inputs

| Variable | What | Where it comes from |
|---|---|---|
| `FIREBASE_WEB_API_KEY` | The env's Firebase Web API key (the smoke check's sign-in) | Firebase console → Project settings |
| `TF_VAR_google_oauth_client_id` | Google OAuth client ID for Identity Platform | Google Cloud console → Credentials |
| `TF_VAR_google_oauth_client_secret` | Google OAuth client secret | Read from Secret Manager `google-oauth-client-secret-<env>` if unset |
| `TF_VAR_apple_client_secret` | Sign in with Apple client secret (JWT) | Read from Secret Manager `apple-oauth-client-secret-<env>` if unset |
| `TF_VAR_apple_services_id` | Apple Services ID | Defaults to `com.activequeue.auth` |
| `TF_VAR_smoke_test_signers` | Who may sign the smoke test's custom token, e.g. `'["user:you@example.com"]'` | Set once per env and keep it the same for every deployer, because Terraform replaces the list |

### First deploy of an environment

The Artifact Registry repository has to exist before the image can be pushed, so on the first run the script shows a targeted plan for just that repository and asks you to confirm it. After the full apply, add versions to the three secrets Terraform created:

- `youtube-api-key-<env>`
- `google-oauth-client-secret-<env>`
- `apple-oauth-client-secret-<env>`

Then deploy again. The first deploy's smoke check also needs you in `TF_VAR_smoke_test_signers`.

The smoke user (`smoke-test-<env>`) gets a normal user document on its first `/users/me`. It holds no data beyond default preferences.

---

## 4. What CI checks before a deploy can happen

- **`container` job:** hadolint, then a build of the exact image Cloud Run runs. It fails on a root user, runs a Trivy scan, then starts the image **read-only** against the emulators and runs the same smoke check.
- **`terraform` job:**
  - fmt, then `validate` of each environment with locked providers
  - `terraform test` of the module with a mocked Google provider: deployed image, public invoker, least-privilege IAM, startup probe, traffic, and OAuth inputs
  - tflint, and a Trivy config scan
  - stubbed tests of this deploy script and the smoke check
- **Backend emulator tier:** every Firestore query it runs must have a serving index in `firestore.indexes.json`, and every declared index must be used.

`terraform plan` per environment joins CI once CI has GCP credentials (SPEC §12.5).
