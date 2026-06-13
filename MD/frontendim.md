# TrustScan — iOS Frontend Design Review & Implementation Guide
**Prepared for:** TrustScan Development Team  
**Review scope:** Authentication, Onboarding, Scan, + Proposed new screens  
**Design benchmark:** iOS 17 HIG, Mobbin/Dribbble security app patterns  
**Constraint:** Preserve existing color palette and brand identity

---

## 0. Design Token Reference (keep these consistent everywhere)

```swift
// Colors — do not introduce any new colors
Background:     #EFF1EC   // Light sage-cream, used as app-wide bg
Surface:        #FFFFFF   // Cards, modals, bottom sheets
PrimaryGreen:   #1B4738   // Buttons, active tab, logo, CTAs
PrimaryGreenHover: #163A2F // Press/active state of PrimaryGreen
ErrorRed:       #E53935   // Validation errors only
TextPrimary:    #1A1A1A
TextSecondary:  #6B7280
TextMuted:      #9CA3AF
Border:         #E5E7EB   // Input borders, dividers
BadgeBg:        #F3F4F0   // Pill badges background

// Typography
FontFamily: SF Pro Rounded (system, use .rounded design variant)
H1:   28pt / Bold      / TextPrimary   / lineHeight 34pt
H2:   22pt / Bold      / TextPrimary   / lineHeight 28pt
H3:   17pt / Semibold  / TextPrimary
Body: 15pt / Regular   / TextPrimary   / lineHeight 22pt
Caption: 13pt / Regular / TextSecondary

// Spacing (8pt grid)
XS: 4pt  |  S: 8pt  |  M: 16pt  |  L: 24pt  |  XL: 32pt  |  XXL: 48pt

// Radius
CardRadius:   16pt
ButtonRadius: 12pt
InputRadius:  12pt
PillRadius:   100pt  // Fully rounded badges/chips
TabRadius:    0pt    // Tab bar: flat top
```

---

## 1. CRITICAL ERRORS — Fix These First

### 1.1 Google Auth Button — Brand Violation 🚨

**Current:** Uses a 🌐 globe emoji  
**Problem:** Google's Brand Guidelines mandate their exact colored "G" logo in auth buttons. Using any substitute is a ToS violation. Apple App Store reviewers can flag third-party login misrepresentation.

**Fix:**
```swift
// Use GoogleSignIn SDK — it provides the correct button automatically
import GoogleSignIn

// Or if building custom:
// Download official SVG from https://developers.google.com/identity/branding-guidelines
// The button must be:
// - Google "G" logo (colored: blue/red/yellow/green), NOT a globe
// - Text: "Continue with Google" or "Sign in with Google" (no variation)
// - Same visual weight as the Apple button — both ghost style with border

// CORRECT button spec:
Button(style: .bordered) {
    HStack {
        Image("google_g_logo")     // Official Google G asset
            .frame(width: 20, height: 20)
        Text("Continue with Google")
            .font(.system(size: 16, weight: .medium))
            .foregroundColor(.textPrimary)
    }
}
.frame(height: 52)
.background(Color.surface)
.cornerRadius(12)
.overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.border, lineWidth: 1))
```

---

### 1.2 Missing "Forgot Password?" Link 🚨

**Current:** No password recovery path exists  
**Problem:** This is a critical trust failure — a *security app* that traps users when they forget their password will get 1-star reviews immediately. Also violates Apple App Store Guideline 5.1.1 (user account management).

**Fix:** Add below the password field, right-aligned:
```swift
HStack {
    Spacer()
    Button("Forgot Password?") {
        // Navigate to ForgotPasswordView
    }
    .font(.system(size: 13, weight: .medium))
    .foregroundColor(Color.primaryGreen)
}
.padding(.top, 4)
.padding(.bottom, 16)
```

---

### 1.3 No Password Visibility Toggle 🚨

