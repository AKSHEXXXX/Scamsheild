# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

Open `TrustScan/TrustScan.xcodeproj` in Xcode 15+, select an iOS 16+ simulator, and press **Cmd+R**.

The root workspace file is `ScamShield.xcworkspace` — open that if you need both the app and share extension targets in scope at once.

**Run tests:**
- All tests: **Cmd+U** in Xcode, or via CLI:
  ```bash
  xcodebuild test -project TrustScan/TrustScan.xcodeproj -scheme TrustScan -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
  ```
- Single test class:
  ```bash
  xcodebuild test -project TrustScan/TrustScan.xcodeproj -scheme TrustScan -destination 'platform=iOS Simulator,name=iPhone 15 Pro' -only-testing:TrustScanTests/DTOsDomainMappingTests
  ```

## Environment Setup

The app reads credentials at runtime from `TrustScan/TrustScan/.env` using a simple `KEY=VALUE` parser in `App/Environment.swift`. This file is gitignored and must be dragged into the Xcode project navigator with **Target Membership: TrustScan** checked.

Keys read by the app:
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_ANON_KEY` — Supabase anon/public key
- `BACKEND_URL` — Railway FastAPI backend base URL

## Architecture

The project follows Clean Architecture with strict layer separation. Dependencies only flow inward (Features → Domain ← Data).

```
App/           — Entry point, DI container (AppEnvironment), deep-link routing
Core/          — Design tokens, shared UI components, NetworkMonitor, permissions
Domain/        — Pure Swift: Models, Port protocols (interfaces), Use Cases. No SwiftUI/UIKit imports.
Data/          — Concrete implementations: APIClient, SupabaseAuthService, Repositories, DTOs
Features/      — SwiftUI Views + ObservableObject ViewModels, split by screen
ScamShieldShareExtension/ — iOS Share Extension that deep-links back into the app
```

**Dependency injection** is handled entirely in `App/AppEnvironment.swift` — all repositories, use cases, and view models are constructed and wired there. Views receive dependencies via `@EnvironmentObject`.

**The scan flow:**
1. User picks image/QR/text → `SubmissionViewModel`
2. `SubmitAnalysisUseCase` runs Vision OCR on-device first
3. If OCR confidence ≥ 60% and text ≥ 20 chars → `POST /api/v1/analyze-text`
4. OCR fallback (low confidence or image-only) → base64 image to `POST /api/v1/sandbox-image`
5. QR codes detected via `VNDetectBarcodesRequest` → `POST /api/v1/check-qr`
6. Response `ScanOutDTO.toDomain()` maps backend verdict strings (`low_risk`/`suspicious`/`high_risk`) to `ThreatVerdict` enum (`.safe`/`.suspicious`/`.scam`)

**Auth flow** (`Data/Auth/SupabaseAuthService.swift`) is a hand-rolled Supabase client (no SDK) — tokens are persisted in `UserDefaults`. After sign-in, `AppEnvironment.syncAuthToken()` must be called to propagate the JWT to `APIClient` as a `Bearer` header.

**Backend API contract** (`Data/DTOs/DTOs.swift`):
- Score field: `scam_score` (not `score`)
- Finding description field: `message` (not `description`, kept as fallback)
- `flagged_urls` can be either a plain string array or array of `{url: string}` objects — `FlaggedUrlDTO` handles both

## Design System

All colors, typography, and spacing live in `Core/DesignTokens.swift`. Use `ColorTokens`, `TypographyTokens`, and `SpacingTokens` exclusively — no hardcoded values in views. Reusable components are in `Core/Components/Components.swift`.

## Testing Conventions

Tests use `@testable import TrustScan` and mock ports with hand-written fakes (e.g. `MockAnalysisRepository` in `SubmitAnalysisUseCaseTests.swift`). There is no mocking framework — implement the port protocol directly. Domain use cases and DTO mappings are the primary test targets.

## Deep Link / Share Extension

URL scheme: `scamshield://`
- `scamshield://scan?text=...` — text shared from another app
- `scamshield://scan?url=...` — URL shared from another app  
- `scamshield://scan?file=<filename>` — image written to App Group `group.com.binaryz.scamshield` by the share extension
- `scamshield://auth-callback` — Supabase OAuth redirect

The `AppDelegate` also blocks screen recording with a black overlay window.

