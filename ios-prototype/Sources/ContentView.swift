import SwiftUI

struct ContentView: View {
    @StateObject private var network = NetworkMonitor()
    @StateObject private var drawingVM = DrawingViewModel()
    @StateObject private var webVM = WebViewModel()

    // 設定: 実際のリモートURLに置き換えてください
    private let remoteURL = URL(string: "https://webpage-three-kohl.vercel.app/Calcu.html")!
    private let bundledFilename = "Calcu"
    private let bundledExtension = "html"

    @State private var isDrawing: Bool = false
    @State private var selectedDrawing: DrawingItem?

    var body: some View {
        NavigationSplitView {
            // サイドバー: 描画リストとコントロール
            sidebar
                .navigationTitle("Calcu")
                .navigationSplitViewColumnWidth(min: 320, ideal: 400, max: 500)
        } detail: {
            // 詳細ビュー: キャンバスとWebView
            detailView
        }
        .onAppear {
            loadRemote()
        }
    }

    private var sidebar: some View {
        List(selection: $selectedDrawing) {
            Section("Controls") {
                Button(action: loadRemote) {
                    Label("Reload Remote", systemImage: "arrow.clockwise")
                }
                .disabled(webVM.isLoading)

                Button(action: loadLocal) {
                    Label("Load Local", systemImage: "doc")
                }

                Button(action: { isDrawing = true }) {
                    Label("New Drawing", systemImage: "pencil")
                }
                .keyboardShortcut("n", modifiers: .command)
            }

            Section("Drawings") {
                ForEach(drawingVM.drawings) { drawing in
                    DrawingRow(drawing: drawing)
                        .tag(drawing)
                }
            }
        }
        .listStyle(.sidebar)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button(action: { drawingVM.clearAllDrawings() }) {
                    Label("Clear All", systemImage: "trash")
                }
            }
        }
    }

    private var detailView: some View {
        ZStack {
            // WebViewまたはキャンバス
            if let selectedDrawing = selectedDrawing {
                DrawingCanvas(drawing: selectedDrawing, viewModel: drawingVM)
            } else {
                WebView(viewModel: webVM)
                    .edgesIgnoringSafeArea(.all)
            }

            // 描画オーバーレイ
            if isDrawing {
                DrawingOverlay(onDone: { image in
                    isDrawing = false
                    drawingVM.addDrawing(from: image)
                }, onCancel: {
                    isDrawing = false
                })
                .transition(.move(edge: .bottom))
            }

            // ローディングインジケーター
            if webVM.isLoading {
                VStack {
                    ProgressView()
                        .scaleEffect(1.5)
                    Text("Loading...")
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(.ultraThinMaterial)
            }
        }
        .toolbar {
            ToolbarItemGroup(placement: .navigation) {
                if selectedDrawing != nil {
                    Button(action: { self.selectedDrawing = nil }) {
                        Label("Back to Web", systemImage: "arrow.left")
                    }
                }
            }
        }
    }

    private func loadRemote() {
        webVM.load(url: remoteURL)
    }

    private func loadLocal() {
        webVM.loadBundled(filename: bundledFilename, extension: bundledExtension)
    }
}
                    Button(action: { loadRemote() }) {
                        Image(systemName: "arrow.clockwise")
                    }
                    Button(action: { share() }) {
                        Image(systemName: "square.and.arrow.up")
                    }
                    Button(action: { isDrawing.toggle() }) {
                        Image(systemName: "pencil.tip")
                    }
                }
                .padding(12)
            }
            .onAppear {
                decideInitialLoad()
                webVM.onLoadError = { _ in
                    // リモート読み込み失敗時はローカルにフォールバック
                    loadLocal()
                }
            }
        }
    }

    private func decideInitialLoad() {
        if network.isConnected {
            loadRemote()
        } else {
            loadLocal()
        }
    }

    private func loadRemote() {
        webVM.loadRemote(url: remoteURL)
    }

    private func loadLocal() {
        if let fileURL = Bundle.main.url(forResource: bundledFilename, withExtension: bundledExtension, subdirectory: "www") {
            webVM.loadLocal(fileURL: fileURL)
        } else {
            // バンドルに存在しない場合は簡易メッセージを表示
            let temp = FileManager.default.temporaryDirectory.appendingPathComponent("fallback.html")
            try? "<html><body><h1>Offline - no local bundle</h1></body></html>".write(to: temp, atomically: true, encoding: .utf8)
            webVM.loadLocal(fileURL: temp)
        }
    }

    private func openInSafari() {
        UIApplication.shared.open(remoteURL)
    }

    private func share() {
        guard let url = network.isConnected ? remoteURL : Bundle.main.url(forResource: bundledFilename, withExtension: bundledExtension, subdirectory: "www") else { return }
        let av = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        UIApplication.shared.windows.first?.rootViewController?.present(av, animated: true)
    }
}

struct ContentView_Previews: PreviewProvider {
    static var previews: some View {
        ContentView()
    }
}