**Current:** Password field shows only bullets, no way to reveal  
**Problem:** iOS HIG standard since iOS 15. Users on mobile mistype passwords constantly. Hiding this toggle increases friction and drop-off.

**Fix:**
```swift
HStack {
    if isPasswordVisible {
        TextField("Password", text: $password)
    } else {
        SecureField("Password", text: $password)
    }
    Button(action: { isPasswordVisible.toggle() }) {
        Image(systemName: isPasswordVisible ? "eye.slash.fill" : "eye.fill")
            .foregroundColor(Color.textMuted)
    }
}
.padding(16)
.background(Color.surface)
.cornerRadius(12)
.overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.border))
```

---

### 1.4 Auth Button Style Inconsistency 🚨

**Current:** Apple = solid gray filled | Google = ghost text with blue color  
**Problem:** These two buttons have completely different visual languages, making the screen feel unfinished. Both should be identical in style — only differing in logo and label.

**Fix:** Standardize both as bordered ghost buttons with `1pt` border, height `52pt`, same font, same color. Only the icon changes.

---

### 1.5 Onboarding Has No Page Indicator 🚨

**Current:** Single text screen, no dots, no sense of progress  
**Problem:** Users don't know if there's 1 slide or 7. This causes anxiety and premature "Skip" taps, meaning users never understand the app's value.

**Fix:** Add `TabView` with `.page` style and page dots, minimum 3 onboarding slides (see Section 4 for full spec).

---

## 2. UX BUGS & MISTAKES

### 2.1 "No sign-in required" Badge After Login

**Screen:** Scan (main screen)  
**Problem:** After logging in, showing "No sign-in required" on the scan card is contradictory. The user just signed in. This erodes confidence in the app's intelligence.

**Fix:** This badge should only appear for unauthenticated/guest users. For authenticated users, replace with:
```swift
// For authenticated users, show:
Label("Your scans are private", systemImage: "lock.shield.fill")
    .font(.caption)
    .foregroundColor(Color.textSecondary)

// For guest users only, show:
Label("No sign-in required", systemImage: "person.crop.circle.badge.questionmark")
```

---

### 2.2 "Take Photo" Button Has Insufficient Visual Weight

**Current:** Button uses a very light gray background, almost invisible  
**Problem:** The contrast ratio between the background (`#EFF1EC`) and the button (`#F0F0EE`) is likely below WCAG AA 3:1 ratio. Secondary actions must be clearly distinct.

**Fix:**
```swift
// Secondary button: use a distinct border + white fill
Button("Take Photo") { }
.frame(maxWidth: .infinity, height: 52)
.background(Color.surface)                         // White fill
.foregroundColor(Color.primaryGreen)
.font(.system(size: 16, weight: .semibold))
.cornerRadius(12)
.overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.primaryGreen.opacity(0.4), lineWidth: 1.5))
```

---

### 2.3 "Skip" Text on Onboarding Is Not Accessible

**Current:** Plain text label with no button affordance  
**Problem:** Tap target is too small (likely under 44×44pt, violating iOS HIG minimum). Screen readers may not identify it as interactive.

**Fix:**
```swift
Button(action: { skipOnboarding() }) {
    Text("Skip")
        .font(.system(size: 15, weight: .medium))
        .foregroundColor(Color.textSecondary)
        .frame(minWidth: 60, minHeight: 44)  // Minimum 44pt tap target
}
.accessibilityLabel("Skip onboarding")
```

---

### 2.4 Error Message Is Generic and Unhelpful

**Current:** "Invalid login credentials"  
**Problem:** Doesn't tell the user what to do. Rate-limiting attempts? Wrong email? Wrong password? These are different problems with different solutions.

