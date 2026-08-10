# Custom Authentication Domain Setup Guide

**ActiveQueue Infrastructure Specification §10.5 & House Standard 007 §2**

---

## 1. Overview & Policy Requirement

Per **House Standard 007 §2**, all production authentication flows for ActiveQueue (Google OAuth & Sign in with Apple) **MUST** route through a single, shared custom authentication domain (e.g. `auth.activequeue.app` or `auth.b1codes.com`).

> [!IMPORTANT]
> The default `*.firebaseapp.com` or `*.web.app` domains **MUST NEVER** be used in production. Default Firebase domains break Apple's strict domain verification requirements for Sign in with Apple and result in authentication failures on physical iOS devices.

---

## 2. DNS Record Delegation

To verify ownership and route custom authentication requests, add the following DNS records to your domain registrar (e.g. Cloudflare, Route53, Namecheap):

### A. TXT Domain Ownership Verification Record
| Record Type | Host / Name | Value / Content | TTL |
| :--- | :--- | :--- | :--- |
| `TXT` | `auth` | `google-site-verification=<VERIFICATION_CODE_FROM_GCP_CONSOLE>` | `Auto` / `300` |

### B. CNAME Routing Records
| Record Type | Host / Name | Target / Destination | TTL |
| :--- | :--- | :--- | :--- |
| `CNAME` | `auth` | `firebase.googleapis.com.` | `Auto` / `300` |

---

## 3. GCP Identity Platform Domain Authorization

Once DNS records are propagated, verify the custom domain in Identity Platform:

1. Navigate to **GCP Console → Identity Platform → Settings → Authorized Domains**.
2. Add `auth.activequeue.app` to the Authorized Domains list (handled automatically by Terraform in `infra/modules/activequeue_app/main.tf`).
3. Add `auth.activequeue.app` under **Apple Developer Portal → Certificates, Identifiers & Profiles → Service IDs → Sign in with Apple → Return URLs**:
   - Return URL: `https://auth.activequeue.app/__/auth/handler`

---

## 4. Frontend Client Environment Configuration

Ensure `.env.production` sets `EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN`:

```bash
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN="auth.activequeue.app"
```

In `frontend/src/features/auth/firebase.ts`:

```typescript
const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY || "fake-api-key",
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN || "auth.activequeue.app",
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID || "activequeue-prod",
};
```
