#!/usr/bin/env bash
# 把 .app / .xcarchive 打成 .ipa —— 本质就是 zip
# .ipa 结构: Payload/<AppName>.app
#
# 用法:
#   bash scripts/pack-ipa.sh [APP_OR_ARCHIVE] [OUT_IPA]
# 默认:
#   IN  = build/App.xcarchive/Products/Applications/App.app
#   OUT = build/ipa/WebWrapper.ipa
set -euo pipefail

IN="${1:-build/App.xcarchive/Products/Applications/App.app}"
OUT="${2:-build/ipa/WebWrapper.ipa}"

if [ -d "$IN" ] && [ "${IN##*.}" = "xcarchive" ]; then
  IN="$IN/Products/Applications/App.app"
fi
[ -d "$IN" ] || { echo "[-] 找不到 .app: $IN" >&2; exit 1; }

mkdir -p "$(dirname "$OUT")"
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
rm -f "$OUT"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/Payload"

# macOS 用 ditto 保留符号链接与扩展属性，其他平台退回 cp -R
if command -v ditto >/dev/null 2>&1; then
  ditto "$IN" "$WORK/Payload/$(basename "$IN")"
else
  cp -R "$IN" "$WORK/Payload/"
fi

if command -v zip >/dev/null 2>&1; then
  ( cd "$WORK" && zip -qry "$OUT" Payload )
else
  python3 - "$WORK" "$OUT" <<'PY'
import os, sys, zipfile
work, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for base, dirs, names in os.walk(os.path.join(work, "Payload")):
        for n in names:
            p = os.path.join(base, n)
            z.write(p, os.path.relpath(p, work))
PY
fi

echo "[+] IPA: $OUT"
echo "[i] size: $(du -h "$OUT" | cut -f1)"
echo "[i] check: unzip -l '$OUT' | head"