**Fix (smart error differentiation):**
```swift
// After failed API call, determine error type:
switch authError {
case .wrongPassword:
    errorMessage = "Incorrect password. Forgot it? Tap below to reset."
case .userNotFound:
    errorMessage = "No account found with that email."
case .tooManyAttempts:
    errorMessage = "Too many attempts. Try again in 5 minutes."
case .networkError:
    errorMessage = "No connection. Check your internet and try again."
default:
    errorMessage = "Something went wrong. Please try again."
}
```

---

### 2.5 No Biometric Authentication (Face ID / Touch ID)

**Current:** Only email/password  
**Problem:** For a security-focused app, NOT offering Face ID login is a major trust miss. Users expect a security app to use the most secure auth available. Apple also recommends biometric for any app handling sensitive data.

**Fix:** Add to login screen and Settings:
```swift
// On app launch if already authenticated:
let context = LAContext()
context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
    localizedReason: "Authenticate to access TrustScan") { success, error in
    if success { navigateToMain() }
}

// Login screen: Show Face ID button if credentials are saved
if keychainHasCredentials {
    Button(action: { authenticateWithBiometrics() }) {
        Image(systemName: "faceid")
            .font(.system(size: 28))
            .foregroundColor(Color.primaryGreen)
    }
}
```

---

### 2.6 Navigation Architecture Is Wrong

**Current:** `[Scan] [History] [Settings]` — 3 tabs  
**Problem:**
- Settings as a primary tab is poor iOS convention (Instagram, WhatsApp, Twitter — none have Settings as a primary tab)
- No Profile
- No Blogs/News feed
- Settings should live inside Profile

**Fix — Correct tab architecture:**
```
[Scan] [Blogs] [History] [Profile]
  🛡️     📰      🕐        👤
```
Settings moves to Profile → nested navigation inside Profile screen. This follows Instagram, Twitter, and Robinhood patterns.

---

## 3. SCREEN-BY-SCREEN: COMPLETE REDESIGN NOTES

### 3.1 Auth / Login Screen

**Keep:** Logo, tagline, form layout, Sign In button style  
**Change:**

```
┌─────────────────────────────────────┐
│                                     │
│         🛡️ TrustScan                │  ← Logo + wordmark
│   Scan suspicious messages before   │  ← Tagline (same)
│         they cost you.              │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  admin@trustscan.app          │  │  ← Email field
│  └───────────────────────────────┘  │
│  ┌─────────────────────────── 👁 ┐  │  ← Password + eye toggle [NEW]
│  │  ••••••••••                   │  │
│  └───────────────────────────────┘  │
│                          Forgot?    │  ← Right-aligned [NEW]
│                                     │
│  ⚠️ Incorrect password. Tap Forgot  │  ← Smarter error copy [NEW]
│     Password to reset it.           │
│                                     │
│  ┌─────────────────────────────── ┐ │
│  │          Sign In               │ │  ← Same green button
│  └───────────────────────────────┘ │
│              — or —                 │
│  ┌───────────────────────────────┐  │
│  │  🍎  Continue with Apple      │  │  ← Bordered ghost style
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │  G   Continue with Google     │  │  ← Same bordered ghost [FIX]
│  └───────────────────────────────┘  │
│       👁‍🗨  Sign in with Face ID      │  ← If saved [NEW]
│                                     │
│   Don't have an account? Create one │
└─────────────────────────────────────┘
```

---

### 3.2 Onboarding — Full Redesign (3 slides)

**Keep:** Font, color palette, Next/Skip structure  
**Change:** Add illustrations, page dots, 3 meaningful slides

**Slide 1 — Problem Hook:**
```
┌─────────────────────────────────────┐
│                              Skip   │  ← Top-right
│                                     │
│  ┌─────────────────────────────┐    │
│  │   [Illustration: phone with │    │  ← Custom illustration
│  │    sketchy message/invoice] │    │    Use SF Symbols layered
│  └─────────────────────────────┘    │    or Lottie animation
│                                     │
│   Scammers are getting smarter.     │  ← H2
│                                     │
│   Fake invoices, phishing links,    │  ← Body
│   and impersonation calls cost      │
│   billions every year.              │
│                                     │
│              ● ○ ○                  │  ← Page dots [NEW]
│                                     │
│         ┌──────────────┐            │
│         │     Next     │            │
│         └──────────────┘            │
└─────────────────────────────────────┘
```

