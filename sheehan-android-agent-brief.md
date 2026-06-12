# Build Brief — Sheehan (Android) · SentinelShield/Scamshield

**For your coding agent (Claude Code / Codex).** This is the single source of truth for the Android app's current scope. Work top to bottom. Do not invent endpoints, payloads, or field names — they are fixed by the SHARED CONTRACT below and must match the iOS app and backend exactly. If something here conflicts with code already in the repo, stop and surface the conflict instead of guessing.

---

## Who owns what (so you don't build the wrong thing)

- **You (Sheehan): Android app — Jetpack Compose.** You implement only the two mobile sub-tasks: call the config endpoint on boot (1.4) and the screenshot scan flow (2.1).
- Akshat: iOS app (mirror of yours).
- Pradyun: backend (FastAPI) + Supabase DB + admin. He provides the deployed base URL and owns OCR/scoring/threat data. **You do not build any backend, OCR, or scoring logic.**

---

## ⚠️ SHARED API CONTRACT — identical for iOS, Android, Backend. Never change.

**Backend:** Python FastAPI service; database is Supabase Postgres. The app talks only to these HTTP endpoints.

**Base URL:** `<API_BASE_URL>` — Pradyun provides once deployed. Until then, use a placeholder constant; the final swap must be one line.

### Endpoint A — `GET /api/v1/config` (call once on launch, no auth)
200 response:
```json
{ "scan_credit_cap": 50, "ad_frequency": 3, "sensitivity_threshold": 70, "config_version": 1 }
```

### Endpoint B — `POST /api/v1/sandbox-image` (on screenshot submit, auth required)
Headers: `Content-Type: application/json`, `Authorization: Bearer <SUPABASE_ACCESS_TOKEN>`
Body:
```json
{ "image_base64": "<base64, no data: prefix>", "os": "Android" }
```
200 response:
```json
{
  "risk_score": 84,
  "verdict": "high_risk",
  "extracted_text": "…",
  "matched_keywords": ["Urgent KYC", "Account Blocked"],
  "flagged_urls": [{ "url": "http://x", "final_url": "http://y", "reputation": "malicious" }]
}
```
`verdict` ∈ `low_risk` | `suspicious` | `high_risk`. `<SUPABASE_ACCESS_TOKEN>` is the signed-in user's session token from the Supabase SDK.

> This replaces the old `smart-processor` test function. Do not wire the app to `smart-processor`.

---

## Non-negotiable rules for the agent

1. **Branch hygiene.** Pull the latest from the integration branch (`develop`) before starting. Work on `feature/sheehan-android`. Never commit directly to `main` or `develop`.
2. **Do not change the contract.** Endpoint paths, the request bodies, and every response field name above are fixed across three codebases. If you think one is wrong, raise it — don't edit it.
3. **`"os"` must be the exact string `"Android"`.** Backend telemetry splits iOS vs Android on this.
4. **HTTPS only.** Do not add `usesCleartextTraffic="true"` unless testing against Pradyun's plain-HTTP *dev* URL, and remove it before release.
5. **Never block the main thread.** Network calls run on `Dispatchers.IO`.
6. **Secrets:** only the Supabase **anon/publishable** key belongs in the app. Never the `service_role`/secret key.
7. After each phase, run the build and the listed acceptance check before moving on. Report status per phase.

---

## Phase 0 — Project builds and runs
- [ ] Gradle sync succeeds; the `app` run config appears; app launches on an emulator/device.
- [ ] `<uses-permission android:name="android.permission.INTERNET" />` is present in the manifest.
- **Acceptance:** blank app launches with no crash.

## Phase 1 — Auth (prerequisite for Phase 3)
- [ ] Supabase Kotlin SDK added; client initialized with project URL + anon/publishable key in one config object.
- [ ] Email/password sign-up and sign-in work.
- [ ] Google OAuth works: scheme + host set in the Auth config, matching redirect URL added in the Supabase dashboard, and `supabase.handleDeeplinks(intent)` called on startup.
- [ ] Can read the current access token via `supabase.auth.currentAccessTokenOrNull()`.
- **Acceptance:** a user can sign in with both email and Google, and the app can print a non-null access token.

## Phase 2 — Task 1.4: config on boot
- [ ] One `API_BASE_URL` constant (placeholder for now).
- [ ] On launch (`LaunchedEffect`/ViewModel init) call `GET /api/v1/config` on `Dispatchers.IO`, parse with `kotlinx.serialization`, `ignoreUnknownKeys = true`.
- [ ] UI reads `sensitivity_threshold`, `ad_frequency`, `scan_credit_cap` from this — nothing hardcoded.
- [ ] On failure, fall back to safe defaults (don't crash, don't block launch).
- **Acceptance:** with a mock/dev server returning the sample JSON, the values reach the UI; with the server down, the app still launches on defaults.

## Phase 3 — Task 2.1: screenshot → scan
- [ ] Screenshot picker (Photo Picker `PickVisualMedia` or `GetContent`) → `Bitmap`.
- [ ] Compress to JPEG (~quality 50) → `Base64.encodeToString(..., Base64.NO_WRAP)`.
- [ ] `POST /api/v1/sandbox-image` with the three headers and body `{ "image_base64": ..., "os": "Android" }`.
- [ ] Screen is gated behind sign-in (needs the token).
- [ ] Render result: `risk_score` as a 0–100 gauge, color by `verdict`, list `matched_keywords` and `flagged_urls`.
- [ ] Handle non-200 (e.g. 401 unauthenticated, 429 over credit cap) with a clear message.
- **Acceptance:** against a mock returning the sample response, the full pick→compress→upload→render path works and shows the score.

## Phase 4 — Integration (blocked on Pradyun's deployment)
- [ ] Replace the placeholder with Pradyun's real deployed base URL (one-line change).
- [ ] End-to-end: launch → config loads → sign in → pick a scam screenshot → real risk score shown.
- [ ] Confirm the scan registers on the backend (row in `scans` / `active_android_users` telemetry).
- **Acceptance:** a real scam screenshot returns a non-trivial `risk_score` from the live backend.

---

## Definition of done
1. App builds and runs; auth (email + Google) works.
2. Config loads on launch and drives UI dynamically.
3. Signed-in user can scan a screenshot and see `risk_score`/`verdict`/keywords from the live endpoint.
4. `"os": "Android"` sent on every scan; `API_BASE_URL` lives in one constant.
5. All work on `feature/sheehan-android`, contract untouched.

## Where to stop and ask a human
- The contract above seems wrong or the repo already does it differently.
- Pradyun hasn't shared a base URL yet (build Phases 0–3 against a placeholder/mock and wait).
- Anything requires the `service_role` key on the device — it must not go there.
