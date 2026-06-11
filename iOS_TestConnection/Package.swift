// swift-tools-version: 6.0
import PackageDescription

let package = Package(
  name: "iOS_TestConnection",
  platforms: [.iOS(.v18)],
  products: [
    .library(name: "iOS_TestConnection", targets: ["iOS_TestConnection"]),
  ],
  dependencies: [
    .package(url: "https://github.com/supabase/supabase-swift", from: "2.0.0"),
  ],
  targets: [
    .target(
      name: "iOS_TestConnection",
      dependencies: [.product(name: "Supabase", package: "supabase-swift")],
      path: "iOS_TestConnection",
      exclude: ["Assets.xcassets"],
      resources: [.process("Assets.xcassets")]
    ),
  ]
)
