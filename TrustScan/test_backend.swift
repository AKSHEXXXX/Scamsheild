import Foundation
import AppKit

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

let url = URL(string: "https://scamsheild-production-2f8f.up.railway.app/api/v1/sandbox-image")!
var request = URLRequest(url: url)
request.httpMethod = "POST"
request.addValue("application/json", forHTTPHeaderField: "Content-Type")
request.addValue("test-device", forHTTPHeaderField: "X-Device-Id")

let payload: [String: Any] = [
    "image_base64": base64String,
    "os": "iOS"
]
request.httpBody = try! JSONSerialization.data(withJSONObject: payload)

let semaphore = DispatchSemaphore(value: 0)
let task = URLSession.shared.dataTask(with: request) { data, response, error in
    if let error = error {
        print("Error: \(error)")
    } else if let data = data, let str = String(data: data, encoding: .utf8) {
        if let httpResponse = response as? HTTPURLResponse {
            print("Status: \(httpResponse.statusCode)")
        }
        print("Response: \(str)")
    }
    semaphore.signal()
}
task.resume()
semaphore.wait()