**Slide 2 — Solution:**
```
   [Illustration: screenshot → shield → checkmark flow]

   One scan tells you everything.

   Upload any screenshot — message, email,
   invoice, or alert — and TrustScan gives
   you a risk verdict in seconds.

              ○ ● ○

         ┌──────────────┐
         │     Next     │
         └──────────────┘
```

**Slide 3 — Trust / Privacy:**
```
   [Illustration: lock icon + local storage visual]

   Your data stays on your device.

   Scans are analyzed privately. No
   data is stored on our servers
   without your permission.

              ○ ○ ●

         ┌──────────────────┐
         │   Get Started    │   ← Final slide changes to this
         └──────────────────┘
```

**Implementation:**
```swift
TabView(selection: $currentPage) {
    OnboardingSlide1View().tag(0)
    OnboardingSlide2View().tag(1)
    OnboardingSlide3View().tag(2)
}
.tabViewStyle(.page(indexDisplayMode: .always))
.indexViewStyle(.page(backgroundDisplayMode: .always))
// Tint the dots:
UIPageControl.appearance().currentPageIndicatorTintColor = UIColor(Color.primaryGreen)
UIPageControl.appearance().pageIndicatorTintColor = UIColor(Color.primaryGreen).withAlphaComponent(0.3)
```

---

### 3.3 Main Scan Screen — Improvements

**Keep:** Header, card layout, two-button pattern  
**Change:** Fix badge logic, fix button contrast, add recent scans preview

```
┌─────────────────────────────────────┐
│  Good morning, Akshat 👋     🔔      │  ← Personalized [NEW]
├─────────────────────────────────────┤
│  ┌─────────────────────────────┐    │
│  │ What looks suspicious today?│    │
│  │                             │    │
│  │  Upload a screenshot to     │    │
│  │  check for scams instantly. │    │
│  │                             │    │
│  │  🔒 Your scans are private  │    │  ← Context-aware badge [FIX]
│  └─────────────────────────────┘    │
│                                     │
│  Choose a source                    │
│  ┌─────────────────────────────┐    │
│  │  🖼  Choose Screenshot       │    │  ← Primary (green fill)
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │  📷  Take Photo              │    │  ← Secondary (white + green border) [FIX]
│  └─────────────────────────────┘    │
│                                     │
│  Recent Activity            See All │  ← [NEW SECTION]
│  ┌─────────────────────────────┐    │
│  │  ✅ Invoice from "Amazon"   │    │
│  │  Scanned 2 hours ago · Safe │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │  ⚠️ WhatsApp link — "Prize" │    │
│  │  Scanned yesterday · Risky  │    │
│  └─────────────────────────────┘    │
│                                     │
│ [🛡️ Scan] [📰 Blogs] [🕐 History] [👤 Profile] │  ← 4-tab nav [FIX]
└─────────────────────────────────────┘
```

---

## 4. NEW SCREENS TO BUILD

### 4.1 Blogs / News Feed Screen 📰

**Purpose:** Pull and display scam-related news to keep users informed and engaged. Increases app stickiness and positions TrustScan as a scam authority.

**Data sources to integrate:**
- FTC Consumer Alerts RSS: `https://www.ftc.gov/rss/alerts`
- ScamAdviser blog RSS: `https://www.scamadviser.com/rss`
- FBI IC3 News: `https://www.ic3.gov/media/rss`
- Action Fraud (UK): `https://www.actionfraud.police.uk/rss`

