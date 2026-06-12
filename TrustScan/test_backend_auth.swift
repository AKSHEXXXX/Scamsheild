import Foundation
import AppKit

// --- 1. CONFIGURATION ---
let supabaseUrl = "https://woudapmpknaqkebfxeck.supabase.co"
let anonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndvdWRhcG1wa25hcWtlYmZ4ZWNrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODExNjc5NTAsImV4cCI6MjA5Njc0Mzk1MH0.4MtlmphsPksoKQTKcdbUOkuiVnSrzLB0IHHdLsFOjFI"

let email = "admin@trustscan.app"
let password = "Admin123!"

let backendUrl = "https://scamsheild-production-2f8f.up.railway.app/api/v1/sandbox-image"

// --- 2. AUTHENTICATION ---
let authUrl = URL(string: "\(supabaseUrl)/auth/v1/token?grant_type=password")!
var authReq = URLRequest(url: authUrl)
authReq.httpMethod = "POST"
authReq.addValue("application/json", forHTTPHeaderField: "Content-Type")
authReq.addValue(anonKey, forHTTPHeaderField: "apikey")

let authPayload: [String: String] = ["email": email, "password": password]
authReq.httpBody = try! JSONSerialization.data(withJSONObject: authPayload)

let sema = DispatchSemaphore(value: 0)
var jwtToken: String? = nil

URLSession.shared.dataTask(with: authReq) { data, resp, err in
    if let data = data, let dict = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let token = dict["access_token"] as? String {
        jwtToken = token
    } else if let data = data {
        print("Auth failed:", String(data: data, encoding: .utf8) ?? "unknown")
    }
    sema.signal()
}.resume()

sema.wait()

guard let token = jwtToken else {
    print("Failed to authenticate.")
    exit(1)
}
print("Authenticated successfully.")

// --- 3. GENERATE IMAGE ---
let text = """
< Messages AMAZON.CON
ATTENTION: You have been fined $85.22 for failing to return Order No. #23442314. Please log in below within 48 hours to pay this fine or to apply for a waive.
https://shorturl.at/hlMNT
To opt out of future messages or to change your preferences, please click below.
https://shorturl.at/el148
Details
"""

let size = CGSize(width: 800, height: 600)
let img = NSImage(size: size)
img.lockFocus()

NSColor.white.set()
NSRect(origin: .zero, size: size).fill()

let attributes: [NSAttributedString.Key: Any] = [
    .foregroundColor: NSColor.black,
    .font: NSFont.systemFont(ofSize: 24)
]
let attrString = NSAttributedString(string: text, attributes: attributes)
attrString.draw(in: NSRect(x: 20, y: 200, width: 760, height: 380))

img.unlockFocus()

guard let tiffData = img.tiffRepresentation,
      let bitmapRep = NSBitmapImageRep(data: tiffData),
      let pngData = bitmapRep.representation(using: .png, properties: [:]) else {
    print("Failed to create PNG")
    exit(1)
}

let base64String = pngData.base64EncodedString()

// --- 4. CALL BACKEND ---
var req = URLRequest(url: URL(string: backendUrl)!)
req.httpMethod = "POST"
req.addValue("application/json", forHTTPHeaderField: "Content-Type")
req.addValue("test-device", forHTTPHeaderField: "X-Device-Id")
req.addValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

let payload: [String: Any] = [
    "image_base64": base64String,
    "os": "iOS"
]
req.httpBody = try! JSONSerialization.data(withJSONObject: payload)

URLSession.shared.dataTask(with: req) { data, resp, err in
    if let data = data, let str = String(data: data, encoding: .utf8) {
        print("Backend Response: \(str)")
    }
    sema.signal()
}.resume()
sema.wait()

