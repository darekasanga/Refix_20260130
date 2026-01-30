// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "Calcu-iPad",
    platforms: [
        .iOS(.v15)
    ],
    products: [
        .executable(name: "Calcu-iPad", targets: ["Calcu-iPad"])
    ],
    targets: [
        .executableTarget(
            name: "Calcu-iPad",
            dependencies: [],
            path: "Sources",
            resources: [
                .copy("www")
            ]
        )
    ]
)