**Screen Layout:**
```
┌─────────────────────────────────────┐
│  Scam Intelligence              🔍  │  ← Header + search icon
├─────────────────────────────────────┤
│  [All] [Phishing] [Investment]      │  ← Filter chips, scrollable
│  [Romance] [Tech Support] [SMS]     │
├─────────────────────────────────────┤
│  🔥 Trending Now                    │
│  ┌─────────────────────────────┐    │
│  │ [Thumbnail img]             │    │
│  │ New WhatsApp job scam hits  │    │  ← Featured card (tall)
│  │ UAE and India simultaneously│    │
│  │ FTC · 2 hours ago · 4 min  │    │
│  └─────────────────────────────┘    │
│                                     │
│  Latest Alerts                      │
│  ┌──────┐                           │
│  │[img] │ Fake Amazon refund emails │  ← Compact card rows
│  │      │ surge in June 2026        │
│  │      │ IC3 · 5 hours ago         │
│  └──────┘                           │
│  ┌──────┐                           │
│  │[img] │ Investment scam WhatsApp  │
│  │      │ groups targeting students │
│  │      │ ScamAdviser · Yesterday   │
│  └──────┘                           │
│                                     │
│  [🛡️ Scan] [📰 Blogs] [🕐 History] [👤 Profile] │
└─────────────────────────────────────┘
```

**Implementation notes:**
```swift
struct BlogsView: View {
    @StateObject var viewModel = BlogsViewModel()
    
    // Fetch from RSS and parse
    // Use: https://github.com/nmdias/FeedKit (Swift RSS parser)
    // Or build custom XMLParser for FTC/IC3 feeds
    
    // Filter chips state
    @State var selectedCategory: ScamCategory = .all
    
    // Cache: use URLCache + 30 min stale time
    // Show skeleton loading cards while fetching
}

// Blog card component
struct BlogCard: View {
    let article: ScamArticle
    // Thumbnail: AsyncImage with placeholder
    // Source badge: colored by outlet (FTC = blue, IC3 = red, etc.)
    // Read time: estimated from word count
    // Bookmark: local storage toggle
    // Tap: opens SafariViewController (in-app browser, NOT external Safari)
}
```

**Category filter chips:**
```swift
enum ScamCategory: String, CaseIterable {
    case all = "All"
    case phishing = "Phishing"
    case investment = "Investment"
    case romance = "Romance Scam"
    case techSupport = "Tech Support"
    case sms = "SMS / OTP"
    case crypto = "Crypto"
}
```

---

### 4.2 Profile Screen 👤

**Purpose:** Account management, settings access, usage stats, trust-building.

```
┌─────────────────────────────────────┐
│  Profile                            │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  👤  Akshat Saxena           │    │  ← From Apple/Google login
│  │  akshat@email.com            │    │
│  │  Member since Jan 2026       │    │
│  │  ┌─────────────────────┐    │    │
│  │  │  🟢 Free Plan       │ ↑  │    │  ← Upgrade CTA
│  │  └─────────────────────┘    │    │
│  └─────────────────────────────┘    │
│                                     │
│  Your Stats                         │  ← [NEW — gamification]
│  ┌──────────┐ ┌──────────┐          │
│  │ 24       │ │ 3        │          │
│  │ Scans    │ │ Threats  │          │
│  │ this mo. │ │ caught   │          │
│  └──────────┘ └──────────┘          │
│                                     │
│  Security                           │
│  ┌─────────────────────────────┐    │
│  │  🆔  Face ID Login     [ON] │    │
│  │  🔔  Scam Alerts       [ON] │    │
│  │  📤  Auto-report scams [OFF]│    │
│  └─────────────────────────────┘    │
│                                     │
│  Account                            │
│  ┌─────────────────────────────┐    │
│  │  ⚙️  Settings               │ →  │
│  │  🔒  Privacy Policy         │ →  │
│  │  💬  Help & Support         │ →  │
│  │  ⭐  Rate TrustScan         │ →  │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  Sign Out                   │    │  ← Destructive, red text
│  └─────────────────────────────┘    │
│                                     │
│  [🛡️ Scan] [📰 Blogs] [🕐 History] [👤 Profile] │
└─────────────────────────────────────┘
```

