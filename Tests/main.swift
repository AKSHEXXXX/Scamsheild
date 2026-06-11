import Foundation

do {
  try ProjectValidator.run()
} catch {
  print("Error: \(error)")
}
