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

## 3. Automated Deployment Command

Execute the deployment script to deploy to any target environment:

```bash
# Deploy to dev
./scripts/deploy.sh dev

# Deploy to staging
./scripts/deploy.sh staging

# Deploy to prod
./scripts/deploy.sh prod
```

---

## 4. Manual Deployment Workflow

If deploying manually step-by-step:

### Step 1: Build & Submit Container
```bash
gcloud builds submit backend/ \
  --tag us-central1-docker.pkg.dev/activequeue-prod/activequeue-api-prod/api:latest \
  --project activequeue-prod
```

### Step 2: Deploy Firestore Security Rules & Indexes
```bash
firebase deploy --only firestore:rules,firestore:indexes --project activequeue-prod
```

### Step 3: Apply Terraform Configuration
```bash
cd infra/environments/prod
terraform init
terraform apply -auto-approve
```