**Avatar implementation:**
```swift
// Show Apple/Google profile picture if available
// Fallback: initials avatar with PrimaryGreen bg
struct AvatarView: View {
    let user: User
    var body: some View {
        if let photoURL = user.photoURL {
            AsyncImage(url: photoURL) { image in
                image.resizable().scaledToFill()
            } placeholder: {
                initialsView
            }
            .frame(width: 64, height: 64)
            .clipShape(Circle())
        } else {
            initialsView
        }
    }
    
    var initialsView: some View {
        Text(user.initials)
            .font(.system(size: 24, weight: .bold))
            .foregroundColor(.white)
            .frame(width: 64, height: 64)
            .background(Color.primaryGreen)
            .clipShape(Circle())
    }
}
```

---

### 4.3 Scan Results Screen (Critical Missing Screen)

This screen doesn't exist in the provided screenshots but must exist. Based on common scam-detection app patterns:

```
┌─────────────────────────────────────┐
│  ← Back          Result       Share │
├─────────────────────────────────────┤
│                                     │
│         [Scanned thumbnail]         │  ← Blurred preview of image
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │         ⚠️  HIGH RISK       │    │  ← Traffic light: 
│  │                             │    │    GREEN=Safe / YELLOW=Caution
│  │  Risk Score: 87 / 100       │    │    RED=High Risk
│  │  ████████████░░░            │    │
│  │                             │    │
│  └─────────────────────────────┘    │
│                                     │
│  Why we flagged this                │
│  ┌─────────────────────────────┐    │
│  │  🎣 Phishing language       │    │
│  │  "Urgent action required"   │    │
│  │                             │    │
│  │  🔗 Suspicious URL          │    │
│  │  amaz0n-claim.xyz           │    │
│  │                             │    │
│  │  ⏰ Urgency tactics         │    │
│  │  "Expires in 24 hours"      │    │
│  └─────────────────────────────┘    │
│                                     │
│  What to do                         │
│  ┌─────────────────────────────┐    │
│  │  1. Do not click any links  │    │
│  │  2. Block the sender        │    │
│  │  3. Report to authorities   │    │
│  └─────────────────────────────┘    │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  📋 Copy Report             │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │  🚩 Report to Authorities   │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

---

### 4.4 History Screen (Improvements)

**Assuming it exists but needs these features:**

```
┌─────────────────────────────────────┐
│  History                    🔍  ⚙️  │
├─────────────────────────────────────┤
│  ┌──────────────────────────────┐   │
│  │  🔍 Search past scans...     │   │  ← Search bar
│  └──────────────────────────────┘   │
│                                     │
│  Filter: [All ▾] [This Week ▾]      │  ← Filter dropdowns
│                                     │
│  Today                              │
│  ┌─────────────────────────────┐    │
│  │ ✅ Safe · Invoice_April.pdf │    │
│  │    Scanned 2:30 PM           │    │
│  └─────────────────────────────┘    │
│                                     │
│  Yesterday                          │
│  ┌─────────────────────────────┐    │
│  │ 🔴 High Risk · WhatsApp msg │    │
│  │    Scanned 7:15 PM           │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ 🟡 Caution · Email screenshot│   │
│  │    Scanned 3:00 PM           │    │
│  └─────────────────────────────┘    │
│                                     │
│  [Empty state if no history:]       │
│  🛡️                                 │
│  No scans yet                       │
│  Upload your first suspicious       │
│  message to get started.            │
│  ┌─────────────┐                    │
│  │  Start Scan │                    │
│  └─────────────┘                    │
│                                     │
│ [🛡️ Scan] [📰 Blogs] [🕐 History] [👤 Profile] │
└─────────────────────────────────────┘
```

---

## 5. COMPONENT LIBRARY — STANDARD COMPONENTS

### 5.1 Primary Button (Green Fill)
```swift
struct PrimaryButton: View {
    let title: String
    let icon: String?
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if let icon { Image(systemName: icon) }
                Text(title).font(.system(size: 16, weight: .semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(Color.primaryGreen)
            .foregroundColor(.white)
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }
}
```

### 5.2 Secondary Button (White + Green Border)
```swift
struct SecondaryButton: View {
    let title: String
    let icon: String?
    let action: () -> Void
    
    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                if let icon { Image(systemName: icon) }
                Text(title).font(.system(size: 16, weight: .semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(Color.surface)
            .foregroundColor(Color.primaryGreen)
            .cornerRadius(12)
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.primaryGreen.opacity(0.4), lineWidth: 1.5)
            )
        }
        .buttonStyle(.plain)
    }
}
```

### 5.3 Risk Badge Component
```swift
enum RiskLevel {
    case safe, caution, high
    
