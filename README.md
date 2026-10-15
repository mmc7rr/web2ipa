# Skroutz —— 把 https://zalora-nice.com 打包成 iOS .ipa

一个 .ipa 的本质就是 `zip Payload/`，里面只有一个 `Payload/Skroutz.app`。整条链子：

1. **造一个 iOS 壳** —— WKWebView 加载站点（或把前端产物塞进壳里当资源）
2. **编译** —— Xcode 把壳编译成 .app ← **只有 macOS 能做**
3. **打包** —— 把 .app 塞进 `Payload/` 压缩并签名

本机（Windows）已经验证过第 3 步和第 1 步的全部**配置与资源**；第 2 步交给 GitHub 的 macOS runner。

## 没有 Mac 的路线（推荐）

**完整图文步骤见 [docs/NO-MAC-BUILD.md](docs/NO-MAC-BUILD.md)**，最短路径：

```powershell
python scripts/preflight.py          # 推之前先体检，本机已全绿
git init; git add .; git commit -m "Skroutz iOS wrapper"
git branch -M main
git remote add origin https://github.com/<你>/<仓库>.git
git push -u origin main
```

→ GitHub 仓库 **Actions → build-ipa → Run workflow**，`mode` 选 **unsigned** → 8~15 分钟后下载 **Skroutz-ipa** artifact → Windows 上用 **Sideloadly / AltStore** 自签装进 iPhone。

想要带签名的包（TestFlight / Ad-Hoc）就配 5 个 Secrets，`mode` 选 signed，细节同上文档。

## 项目当前状态

| 项 | 值 |
|---|---|
| 站点 | https://zalora-nice.com （标题「智慧銷貨存」，繁体电商销售平台落地页） |
| App 显示名 | **Skroutz** |
| Bundle ID | `com.zaloranice.skroutz` |
| 品牌色 | #FA7401（图标四边采样） |
| 图标 | 源图 1280 → 1024 无 alpha + 18 项 appiconset，四角白边已洪填 |
| 启动图 | 2732×2732 ×3（白底 / 品牌色底 / 深色底） |
| 放行域名 | zalora-nice.com、*.zalora-nice.com、fonts.googleapis.com、fonts.gstatic.com |
| 壳类型 | **在线站点壳**（站点已有 viewport，无 PWA/serviceWorker，无需离线包） |

## 三种壳的取舍

| 路线 | 需要什么 | 适合 |
|---|---|---|
| **CI 出包**（本仓库默认） | 一个 GitHub 账号 | 没有 Mac，就是你现在的情况 |
| Capacitor 本地 | macOS + Xcode + Apple ID | 有 Mac，要频繁调试 |
| 手写 WKWebView | macOS + Xcode | 要极简壳、不想引依赖（源码见 ios-templates/WebViewApp.swift） |

有 Mac 时：

```bash
npm install
npx cap add ios && npx cap sync ios
npx @capacitor/assets generate --ios
npm run ios:archive
npx cap open ios            # 首次去 Xcode 选 Team + 确认 Bundle ID
bash scripts/pack-ipa.sh    # 或 python scripts/pack-ipa.py
```

## 常用命令

```bash
python scripts/preflight.py                          # 推 CI 前体检（语法/图标/占位符/站点连通）
python scripts/make-ios-assets.py assets/icon-source.png .   # 重生成图标与启动图
python scripts/pack-ipa.py <App.app|App.xcarchive> out.ipa   # .app → .ipa
python scripts/pack-ipa.py --list out.ipa                    # 列 .ipa 内容自检
python scripts/verify-ipa.py Skroutz.ipa --expect-id com.zaloranice.skroutz --expect-name Skroutz   # 整包体检
python scripts/make-export-options.py --method ad-hoc --team TEAM_ID --bundle com.zaloranice.skroutz
bash scripts/resign-ipa.sh in.ipa out.ipa "证书名" x.mobileprovision   # 换证书重签
```

## 签名形态对照

