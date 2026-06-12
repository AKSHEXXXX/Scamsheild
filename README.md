# ScamShield

**An anti-scam app for families.** Paste a suspicious message or upload a screenshot, and ScamShield checks it in seconds — flagging fake UPI IDs, phishing links, impersonation, and pressure tactics in plain language anyone can understand. Built with a focus on the scam patterns that target users in India.

> _This is guidance only — not legal advice._

---

## What it does

ScamShield takes a message or screenshot a user is unsure about and returns a clear risk verdict with plain-language reasons:

- **Check a message** — paste WhatsApp/SMS text and get an instant analysis.
- **Scan a screenshot** — upload an image of a message or payment request; the backend runs OCR and analyzes the extracted text.
- **Plain-language result** — a 0–100 risk score, a "Be careful / Looks safe" verdict, and a list of findings ("Fake UPI ID detected", "Pressure language", "No suspicious link found") instead of opaque jargon.
- **Report a scam** — users report scam UPI IDs, numbers, links, and the channel they appeared on, helping warn the wider community.
- **Your history** — every check and report is saved to the user's account so they can revisit past results.

---

## How detection works

For any piece of text (pasted directly, or extracted from a screenshot via OCR), the backend runs a multi-signal analysis:

- **UPI / VPA check** — extracts `name@bank`-style IDs and looks them up against a blacklist of reported fraudulent VPAs.
- **Phone number check** — extracts Indian phone numbers and checks them against a blacklist of reported scam numbers.
- **Link sandboxing** — extracts URLs, traces redirects with `httpx`, and checks the final domain against a phishing-domain blacklist (seeded from OpenPhish).
- **Pressure & impersonation language** — regex across 80+ patterns spanning legal/financial threats, government impersonation, fake order/transaction references, urgency escalation, parcel/courier scams, tech-support scams, and brand impersonation (including typosquatted domains like `amazon.con`).
- **Scoring** — signals are combined into a weighted 0–100 score (text risk + domain reputation) and bucketed into a verdict using a configurable sensitivity threshold. Each signal also produces a human-readable "finding" shown to the user.

The threat blacklists are refreshed nightly from public threat-intelligence feeds.

---

## Architecture

ScamShield is three coordinated codebases sharing one API contract.

| Layer | Tech | Owner |
|-------|------|-------|
| iOS app | SwiftUI | Akshat |
| Android app | Jetpack Compose / Kotlin | Sheehan |
| Backend + admin | Python FastAPI + Supabase | Pradyun |
| UI / UX design | — | Siddhant |

- **Mobile apps** handle auth, capture input (text / screenshot), call the backend, and render results. They never talk to the database directly — only to the backend API.
- **Backend (FastAPI)** runs OCR, the analysis pipeline, scoring, and persistence. Deployed on Railway. Uses the Supabase **service key** for all database access.
- **Database (Supabase Postgres)** stores config, scan history, reports, and the threat blacklists. **Supabase Studio** serves as the admin surface (config editing, telemetry, reviewing reports) — no custom admin portal.

```
[ iOS app ]  \
              >-- HTTPS -->  [ FastAPI on Railway ] -- service key -->  [ Supabase Postgres ]
[ Android app ] /                  |                                         (config, scans,
                            OCR · analysis · scoring                          reports, blacklists)
```

---

## Authentication & security

- **Login required.** Users sign in with email/password or Google (Supabase Auth) before using the app. The backend enforces this server-side — every API call requires a valid JWT and is rejected with `401` otherwise.
- **Per-user data isolation, enforced two ways:**
  1. **Row Level Security (RLS)** on Supabase — `scans` and `reports` are owner-scoped (`auth.uid() = user_id`), so a user can only ever see their own data even via direct database access. Config and blacklist tables are service-key-only.
  2. **Backend ownership checks** — because the service key bypasses RLS, the API independently verifies ownership on every per-user read.
- Cross-user isolation is verified by an automated two-user test (User B cannot read User A's scans or history).
- The mobile apps embed only the Supabase **anon/publishable** key (safe by design). The **service** key lives only in the backend's environment.

---

## API

Base URL: the deployed FastAPI service. All endpoints require `Authorization: Bearer <supabase_jwt>`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/config` | App config (scan caps, ad frequency, sensitivity threshold) |
| POST | `/api/v1/analyze-text` | Analyze pasted message text |
| POST | `/api/v1/sandbox-image` | OCR + analyze a screenshot (base64) |
| POST | `/api/v1/report` | File a scam report |
| GET | `/api/v1/history` | The signed-in user's scan/report history |
| GET | `/api/v1/scan/{scan_id}` | Retrieve a stored analysis result |
| GET | `/health` | Health check |

**Unified result object** (returned by the analyze endpoints and `scan/{id}`):

```json
{
  "scan_id": "uuid",
  "kind": "message | screenshot",
  "risk_score": 73,
  "verdict": "low_risk | suspicious | high_risk",
  "warning_count": 2,
  "extracted_text": "…",
  "findings": [
    { "type": "impersonation", "severity": "high",   "title": "Brand impersonation", "detail": "…" },
    { "type": "pressure",      "severity": "medium", "title": "Pressure language",   "detail": "…" }
  ],
  "flagged_urls": [
    { "url": "…", "final_url": "…", "reputation": "malicious | unknown | unreachable" }
  ]
}
```

---

## Data model (Supabase)

- `app_config` — single editable row of runtime settings.
- `scans` — every analysis, with `kind`, `input_text`, full `result_json`, `risk_score`, `verdict`, `warning_count`, owner `user_id`.
- `reports` — user-submitted scam reports (`report_type`, `value`, `channel`, `description`).
- `blacklisted_vpas`, `blacklisted_numbers`, `blacklisted_domains` — threat-intelligence reference data, B-tree indexed on the lookup columns, refreshed nightly.

---

## Repository layout

- `IOS` — SwiftUI app (Akshat)
- Android app — Jetpack Compose (Sheehan)
- `backend/` — FastAPI service, analysis pipeline, ingestion scripts (Pradyun)

_(Branch/folder names are being consolidated; see open items.)_

---

## Roadmap / open items

- Finish the redesigned multi-screen UI (Check / Scan / Report / History / Result) on both platforms.
- QR-code payment-request scanning.
- "Share result with family" via the native share sheet.
- Hindi/Hinglish keyword coverage and resistance to deliberate misspelling (move beyond pure regex toward a text classifier).
- Move the keyword list into a database table so detection can be tuned without redeploying.
- Custom SMTP for auth emails before scaling to real users.
- Standardize the product name (ShieldUPI / ScamShield) and bundle identifiers before store submission.

---

## Status

Core pipeline is live and verified end-to-end: auth, config, text and screenshot analysis, scoring with findings, reporting, history, RLS-enforced data isolation, and nightly threat-feed ingestion. The redesigned UI and pre-launch polish are in progress.