    var color: Color {
        switch self {
        case .safe:    return Color(hex: "#22C55E")
        case .caution: return Color(hex: "#F59E0B")
        case .high:    return Color(hex: "#EF4444")
        }
    }
    
    var icon: String {
        switch self {
        case .safe:    return "checkmark.shield.fill"
        case .caution: return "exclamationmark.triangle.fill"
        case .high:    return "xmark.shield.fill"
        }
    }
    
    var label: String {
        switch self {
        case .safe:    return "Safe"
        case .caution: return "Caution"
        case .high:    return "High Risk"
        }
    }
}
```

### 5.4 Blog Card Component
```swift
struct BlogCard: View {
    let article: ScamArticle
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Thumbnail
            AsyncImage(url: article.thumbnailURL) { img in
                img.resizable().scaledToFill()
            } placeholder: {
                Rectangle().fill(Color.border)
                    .overlay(Image(systemName: "newspaper").foregroundColor(Color.textMuted))
            }
            .frame(height: 160)
            .clipped()
            
            VStack(alignment: .leading, spacing: 6) {
                // Source + date row
                HStack {
                    Text(article.source)
                        .font(.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(Color.primaryGreen)
                    Spacer()
                    Text(article.relativeDate)
                        .font(.caption)
                        .foregroundColor(Color.textMuted)
                }
                
                // Title
                Text(article.title)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundColor(Color.textPrimary)
                    .lineLimit(2)
                
                // Category chip
                CategoryChip(category: article.category)
            }
            .padding(12)
        }
        .background(Color.surface)
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }
}
```

### 5.5 Skeleton Loading State (for Blogs)
```swift
struct SkeletonCard: View {
    @State var shimmer = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Rectangle()
                .fill(shimmerGradient)
                .frame(height: 160)
            Rectangle()
                .fill(shimmerGradient)
                .frame(height: 14)
                .cornerRadius(4)
            Rectangle()
                .fill(shimmerGradient)
                .frame(height: 14)
                .frame(maxWidth: .infinity * 0.7)
                .cornerRadius(4)
        }
        .cornerRadius(16)
        .onAppear { withAnimation(.easeInOut(duration: 1.2).repeatForever()) { shimmer = true } }
    }
    
    var shimmerGradient: LinearGradient {
        LinearGradient(colors: [Color.border, Color.border.opacity(0.4), Color.border],
                       startPoint: shimmer ? .trailing : .leading,
                       endPoint: shimmer ? .leading : .trailing)
    }
}
```

---

## 6. NAVIGATION ARCHITECTURE (Final)

```
App Entry
├── Onboarding (first launch only, 3 slides)
│   └── → Auth
├── Auth
│   ├── Login (email, Apple, Google, Face ID)
│   ├── Register
│   └── Forgot Password
└── Main Tab Bar
    ├── 🛡️ Scan (index 0)
    │   ├── Scan Home
    │   └── Scan Result
    ├── 📰 Blogs (index 1)
    │   ├── Blogs Feed
    │   ├── Article Detail (SafariVC)
    │   └── Search
    ├── 🕐 History (index 2)
    │   ├── History List
    │   └── Past Result Detail
    └── 👤 Profile (index 3)
        ├── Profile Home
        ├── Settings (nested)
        │   ├── Notifications
        │   ├── Privacy
        │   └── Biometrics
        ├── Subscription
        └── Help & Support
