# TrustScan (ScamShield) iOS App

TrustScan is a modern, iOS-native application designed to protect users from social engineering, phishing, and payment scams. By leveraging on-device photo selection and a powerful Python backend, TrustScan analyzes screenshots of suspicious messages and provides instant, actionable threat intelligence.

## 🌟 Key Features

* **Instant Scam Analysis:** Upload screenshots of text messages, emails, or websites. The backend OCR engine extracts text and checks it against dozens of known scam indicators.
* **Supabase Authentication:** Secure, frictionless login using Email/Password, Apple OAuth, or Google OAuth.
* **Detailed Threat Reports:** Clear, color-coded results indicating if a message is Safe, Suspicious, or Dangerous, complete with extracted keywords and actionable recommendations.
* **Scan History:** Keep track of past scans and easily re-review previous threat indicators.
* **Clean Architecture:** Built using Domain-Driven Design and Clean Architecture principles to ensure scalability and maintainability.

## 🛠 Tech Stack

* **Frontend:** SwiftUI, iOS 16.0+
* **Authentication & Database:** Supabase (PostgreSQL, GoTrue Auth)
* **Backend Integration:** FastAPI (Python), Tesseract OCR, deployed via Railway
* **Architecture:** Clean Architecture (Domain, Data, Core, Features)

## 🚀 Getting Started

### Prerequisites
* **macOS** with **Xcode 15+**
* An active **Supabase** Project
* The TrustScan FastAPI Backend running locally or deployed.

### 1. Clone the repository
```bash
git clone https://github.com/Thebinaryztechnologies/Scam-sheild.git
cd Scam-sheild
```

### 2. Configure Environment Variables
To keep API keys secure, this project uses a `.env` file that is intentionally ignored by Git.

1. Locate the `.env.example` file in the `TrustScan/TrustScan/` directory.
2. Duplicate the file and rename it to `.env`.
3. Open `.env` and fill in your actual Supabase and Backend keys:
   ```env
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your_supabase_anon_key
   BACKEND_URL=https://your-backend-url.com
   ```
4. **Important:** Drag and drop this new `.env` file directly into your Xcode project navigator (inside the `TrustScan` group) and ensure it is checked under **Target Membership: TrustScan**.

### 3. Build and Run
1. Open `TrustScan/TrustScan.xcodeproj` in Xcode.
2. Select an iOS Simulator (e.g., iPhone 15 Pro) or plug in your physical device.
3. Press **Cmd + R** (or click the Play button) to build and run the app!

---

## 🏗 Architecture Overview

The codebase is strictly separated into modular layers to prevent tightly coupled code:

* **`/App`**: Entry point (`TrustScanApp.swift`), Dependency Injection (`AppEnvironment.swift`).
* **`/Core`**: Global design tokens (colors, typography), UI components, network monitors, and permission managers.
* **`/Domain`**: Pure Swift business logic. Contains data Models (`AnalysisResult`, `ThreatIndicator`), Interfaces/Ports, and Use Cases. Does *not* import SwiftUI.
* **`/Data`**: Network clients (`APIClient`), Supabase integration (`SupabaseAuthService`), Data Transfer Objects (DTOs), and concrete Repositories.
* **`/Features`**: The UI layer. Segmented by feature (`Auth`, `Submission`, `Results`, `History`). Each feature contains SwiftUI Views and standard `ObservableObject` ViewModels.

## 🔗 Backend Requirements

The iOS app expects the backend to expose the following endpoints:
* `GET /health` - Health check
* `GET /api/v1/config` - Fetches dynamic configuration (scan caps, versioning)
* `POST /api/v1/sandbox-image` - Requires a Supabase JWT in the `Authorization` header and a unique device string in the `X-Device-Id` header. Expects a base64 encoded image and returns threat findings.

*(Note: Additional endpoints for user history and account deletion are pending backend implementation).*
