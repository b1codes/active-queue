# End-to-End Physical Device & TestFlight Validation Guide

**ActiveQueue Infrastructure Specification §12.4, §15 & Risk #9**

---

## 1. Overview & Physical Device Testing Rationale

Per **SPEC §12.4** and **Risk #9**, emulator-based authentication is insufficient for production sign-off. Firebase Auth Emulators cannot validate:
- Real Apple Services ID entitlement bindings.
- Apple Developer Team & Key ID JWT signature generation.
- Custom Auth Domain (`auth.activequeue.app`) redirect handling.
- Dynamic Type text scaling and VoiceOver screen reader focus management on physical iOS hardware.

---

## 2. Physical Device Testing Matrix (SPEC §12.4)

| Device Category | Target Models | Dynamic Type Level | VoiceOver Audit | Connection Modes |
| :--- | :--- | :--- | :--- | :--- |
| **Small iOS Display** | iPhone SE (3rd Gen) / iPhone 13 mini | Standard & 1.5x | Full VoiceOver Pass | Cellular (LTE/5G) & Wi-Fi |
| **Standard iOS Display** | iPhone 15 / iPhone 16 | Standard & 1.5x | Full VoiceOver Pass | Wi-Fi & Offline Mode |
| **Large iOS Display** | iPhone 15 Pro Max / 16 Plus | Standard & 2.0x Accessibility | Full VoiceOver Pass | Cellular & Low Data Mode |

---

## 3. Physical Device Verification Procedure

### A. Sign in with Apple Verification
1. Install preview build on physical iPhone.
2. Launch ActiveQueue app and tap **"Sign in with Apple"**.
3. Verify native iOS Face ID / Touch ID prompt displays app name `ActiveQueue` and Services ID `com.activequeue.auth`.
4. Authenticate. Verify redirect routes through `https://auth.activequeue.app/__/auth/handler` cleanly without domain mismatch warnings.
5. Verify ID token verification succeeds on backend `POST /api/v1/users/me` and returns user profile document.

### B. End-to-End Session Workflow Verification
1. **Ingest Source**: Paste YouTube playlist URL (`https://youtube.com/playlist?list=PL...`). Verify sync progress bar updates smoothly and source items populate feed.
2. **Select Activity & Time**: Select activity (e.g. `Cycling`, 30 min duration). Verify time-matching algorithm surfaces content within ±10% tolerance window (27–33 min).
3. **Run Active Session**: Start session. Verify active session banner renders and timer ticks down.
4. **Complete Session**: Tap **"Complete Session"**. Verify transactional session completion marks feed items consumed and clears active session state.
5. **Feed Auto-Hide**: Return to feed screen. Verify completed items are automatically hidden from feed per SPEC §7.4.

---

## 4. TestFlight Build & Submission Commands

```bash
# 1. Build production iOS archive via EAS
cd frontend
eas build --platform ios --profile production

# 2. Submit build to App Store Connect / TestFlight
eas submit --platform ios --profile production
```
