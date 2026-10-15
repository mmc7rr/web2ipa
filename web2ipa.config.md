# 占位符 → 实际取值（已填好，改这几处即可换站/换包名）

| 项 | 现值 | 在哪改 |
|---|---|---|
| 站点 | https://zalora-nice.com | capacitor.config.json `server.url` + `hostname` |
| Bundle ID | com.zaloranice.skroutz | capacitor.config.json `appId`；已在 Apple 后台注册过 App ID 才能自动签名 |
| App 显示名 | Skroutz | capacitor.config.json `appName`；Xcode > Target > General > Display Name |
| Team ID | TEAM_ID（用 CI 签名时填 GitHub Secret） | ExportOptions.plist `teamID` |
| 品牌色 | #FA7401 | capacitor.config.json（StatusBar/SplashScreen）+ assets 重新生成时的采样值 |
| 放行域名 | zalora-nice.com / *.zalora-nice.com / fonts.googleapis.com / fonts.gstatic.com | capacitor.config.json `allowNavigation`，以及 WebViewApp.swift 的 `Const.allowHosts` |

## 站点特征（决定选哪种壳）

- 有 `<meta name="viewport">` → 移动端已适配，套壳显示正常
- 无 PWA manifest、无 serviceWorker → 不做离线能力，**在线站点壳**最合适
- 首页资源：`static/js/jquery.min.js`、`static/css/style1.css`、`static/css/agencies.css`、Google Fonts
- 页面有「商店登入 / 註冊申請」入口 → 登录态由 WKWebView 的 Cookie 存储承载，直接可用

## 换站三步

1. 改 capacitor.config.json 的 `server.url` / `hostname` / `allowNavigation`
2. 改 ios-templates/WebViewApp.swift 的 `Const.startURL` / `startHost` / `allowHosts`
3. 换图标：替换 `assets/icon-source.png` 后重跑 `python scripts/make-ios-assets.py assets/icon-source.png .`
