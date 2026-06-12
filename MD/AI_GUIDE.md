# AI_GUIDE.md — AI Continuation and Developer Guide
## TrustScan: iOS Scam Detection Application

**Version:** 1.0  
**Status:** Active  
**Last Updated:** June 2026  
**Purpose:** Enable any AI system or incoming engineer to continue development immediately with full context and zero ambiguity.

---

## Table of Contents

1. [Project Handover](#1-project-handover)
2. [Naming Conventions](#2-naming-conventions)
3. [Folder Conventions](#3-folder-conventions)
4. [Architecture Rules](#4-architecture-rules)
5. [Component Design Principles](#5-component-design-principles)
6. [State Management Rules](#6-state-management-rules)
7. [Dependency Rules](#7-dependency-rules)
8. [Coding Standards](#8-coding-standards)
9. [Testing Standards](#9-testing-standards)
10. [Error Handling Principles](#10-error-handling-principles)
11. [Feature Addition Principles](#11-feature-addition-principles)
12. [Modification Principles](#12-modification-principles)
13. [Maintainability Principles](#13-maintainability-principles)
14. [Scalability Principles](#14-scalability-principles)
15. [Decision Log](#15-decision-log)

---

## 1. Project Handover

### Project Overview

TrustScan is a native iOS application (SwiftUI, iOS 16+) that serves as the client layer of a scam detection platform. Users submit screenshots of suspicious content; the backend performs analysis and returns threat scores, indicators, and recommendations; the iOS app presents results clearly.

The iOS application is **client-only**. It does not perform analysis. It does not own any intelligence data. It does not manage the backend, OCR pipeline, URL sandboxing, or admin tooling.

**What the iOS app does:**
- Accepts images from the photo library or camera
- Prepares and transmits images to a backend API
- Receives and renders structured analysis results
- Persists a history of past analyses locally
- Manages user permissions, offline states, errors, and retries

### Responsibilities

**Owned by iOS:**
- All SwiftUI views and navigation
- All ViewModels and presentation state
- All domain use cases
- All data layer components (API client, persistence, DTOs)
- All reusable components and design tokens
- All local persistence (history, pending submission state, cached configuration)
- Error classification, mapping, and presentation
- Analytics event emission (to a first-party endpoint only)
- Permission management (photos, camera, notifications)

**Not owned by iOS:**
- Backend API implementation
- OCR and text extraction
- Threat scoring algorithm
- URL sandboxing
- Threat intelligence database
- Admin portal
- Infrastructure and deployment

### Assumptions

The following are confirmed assumptions for all development decisions:

1. The backend API is RESTful with JSON responses.
2. The backend defines a contract for image upload format, maximum size, and response shape.
3. The backend returns a structured result with: verdict, threat score, indicators list, recommendations list, and optional educational content.
4. A configuration endpoint exists that delivers feature flags and behavioral parameters.
5. No user authentication is required in version 1.0.
6. The backend may respond synchronously (immediate result) or asynchronously (pending → poll for result). Both paths must be handled.

### Key Dependencies

| Dependency | Type | Purpose | Policy |
|------------|------|---------|--------|
| SwiftUI | Apple Framework | UI | Required. No UIKit unless unavoidable. |
| Swift Concurrency | Apple Framework | Async operations | Required. No Combine, no DispatchQueue except where necessary. |
| SwiftData (iOS 17+) / CoreData (iOS 16) | Apple Framework | Persistence | Required. |
| URLSession | Apple Framework | Networking | Required. No Alamofire or other networking libraries. |
| PHPickerViewController | Apple Framework | Photo selection | Required. No legacy UIImagePickerController. |
| NWPathMonitor | Apple Framework | Network monitoring | Required. |

Third-party dependencies are minimized. Any addition requires documented justification and a wrapping protocol.

### Design Philosophy

- **Clarity over cleverness.** Code should be readable by any Swift developer without explanation.
- **Explicit over implicit.** State is explicit. Navigation is explicit. Errors are explicit.
- **Value types first.** Structs and enums are preferred over classes except where reference semantics are necessary (ViewModels, services).
- **Single responsibility.** Every type does one thing. If a type is doing two things, it should be two types.
- **Fail visibly.** Errors surface to the user with actionable guidance. Silent failures exist only where a silent failure is explicitly better for the user (e.g., history save failure does not disrupt result display).

### Development Principles

1. **Build for the user who is most at risk.** If a feature is confusing to a 70-year-old first-time smartphone user, it is not good enough.
2. **Trust the architecture.** Do not bypass layers for convenience. If bypassing feels necessary, the architecture needs refactoring, not circumvention.
3. **No magic.** No reflection, no swizzling, no runtime hacks. The codebase must be statically analyzable.
4. **Accessibility is not optional.** Every new screen and component must be VoiceOver tested before merging.
5. **Tests before merge.** Any new use case, repository method, or view model must have accompanying tests.

---

## 2. Naming Conventions

### Swift Type Names

| Type | Convention | Example |
|------|-----------|---------|
| Struct | UpperCamelCase, noun | `AnalysisResult`, `HistoryEntry` |
| Class (ViewModel) | UpperCamelCase + `ViewModel` suffix | `SubmissionViewModel`, `HistoryViewModel` |
| Protocol (Port) | UpperCamelCase + `Port` suffix | `AnalysisRepositoryPort`, `HistoryRepositoryPort` |
| Protocol (general) | UpperCamelCase, noun or adjective | `NetworkMonitoring`, `Analyticsable` |
| Enum | UpperCamelCase, noun | `ThreatVerdict`, `ViewState`, `AppError` |
| Enum case | lowerCamelCase | `.safe`, `.dangerous`, `.loading` |
| Use Case | UpperCamelCase + `UseCase` suffix | `SubmitAnalysisUseCase`, `LoadHistoryUseCase` |
| Repository | UpperCamelCase + `Repository` suffix | `AnalysisRepository`, `HistoryRepository` |
| View | UpperCamelCase + `View` suffix | `HomeView`, `ResultsView`, `ThreatVerdictBadgeView` |
| Extension | No suffix — file named `TypeName+ExtensionPurpose` | `Image+Compression.swift` |
| DTO | UpperCamelCase + `DTO` suffix | `AnalysisResultDTO`, `SubmissionResponseDTO` |

### File Names

File names must exactly match the primary type name defined within them.

- One type per file (with the exception of closely related nested types).
- If a file contains an extension: `TypeName+Purpose.swift` (e.g., `View+Accessibility.swift`).

### Property and Variable Names

- Properties: `lowerCamelCase`, descriptive, noun-first. Example: `threatScore`, `isLoading`, `selectedImage`.
- Booleans: prefixed with `is`, `has`, or `can`. Example: `isSubmitting`, `hasResult`, `canRetry`.
- Collections: plural nouns. Example: `indicators`, `historyEntries`.
- Closures stored as properties: descriptive verb phrase. Example: `onSubmitTapped`, `onDismiss`.

### Function Names

- Functions: `lowerCamelCase`, verb-first. Example: `submitAnalysis()`, `loadHistory()`, `prepareImageForUpload(_:)`.
- Async functions: same convention, no special suffix. The `async` keyword communicates the nature.
- Boolean-returning functions: start with `is`, `has`, or `can` unless they are naturally question-answering. Example: `isImageValid(\_:)`.

### Constant and Token Names

Design tokens use a namespace struct pattern:

```
ColorTokens.verdictSafe
ColorTokens.verdictDangerous
TypographyTokens.headline1
SpacingTokens.contentPadding
```

All constants in `Core/Design/Tokens/`.

---

## 3. Folder Conventions

### Rule: Features Are Folders

Each feature is a self-contained folder under `Features/`. A feature folder contains only what is exclusive to that feature: Views, ViewModels, and a feature entry-point file.

### Rule: Shared Code Lives in Core or Domain

If two features need the same component, the component moves to `Core/Components/`. If two features need the same business logic, it becomes a Use Case in `Domain/UseCases/`.

### Rule: Tests Mirror Source Structure

The test folder structure mirrors the source structure exactly:

```
Tests/UnitTests/Domain/UseCases/SubmitAnalysisUseCaseTests.swift
```
mirrors:
```
TrustScan/Domain/UseCases/SubmitAnalysisUseCase.swift
```

### Rule: No Feature Imports Feature

Feature A must never import Feature B. If they share something, it belongs in Core or Domain.

### Rule: Design Tokens Are Centralized

No color, spacing, or font value is defined outside of `Design/Tokens/`. Views import tokens; they do not define their own.

### Rule: DTOs Are Data-Layer Private

Nothing outside `Data/` imports a DTO type. DTOs are transformed to domain models before leaving the Data layer.

---

## 4. Architecture Rules

### Rule 1: Strict Layer Dependency Direction

```
Presentation → Domain → (abstracted) Data
```

No layer may import from a higher layer. No concrete Data type (Repository, APIClient, DTO) appears in Domain or Presentation code.

**Enforcement:** If you find yourself importing a Repository in a ViewModel, you are breaking this rule. The ViewModel must call a Use Case, which calls the Repository Port.

### Rule 2: Use Cases Are the Domain API

ViewModels communicate with the Domain layer exclusively through Use Cases. Use Cases communicate with the Data layer exclusively through Repository Ports (protocols).

**Enforcement:** No ViewModel directly calls a Repository or APIClient.

### Rule 3: ViewModels Own Presentation State

ViewModels own and manage all state that a View renders. Views are pure renderers.

**Enforcement:** No business logic in View bodies. No network calls in View initializers or `.onAppear` beyond calling a ViewModel method.

### Rule 4: Views Call ViewModel Methods, Not Use Cases

Views trigger user intent by calling ViewModel methods (e.g., `viewModel.submitTapped()`). Views never instantiate or call Use Cases directly.

### Rule 5: Domain Models Have No Framework Dependencies

Domain models (`AnalysisResult`, `HistoryEntry`, etc.) must be pure Swift value types. They must not import UIKit, SwiftUI, Foundation beyond basic types, or any third-party library.

**Test:** A domain model file must compile if you remove all imports except `Foundation`. If it cannot, it has invalid dependencies.

### Rule 6: The Router Owns Navigation

No View calls `NavigationLink` with a destination View directly for programmatic navigation. All navigation is triggered by the `AppRouter` in response to ViewModel-emitted navigation events.

Exception: Simple declarative `NavigationLink` within a list (e.g., navigating to History detail) may be used where the destination is a value-type navigation destination registered with the router.

### Rule 7: Error Mapping Happens at Layer Boundaries

`URLError`, `DecodingError`, and other framework errors are caught in the Data layer and mapped to `AppError` domain types before propagation. No framework error type appears in Domain or Presentation code.

### Rule 8: All Async Operations Use Swift Concurrency

No `DispatchQueue.async`, no `OperationQueue`, no Combine pipelines for business logic. Swift concurrency (`async/await`, `Task`, `Actor`) is the standard. Exceptions require documented justification.

---

## 5. Component Design Principles

### Principle 1: Components Are Display-Only

A component receives data and renders it. A component does not fetch data, call a use case, or hold significant business state. Components may hold ephemeral display state (e.g., an expanded/collapsed toggle).

### Principle 2: Components Express Intent, Not Implementation

A component is named for what it communicates, not what it renders. `ThreatVerdictBadge` — not `ColoredRoundedRectangleWithIconAndLabel`.

### Principle 3: Required vs. Optional Properties

Components with required properties receive them as initializer parameters. Optional properties have sensible defaults. A component should be usable with minimal configuration and customizable without reimplementation.

### Principle 4: Accessibility Is Built In

Every component defines its own accessibility behavior. Accessibility labels and hints are part of the component specification, not an afterthought added externally.

### Principle 5: Tokens Not Literals

Every color, spacing value, font, and animation duration used in a component references a design token. If the token does not exist, create it. Never inline a literal value.

### Principle 6: Document at Definition

Every component file starts with a comment block:
- What this component renders
- Required parameters and their semantics
- Optional parameters and their defaults
- Events emitted
- Accessibility notes if non-obvious

---

## 6. State Management Rules

### Rule 1: Use ViewState<T> Universally

Every ViewModel that represents a screen with a loaded state uses the `ViewState<T>` enum pattern:

```
idle / loading / success(T) / error(AppError) / empty
```

This creates predictability. Any engineer reading a ViewModel immediately knows its state model.

### Rule 2: ViewModels Are @MainActor

All ViewModels are annotated `@MainActor`. State mutations always occur on the main actor. Async work happens in tasks that update state back on `@MainActor`.

### Rule 3: No Shared Mutable State Between Features

Features do not share mutable state. If feature A needs data from feature B, it reads from a shared repository, not from feature B's ViewModel.

### Rule 4: Navigation State Is Owned by AppRouter

Navigation path, presented sheets, and modals are owned by `AppRouter`. ViewModels signal navigation intent to the router via an event mechanism — they do not hold or mutate navigation state directly.

### Rule 5: Pending State Survives App Termination

Any state that must survive a crash or termination (e.g., `PendingSubmission`) is persisted to the local store, not held only in memory.

### Rule 6: Remote Configuration Is Defensive

All code that reads from `AppConfiguration` must have a fallback to a default value. The app must behave correctly if configuration is unavailable.

---

## 7. Dependency Rules

### Rule 1: No Third-Party Dependency Without Protocol Wrapper

Every third-party library (if any) is used through a protocol wrapper. This allows the library to be replaced without changes to calling code.

### Rule 2: All Dependencies Are Injected

No component creates its own dependencies. Dependencies are injected via constructor. This enables test isolation.

### Rule 3: AppEnvironment Is the Composition Root

`AppEnvironment` is the only place where concrete dependencies are instantiated. It wires together repositories, use cases, and services. The rest of the app depends on abstractions.

### Rule 4: Dependencies Are Explicit

No singletons, no global state, no `shared` instances accessed from anywhere. If a component needs a service, it receives it at initialization. The dependency graph is visible and auditable.

### Rule 5: Minimize Third-Party Surface Area

Before adding a third-party dependency, verify:
- Apple's standard library does not provide equivalent functionality.
- The benefit justifies the maintenance burden and security audit.
- A protocol wrapper is defined so it can be replaced.
- It is documented in `DEPENDENCIES.md`.

---

## 8. Coding Standards

### Swift Version

Swift 5.9+. New features (macros, observation framework) used where they reduce boilerplate and are compatible with the minimum deployment target.

### Code Formatting

Code is formatted using Swift's standard style conventions. A `.swiftformat` or `.swift-format` configuration file is included at the project root. All code must be formatted before committing.

### No Force Unwrap in Production Code

`!` force unwrap is forbidden in production code. Use guard-let, if-let, or provide explicit error handling. The only exception: tests, where force unwrap is acceptable for known-good fixture data.

### No Magic Strings

No hardcoded string literals appear in production code except:
- Localizable string keys (which reference `Localizable.strings` values)
- Debug/logging messages that are stripped in production builds

All user-facing strings are defined in `Localizable.strings`. Even for v1.0 where localization is English-only, this pattern must be established from day one.

### Computed Properties vs. Stored Properties

Prefer computed properties for derived values that are cheap to compute. Use stored properties for values that are expensive to derive, need to persist, or require identity.

### Guard Over Nested If

Early returns using `guard` are preferred over deeply nested `if` statements for conditional logic.

### Access Control

- Default to `private` or `internal`. Escalate visibility only when necessary.
- `public` is only required if the project is modularized with Swift Package Manager boundaries.
- All properties and methods should have the most restrictive access level that still allows them to function.

### Async Context

- `Task` in ViewModels is created with `Task { @MainActor in ... }` to ensure state updates occur on the main actor.
- `Task` references are stored in ViewModels for cancellation on deinitialization.
- Never use `Task.detached` unless there is an explicit reason to escape the current actor context.

---

## 9. Testing Standards

### What Must Be Tested

| Component | Test Type | Requirement |
|-----------|-----------|-------------|
| All Use Cases | Unit test | Every public method, success and failure paths |
| All Repositories | Unit test with mocks | Success paths, error paths, edge cases |
| All DTOs | Unit test | Encoding/decoding correctness |
| Error mapping | Unit test | All error type mappings |
| Image preparation | Unit test | Compression decisions, format validation |
| Critical user journeys | UI test | At minimum: submit success, submit fail+retry, offline state |
| Key screens | Snapshot test | Light/dark mode, accessibility sizes |

### Mock Strategy

Mocks are written by hand, not generated. Each mock:
- Conforms to the same protocol as the real implementation
- Has configurable return values and failure modes
- Records calls for assertion

Mock files live in `Tests/Mocks/` with the naming convention `Mock{ProtocolName}.swift`.

### Test Naming Convention

Tests follow the `Given_When_Then` pattern in their method names:
- `test_givenValidImage_whenSubmitted_thenUseCaseIsCalledWithPreparedImage()`
- `test_givenNetworkError_whenSubmitting_thenViewStateIsError()`

### No Tests Without Assertions

Every test must contain at least one `XCTAssert*` call. Tests that only call methods without asserting output are invalid.

### Test Coverage Gate

PRs that reduce overall test coverage of the Domain or Data layers are flagged in code review. The target is >80% coverage for these layers.

---

## 10. Error Handling Principles

### Principle 1: Map Early, Use Late

Errors are mapped from their native types to `AppError` domain types at the earliest possible point — in the Data layer, before use cases receive them. Use cases and ViewModels work with `AppError` only.

### Principle 2: Every Error Is Actionable

No error reaches the user without an associated action. The `AppError` enum provides the metadata needed to generate user copy and actions. ViewModels transform `AppError` into display-ready error models.

### Principle 3: Errors Are Categorized, Not Raw

The eight categories of `AppError` (see ARCHITECTURE.md Error Recovery Matrix) cover all expected failure modes. Unknown errors are mapped to `.unknown` with internal logging. New error types are added to the enum only when they represent a genuinely distinct failure mode with different user-facing handling.

### Principle 4: Logging Is for Debugging, Not Users

Error details (stack traces, HTTP codes, server messages) are written to the internal diagnostic log, never shown to users.

### Principle 5: Scope Errors to Their Origin

A failure in the history persistence layer does not cause a global app error. Errors are scoped to the feature that originated them. If history saving fails silently, the results screen continues to function normally.

### Principle 6: Retryable Errors Are Clearly Retryable

ViewModels expose a `canRetry` boolean derived from the error type. The view uses this to show or hide retry actions. The user is never shown a retry button for non-retryable errors (e.g., unsupported image format — retrying the same image will fail again).

### Principle 7: Third-Party Errors Are Opaque to the Domain

Any error originating from a third-party library is caught in the Data layer and transformed into an `AppError` before propagation. If the third-party library is replaced, the error mapping changes but nothing above the Data layer changes.

---

## 11. Feature Addition Principles

### Process for Adding a Feature

1. **Assess domain impact.** Does this feature require new Domain models? New Use Cases? New Repository Port methods? Define these first.
2. **Create a feature folder.** New feature lives in `Features/{FeatureName}/`.
3. **Define the Use Case(s).** Write the Use Case(s) with mock repository implementations first (test-driven).
4. **Implement the Repository method(s).** Add to the Repository Port protocol and implement in the concrete Repository.
5. **Build the ViewModel.** ViewModel depends only on Use Cases. Define `ViewState` for the feature.
6. **Build Views.** Views are built last. They render ViewModel state.
7. **Add to Router.** Register new destinations with `AppRouter`.
8. **Wrap with a feature flag.** New features are always behind a feature flag for the first release. This allows safe rollout and instant rollback.
9. **Add analytics events.** Define and implement analytics for all new user interactions.
10. **Accessibility review.** VoiceOver test the feature before marking it complete.

### Adding a New Screen

A new screen requires:
- A View file in the appropriate feature folder
- A ViewModel with defined `ViewState`
- A screen ID added to the `FRONTEND_SPEC.md` screen inventory
- Navigation destination registered with `AppRouter`
- Analytics events for `{screen}_viewed`

### Adding a New Reusable Component

A component graduates from feature-specific to `Core/Components/` when:
- It is used by two or more features, OR
- It is clearly a generic UI primitive (not feature-specific in intent)

Before promotion: Remove any feature-specific props. Generalize parameters. Write documentation.

---

## 12. Modification Principles

### Principle 1: Understand Before Modifying

Before modifying any component, read the tests for that component. The tests describe the intended behavior. If the behavior needs to change, update the tests first.

### Principle 2: Respect the Layer Boundary

Modifications to a Domain Use Case must not introduce Data layer dependencies. Modifications to a View must not introduce Domain dependencies. If a modification seems to require a cross-layer dependency, the modification is wrong — the architecture needs to be extended correctly.

### Principle 3: Changing a Domain Model

Domain model changes propagate through the entire system. When changing a domain model:
1. Update the model in `Domain/Models/`.
2. Update all DTOs that map to/from this model.
3. Update all Use Cases that use this model.
4. Update all ViewModels that use this model.
5. Update all Views that display this model.
6. Update all persistence entity mappings.
7. Run all tests.

### Principle 4: Never Modify Without a Test

Any modification to business logic (Use Case, Repository method, ViewModel) must be accompanied by a test that validates the modified behavior.

### Principle 5: Deprecate, Don't Delete

When removing or replacing functionality, mark old code as deprecated (`@available(*, deprecated, renamed: "NewName")`) for one release cycle before deleting. This prevents unexpected breakage.

### Principle 6: API Contract Changes

If the backend changes the API contract (response shape, new field, removed field), the change is handled in the DTO layer:
1. Update the DTO struct.
2. Update the mapping from DTO to Domain model.
3. Do not change the Domain model unless the semantic meaning has changed.
4. Update the DTO decoding tests.
5. No other layer should require changes unless semantic meaning changed.

---

## 13. Maintainability Principles

### Code Review Checklist

Every PR must satisfy the following before merge:

- [ ] New code follows naming conventions
- [ ] New code follows folder conventions
- [ ] Architecture rules are not violated
- [ ] All new logic has unit tests
- [ ] No force unwraps introduced
- [ ] No hardcoded string literals in user-facing code
- [ ] Accessibility labels added to all new interactive elements
- [ ] Analytics events added for new user interactions
- [ ] New features are behind a feature flag
- [ ] Error states are handled for all new async operations
- [ ] Documentation comment added to new public types

### Documentation Requirements

- All public types and methods in the Domain layer have documentation comments.
- All reusable components have documentation comments.
- Significant architectural decisions are recorded in the Decision Log (Section 15).

### Technical Debt Policy

Technical debt is tracked in `TECH_DEBT.md`. When debt is introduced knowingly (e.g., a temporary workaround), a TODO is added with a ticket reference. Debt is reviewed at the start of each sprint. No debt item is older than 2 release cycles without a documented decision to accept or resolve it.

### Dependency Audit

`DEPENDENCIES.md` is reviewed with every release. Transitive dependencies are audited for security advisories. Any dependency with an unpatched security vulnerability blocks release.

---

## 14. Scalability Principles

### Feature Flags Drive Rollout

Every new feature shipped is off by default, enabled by remote configuration. This:
- Allows testing in production without user exposure
- Allows gradual rollout
- Allows instant rollback without a new release
- Prevents partial state from a half-shipped feature affecting stable behavior

### Backend Protocol Changes Are Isolated

The DTO layer is the only code that changes when the backend changes its API shape. Domain models change only when the semantics change. This allows the backend to evolve rapidly without cascading app changes.

### New Use Cases Are Cheap

The architecture makes adding a new Use Case a small, contained change. New Use Cases:
- Define a protocol-conforming struct
- Receive dependencies via constructor
- Return `Result<T, AppError>` or throw `AppError`
- Are immediately unit-testable

There is no shared base class, no registration system, no ceremony.

### Analytics Is Pluggable

The `AnalyticsProtocol` abstraction means the analytics destination can be swapped or supplemented without changing event emission sites. Adding a second analytics destination in the future requires only a new `AnalyticsService` implementation — no view or ViewModel changes.

### Multi-Language Is Structural

`Localizable.strings` is used from v1.0. Adding a new language requires:
- Translating `Localizable.strings`
- Testing layouts at longer string lengths (German, Finnish, etc.)
No structural code changes.

### Modularization Path

The folder structure maps directly to Swift Package Manager modules if the project needs to be modularized (e.g., for App Extensions or faster build times). The module boundaries would be:
- `TrustScanCore` — Core components, design tokens, utilities
- `TrustScanDomain` — Domain models, use cases, ports
- `TrustScanData` — Repositories, API client, persistence
- `TrustScanFeatureSubmission`, `TrustScanFeatureHistory`, etc.

This migration can be performed without architectural changes to the code itself.

---

## 15. Decision Log

The Decision Log records significant architectural and technical decisions, the options considered, and the rationale for the chosen path. This prevents future developers from re-litigating resolved decisions.

---

### DEC-001: UI Framework — SwiftUI

**Date:** Project inception  
**Decision:** Use SwiftUI exclusively.  
**Alternatives considered:** UIKit, SwiftUI + UIKit hybrid.  
**Rationale:** SwiftUI's declarative model maps directly to the unidirectional state flow architecture. The minimum deployment target (iOS 16) provides full production-ready SwiftUI support. SwiftUI is the correct investment for a new iOS project in 2024+.  
**Trade-offs:** Some SwiftUI behaviors (navigation, large datasets) require workarounds on older iOS versions. These are documented per-instance.

---

### DEC-002: Navigation — NavigationStack + AppRouter

**Date:** Project inception  
**Decision:** Centralized router pattern using `NavigationPath`.  
**Alternatives considered:** Decentralized NavigationLink, coordinator pattern with UINavigationController.  
**Rationale:** Centralized navigation makes deep linking, programmatic navigation, and testing straightforward. NavigationStack with a path value provides type-safe, programmatic control without UIKit.  
**Trade-offs:** More boilerplate for simple navigation than inline NavigationLink. Justified by the deep link and state restoration requirements.

---

### DEC-003: Persistence — SwiftData (iOS 17+) / CoreData (iOS 16)

**Date:** Project inception  
**Decision:** SwiftData as primary persistence engine with CoreData fallback for iOS 16.  
**Alternatives considered:** SQLite directly, Realm, UserDefaults only.  
**Rationale:** SwiftData provides native Swift integration, async/await support, and is Apple's forward investment. CoreData fallback is minimal — the schema is simple enough to maintain both with a shared abstraction.  
**Trade-offs:** Dual path increases implementation cost for persistence. Accepted for the iOS 16 compatibility requirement.

---

### DEC-004: No User Authentication in v1.0

**Date:** Project inception  
**Decision:** Use an anonymous device-level session token. No account creation, login, or OAuth.  
**Alternatives considered:** Apple Sign In, anonymous Firebase auth, full account system.  
**Rationale:** Authentication adds friction for the "Elderly User" and "Cautious Consumer" personas — the most critical users. The backend can operate with anonymous session tokens. Authentication is scheduled for a future phase when sync and multi-device features justify the friction.  
**Trade-offs:** History cannot sync across devices. Data deletion requires a local action + an API request with the session token (cannot re-authenticate to delete). Accepted for v1.0.

---

### DEC-005: Polling vs. Push Notifications for Async Results

**Date:** Project inception  
**Decision:** Implement polling as the primary result retrieval mechanism. Push notification support is architected but not built for v1.0.  
**Alternatives considered:** Long polling, WebSocket, Push notifications as primary, combined.  
**Rationale:** Polling requires no backend push infrastructure and works immediately. The architecture is designed so polling can be replaced with push notifications by changing only the Data layer without touching Domain or Presentation code.  
**Trade-offs:** Polling is less efficient for long-running analyses. Acceptable for v1.0 given expected analysis times.

---

### DEC-006: Analytics — First-Party Endpoint Only

**Date:** Project inception  
**Decision:** All analytics are sent to a first-party endpoint via the same `APIClient`. No third-party analytics SDK.  
**Alternatives considered:** Firebase Analytics, Mixpanel, Amplitude, AppsFlyer.  
**Rationale:** The app handles sensitive content (suspected scam screenshots). Users must be able to trust that their behavior data is not transmitted to third parties. First-party analytics maintains full data control. The `AnalyticsProtocol` abstraction allows adding a third-party destination in the future with a documented privacy disclosure.  
**Trade-offs:** First-party analytics dashboard is the backend team's responsibility. iOS team cannot use out-of-the-box dashboards. Accepted as the privacy-correct choice.

---

### DEC-007: Certificate Pinning — Embedded Public Key Hash

**Date:** Project inception  
**Decision:** Pin the server's public key hash (not the certificate itself).  
**Alternatives considered:** Certificate pinning, no pinning (ATS only).  
**Rationale:** Public key pinning survives certificate renewals (the key is reused), eliminating the window where users on an old app version cannot connect after a certificate renewal. Two pins are always embedded (primary + backup) for key rotation support.  
**Trade-offs:** If the private key is compromised and rotated, all installed app versions will fail until users update. Accepted — this is the intended security behavior.

---

*End of AI_GUIDE.md*