| 形态 | `ExportOptions.plist` method | 装到哪 |
|---|---|---|
| 开发签名 | development | 描述文件里列了 UDID 的设备 |
| Ad-Hoc | ad-hoc | 最多 100 台已注册设备 |
| App Store | app-store-connect | TestFlight / 商店 |
| 企业签 | enterprise | 企业内部分发（需 Enterprise 账号） |
| 无签名 | `CODE_SIGNING_ALLOWED=NO` | 需 Sideloadly / AltStore 等自签后安装 |

## 本机已验证（Windows / Python 3.12.10）

- `pack-ipa.py`：`.app` 直打 与 `.xcarchive` 自动定位两条分支都通过，产物 `zipfile.testzip()` 返回 None，结构为 `Payload/<App>.app/...`
- `make-ios-assets.py`：18 项图标尺寸/通道自检 ALL OK；`assets/icon.png` 为 1024×1024 PNG color type 2（无 alpha）
- `preflight.py`：15 项全绿（含 YAML 语法、站点 HTTP 200）
- `make-export-options.py`：生成的 plist 可被 `plistlib` 正确读回

## 踩坑清单

1. **Bundle ID 要先在 Apple 后台注册**（`com.zaloranice.skroutz`），否则自动签名报 `No profiles`。真实 Skroutz 家的 App ID 已被占用，所以用了自己域名前缀。
2. `ios/`、`build/`、`node_modules/` 不要提交（.gitignore 已配），CI 里重新生成。
3. 纯 `server.url` 空壳在 App Store 容易撞 4.2（minimum functionality）；要上架就补原生能力（推送/相机/离线缓存）或改离线资源壳。
4. 壳里调相机/相册/定位，必须补 Info.plist 用途字符串（见 ios-templates/Info.plist.snippet.xml），否则闪退。
5. 站点有 `http://` 子资源会被 ATS 拦；要么全站 https，要么用 NSExceptionDomains 放行。
6. Windows 上提交 .sh 记得 `git update-index --chmod=+x scripts/*.sh`，否则 CI 报 Permission denied。
7. Windows 上 `python3` 是 Microsoft Store 别名，可能返回空输出/exit 1；**本机请用 `python`**（3.12.10 实测正常）。macOS/CI 上 `python3` 没问题。
8. 上传 App Store 前版本号必须大于已上传版本，否则 export/upload 阶段报错。
9. `server.url` 站点若按 UA 区分入口，壳里看到的是 `(iPhone; CPU iPhone OS ...) WebWrapper/1.0` 这类串。

## 文件清单

| 文件 | 作用 |
|---|---|
| capacitor.config.json | 壳配置：server.url / appId / appName / allowNavigation |
| .github/workflows/build-ipa.yml | 无 Mac 出包：unsigned / signed 两种模式 |
| docs/NO-MAC-BUILD.md | 无 Mac 全流程（CI + Windows 侧自签安装 + 报错对照） |
| scripts/preflight.py | 推 CI 前体检 |
| scripts/make-ios-assets.py | 源图 → appiconset + 启动图 + 预览 |
| scripts/pack-ipa.py | .app / .xcarchive → .ipa（跨平台，带 --list） |
| scripts/verify-ipa.py | 校验 .ipa：zip 完整性 / Info.plist 字段 / Mach-O / 图标 / 签名 |
| scripts/pack-ipa.sh | 同上，macOS/Linux bash 版 |
| scripts/resign-ipa.sh | 换证书重签已有 ipa |
| scripts/make-export-options.py | 生成 `ExportOptions.plist` |
| ios-templates/WebViewApp.swift | 零依赖 WKWebView 壳源码 |
| ios-templates/Info.plist.app-section.xml | 显示名 / 本地化 / 方向 / 状态栏 |
| ios-templates/Info.plist.snippet.xml | ATS + 权限用途字符串 |
| ios-templates/AppIcon.appiconset/ | 18 项完整图标集 |
| assets/ | 主图标 / 三套启动图 / 两张预览图 |
| web2ipa.config.md | 占位符 → 实际取值对照 |