```

---

## 7. iOS SPECIFIC REQUIREMENTS CHECKLIST

### Human Interface Guidelines Compliance
- [ ] All tap targets minimum 44×44pt (fix "Skip" button)
- [ ] Safe area insets respected on all screens (bottom: 83pt on iPhone 14+)
- [ ] Dynamic Type support for all text labels
- [ ] Reduce Motion respected for all animations (`@Environment(\.accessibilityReduceMotion)`)
- [ ] Dark Mode support (even if not the primary mode — test all screens)
- [ ] VoiceOver labels on all interactive elements
- [ ] Keyboard avoidance on login screen (use `ignoresSafeArea(.keyboard)` correctly)

### Brand & Legal Compliance
- [ ] Replace globe icon with official Google "G" logo (download from Google Brand guidelines)
- [ ] Apple Sign In button: must follow Apple's exact guidelines (current implementation appears correct)
- [ ] Privacy Policy link accessible before account creation (App Store requirement)
- [ ] Data deletion option in Profile (App Store Guideline 5.1.1)

### Performance
- [ ] Blog images: lazy loading with `AsyncImage` + disk cache
- [ ] RSS feed: background refresh with `BackgroundTasks` framework
- [ ] Scan history: CoreData or SwiftData for local persistence
- [ ] Image upload: compress before sending (max 2MB for scan)

### Notifications
- [ ] Request notification permission on Profile screen (not on launch)
- [ ] Push notification categories: [SCAM_ALERT, WEEKLY_DIGEST]
- [ ] Local notification after scan completes if app is backgrounded

---

## 8. QUICK WINS (Can ship in <1 week)

| Priority | Fix | Effort |
|----------|-----|--------|
| 🔴 P0 | Replace globe with Google G logo | 30 min |
| 🔴 P0 | Add Forgot Password flow | 2 hours |
| 🔴 P0 | Add password visibility toggle | 1 hour |
| 🔴 P0 | Fix secondary button contrast | 30 min |
| 🟡 P1 | Fix Google/Apple button style parity | 1 hour |
| 🟡 P1 | Add page indicator dots to onboarding | 1 hour |
| 🟡 P1 | Fix "No sign-in required" badge logic | 30 min |
| 🟡 P1 | Add Face ID login | 3 hours |
| 🟡 P1 | Better error messages on auth | 1 hour |
| 🟢 P2 | Rebuild tab bar to 4 tabs | 2 hours |
| 🟢 P2 | Build Profile screen | 1 day |
| 🟢 P2 | Add onboarding illustrations | 2 days |
| 🟢 P3 | Build Blogs/News feed | 3-4 days |
| 🟢 P3 | Add Recent Activity to Scan home | 1 day |

---

## 9. DESIGN REFERENCES (Mobbin / Dribbble)

Apps to study on Mobbin for component patterns:
- **1Password** → secure auth flow, biometrics, trust-building
- **Revolut** → risk indicators, transaction status cards
- **Norton Mobile Security** → scan result screens, threat breakdown
- **Lookout Security** → history lists, news/alerts feed
- **NordVPN** → security status communication, minimal scan UI

Search Dribbble for: "scam detector app", "security scan results UI", "iOS news feed card", "risk score indicator mobile"

---

*End of TrustScan Frontend Review — v1.0*  
*Review prepared against: iOS 17 HIG, Apple App Store Guidelines 2024, Google Brand Guidelines, WCAG 2.1 AA*