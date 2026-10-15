# 图标与启动图资源

## 一条命令重生成

```bash
python scripts/make-ios-assets.py assets/icon-source.png .
```

## 产物

| 文件 | 尺寸 | 用途 |
|---|---|---|
| assets/icon-source.png | 1280x1280 | 原始素材 |
| assets/icon.png | 1024x1024 RGB 无 alpha | `npx @capacitor/assets generate --ios` 的输入 |
| assets/splash.png | 2732x2732 白底 | 亮色启动图 |
| assets/splash-brand.png | 2732x2732 品牌色 #FA7401 底 | 无缝版（图标与底同色） |
| assets/splash-dark.png | 2732x2732 #111 底 | 深色模式启动图 |
| assets/preview-icon.png | 1180x1180 | 蒙 iOS squircle 遮罩的预览，核对四角 |
| ios-templates/AppIcon.appiconset/ | 18 项 / 13 个 PNG | Xcode 直接拖进 Assets.xcassets |

## 处理过的两件事

1. **四角留白洪填**：源图是"圆角方 + 白底"，iOS 用超椭圆(squircle)遮罩，弧度与源图不等，
   不处理会在四个角露白月牙。脚本从四角 flood fill 成品牌色 #FA7401，预览图已确认无白边。
2. **去掉 alpha 通道**：App Store 会直接拒收带 alpha 的 1024 marketing icon，产物统一 RGB。

## 上线方式

```bash
# Capacitor 官方资源工具：自动铺满各机型 + 深色模式
npx @capacitor/assets generate --ios

# 或手工：把 ios-templates/AppIcon.appiconset/ 整个拖进 Xcode 的 Assets.xcassets，
# 删掉原 AppIcon 占位，确认 Target > General > App Icons 指向 AppIcon
```

## 命名提醒

App 显示名已按你的要求定为 **Skroutz**（源图上的字也是 Skroutz），域名仍是 zalora-nice.com。
改 `capacitor.config.json` 的 `appName` 一处即可同步所有位置。
