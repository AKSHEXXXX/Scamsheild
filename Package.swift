// swift-tools-version: 6.0
import PackageDescription

let package = Package(
  name: "iOS-TestConnection-Validation",
  platforms: [
    .macOS(.v13),
  ],
  targets: [
    .executableTarget(
      name: "ProjectValidator",
      path: "Tests"
    )
  ]
)
