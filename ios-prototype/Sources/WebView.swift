import SwiftUI
import WebKit

struct WebView: UIViewRepresentable {
    @ObservedObject var viewModel: WebViewModel

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> WKWebView {
        let prefs = WKPreferences()
        prefs.javaScriptEnabled = true

        let config = WKWebViewConfiguration()
        config.preferences = prefs
        config.userContentController = WKUserContentController()
        config.allowsInlineMediaPlayback = true

        let wv = WKWebView(frame: .zero, configuration: config)
        wv.navigationDelegate = context.coordinator
        wv.uiDelegate = context.coordinator
        wv.allowsBackForwardNavigationGestures = true
        // expose the WKWebView to the view model so other UI can run JS
        viewModel.webView = wv
        return wv
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        if let request = viewModel.currentRequest {
            uiView.load(request)
        } else if let fileURL = viewModel.localFileURL {
            uiView.loadFileURL(fileURL, allowingReadAccessTo: fileURL.deletingLastPathComponent())
        }
    }

    class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        var parent: WebView
        init(_ parent: WebView) { self.parent = parent }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.viewModel.isLoading = false
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.viewModel.isLoading = false
            parent.viewModel.onLoadError?(error)
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.viewModel.isLoading = false
            parent.viewModel.onLoadError?(error)
        }
    }
}

final class WebViewModel: ObservableObject {
    @Published var isLoading: Bool = false
    var onLoadError: ((Error) -> Void)?

    private(set) var currentRequest: URLRequest?
    private(set) var localFileURL: URL?

    // hold a weak reference to the active WKWebView so callers can evaluate JS
    weak var webView: WKWebView?

    func load(url: URL) {
        currentRequest = URLRequest(url: url)
        localFileURL = nil
        isLoading = true
    }

    func loadBundled(filename: String, extension: String) {
        guard let fileURL = Bundle.main.url(forResource: filename, withExtension: `extension`, subdirectory: "www") else {
            onLoadError?(NSError(domain: "WebViewModel", code: -1, userInfo: [NSLocalizedDescriptionKey: "Bundled file not found"]))
            return
        }
        currentRequest = nil
        localFileURL = fileURL
        isLoading = true
    }

    func evaluateJS(_ js: String) {
        DispatchQueue.main.async { [weak self] in
            self?.webView?.evaluateJavaScript(js, completionHandler: { _, error in
                if let err = error {
                    print("JS eval error:\(err)")
                }
            })
        }
    }
}
