# FRONTEND_SPEC.md — Frontend Specification
## TrustScan: iOS Scam Detection Application

**Version:** 1.0  
**Status:** Active  
**Last Updated:** June 2026

---

## Table of Contents

1. [Screen Inventory](#1-screen-inventory)
2. [Navigation Architecture](#2-navigation-architecture)
3. [User Journeys](#3-user-journeys)
4. [Screen Specifications](#4-screen-specifications)
5. [Reusable Components](#5-reusable-components)
6. [State Definitions](#6-state-definitions)
7. [Permissions Handling](#7-permissions-handling)
8. [Image Submission Requirements](#8-image-submission-requirements)
9. [Result Presentation Requirements](#9-result-presentation-requirements)
10. [Analytics Requirements](#10-analytics-requirements)
11. [Accessibility Requirements](#11-accessibility-requirements)
12. [Offline Behavior](#12-offline-behavior)
13. [Edge Cases and Failure Scenarios](#13-edge-cases-and-failure-scenarios)
14. [Validation Requirements](#14-validation-requirements)
15. [Retry Behavior](#15-retry-behavior)

---

## 1. Screen Inventory

| Screen ID | Screen Name | Type | Priority |
|-----------|------------|------|---------|
| S-01 | Onboarding — Welcome | Onboarding | P0 |
| S-02 | Onboarding — How It Works | Onboarding | P0 |
| S-03 | Onboarding — Privacy Promise | Onboarding | P0 |
| S-04 | Home (Dashboard) | Primary | P0 |
| S-05 | Image Source Selection | Sheet | P0 |
| S-06 | Image Preview & Confirm | Modal | P0 |
| S-07 | Analysis Loading | Full-screen overlay | P0 |
| S-08 | Analysis Results | Primary | P0 |
| S-09 | Indicator Detail | Sheet | P1 |
| S-10 | History List | Primary | P1 |
| S-11 | History Entry Detail | Primary | P1 |
| S-12 | Settings | Primary | P1 |
| S-13 | Privacy Policy & Data Handling | Secondary | P1 |
| S-14 | Permission Denied — Photos | Sheet | P0 |
| S-15 | Permission Denied — Camera | Sheet | P0 |
| S-16 | Error — Network Unavailable | Inline/Full | P0 |
| S-17 | Error — Analysis Failed | Inline | P0 |
| S-18 | Error — Server Error | Inline | P0 |
| S-19 | Delete Confirmation | Alert/Sheet | P1 |
| S-20 | Share Result | System Share Sheet | P2 |

---

## 2. Navigation Architecture

### Navigation Model

The application uses a tab-based navigation structure with three primary tabs:

- **Tab 1: Scan** (home, submission, and results)
- **Tab 2: History** (list and detail)
- **Tab 3: Settings** (settings, privacy, and information)

Navigation within each tab uses a `NavigationStack` with a `NavigationPath`. The router pushes and pops destinations by value type, keeping navigation logic out of View code.

### Navigation Flow Diagram

```
App Launch
    │
    ├── [First Launch] → Onboarding (S-01 → S-02 → S-03) → Home (S-04)
    └── [Returning User] → Home (S-04)

Home (S-04)
    │
    ├── Tap "Scan" → Image Source Selection Sheet (S-05)
    │       │
    │       ├── Select from Photos → [Permission Check] → Image Preview (S-06)
    │       │       │
    │       │       └── Confirm → Analysis Loading (S-07)
    │       │               │
    │       │               ├── Success → Analysis Results (S-08)
    │       │               │       │
    │       │               │       └── Tap Indicator → Indicator Detail Sheet (S-09)
    │       │               │
    │       │               └── Failure → Error State within S-07 (inline)
    │       │
    │       ├── Take Photo → [Permission Check] → Camera → Image Preview (S-06)
    │       │
    │       └── Dismiss → Back to Home
    │
    └── [If error inline on home] → Error state within S-04

History (S-10)
    │
    └── Tap Entry → History Entry Detail (S-11)
            │
            └── Tap Indicator → Indicator Detail Sheet (S-09)

Settings (S-12)
    │
    ├── Privacy & Data → Privacy Screen (S-13)
    └── Delete All Data → Confirmation (S-19) → Settings (S-12)
```

### Deep Link Support

The app supports the following deep link paths for push notification routing:

| Deep Link | Destination | Notes |
|-----------|------------|-------|
| `trustscan://result/{analysisId}` | Analysis Results (S-08) | Fetches result by ID |
| `trustscan://history` | History List (S-10) | — |
| `trustscan://scan` | Home (S-04), scan action triggered | Equivalent to tapping Scan |

---

## 3. User Journeys

### Journey 1: First-Time User, Successful Scan

1. User opens app for the first time.
2. App presents onboarding (3 screens). User taps through.
3. App presents Home screen (S-04) with prominent scan CTA.
4. User taps "Scan Now."
5. Image source selection sheet appears (S-05).
6. User selects "Choose from Photos."
7. System photo picker appears. App has not yet requested permission — system triggers permission prompt.
8. User grants permission. Photo picker displays their library.
9. User selects a screenshot.
10. Image Preview screen appears (S-06) with the selected image, a "Confirm & Analyze" button, and a "Choose Different" option.
11. User taps "Confirm & Analyze."
12. Analysis loading screen appears (S-07) — animated indicator, "Analyzing your image…" copy.
13. Analysis completes. App navigates to Results screen (S-08).
14. Results screen shows threat verdict (e.g., "Suspicious"), score, indicators list, and recommended action.
15. User reads the result. Taps an indicator to see detail (S-09).
16. User dismisses detail sheet. Result is automatically saved to history.
17. User returns to Home.

**Critical points:** Steps 7–9 must be seamless. If permission was previously granted, step 7 skips the system prompt. The photo picker must appear immediately from step 8.

---

### Journey 2: Returning User, Denied Permission

1. User opens app and navigates to Scan.
2. App checks photo library permission — status is `.denied`.
3. App does not attempt to open photo picker.
4. App presents permission denied sheet (S-14) explaining why photos are needed.
5. Sheet includes "Open Settings" button and "Cancel" button.
6. User taps "Open Settings." iOS Settings app opens to TrustScan's permission page.
7. User grants permission and returns to TrustScan.
8. App resumes from Home with permission now available.

---

### Journey 3: Submission Failure with Retry

1. User selects an image and taps "Confirm & Analyze."
2. Loading screen appears (S-07).
3. Network request times out or returns a server error.
4. Loading screen transitions to an error state (inline within S-07, not a new screen).
5. Error message is displayed: "We couldn't analyze this image. Please try again."
6. A "Try Again" button is shown. The selected image is still held in memory.
7. User taps "Try Again."
8. Loading resumes without requiring re-selection of the image.
9. Analysis completes successfully. App navigates to Results.

---

### Journey 4: Offline Submission Attempt

1. User is offline and navigates to Scan.
2. User selects an image and taps "Confirm & Analyze."
3. Before making the network request, the app detects no connectivity.
4. App presents offline error state immediately, not after a timeout.
5. Error message: "No internet connection. Please check your connection and try again."
6. User can dismiss or wait. The image remains selected.
7. If connectivity is restored while the user is on the screen, the app detects it and automatically re-enables the retry action.

---

### Journey 5: Reviewing History

1. User opens History tab.
2. History list displays past analyses sorted by date (newest first).
3. Each entry shows: compressed thumbnail, verdict badge, date, and brief label.
4. User taps an entry.
5. History detail screen shows the full result view for that analysis.
6. If the result data is available locally, no network request is made.
7. User swipes back to history list.
8. User long-presses an entry to reveal a delete option.
9. User taps delete. Confirmation alert appears.
10. User confirms. Entry is removed from list with an animation.

---

### Journey 6: Empty History

1. User opens History tab for the first time (no analyses yet).
2. Empty state is displayed: illustration, "No scans yet" headline, brief description.
3. A "Start Scanning" CTA is present that navigates to the Scan tab.

---

## 4. Screen Specifications

---

### S-01: Onboarding — Welcome

**Purpose:** Introduce the app's core value proposition in a single impactful screen.

**Layout:**
- Full-screen background with brand illustration (shield + magnifying glass motif).
- Large headline: "Scan. Detect. Stay Safe."
- Supporting body copy (2 sentences max): "TrustScan analyzes suspicious messages, emails, and notifications in seconds. Take a screenshot and know instantly if it's a threat."
- Primary CTA button: "Get Started"
- Skip link (text button): "Skip" — navigates directly to Home, marking onboarding as complete.

**States:** Single state (no loading, no error).

**Interactions:**
- Tap "Get Started" → S-02
- Tap "Skip" → S-04, marks onboarding complete

**Analytics events:** `onboarding_welcome_viewed`, `onboarding_skipped` (if Skip tapped)

---

### S-02: Onboarding — How It Works

**Purpose:** Explain the three-step process simply.

**Layout:**
- Three illustrated steps in a vertical list or carousel:
  1. "Take a Screenshot" — Illustration of a screenshot.
  2. "Submit for Analysis" — Illustration of an upload/scan animation.
  3. "Get Your Result" — Illustration of a verdict badge.
- Progress indicator (dots): 2 of 3.
- Primary CTA: "Next"
- Back navigation available.

**States:** Single state.

**Interactions:**
- Tap "Next" → S-03
- Swipe left → S-03
- Swipe right / Back → S-01

---

### S-03: Onboarding — Privacy Promise

**Purpose:** Address the most common user concern (what happens to my data) before they use the product.

**Layout:**
- Icon: Lock or shield illustration.
- Headline: "Your Privacy Matters"
- Three privacy commitments presented as simple bullets with checkmark icons:
  - "We never store your images longer than needed to analyze them."
  - "Your results are private and never shared."
  - "No account required to use TrustScan."
- Link text: "Read our full privacy policy" — opens S-13 as a modal.
- Primary CTA: "Start Scanning"
- Progress indicator: 3 of 3.

**States:** Single state.

**Interactions:**
- Tap "Start Scanning" → S-04, marks onboarding as complete.
- Tap "Read our full privacy policy" → S-13 presented modally, then dismisses back to S-03.
- Back → S-02.

**Analytics events:** `onboarding_completed`

---

### S-04: Home (Dashboard)

**Purpose:** The app's primary screen. Entry point for analysis submission and summary of recent activity.

**Layout:**
- Navigation bar: App name/logo (leading), Settings gear icon (trailing, navigates to S-12).
- Hero area:
  - Greeting copy: "What looks suspicious today?"
  - Subheading: "Upload a screenshot to check for scams instantly."
  - Primary CTA button (full-width, prominent): "Scan a Screenshot"
- Recent activity section (shown only if history exists):
  - Section header: "Recent Scans"
  - Horizontally scrolling row of the 3 most recent `HistoryEntryCard` components.
  - "See All" link → navigates to History tab / S-10.
- If no history: Omit the recent activity section entirely.

**States:**

| State | Behavior |
|-------|----------|
| Idle | Normal layout as above |
| Loading history | Skeleton placeholders in recent activity area |
| Empty (no history) | Recent activity section hidden |
| Offline | Offline banner displayed below navigation bar: "No internet connection — scanning is unavailable." Primary CTA is disabled and visually dimmed. |

**Interactions:**
- Tap "Scan a Screenshot" → S-05 (image source selection sheet)
- Tap settings icon → S-12
- Tap history entry card → S-11

**Analytics events:** `home_viewed`, `scan_initiated`

---

### S-05: Image Source Selection

**Presentation:** Bottom sheet (half-height).

**Purpose:** Let the user choose how to provide an image.

**Layout:**
- Sheet handle at top.
- Headline: "Choose Image Source"
- Option 1 cell: Photo library icon + "Choose from Photos"
- Option 2 cell: Camera icon + "Take a Photo"
- Cancel button at bottom.

**States:**

| State | Behavior |
|-------|----------|
| Default | Both options visible and tappable |
| Camera unavailable (simulator, no hardware) | Camera option is dimmed with a note "Camera not available on this device" |

**Interactions:**
- Tap "Choose from Photos" → Check photo permission → S-14 if denied, PHPickerViewController if granted/not-determined
- Tap "Take a Photo" → Check camera permission → S-15 if denied, camera if granted/not-determined
- Tap Cancel / drag down → Dismiss sheet, return to S-04

---

### S-06: Image Preview & Confirm

**Purpose:** Allow the user to review their selected image before committing to analysis.

**Layout:**
- Navigation bar: "Review Image" title, X dismiss button (leading).
- Image preview: Full-width aspect-ratio-fit display of the selected image.
- Validation feedback zone: If the image fails validation (too large, unsupported format), a yellow warning banner is displayed below the image with a description.
- Secondary action: "Choose a Different Image" (text button, below image).
- Primary CTA: "Confirm & Analyze" (bottom of screen, full-width). Disabled if validation fails.

**States:**

| State | Behavior |
|-------|----------|
| Valid image | CTA enabled, no warning |
| Image too large | Warning banner: "This image is quite large and may take longer to analyze." CTA still enabled. |
| Unsupported format | Warning banner: "This format is not supported. Please choose a JPG or PNG image." CTA disabled. |
| No image (edge case) | Should never reach this screen without an image. If it does, dismiss and return to S-04. |

**Interactions:**
- Tap "Confirm & Analyze" → Begin submission → S-07
- Tap "Choose a Different Image" → Return to S-05
- Tap X → Dismiss, return to S-04

**Analytics events:** `image_preview_viewed`, `submission_confirmed`, `image_reselected`

---

### S-07: Analysis Loading

**Purpose:** Communicate clearly that analysis is in progress and manage the wait experience.

**Presentation:** Full-screen, presented over the navigation stack (modal full-screen or navigation push depending on implementation preference; push is recommended for back-gesture consistency).

**Layout:**
- No navigation bar back button during active loading (prevent accidental cancellation).
- Central animated indicator: A scanning animation (progress ring, wave, or pulsing shield — must respect Reduce Motion preference).
- Primary text: "Analyzing your image…"
- Secondary text: Rotating contextual hints (cycle every 4 seconds):
  - "Checking for suspicious links…"
  - "Scanning for scam patterns…"
  - "Almost there…"
- Cancel link (text button, bottom of screen): "Cancel Analysis" — shown after 5 seconds to prevent accidental cancellation.

**States:**

| State | Behavior |
|-------|----------|
| Active loading | Animation running, hints cycling |
| Polling (delayed result) | Same as loading — user does not see a difference unless timeout approaches |
| Approaching timeout (>15 seconds) | Secondary text changes to "This is taking longer than usual…" |
| Error | See Error State below |
| Success | Transition to S-08 (automatic, no user action) |

**Error State (inline within S-07):**

The screen does not navigate away on error. Instead, it transitions to an error presentation within the same screen:
- Animation stops and fades out.
- Error icon appears (caution triangle or X).
- Error headline: Based on error type (see Error Handling section).
- Error description: Plain language explanation.
- Primary CTA: "Try Again" — retries submission with the same image.
- Secondary action: "Choose Different Image" — returns to S-05.

**Interactions (Active State):**
- Tap "Cancel Analysis" → Confirmation alert ("Cancel this analysis?") → If confirmed, cancel request and return to S-04.

**Interactions (Error State):**
- Tap "Try Again" → Retry submission
- Tap "Choose Different Image" → Return to S-05

**Analytics events:** `analysis_loading_started`, `analysis_cancelled`, `analysis_error_shown`, `analysis_retry_tapped`

---

### S-08: Analysis Results

**Purpose:** Present the analysis verdict and all associated information clearly and actionably.

**Layout:**

**Section 1 — Verdict Header (above fold, full attention):**
- Verdict badge (large): Icon + label. Examples: "⚠️ Suspicious", "🛑 Dangerous", "✅ Safe", "❓ Inconclusive"
- Verdict background color (subtle): Semantic color per verdict (warning/yellow for suspicious, danger/red for dangerous, success/green for safe, neutral/gray for inconclusive)
- Threat score display: Numeric or visual ring (e.g., "Risk Score: 78/100")
- Primary recommended action (highlighted): e.g., "Do not click any links in this message."

**Section 2 — Flagged Indicators (scrollable):**
- Section header: "What We Found"
- List of `ThreatIndicatorCard` components, one per indicator.
- Each card: category icon, category label, brief description, severity dot.
- Tapping a card opens Indicator Detail Sheet (S-09).
- If no indicators and verdict is safe: Single card: "No threats detected."

**Section 3 — Recommendations:**
- Section header: "What to Do"
- List of `RecommendedActionItem` components.
- Each item: numbered step, action text.

**Section 4 — Educational Context (optional):**
- Section header: "About This Type of Scam"
- Collapsed by default ("Tap to learn more" chevron).
- Expands to show educational copy about the scam category detected.
- If no educational content from backend: Section is omitted.

**Section 5 — Actions footer:**
- "Share This Result" button (secondary style) → iOS share sheet with a formatted text summary.
- "Done" / "Scan Another" button (primary) → Returns to S-04.

**States:**

| State | Behavior |
|-------|----------|
| Loaded | Full layout as above |
| Loading (navigating from S-07) | Not shown — navigation happens after result is ready |
| Loaded from history (S-11 path) | Same layout, but footer shows "Back to History" instead of "Scan Another" |

**Interactions:**
- Tap indicator card → S-09 (sheet)
- Tap "Share This Result" → System share sheet (S-20)
- Tap "Scan Another" → Return to S-04
- Tap "Back to History" (if from history) → Pop to S-10

**Analytics events:** `results_viewed`, `results_verdict_{verdictType}`, `indicator_detail_viewed`, `result_shared`, `scan_another_tapped`

---

### S-09: Indicator Detail

**Presentation:** Bottom sheet (expandable, up to 75% screen height).

**Purpose:** Deep-dive on a single flagged indicator.

**Layout:**
- Sheet handle.
- Category icon (large) + category name.
- Severity badge.
- "What We Found" section: The specific element identified (e.g., a URL, phone number, or text phrase). Displayed in a monospaced or differentiated style.
- "Why This Is Suspicious" section: A plain-language explanation of why this indicator is a threat signal.
- "What It Could Mean" section: 1–2 sentences about the likely scam type this indicator represents.
- "Close" button or natural drag-down dismiss.

**States:** Single state (data is required to open this sheet; no loading state needed).

---

### S-10: History List

**Purpose:** Browsable record of past analyses.

**Layout:**
- Navigation bar: "History" title, Edit button (trailing, enables deletion mode).
- Search bar (iOS-native) for filtering by date keyword or verdict.
- List of `HistoryEntryListItem` components, sorted newest first.
- Each item: Thumbnail image, verdict badge, date/time, brief description ("Suspicious message detected").

**States:**

| State | Behavior |
|-------|----------|
| Populated | Full list |
| Empty | S-10 Empty State: Illustration + "No scans yet" + "Start Scanning" CTA |
| Edit mode | Checkboxes appear, "Delete Selected" button in toolbar |
| Loading | Skeleton list items while data loads from persistence |
| Search active | Filtered list based on query; "No results for [query]" if no matches |

**Interactions:**
- Tap entry → S-11
- Swipe left on entry → Delete action
- Tap Edit → Enable edit mode, "Delete All" option appears
- Long press entry → Context menu: "Delete"
- Tap "Start Scanning" (empty state) → Navigate to Scan tab

**Analytics events:** `history_viewed`, `history_entry_opened`, `history_entry_deleted`, `history_cleared`

---

### S-11: History Entry Detail

**Purpose:** Display the full analysis result for a historical entry.

**Layout:** Identical to S-08 (Analysis Results), with the following differences:
- Navigation bar shows a back button to S-10.
- Footer shows "Scan Another" (navigates to S-04, switches to Scan tab).
- A "Analyzed on [date]" timestamp is shown in the header section.

**States:**

| State | Behavior |
|-------|----------|
| Loaded from local cache | Normal view |
| Data unavailable (corrupted/missing) | Error state: "This result is no longer available." + "Go Back" button |

---

### S-12: Settings

**Purpose:** Allow users to manage preferences, view legal information, and control their data.

**Layout:**
- Navigation bar: "Settings" title.
- Sections:

**Account / Session:**
- Session identifier (last 8 characters, read-only display): "Your Session ID: …XXXXXX" — allows correlation in support requests.

**Notifications:**
- Toggle: "Analysis Complete Notifications" (off by default)
- Toggle: "Security Tips" (off by default, conditional on feature flag)

**Privacy & Data:**
- List item: "Privacy Policy & Data Handling" → S-13
- Destructive list item: "Delete All My Data" → S-19 confirmation

**Permissions:**
- List item: "Photo Library Access" — shows current status (Granted / Limited / Denied), tapping opens iOS Settings.
- List item: "Camera Access" — shows current status, tapping opens iOS Settings.

**Support:**
- List item: "Send Feedback" → Compose email to support address (or opens system feedback mechanism)
- List item: "Version" → Displays app version and build number (not tappable)

**Interactions:**
- All list items navigate or perform their described action.
- Toggles update UserDefaults / notification registration immediately.

**Analytics events:** `settings_viewed`

---

### S-13: Privacy Policy & Data Handling

**Purpose:** Transparent, plain-language explanation of data practices.

**Layout:**
- Navigation bar: "Privacy & Data" title, Back button.
- Sections presented as expandable accordions or scrollable sections:
  1. "What we collect" — Anonymous session ID, submitted images (temporarily), analysis results.
  2. "What we do with your images" — Processed for analysis only, not stored permanently, not used for training.
  3. "How long we keep data" — Images: deleted after analysis. Results: retained for [X days] per backend policy.
  4. "What we never do" — Never sold, never shared with advertisers, never linked to identity.
- Full scrollable legal privacy policy text (loaded from a bundled string or fetched URL with a fallback to bundled version).

**States:**

| State | Behavior |
|-------|----------|
| Default | Full content rendered |
| Loading remote policy | Skeleton loader, then content |
| Remote load failed | Bundled fallback content shown with a note: "Showing cached version." |

---

### S-14: Permission Denied — Photos

**Presentation:** Bottom sheet.

**Purpose:** Explain why photo access is needed and provide a clear path to grant it.

**Layout:**
- Illustration: Photo library icon with a lock overlay.
- Headline: "Photo Access Required"
- Body: "TrustScan needs access to your photo library so you can select screenshots for analysis. Your photos are never accessed or stored by TrustScan without your action."
- Primary CTA: "Open Settings" → Opens iOS Settings app.
- Secondary action: "Not Now" → Dismiss sheet.

---

### S-15: Permission Denied — Camera

**Presentation:** Bottom sheet.

**Purpose:** Explain why camera access is needed.

**Layout:** Identical structure to S-14, with camera-specific copy.
- Headline: "Camera Access Required"
- Body: "TrustScan needs camera access so you can photograph a document or screen directly. Your camera is never accessed except when you initiate a scan."

---

### S-16: Offline State

**Presentation:** Inline banner on S-04 (home). Full-screen if the user attempts a submission action while offline.

**Banner layout:**
- System-style warning color strip below navigation bar.
- WiFi-off icon + "No internet connection — scanning is unavailable."
- Dismissible (X button).
- Auto-dismisses when connectivity is restored.

**Full-screen layout (if submission attempted while offline):**
- This appears as the error state within S-07 (described in S-07 spec).

---

### S-19: Delete Confirmation

**Presentation:** Alert (for single entry), Action Sheet (for Delete All).

**Single entry alert:**
- Title: "Delete This Scan?"
- Message: "This will remove this scan from your history permanently."
- Actions: "Delete" (destructive), "Cancel"

**Delete all action sheet:**
- Title: "Delete All Scan History?"
- Message: "All {count} scans will be permanently deleted from this device. This cannot be undone."
- Actions: "Delete All History" (destructive), "Cancel"

---

## 5. Reusable Components

### ThreatVerdictBadge

**Purpose:** Displays the verdict (safe/suspicious/dangerous/inconclusive) with consistent visual treatment.  
**Properties:** `verdict: ThreatVerdict`  
**Renders:** Background color (semantic token), icon, label.  
**Accessibility:** Label reads: "[Verdict] threat level"

---

### ThreatScoreRing

**Purpose:** Visual representation of the normalized threat score (0.0–1.0).  
**Properties:** `score: Double`, `size: RingSize` (small/medium/large)  
**Renders:** Circular progress ring with score numeral in center.  
**Colors:** Interpolated across safe/warning/danger semantic tokens based on score range.  
**Reduce Motion:** When Reduce Motion is on, renders as a static filled ring, no animation.

---

### ThreatIndicatorCard

**Purpose:** Displays a single flagged indicator in list context.  
**Properties:** `indicator: ThreatIndicator`, `onTap: () -> Void`  
**Renders:** Category icon, category label, brief description, severity dot.  
**Min tap target:** 44pt height.

---

### HistoryEntryListItem

**Purpose:** A list row for a historical analysis entry.  
**Properties:** `entry: HistoryEntry`, `onTap: () -> Void`, `onDelete: () -> Void`  
**Renders:** Thumbnail (44x44pt), verdict badge, date, description.

---

### RecommendedActionItem

**Purpose:** Displays a single recommended action.  
**Properties:** `action: RecommendedAction`, `index: Int`  
**Renders:** Step number, action text.

---

### LoadingStateView

**Purpose:** Full-view loading placeholder.  
**Properties:** `message: String?`, `progress: Double?`  
**Renders:** Animated spinner or progress ring, optional message.  
**Reduce Motion:** Static spinner or progress indicator, no pulsing.

---

### EmptyStateView

**Purpose:** Consistent empty state presentation across all list and content screens.  
**Properties:** `illustration: IllustrationAsset`, `title: String`, `description: String`, `action: EmptyStateAction?`  
**Renders:** Centered illustration, headline, body, optional CTA button.

---

### InlineErrorView

**Purpose:** Contextual error presentation within a screen.  
**Properties:** `error: AppError`, `onRetry: (() -> Void)?`, `onDismiss: (() -> Void)?`  
**Renders:** Error icon, headline, description, conditional retry/dismiss buttons.

---

### PermissionPromptSheet

**Purpose:** Reusable sheet for explaining and requesting a permission.  
**Properties:** `permissionType: PermissionType`, `onOpenSettings: () -> Void`, `onDismiss: () -> Void`  
**Renders:** Illustration, headline, body, primary CTA, secondary link.

---

### ScanCTAButton

**Purpose:** The primary scan action button used on the home screen.  
**Properties:** `isEnabled: Bool`, `isLoading: Bool`, `action: () -> Void`  
**Renders:** Full-width primary button with camera/upload icon. Shows loading indicator if `isLoading`.

---

### OfflineBanner

**Purpose:** Persistent inline notification of offline status.  
**Properties:** `onDismiss: () -> Void`  
**Renders:** Warning-colored strip with icon and message. Auto-dismiss behavior.

---

## 6. State Definitions

### SubmissionViewState

Used by the Submission ViewModel (spanning S-05, S-06, S-07):

```
idle               — No active submission, no image selected
imageSelected      — Image selected, awaiting confirmation
preparing          — Image compression in progress
submitting         — Network request in flight
polling(Int)       — Awaiting result, N polls attempted
success(AnalysisResult) — Result received, ready to navigate
error(AppError)    — Failure occurred, error displayed
cancelled          — User cancelled active submission
```

### HistoryViewState

```
idle
loading
populated([HistoryEntry])
empty
error(AppError)
```

### ResultViewState

```
loading            — Used only when navigating from a deep link
loaded(AnalysisResult)
error(AppError)    — Used when result cannot be loaded from history
```

---

## 7. Permissions Handling

### Photo Library

| Scenario | App Behavior |
|----------|-------------|
| `.notDetermined` | App calls `PHPhotoLibrary.requestAuthorization`. System shows standard prompt. |
| `.authorized` | Photo picker presented immediately. |
| `.limited` | Photo picker presented. A banner within the picker prompts for full access (system-handled). App functions normally. |
| `.denied` | S-14 sheet presented. Photo picker not opened. |
| `.restricted` | S-14 sheet presented with modified copy: "Photo access is restricted on this device." Settings link shown. |

### Camera

| Scenario | App Behavior |
|----------|-------------|
| `.notDetermined` | App calls `AVCaptureDevice.requestAccess`. System prompt shown. |
| `.authorized` | Camera opened immediately. |
| `.denied` | S-15 sheet presented. |
| `.restricted` | S-15 sheet with restricted copy. |

### Push Notifications

Notifications are optional. The app requests notification authorization the first time the user enables notifications in Settings (S-12), not at launch. The standard system prompt appears in response to the toggle interaction, not proactively.

### Permission Check Timing

Permission status is checked on every submission attempt, not cached in app state. This ensures the app responds correctly if a user changes permissions in iOS Settings while the app is in the background.

---

## 8. Image Submission Requirements

### Supported Formats

JPEG, PNG, HEIC (the native iOS screenshot format). HEIC images are converted to JPEG before submission.

### Validation Rules

| Rule | Action |
|------|--------|
| File size exceeds backend maximum | Compression is applied. If still oversized after compression, show warning on S-06. CTA disabled. |
| Format not JPEG/PNG/HEIC | Show unsupported format warning on S-06. CTA disabled. |
| Image dimensions below 100x100px | Show warning: "This image may be too small to analyze accurately." CTA remains enabled. |
| No image data (nil/corrupt) | Dismiss to S-05 silently. Do not reach S-06. |

### Compression Strategy

1. If image is below the configured maximum size: No compression applied.
2. If image exceeds maximum: Apply iterative JPEG compression, starting at quality 0.9, reducing in 0.1 increments until the file size is within the configured limit.
3. If maximum compression (0.4) is reached and file is still too large: Crop to the maximum supported dimensions while preserving the center of the image.
4. All compression occurs in a background context (off the main thread).

### Upload Format

Images are uploaded as `multipart/form-data` with the image field named as defined in the API contract. The content type header is set according to the actual format of the submitted data (image/jpeg, image/png).

### Upload Progress

For images larger than a threshold (e.g., 1MB), display a progress bar on S-07 reflecting upload progress via URLSession's `uploadProgress` delegate. Below the threshold, no progress bar is shown — the animation communicates activity.

---

## 9. Result Presentation Requirements

### Verdict Display

| Verdict | Color Token | Icon | Label |
|---------|------------|------|-------|
| `.safe` | `colorSuccess` | Checkmark shield | "Safe" |
| `.suspicious` | `colorWarning` | Warning triangle | "Suspicious" |
| `.dangerous` | `colorDanger` | X shield | "Dangerous" |
| `.inconclusive` | `colorNeutral` | Question mark | "Inconclusive" |

Color must never be the sole differentiator. Icon and label are always shown alongside color.

### Threat Score Display

- Score is displayed as a percentage (score × 100) or as a descriptive label if the backend returns a categorical score.
- The ring component fills to the appropriate proportion.
- Verbal description accompanies the number: "Very Low Risk" (0–20%), "Low Risk" (21–40%), "Moderate Risk" (41–60%), "High Risk" (61–80%), "Critical Risk" (81–100%).

### Indicator List

- Maximum of 10 indicators displayed. If more exist, a "See all X indicators" link expands the list.
- Each indicator displays its severity. Severity ordering: Critical > High > Medium > Low > Informational.
- List is pre-sorted by severity descending.

### Recommendations

- Maximum of 5 recommendations displayed.
- Each recommendation is an actionable instruction.
- Recommendations with `actionType: .deepLink` display as tappable links (e.g., "Report to Action Fraud" → opens a URL).
- `systemAction` type recommendations (e.g., "Block this number") show a "Learn how" link opening a relevant iOS documentation URL.

### Sharing

The share sheet exports a plain-text summary containing:
- App name and analysis date
- Verdict
- Threat score
- List of indicators with descriptions
- Recommendations
- A disclaimer: "This analysis is provided for informational purposes only."

No image content is included in the shared text.

---

## 10. Analytics Requirements

### Instrumentation Philosophy

All analytics events are dispatched via the `AnalyticsService` abstraction. No analytics SDK is called directly from Views or ViewModels. Events are batched and dispatched to the first-party analytics endpoint. No third-party analytics service receives raw event data.

### Event Naming Convention

All events follow the pattern: `{screen_or_context}_{action}`.  
Examples: `home_scan_initiated`, `results_indicator_tapped`, `settings_notification_toggled`.

### Required Events

| Event | Trigger | Properties |
|-------|---------|------------|
| `app_launched` | App enters foreground | `first_launch: Bool`, `onboarding_complete: Bool` |
| `onboarding_step_viewed` | Each onboarding screen viewed | `step: Int` |
| `onboarding_completed` | User exits onboarding | `skipped: Bool` |
| `scan_initiated` | User taps primary CTA | — |
| `image_source_selected` | User selects photo or camera | `source: String` |
| `image_confirmed` | User taps Confirm & Analyze | `image_size_bytes: Int` |
| `analysis_submitted` | Network request sent | — |
| `analysis_completed` | Result received | `verdict: String`, `threat_score: Double`, `duration_ms: Int` |
| `analysis_failed` | Error received | `error_type: String` |
| `analysis_retried` | Retry tapped | `error_type: String`, `attempt: Int` |
| `results_viewed` | Results screen rendered | `verdict: String`, `from_history: Bool` |
| `indicator_detail_viewed` | Indicator card tapped | `category: String`, `severity: String` |
| `result_shared` | Share button tapped | — |
| `history_viewed` | History tab opened | `entry_count: Int` |
| `history_entry_deleted` | Entry deleted | — |
| `settings_viewed` | Settings tab opened | — |
| `permission_prompt_shown` | Permission sheet shown | `permission_type: String` |
| `permission_settings_opened` | Settings redirect tapped | `permission_type: String` |
| `offline_state_shown` | Offline banner shown | — |

### Properties Policy

- No PII in any event.
- No image content or analysis content in any event.
- Session ID (anonymous) is attached to all events.
- All events include: `timestamp`, `session_id`, `app_version`, `os_version`.

---

## 11. Accessibility Requirements

### VoiceOver

- Every interactive element has a meaningful `accessibilityLabel` and, where interaction is non-obvious, an `accessibilityHint`.
- The threat verdict badge announces: "Threat level: [Verdict]. [Score description]."
- The ThreatScoreRing announces its value as: "Risk score: [percentage] percent, [verbal category]."
- The analysis loading screen announces: "Analyzing your image, please wait." When cycling hint text changes, do not announce changes automatically to avoid interrupting VoiceOver narration of other content.
- Error states announce the error message immediately when they appear, using `accessibilityPostNotification(.announcement)`.
- Navigation between screens announces the screen title.

### Dynamic Type

- All text elements use semantic text styles (`.title`, `.body`, `.caption`) rather than fixed font sizes.
- Layouts adapt to larger text sizes: horizontal layouts switch to vertical stacking when text size exceeds the `accessibility1` size class.
- The threat score ring scales with text size category.
- Minimum testing requirement: All screens must be verified at `xSmall` and `accessibilityExtraExtraExtraLarge` text sizes.

### Reduce Motion

- All custom animations (scanning animation, score ring fill animation, loading spinner) respect the `UIAccessibility.isReduceMotionEnabled` flag.
- When Reduce Motion is on: Animations are replaced with instant transitions or opacity crossfades.
- No animation may block user interaction regardless of the Reduce Motion setting.

### Color and Contrast

- Minimum contrast ratio of 4.5:1 for all text on backgrounds.
- Minimum contrast ratio of 3:1 for all UI components and graphical elements conveying information.
- Semantic color tokens define separate values for light mode, dark mode, and increased contrast mode.

### Dark Mode

All screens support Dark Mode. Color tokens define appropriate light/dark variants. No hardcoded `UIColor` or `Color` literals appear in View code.

### Minimum Tap Targets

All interactive elements have a minimum tappable area of 44×44 points, enforced via padding or `.contentShape`.

---

## 12. Offline Behavior

### Network Detection

`NetworkMonitor` runs continuously and publishes connectivity state. ViewModels observe this state.

### Offline — Home Screen

- Offline banner shown below navigation bar.
- "Scan a Screenshot" CTA is disabled with a visual dim and a tooltip: "No internet connection."
- Recent history is still visible (loaded from local persistence).

### Offline — Mid-Submission

If connectivity is lost after submission begins:
- The loading state continues briefly.
- When the URLSession request fails with a connectivity error, the error state is presented.
- Error message: "Your connection was lost. Please try again when you're back online."
- "Try Again" button is disabled until connectivity is restored. It enables automatically when connection is restored (ViewModel observes `NetworkMonitor`).

### Offline — History

History is fully available offline. All history entries and their cached results are accessible without a network connection. If a result detail was not cached (rare edge case), an error message indicates the result is unavailable offline.

### Offline — Settings

Settings are fully available offline.

### Connectivity Restoration

When connectivity is restored:
- The offline banner on the home screen automatically dismisses.
- The "Try Again" button on any error state re-enables.
- No automatic retry is initiated — the user must explicitly take action after restoration.

---

## 13. Edge Cases and Failure Scenarios

### Submission Edge Cases

| Scenario | Behavior |
|----------|----------|
| User submits the same image twice within 30 seconds | Second submission is accepted (no deduplication on client). Backend handles deduplication if needed. |
| User backgrounds the app during analysis | Analysis continues in the background. On return to foreground, the correct state is restored. |
| User force-quits app during analysis | On relaunch, a `PendingSubmission` entry is found in persistence. The home screen shows a banner: "You have an incomplete scan. Would you like to check the status?" — Tapping initiates a status check for the pending analysis ID. |
| App is backgrounded for an extended period and analysis has completed | On foreground, the pending submission state is checked. If result is available, navigate to results automatically. |
| Image picker returns a Live Photo | Extract the still frame from the Live Photo. Do not transmit the video component. |
| Image picker returns a RAW format (rare) | Treat as unsupported format. Show warning on S-06. |

### Result Edge Cases

| Scenario | Behavior |
|----------|----------|
| Backend returns an empty indicators array | Section header "What We Found" still shows; a single item: "No specific threats identified." |
| Backend returns unknown verdict value | Map to `.inconclusive`. Log the unrecognized value. |
| Backend returns no recommendations | Omit the recommendations section entirely. |
| Result data exceeds expected size | Decode what is possible. Truncate indicator list to 10. Log oversized payload. |

### History Edge Cases

| Scenario | Behavior |
|----------|----------|
| History persistence write fails | Log the error. History entry is not saved. No user-facing error (silent failure to avoid disrupting the result view). |
| History load fails on launch | History screen shows an error state with a retry. Home screen shows no recent activity without error. |
| Large history (500+ entries) | Lazy loading is used. Initial page size: 50 entries. Subsequent pages loaded on scroll. |

### Crash and Recovery

| Scenario | Behavior |
|----------|----------|
| App crashes during persistence write | On relaunch, write is either complete or rolled back. No partial entries. |
| App crashes during image upload | `PendingSubmission` record exists. Crash recovery flow (see Submission Edge Cases above). |

---

## 14. Validation Requirements

### Image Validation (Pre-Submission)

| Validation | Rule | User Feedback |
|------------|------|---------------|
| Format check | JPEG, PNG, HEIC only | Warning on S-06 |
| Size check | Within configured maximum after compression | Warning on S-06 |
| Dimension check | At least 100x100px | Warning on S-06 |
| Nil/corrupt check | Image data must be non-nil and decodable | Silent dismiss to S-05 |

### No Form Validation Required

Version 1.0 has no text input fields that require validation. Image validation covers all user input paths.

---

## 15. Retry Behavior

### Automatic Retry

The networking layer performs automatic silent retries for transient failures (connection lost, timeout) with exponential backoff. These retries are invisible to the user — the loading state remains active. Maximum automatic retries: 3.

### User-Initiated Retry

After automatic retries are exhausted:
- Error state is shown on S-07.
- "Try Again" button triggers a fresh submission attempt with the same image.
- Retry count is tracked in the ViewModel. After 3 user-initiated retries, a secondary option "Contact Support" is shown alongside "Try Again."
- There is no maximum to user-initiated retries — users may keep retrying.

### Retry State Preservation

The selected image is held in memory until:
- Analysis succeeds
- User explicitly selects a different image
- User navigates fully away from the submission flow (to Home or another tab)

This ensures a user can retry multiple times without re-selecting their image.

### Retry After App Backgrounding

If the user backgrounds and foregrounds the app during an active loading state:
- If the request is still in flight: Loading state resumes.
- If the request has received a response during background: State updates immediately on foreground.
- If the app was memory-killed: Crash recovery flow activates as described in the edge cases section.