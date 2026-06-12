# ARCHITECTURE.md — Technical Architecture
## TrustScan: iOS Scam Detection Application

**Version:** 1.0  
**Status:** Active  
**Last Updated:** June 2026

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Responsibility Boundaries](#2-responsibility-boundaries)
3. [Layered Architecture](#3-layered-architecture)
4. [Data Flow](#4-data-flow)
5. [Domain Models](#5-domain-models)
6. [State Management Strategy](#6-state-management-strategy)
7. [Folder Structure](#7-folder-structure)
8. [Dependency Boundaries](#8-dependency-boundaries)
9. [Networking Architecture](#9-networking-architecture)
10. [Local Persistence Architecture](#10-local-persistence-architecture)
11. [Reusable Component Philosophy](#11-reusable-component-philosophy)
12. [Error Handling Philosophy](#12-error-handling-philosophy)
13. [Security Architecture](#13-security-architecture)
14. [Performance Architecture](#14-performance-architecture)
15. [Testing Strategy](#15-testing-strategy)
16. [Scalability Considerations](#16-scalability-considerations)

---

## 1. High-Level Architecture

TrustScan is a native iOS application following **Clean Architecture** principles, organized into three primary layers: Presentation, Domain, and Data. The architecture enforces strict dependency direction — outer layers depend on inner layers, never the reverse.

```
┌───────────────────────────────────────┐
│           PRESENTATION LAYER          │
│  SwiftUI Views · ViewModels · Router  │
└───────────────────┬───────────────────┘
                    │ depends on
┌───────────────────▼───────────────────┐
│              DOMAIN LAYER             │
│  Use Cases · Domain Models · Ports    │
└───────────────────┬───────────────────┘
                    │ depends on (via abstractions)
┌───────────────────▼───────────────────┐
│               DATA LAYER              │
│  Repositories · API Client · Storage  │
└───────────────────────────────────────┘
                    │ communicates with
┌───────────────────▼───────────────────┐
│            EXTERNAL SYSTEMS           │
│  Backend API · iOS System APIs · OS   │
└───────────────────────────────────────┘
```

The architecture is optimized for:

- **Testability:** All business logic exists in the Domain layer, independent of SwiftUI, networking, and persistence.
- **Replaceability:** Any infrastructure component (networking library, persistence engine, analytics provider) can be swapped without touching Domain or Presentation code.
- **AI-assisted development:** Feature modules are self-contained with clear entry points, minimizing context required to add or modify behavior.
- **Explicit data flow:** State flows in one direction, making behavior predictable and debuggable.

---

## 2. Responsibility Boundaries

### iOS Application Responsibilities

The iOS application is responsible exclusively for the client layer:

| Responsibility | Description |
|----------------|-------------|
| Image capture and selection | Interfacing with PHPickerViewController and AVCaptureSession |
| Image preparation | Compression, resizing, and format validation before transmission |
| API communication | Constructing, sending, and receiving HTTP requests to the backend |
| Result presentation | Rendering threat scores, indicators, verdicts, and recommendations |
| Local history | Persisting analysis results for user reference |
| State management | Managing UI state across submission, loading, result, and error phases |
| Permission management | Requesting and handling photo library and camera permissions |
| Error recovery | Detecting, categorizing, and presenting recoverable error states |
| Analytics | Emitting anonymized usage telemetry to a first-party endpoint |

### Backend Responsibilities (Out of Scope for iOS)

| Responsibility | Description |
|----------------|-------------|
| OCR processing | PaddleOCR-based text extraction from images |
| Text analysis | Threat pattern detection in extracted text |
| URL sandboxing | Dynamic analysis of URLs found in content |
| Threat scoring | Algorithm-based risk score calculation |
| Intelligence databases | Known scam indicators, domains, and patterns |
| Telemetry aggregation | Collection and analysis of platform-wide signals |
| Dynamic configuration | Feature flags and remote configuration delivery |
| Admin portal | Internal tooling for platform management |

---

## 3. Layered Architecture

### 3.1 Presentation Layer

The Presentation layer is composed of SwiftUI Views and their associated ViewModels. This layer is responsible solely for rendering state and translating user interactions into intent signals.

**Views** are passive renderers. They observe ViewModel state and emit user events. Views contain no business logic.

**ViewModels** mediate between the View and the Domain layer. They:
- Hold the view's observable state
- Call use cases in response to user events
- Transform domain models into view-ready display models
- Handle presentation-specific logic (formatting, truncation, copy)

**Router / Navigation** manages all navigation state. Navigation is centralized to prevent scattered push/present calls across the view tree. A single NavigationCoordinator owns the navigation stack and path.

### 3.2 Domain Layer

The Domain layer is the heart of the application. It contains:

**Use Cases** — named, single-responsibility objects encapsulating a specific user-facing action:
- `SubmitAnalysisUseCase`
- `FetchAnalysisResultUseCase`
- `LoadHistoryUseCase`
- `DeleteHistoryEntryUseCase`
- `CheckAnalysisStatusUseCase`
- `PrepareImageForSubmissionUseCase`

**Domain Models** — pure Swift data structures with no framework dependencies. These are the canonical data shapes used throughout the app.

**Repository Ports** — protocol definitions that the Data layer implements. The Domain layer depends on these abstractions, not on concrete implementations.

**Error Types** — a domain-level error enumeration that categorizes all possible failure modes. Network, parsing, validation, and system errors are mapped to domain errors before reaching the Domain layer.

### 3.3 Data Layer

The Data layer implements the Repository Ports defined in the Domain layer. It is the only layer permitted to depend on:
- Networking (URLSession / networking abstraction)
- Persistence (SwiftData / CoreData / file system)
- Keychain
- External SDKs

**Repositories** implement data access, combining API and local storage as required. Example: `AnalysisRepository` fetches from the API and writes to local persistence on success.

**API Client** handles HTTP request construction, encoding, execution, and response decoding. It is a thin infrastructure component — it does not contain business logic.

**Local Storage** manages persistent data using SwiftData (iOS 17+) with a CoreData fallback path for iOS 16. History entries, pending submission state, and cached configuration are stored here.

---

## 4. Data Flow

### Submission Flow

```
User Action (tap submit)
        │
        ▼
View emits event to ViewModel
        │
        ▼
ViewModel calls PrepareImageForSubmissionUseCase
        │
        ▼
Use Case validates, compresses, and prepares image
        │
        ▼
ViewModel calls SubmitAnalysisUseCase
        │
        ▼
Use Case calls AnalysisRepository.submit(image:)
        │
        ▼
Repository delegates to APIClient.post(...)
        │
        ▼
APIClient sends multipart/form-data request
        │
        ▼
Backend returns analysis ID or immediate result
        │
        ▼
Repository maps response to domain model
        │
        ▼
Use Case returns Result<AnalysisSubmission, DomainError>
        │
        ▼
ViewModel updates state → View re-renders
```

### Result Polling / Async Result Flow

If the backend responds with a pending status and an analysis ID (as opposed to an immediate result), the following polling flow is used:

```
SubmitAnalysisUseCase returns AnalysisSubmission(status: .pending, id: String)
        │
        ▼
ViewModel starts CheckAnalysisStatusUseCase with polling interval
        │
        ▼
Use Case polls GetAnalysisResultUseCase at configured intervals
        │
        ▼
On status: .complete → returns AnalysisResult domain model
On status: .failed   → returns DomainError.analysisFailure
On timeout           → returns DomainError.timeout
        │
        ▼
ViewModel updates to result state → View renders result screen
```

The polling behavior is driven by remote configuration. If the backend switches to a push-notification or long-polling model, only the DataLayer implementation changes.

### State Flow (Unidirectional)

```
ViewState (enum: idle / loading / polling / success / error)
    ↑ updated by
ViewModel
    ↑ driven by
Use Case Results
    ↑ driven by
Repository Responses
```

---

## 5. Domain Models

The following are the canonical domain models. They are pure Swift value types with no UI or framework dependencies.

### AnalysisSubmission

Represents the immediate acknowledgment of a submitted analysis. Contains a reference identifier used for polling or result retrieval.

Fields: `id`, `status` (pending/complete/failed), `submittedAt`

### AnalysisResult

Represents the complete result of an analysis. This is the central output model of the system.

Fields:
- `id` — unique identifier
- `verdict` — `ThreatVerdict` enum (safe, suspicious, dangerous, inconclusive)
- `threatScore` — normalized 0.0–1.0 value
- `indicators` — array of `ThreatIndicator`
- `recommendations` — array of `RecommendedAction`
- `analysisTimestamp`
- `educationalContext` — optional `EducationalContent`

### ThreatIndicator

Represents a specific signal identified by the backend.

Fields: `id`, `category` (`ThreatCategory` enum), `description`, `severity` (`IndicatorSeverity` enum), `rawValue` (optional — the specific text, URL, or number found)

### ThreatCategory

Enum covering: `urlThreat`, `impersonation`, `urgencyManipulation`, `personalDataRequest`, `paymentFraud`, `unknownSender`, `maliciousContent`, `other`

### RecommendedAction

Represents a concrete step the user should take.

Fields: `id`, `priority` (Int), `actionText`, `actionType` (`ActionType` enum: informational, deepLink, systemAction)

### HistoryEntry

Represents a locally stored record of a past analysis.

Fields: `id`, `analysisId`, `thumbnailData` (compressed), `verdict`, `threatScore`, `analyzedAt`, `resultSnapshot` (serialized AnalysisResult for offline access)

### ThreatVerdict

Enum: `.safe`, `.suspicious`, `.dangerous`, `.inconclusive`

Each case maps to: a display label, a semantic color token (resolved at the presentation layer, not in the model), and an icon name.

### AppConfiguration

Represents remotely delivered feature flags and behavioral parameters.

Fields: `maxImageFileSizeBytes`, `maxImageDimension`, `pollingIntervalSeconds`, `pollingMaxAttempts`, `supportedImageFormats`, `featureFlags` (dictionary of feature identifiers to Bool)

---

## 6. State Management Strategy

### Philosophy

State is owned at the lowest appropriate level. Global state is avoided. ViewModels own transient view state. The local persistence layer owns durable state. Remote configuration is fetched at launch and cached locally with TTL.

### ViewModel State Shape

Each ViewModel maintains a `ViewState` enum:

```
ViewState<T>:
  - idle
  - loading(progress: Double?)
  - polling(attempt: Int)
  - success(data: T)
  - error(AppError)
  - empty
```

This pattern is applied consistently across all ViewModels. The View switches over this enum to render the appropriate UI state without conditional logic scattered across the view body.

### Observation Pattern

ViewModels conform to `@Observable` (iOS 17+) or use `@ObservableObject` / `@Published` for iOS 16 compatibility. The ViewModel is the single source of truth for all state rendered by its associated View.

### Navigation State

Navigation state is managed by a central `AppRouter` using a `NavigationPath`. All navigation decisions are made by the Router in response to ViewModel events, keeping Views decoupled from navigation logic.

### Persistence-Backed State

History and pending submission state are sourced from the local persistence layer via their respective repositories. ViewModels do not cache this data; they always fetch from the repository, which handles caching internally.

### Remote Configuration State

Remote configuration is fetched asynchronously at application launch. Until configuration arrives, the application uses safe defaults defined in a `DefaultConfiguration` struct. Configuration is cached locally with a defined TTL (e.g., 1 hour) so the app behaves correctly when launched offline.

---

## 7. Folder Structure

The folder structure is organized by feature. Each feature is self-contained. Shared infrastructure lives in dedicated modules that features import.

```
TrustScan/
├── App/
│   ├── TrustScanApp.swift          # App entry point
│   ├── AppRouter.swift             # Central navigation coordinator
│   ├── AppEnvironment.swift        # Dependency container
│   └── AppConfiguration.swift     # Launch-time configuration setup
│
├── Features/
│   ├── Onboarding/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   └── OnboardingFeature.swift # Feature entry point / factory
│   │
│   ├── Submission/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   └── SubmissionFeature.swift
│   │
│   ├── Results/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   └── ResultsFeature.swift
│   │
│   ├── History/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   └── HistoryFeature.swift
│   │
│   └── Settings/
│       ├── Views/
│       ├── ViewModels/
│       └── SettingsFeature.swift
│
├── Domain/
│   ├── Models/
│   │   ├── AnalysisResult.swift
│   │   ├── AnalysisSubmission.swift
│   │   ├── ThreatIndicator.swift
│   │   ├── HistoryEntry.swift
│   │   ├── RecommendedAction.swift
│   │   └── AppConfiguration.swift
│   │
│   ├── UseCases/
│   │   ├── SubmitAnalysisUseCase.swift
│   │   ├── FetchAnalysisResultUseCase.swift
│   │   ├── CheckAnalysisStatusUseCase.swift
│   │   ├── PrepareImageForSubmissionUseCase.swift
│   │   ├── LoadHistoryUseCase.swift
│   │   ├── DeleteHistoryEntryUseCase.swift
│   │   └── FetchConfigurationUseCase.swift
│   │
│   └── Ports/
│       ├── AnalysisRepositoryPort.swift
│       ├── HistoryRepositoryPort.swift
│       └── ConfigurationRepositoryPort.swift
│
├── Data/
│   ├── Repositories/
│   │   ├── AnalysisRepository.swift
│   │   ├── HistoryRepository.swift
│   │   └── ConfigurationRepository.swift
│   │
│   ├── Networking/
│   │   ├── APIClient.swift
│   │   ├── RequestBuilder.swift
│   │   ├── ResponseDecoder.swift
│   │   ├── NetworkMonitor.swift
│   │   └── CertificatePinner.swift
│   │
│   ├── Persistence/
│   │   ├── PersistenceController.swift
│   │   ├── HistoryEntryEntity.swift
│   │   └── PendingSubmissionEntity.swift
│   │
│   └── DTOs/
│       ├── AnalysisResultDTO.swift
│       ├── SubmissionResponseDTO.swift
│       └── ConfigurationDTO.swift
│
├── Core/
│   ├── Components/
│   │   ├── Buttons/
│   │   ├── Cards/
│   │   ├── Indicators/
│   │   ├── Sheets/
│   │   └── EmptyStates/
│   │
│   ├── Extensions/
│   ├── Utilities/
│   ├── Analytics/
│   │   ├── AnalyticsProtocol.swift
│   │   └── AnalyticsService.swift
│   │
│   └── Permissions/
│       ├── PhotoLibraryPermissionManager.swift
│       └── CameraPermissionManager.swift
│
├── Design/
│   ├── Tokens/
│   │   ├── ColorTokens.swift
│   │   ├── TypographyTokens.swift
│   │   └── SpacingTokens.swift
│   ├── Theme.swift
│   └── Assets.xcassets
│
└── Tests/
    ├── UnitTests/
    │   ├── Domain/
    │   └── Data/
    ├── IntegrationTests/
    └── UITests/
```

---

## 8. Dependency Boundaries

### Rules

1. **Presentation → Domain only.** ViewModels call Use Cases. ViewModels never call Repositories, APIClient, or persistence directly.
2. **Domain → nothing concrete.** Use Cases depend on Repository Ports (protocols), not on Repository implementations.
3. **Data implements Domain Ports.** Repositories conform to the protocols defined in `Domain/Ports/`.
4. **Core is infrastructure.** All features and layers may depend on Core. Core depends on nothing feature-specific.
5. **DTOs are data-layer private.** DTO types never escape the Data layer. They are mapped to Domain models before being returned from Repositories.
6. **No circular dependencies.** Features never import other features. Shared types live in Core or Domain.

### Dependency Injection

Dependencies are assembled in `AppEnvironment`, which acts as a lightweight dependency container constructed at application launch. Use Cases receive their Repository dependencies via constructor injection. ViewModels receive their Use Cases via constructor injection. This makes all components independently testable with mock implementations.

### Third-Party Dependency Policy

The project maintains a minimal third-party dependency footprint. Any new third-party dependency must be:
- Justified by a documented capability gap in Apple frameworks
- Wrapped behind a protocol boundary so it can be replaced without cascading changes
- Approved and recorded in a `DEPENDENCIES.md` file with version constraints

---

## 9. Networking Architecture

### Transport

All network communication uses `URLSession` directly. No third-party networking library is introduced. URLSession is wrapped in a protocol-conforming `APIClient` that the Data layer owns.

### Request Construction

Requests are built by a `RequestBuilder` that accepts a typed `APIEndpoint` enum. Endpoints carry their HTTP method, path, headers, and body encoding strategy. This centralizes all request construction and makes endpoint changes auditable.

### Response Decoding

Responses are decoded by a `ResponseDecoder` using `JSONDecoder` with a defined date strategy and key decoding strategy. Decoding errors are caught and mapped to a `.decodingFailure` domain error before propagation.

### Error Categorization

HTTP responses are evaluated for status codes before decoding. The following mapping is applied:
- 2xx → decode and return success
- 4xx client errors → map to specific `DomainError` cases (validation failure, not found, rate limited)
- 5xx server errors → map to `DomainError.serverError`
- Network connectivity errors → map to `DomainError.networkUnavailable`
- Timeout errors → map to `DomainError.timeout`

### Certificate Pinning

The `CertificatePinner` component validates the server certificate against a pinned public key hash during the URLSession authentication challenge. Pinned values are embedded at build time and updated via app releases. A backup pin is always included to support key rotation without a forced update gap.

### Retry Strategy

Network requests that fail with transient errors (timeout, connection lost) are eligible for automatic retry. The retry strategy uses exponential backoff with jitter. The maximum retry count is defined per request type:
- Analysis submission: up to 3 retries
- Status polling: infinite retries up to the polling timeout
- Configuration fetch: up to 2 retries on launch

### Network Monitoring

`NetworkMonitor` uses `NWPathMonitor` to observe connectivity status. ViewModels and the APIClient consult this monitor to present offline states and gate submission attempts.

---

## 10. Local Persistence Architecture

### Engine

SwiftData is the primary persistence engine for iOS 17+ targets. For iOS 16 compatibility, CoreData is used with an identical schema. The `PersistenceController` abstracts the difference and presents a unified async interface.

### Persisted Data

| Data Type | Reason | Retention Policy |
|-----------|--------|-----------------|
| HistoryEntry | User reference, offline access | Until user deletes |
| PendingSubmission | Crash resilience for in-flight submissions | Deleted on result or explicit cancel |
| CachedConfiguration | Offline-safe remote configuration | TTL: 1 hour |

### Data Encryption

The persistent store file is protected using `NSFileProtectionCompleteUnlessOpen`, ensuring it is encrypted at rest and inaccessible when the device is locked (except for background access required for pending submission recovery).

### Migration Strategy

Schema migrations are handled as lightweight migrations where possible. Any migration requiring a heavyweight mapping is documented in a `MIGRATIONS.md` log with the schema version and change description.

---

## 11. Reusable Component Philosophy

### Principles

1. **Components express state, not behavior.** A reusable component receives display properties and emits events — it never calls a Use Case or accesses a Repository.
2. **Components are composable.** Small, focused components are composed into larger UI patterns. A `ThreatScoreBadge` composes a `SeverityColorIndicator` and a `ScoreLabel`.
3. **Components are documented at definition.** Each component has a comment block describing its purpose, required properties, optional properties, and emitted events.
4. **Components live in Core.** No feature-specific component is placed in Core. If a component starts as feature-specific and generalizes, it is promoted to Core with a refactor.
5. **Design tokens are used universally.** No hardcoded colors, font sizes, or spacing values appear in View code. All values reference token constants.

### Component Categories

| Category | Examples |
|----------|---------|
| Buttons | Primary action, secondary, destructive, icon-only, loading state |
| Cards | History entry card, result summary card, indicator card |
| Indicators | Threat verdict badge, score ring, severity dot |
| Feedback | Loading spinner, progress bar, skeleton loader |
| Empty States | No history, no results, offline |
| Error States | Network error, analysis failure, permission denied |
| Sheets | Confirmation sheet, permission prompt sheet, info sheet |

---

## 12. Error Handling Philosophy

### Principles

1. **Errors are domain-typed before reaching the presentation layer.** No `URLError`, `DecodingError`, or system error type is exposed to a ViewModel. All errors pass through the data layer's error mapping.
2. **Every error has a user-facing recovery action.** The presentation layer never displays a dead end. Every error state includes at least one actionable path (retry, go home, open settings).
3. **Errors are categorized, not raw.** The `AppError` enum categorizes errors into user-facing buckets: `networkUnavailable`, `analysisFailure`, `submissionTooLarge`, `unsupportedFormat`, `serverError`, `timeout`, `permissionDenied`, `unknown`. Each has associated copy and recommended action.
4. **Errors are logged, not hidden.** All errors are written to a local diagnostic log buffer (capped at a rolling window). This buffer is available for debugging and can be included in a user-initiated support report.
5. **Partial failures are handled gracefully.** If history loading fails, the app shows an empty history state rather than a global error. If configuration fetching fails, safe defaults are used. Errors are scoped to the affected feature, not the entire app.

### Error Recovery Matrix

| Error Type | User Message | Primary Action | Secondary Action |
|------------|-------------|----------------|-----------------|
| networkUnavailable | "No internet connection. Please check your connection and try again." | Retry | Dismiss |
| timeout | "Analysis is taking longer than expected." | Retry | Dismiss |
| analysisFailure | "We couldn't analyze this image. Please try again." | Retry | Try different image |
| submissionTooLarge | "This image is too large to analyze. Please try a different image." | Try different image | - |
| unsupportedFormat | "This image format isn't supported. Please use a JPG or PNG." | Try different image | - |
| serverError | "Something went wrong on our end. Please try again later." | Retry | Dismiss |
| permissionDenied | "Photo access is required to scan images. You can enable this in Settings." | Open Settings | Dismiss |
| unknown | "Something unexpected happened. Please try again." | Retry | - |

---

## 13. Security Architecture

### Transport Security

- All API communication uses HTTPS exclusively.
- Certificate pinning is enforced via `CertificatePinner`.
- App Transport Security (ATS) exceptions are not permitted.
- TLS 1.2 minimum; TLS 1.3 preferred.

### Data at Rest

- Keychain is used for session tokens and any sensitive identifiers.
- The persistence store uses `NSFileProtectionCompleteUnlessOpen`.
- No sensitive data (image content, analysis results) is written to unprotected temp files beyond the active session.
- Thumbnail data stored in history is compressed and limited in resolution.

### Network

- No user-identifying information is included in API requests beyond a randomly generated anonymous session token.
- The session token is not tied to a device identifier (IDFV/IDFA). It is generated fresh at first launch and stored in Keychain.

### Logging and Diagnostics

- No image content, analysis results, or user-identifying information is written to any log.
- Diagnostic logs contain only error categories, timestamps, and anonymous session references.
- Debug logging is disabled in production builds via compile-time flags.

### Code Integrity

- Jailbreak detection is out of scope for v1.0 but the architecture does not obstruct adding it.
- The app uses Swift's type system and value semantics to minimize runtime memory vulnerabilities.

---

## 14. Performance Architecture

### Main Thread Protection

- All networking, persistence reads/writes, and image processing are performed off the main thread using Swift Concurrency (async/await with actors where appropriate).
- ViewModels are marked `@MainActor` to ensure state updates always occur on the main thread.

### Image Handling

- `PrepareImageForSubmissionUseCase` performs compression and resizing on a background actor.
- Thumbnail generation for history storage is performed after successful submission, not blocking the result display.
- History thumbnails are lazy-loaded in the list view.

### Memory Management

- Large image data is not held in memory beyond its active use. UIImages used for submission are released immediately after encoding for upload.
- The history list uses SwiftUI's lazy containers to avoid rendering off-screen cells.

### Launch Performance

- The app performs no synchronous heavy work on the main thread during launch.
- Configuration fetch and history preload are dispatched concurrently and their completion is not awaited before the home screen renders.

---

## 15. Testing Strategy

### Unit Tests

Cover all Domain layer components without mocking UI:
- All Use Cases with mock Repository implementations
- All domain model transformations
- Error mapping logic in Data layer DTOs

**Target coverage:** > 80% of Domain and Data layer code.

### Integration Tests

Cover the Data layer with real URLSession against a local test server or mock server:
- API Client request construction and response decoding
- Repository behavior across success and failure paths
- Persistence read/write correctness

### UI Tests (XCTest / XCUITest)

Cover critical user journeys end-to-end:
- Onboarding completion
- Screenshot submission success flow
- Screenshot submission failure and retry
- History navigation and deletion
- Permission denial handling

UI tests use a mock backend mode injected via launch arguments.

### Snapshot Tests

Key screens are snapshot-tested for visual regression across:
- Light and Dark mode
- Smallest and largest Dynamic Type sizes
- Key error and empty states

### Test Infrastructure

- Mock implementations for all Repository Ports
- A `MockAPIServer` utility that intercepts URLSession requests in test targets
- Factory methods for constructing domain model fixtures

---

## 16. Scalability Considerations

### Feature Addition

New features are added as new modules under `Features/`. They do not modify existing features. Shared behavior is abstracted into Core or Domain Use Cases.

### Backend Protocol Evolution

The DTO layer insulates the domain model from backend API changes. When the backend adds new fields, DTOs are extended first. When the backend changes a field structure, only the DTO and its mapping to the domain model changes.

### Multi-Language Support

All user-facing strings are defined in `Localizable.strings` from the first commit. Even if localization is not a day-one priority, the architecture prevents hardcoded strings from accumulating.

### Push Notification Support

If the backend adopts push notifications for analysis completion, the architecture accommodates this:
- `AppRouter` handles deep links to result screens
- `PushNotificationCoordinator` (to be added) maps notification payloads to navigation actions
- No existing component requires modification

### Feature Flags

`AppConfiguration` carries a `featureFlags` dictionary. ViewModels check feature flag state before enabling features. This allows features to be developed, shipped, and enabled remotely without new releases.

### iPad and Multi-Window

The layout system uses adaptive layout primitives (GeometryReader, size class conditionals) to adapt the interface for iPad. Multi-window support is not a v1.0 requirement but the app's stateless presentation architecture supports it without structural changes.