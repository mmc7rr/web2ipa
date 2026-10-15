#!/usr/bin/env bash
# 用另一套证书/描述文件重签已有 ipa（换开发者账号、换设备名单、企业签、自签都用这个）
# 依赖: 钥匙串里已安装的签名身份 + 对应 .mobileprovision
#
# 用法:
#   bash scripts/resign-ipa.sh in.ipa out.ipa "Apple Development: Your Name (TEAMID)" path/to/x.mobileprovision
set -euo pipefail

IN="$1"; OUT="$2"; IDENTITY="$3"; PROFILE="$4"

W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
unzip -q "$IN" -d "$W"
APP="$(find "$W/Payload" -maxdepth 1 -name '*.app' | head -n1)"
[ -n "$APP" ] || { echo "[-] Payload 下没有 .app" >&2; exit 1; }

cp "$PROFILE" "$APP/embedded.mobileprovision"

security cms -D -i "$PROFILE" > "$W/profile.plist"
/usr/libexec/PlistBuddy -x -c 'Print :Entitlements' "$W/profile.plist" > "$W/entitlements.plist"

# 清掉旧签名
find "$APP" -name '_CodeSignature' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$APP" -name 'CodeResources' -delete 2>/dev/null || true

# 先签嵌套的 framework / dylib / appex，再签主包
if [ -d "$APP/Frameworks" ]; then
  find "$APP/Frameworks" -maxdepth 1 \( -name '*.framework' -o -name '*.dylib' \) -print0 \
    | xargs -0 -I{} codesign --force --timestamp=none --sign "$IDENTITY" {} || true
fi
if [ -d "$APP/PlugIns" ]; then
  find "$APP/PlugIns" -maxdepth 1 -name '*.appex' -print0 \
    | xargs -0 -I{} codesign --force --timestamp=none --entitlements "$W/entitlements.plist" --sign "$IDENTITY" {} || true
fi
codesign --force --deep --timestamp=none --entitlements "$W/entitlements.plist" --sign "$IDENTITY" "$APP"

echo "[i] signatures:"
codesign -dv --verbose=4 "$APP" 2>&1 | sed -n '1,8p'

mkdir -p "$W/out/Payload"
mv "$APP" "$W/out/Payload/"
( cd "$W/out" && zip -qry "$W/resigned.ipa" Payload )
mkdir -p "$(dirname "$OUT")"
mv "$W/resigned.ipa" "$OUT"
echo "[+] 重签完成: $OUT"
