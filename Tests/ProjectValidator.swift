import Foundation

struct ProjectValidator {
  static func run() throws {
    let root = URL(fileURLWithPath: #filePath)
      .deletingLastPathComponent().deletingLastPathComponent()

    print("=== iOS Test Connection - Project Validation ===\n")
    var passed = 0
    var failed = 0

    func check(_ label: String, condition: Bool) {
      if condition {
        print("  ✅ \(label)")
        passed += 1
      } else {
        print("  ❌ \(label)")
        failed += 1
      }
    }

    // File structure checks
    let expectedFiles = [
      "iOS_TestConnection/iOS_TestConnection/TestConnectionApp.swift",
      "iOS_TestConnection/iOS_TestConnection/ContentView.swift",
      "iOS_TestConnection/iOS_TestConnection/SupabaseConfig.swift",
      "iOS_TestConnection/iOS_TestConnection/Info.plist",
      "iOS_TestConnection/iOS_TestConnection/Assets.xcassets/Contents.json",
      "iOS_TestConnection/iOS_TestConnection.xcodeproj/project.pbxproj",
    ]

    print("📁 File Structure:")
    for file in expectedFiles {
      let fullPath = root.appendingPathComponent(file).path
      check("\(file) exists", condition: FileManager.default.fileExists(atPath: fullPath))
    }

    // ContentView.swift checks
    print("\n📄 ContentView.swift:")
    let contentViewPath = root.appendingPathComponent("iOS_TestConnection/iOS_TestConnection/ContentView.swift").path
    let contentView = try String(contentsOfFile: contentViewPath, encoding: .utf8)
    check("Contains 'Test Connection' button", condition: contentView.contains("Button(\"Test Connection\")"))
    check("Has serverIP constant", condition: contentView.contains("let serverIP"))
    check("Has port constant", condition: contentView.contains("let port = 8000"))
    check("Uses POST method", condition: contentView.contains("httpMethod = \"POST\""))
    check("Sets Content-Type header", condition: contentView.contains("Content-Type"))
    check("Sends 'Hello from iOS'", condition: contentView.contains("Hello from iOS"))
    check("Has status state", condition: contentView.contains("@State"))
    check("Uses URLSession", condition: contentView.contains("URLSession"))
    check("Dispatches to main queue", condition: contentView.contains("DispatchQueue.main"))

    // TestConnectionApp.swift checks
    print("\n📄 TestConnectionApp.swift:")
    let appPath = root.appendingPathComponent("iOS_TestConnection/iOS_TestConnection/TestConnectionApp.swift").path
    let appFile = try String(contentsOfFile: appPath, encoding: .utf8)
    check("Has @main attribute", condition: appFile.contains("@main"))
    check("Uses WindowGroup", condition: appFile.contains("WindowGroup"))
    check("Contains ContentView()", condition: appFile.contains("ContentView()"))

    // SupabaseConfig.swift checks
    print("\n📄 SupabaseConfig.swift:")
    let supabasePath = root.appendingPathComponent("iOS_TestConnection/iOS_TestConnection/SupabaseConfig.swift").path
    let supabaseFile = try String(contentsOfFile: supabasePath, encoding: .utf8)
    check("Has Supabase import", condition: supabaseFile.contains("import Supabase"))
    check("Has supabaseURL", condition: supabaseFile.contains("supabaseURL"))
    check("Has supabaseAnonKey", condition: supabaseFile.contains("supabaseAnonKey"))
    check("Has functionURL", condition: supabaseFile.contains("functionURL"))
    check("Has SupabaseClient", condition: supabaseFile.contains("SupabaseClient"))
    check("Has smart-processor", condition: supabaseFile.contains("smart-processor"))

    // Info.plist checks
    print("\n📄 Info.plist:")
    let plistPath = root.appendingPathComponent("iOS_TestConnection/iOS_TestConnection/Info.plist").path
    let plistFile = try String(contentsOfFile: plistPath, encoding: .utf8)
    check("Has NSAllowsLocalNetworking", condition: plistFile.contains("NSAllowsLocalNetworking"))
    check("Has UILaunchScreen", condition: plistFile.contains("UILaunchScreen"))

    // project.pbxproj checks
    print("\n📄 project.pbxproj:")
    let pbxPath = root.appendingPathComponent("iOS_TestConnection/iOS_TestConnection.xcodeproj/project.pbxproj").path
    let pbxFile = try String(contentsOfFile: pbxPath, encoding: .utf8)
    check("References TestConnectionApp.swift", condition: pbxFile.contains("TestConnectionApp.swift"))
    check("References ContentView.swift", condition: pbxFile.contains("ContentView.swift"))
    check("References SupabaseConfig.swift", condition: pbxFile.contains("SupabaseConfig.swift"))
    check("Has Supabase package dependency", condition: pbxFile.contains("supabase-swift"))
    check("Has Supabase product dependency", condition: pbxFile.contains("\"Supabase\""))
    check("Has NSAllowsLocalNetworking in build settings", condition: pbxFile.contains("GENERATE_INFOPLIST_FILE"))

    // Summary
    print("\n" + String(repeating: "=", count: 40))
    print("RESULTS: \(passed) passed, \(failed) failed out of \(passed + failed) checks")
    if failed > 0 {
      print("STATUS: ❌ SOME CHECKS FAILED")
      throw ValidationError.failedChecks
    } else {
      print("STATUS: ✅ ALL CHECKS PASSED")
    }
  }
}

enum ValidationError: Error, CustomStringConvertible {
  case failedChecks

  var description: String {
    return "Validation failed"
  }
}
