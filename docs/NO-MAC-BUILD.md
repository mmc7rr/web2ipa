# 没有 Mac 怎么出 .ipa

## 先说结论

iOS 应用能不能**编译**，只取决于有没有 **Xcode**；Xcode 只跑在 macOS 上。
所以没有 Mac 的可行路径只有一条：**把编译放到别人的 macOS 上跑**，你本地只做两件事 —— 传代码、收 .ipa。

| 环节 | 能不能在 Windows 上做 |
|---|---|
| 写站点壳代码、改配置、生成图标资源 | ✅ 全部（本仓库本机已实跑） |
| 编译 .app / 签名 | ❌ 需要 Xcode（macOS） |
| 把 .app 打成 .ipa（Payload + zip） | ✅ `scripts/pack-ipa.py` 已跑通 |
| 把 .ipa 装进 iPhone | ✅ Sideloadly / AltStore 等（见下） |

---

## 路线 1：GitHub Actions（免费，推荐）

### 一次性准备

```powershell
# 在 web2ipa 目录里
git init
git add .
git commit -m "Skroutz iOS wrapper"
git branch -M main
git remote add origin https://github.com/<你的账号>/<仓库名>.git
git push -u origin main
```

> 推之前先跑体检，能省掉一轮失败构建：
> ```powershell
> python scripts/preflight.py
> ```

### 出包

1. GitHub 仓库页 → **Actions** → 左侧 **build-ipa** → 右侧 **Run workflow**
2. `mode` 选 **unsigned**（先走这条，不需要任何证书）
3. 等 8~15 分钟，Jobs 变绿后进这次 run，页面底部 **Artifacts** 下载 **Skroutz-ipa**
4. 解压得到 `Skroutz.ipa`，本地先体检一遍：
   ```powershell
   python scripts/verify-ipa.py Skroutz.ipa --expect-id com.zaloranice.skroutz --expect-name Skroutz
   ```
   会逐项打出 zip 完整性、Payload 结构、Bundle ID/显示名、Mach-O 类型、图标尺寸、是否已签名。

### 想做签名包（上 TestFlight / Ad-Hoc 分发）

在仓库 **Settings → Secrets and variables → Actions** 加这几个：

| Secret | 内容 | 怎么拿 |
|---|---|---|
| `CERT_P12_BASE64` | .p12 证书的 base64 | `certutil -encode cert.p12 cert.b64` 后去掉头尾行 |
| `CERT_PASSWORD` | 导出 .p12 时设的密码 | 你自己设的 |
| `PROFILE_BASE64` | .mobileprovision 的 base64 | 同上 |
| `KEYCHAIN_PASSWORD` | 随便一个字符串 | CI 里临时钥匙串的密码 |
| `TEAM_ID` | Apple Developer Team ID（10 位） | Apple 后台 Membership 页 |

然后 Run workflow 时 `mode` 选 **signed**、`method` 选 `ad-hoc` 或 `app-store-connect`。
证书和描述文件需要在 <https://developer.apple.com/account/resources> 手工创建（付费账号）。

---

## 路线 2：其他 macOS 云

| 服务 | 说明 |
|---|---|
| Codemagic | 有免费额度，内置 iOS 签名向导，能直接产出带签名的 .ipa |
| Bitrise | 同上，workflow 编辑器 |
| Xcode Cloud | Apple 官方，需付费开发者账号，和 App Store Connect 打通 |
| MacinCloud / Scaleway Apple Silicon / MacStadium | 租一台云 Mac，按小时计费，可以远程桌面操作 Xcode |

把本仓库推上去，build 命令填：

```bash
npm install
npx cap add ios || true
npx cap sync ios
npx @capacitor/assets generate --ios
xcodebuild -workspace ios/App/App.xcworkspace -scheme App -configuration Release \
  -sdk iphoneos -destination "generic/platform=iOS" \
  -archivePath build/App.xcarchive archive
python3 scripts/pack-ipa.py build/App.xcarchive build/ipa/Skroutz.ipa
```

---

## 拿到 .ipa 之后：装进 iPhone（Windows 可做）

| 工具 | 需要什么 | 有效期 |
|---|---|---|
| **Sideloadly** | Windows + 一个 Apple ID（免费即可）+ iTunes/驱动 | 免费 ID 签的 7 天，到期重签 |
| **AltStore / SideStore** | 同上，装上后可自动续签 | 7 天自动续 |
| **爱思助手 / iMazing** | 已签名（Ad-Hoc/企业签）的 .ipa | 按证书 |
| **TrollStore** | 越狱设备 | 永久 |
| TestFlight | App Store Connect + 付费账号 | 90 天一轮，可对外分发 |

免费 Apple ID 自签的注意点：同一 Apple ID 最多同时装 3 个自签 App，Bundle ID 会被改写成 `com.<你>` 前缀，7 天要重签一次。
要长期用或对外分发，需要 99 美元/年的 Apple Developer Program。

---

## 常见报错对照

| 报错 | 原因 / 处理 |
|---|---|
| `No profiles for 'com.zaloranice.skroutz'` | Apple 后台没注册这个 App ID，或 team ID 填错；unsigned 模式不会有这个错 |
| `Signing for "App" requires a development team` | 用 unsigned 模式，或在 Xcode 项目里选 Team（本地有 Xcode 时） |
| `Command PhaseScriptExecution failed` | 依赖没装全，先 `npm install` 再 `npx cap sync ios` |
| `unable to open file ... capacitor.config.json` | `webDir` 对应的 `www/` 缺文件，确认 `www/index.html` 存在 |
| 装到手机后卡白屏 | 站点用了 ATS 不认的证书/混合内容，看 ios-templates/Info.plist.snippet.xml 的 NSExceptionDomains |
| Sideloadly 报 `Unable to connect` | 装最新 iTunes（非 Microsoft Store 版）和 iCloud，或用 `--use-anisette` 兼容模式 |
