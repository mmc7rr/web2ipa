// 零依赖最小壳：新建 Xcode iOS App 工程（SwiftUI 生命周期），用本文件覆盖入口即可
// 目标站点: https://zalora-nice.com （改下面 Const 里的域名即可换站）
import SwiftUI
import WebKit

enum Const {
    static let startHost = "zalora-nice.com"
    static let startURL = URL(string: "https://zalora-nice.com")!
    // 站外域名一律交给系统 Safari；要留在壳里的第三方域名追加到下面
    static let allowHosts = ["zalora-nice.com", "fonts.googleapis.com", "fonts.gstatic.com"]
}

struct WebView: UIViewRepresentable {
    let url: URL

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        cfg.preferences.javaScriptCanOpenWindowsAutomatically = true
        cfg.defaultWebpagePreferences.allowsContentJavaScript = true

        let wv = WKWebView(frame: .zero, configuration: cfg)
        wv.navigationDelegate = context.coordinator
        wv.uiDelegate = context.coordinator
        wv.allowsBackForwardNavigationGestures = true
        wv.allowsLinkPreview = true
        wv.scrollView.contentInsetAdjustmentBehavior = .never
        wv.load(URLRequest(url: url))
        return wv
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        // 站内链接留在壳里，站外链接丢给系统 Safari
        func webView(_ webView: WKWebView,
                     decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let host = navigationAction.request.url?.host else {
                return decisionHandler(.allow)
            }
            let allowed = Const.allowHosts.contains { host == $0 || host.hasSuffix("." + $0) }
            if allowed {
                decisionHandler(.allow)
            } else if navigationAction.navigationType == .linkActivated {
                if let u = navigationAction.request.url { UIApplication.shared.open(u) }
                decisionHandler(.cancel)
            } else {
                decisionHandler(.allow)
            }
        }

        // target=_blank / window.open 在当前 webview 打开
        func webView(_ webView: WKWebView,
                     createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction,
                     windowFeatures: WKWindowFeatures) -> WKWebView? {
            if navigationAction.targetFrame == nil, let u = navigationAction.request.url {
                webView.load(URLRequest(url: u))
            }
            return nil
        }

        // JS alert
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping () -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "OK", style: .default) { _ in completionHandler() })
            topVC()?.present(a, animated: true)
        }

        // JS confirm
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping (Bool) -> Void) {
            let a = UIAlertController(title: nil, message: message, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "取消", style: .cancel) { _ in completionHandler(false) })
            a.addAction(UIAlertAction(title: "确定", style: .default) { _ in completionHandler(true) })
            topVC()?.present(a, animated: true)
        }

        private func topVC() -> UIViewController? {
            let scene = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first
            var vc = scene?.windows.first(where: { $0.isKeyWindow })?.rootViewController
            while let p = vc?.presentedViewController { vc = p }
            return vc
        }
    }
}

@main
struct WebWrapperApp: App {
    var body: some Scene {
        WindowGroup {
            WebView(url: Const.startURL)
                .ignoresSafeArea(.container, edges: .bottom)
        }
    }
}
