import SwiftUI
import AppKit

@main
struct CalcuApp: App {
    var body: some Scene {
        WindowGroup(id: "main") {
            ContentView()
        }
        .defaultSize(
            width: NSScreen.main?.visibleFrame.width ?? 1024,
            height: NSScreen.main?.visibleFrame.height ?? 768
        )
        .windowResizability(.automatic)
    }
}
