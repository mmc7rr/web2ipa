#!/usr/bin/env python3
"""校验一个 .ipa 是否结构完整、能装、字段对不对（Windows 上也能跑）。

用法:
  python scripts/verify-ipa.py path/to/Skroutz.ipa
  python scripts/verify-ipa.py path/to/Skroutz.ipa --expect-id com.zaloranice.skroutz --expect-name Skroutz

检查项：zip 完整性、Payload 下唯一 .app、Info.plist 关键字段、可执行文件存在且是 Mach-O、
图标是否齐全（含 1024 无 alpha）、签名文件是否存在。签名有效性与 provisioning 只能靠 macOS 的
codesign 验，Windows 上不做假阳性判断。
"""
import argparse
import io
import plistlib
import struct
import sys
import zipfile

MACHO_MAGIC = {
    b"\xcf\xfa\xed\xfe": "Mach-O 64-bit LE",
    b"\xce\xfa\xed\xfe": "Mach-O 32-bit LE",
    b"\xfe\xed\xfa\xcf": "Mach-O 64-bit BE",
    b"\xca\xfe\xba\xbe": "Mach-O fat/universal",
}

results = []
fails = []


def ok(msg):
    results.append(("OK  ", msg))


def bad(msg):
    results.append(("FAIL", msg))
    fails.append(msg)


def warn(msg):
    results.append(("WARN", msg))


def png_size(data):
    """返回 (w, h, color_type, 是否 Apple CgBI 优化过)。Xcode 的 pngcrush 会在 sig 后插 CgBI 块，
    所以不能写死偏移 16，必须扫 chunk 找 IHDR。"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    off, cgbi = 8, False
    while off + 8 <= len(data):
        ln = struct.unpack(">I", data[off:off + 4])[0]
        typ = data[off + 4:off + 8]
        if typ == b"CgBI":
            cgbi = True
        if typ == b"IHDR":
            w, h = struct.unpack(">II", data[off + 8:off + 16])
            return w, h, data[off + 17], cgbi
        off += 12 + ln
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ipa")
    ap.add_argument("--expect-id", default="")
    ap.add_argument("--expect-name", default="")
    a = ap.parse_args()

    try:
        z = zipfile.ZipFile(a.ipa)
    except Exception as e:
        print("[-] 打不开: %s" % e)
        return 1

    bad_zip = z.testzip()
    if bad_zip:
        bad("zip 损坏，首个坏条目: " + bad_zip)
    else:
        ok("zip 完整性 testzip() = None")

    names = z.namelist()
    ok("条目数 %d，解压后 %.1f MB" % (len(names), sum(i.file_size for i in z.infolist()) / 1048576.0))

    apps = sorted({n.split("/")[1] for n in names if n.startswith("Payload/") and "/" in n[8:] and n.count("/") >= 1 and n.split("/")[1].endswith(".app")})
    if len(apps) != 1:
        bad("Payload 下 .app 数量 = %d（应恰好 1 个）: %s" % (len(apps), apps))
        for s, m in results:
            print("[%s] %s" % (s, m))
        return 1
    app = apps[0]
    root = "Payload/" + app
    ok("Payload/%s" % app)

    # Info.plist
    try:
        raw = z.read(root + "/Info.plist")
        try:
            pl = plistlib.loads(raw)
        except Exception:
            pl = plistlib.loads(io.BytesIO(raw).read())
        keys = ["CFBundleIdentifier", "CFBundleDisplayName", "CFBundleName",
                "CFBundleShortVersionString", "CFBundleVersion",
                "MinimumOSVersion", "CFBundleExecutable", "CFBundlePackageType"]
        for k in keys:
            if k in pl:
                ok("%s = %s" % (k, pl[k]))
            else:
                warn("Info.plist 缺 %s" % k)
        if a.expect_id and pl.get("CFBundleIdentifier") != a.expect_id:
            bad("Bundle ID 不符: 实际 %s，期望 %s" % (pl.get("CFBundleIdentifier"), a.expect_id))
        if a.expect_name and pl.get("CFBundleDisplayName") != a.expect_name:
            bad("显示名不符: 实际 %s，期望 %s" % (pl.get("CFBundleDisplayName"), a.expect_name))
        if pl.get("CFBundlePackageType") not in (None, "APPL"):
            bad("CFBundlePackageType = %s（应为 APPL）" % pl.get("CFBundlePackageType"))
        if "NSAppTransportSecurity" in pl:
            ok("含 NSAppTransportSecurity 配置")
    except KeyError:
        bad("缺 Info.plist")
        pl = {}

    # 主可执行文件
    exe = pl.get("CFBundleExecutable")
    if exe:
        p = root + "/" + exe
        try:
            head = z.open(p).read(4)
            kind = MACHO_MAGIC.get(head)
            if kind:
                ok("可执行文件 %s 是 %s" % (exe, kind))
            else:
                bad("%s 不是 Mach-O（头部 %r）" % (exe, head))
        except KeyError:
            bad("Info.plist 指向的可执行文件不存在: " + p)

    # 图标
    icons = [n for n in names if n.startswith(root + "/") and n.endswith(".png") and "AppIcon" in n]
    if icons:
        ok("图标 %d 个" % len(icons))
    else:
        warn("没找到 AppIcon*.png（可能是资源目录里，需在 Xcode 里确认）")
    for n in icons[:6]:
        info = png_size(z.read(n))
        if not info:
            warn("图标不是标准 PNG: " + n.split("/")[-1])
            continue
        w, h, ct, cgbi = info
        tag = " (Apple CgBI 优化)" if cgbi else ""
        if w == 1024 and ct != 2:
            bad("1024 marketing icon 带 alpha: " + n)
        else:
            ok("图标 %s %dx%d color type=%d%s" % (n.split("/")[-1], w, h, ct, tag))
    if root + "/Assets.car" in names:
        ok("存在 Assets.car（图标/启动图已编进资源目录）")

    # 签名文件
    if root + "/_CodeSignature/CodeResources" in names:
        ok("存在 _CodeSignature/CodeResources（已签名）")
    else:
        warn("没有 _CodeSignature/CodeResources —— 未签名包，装之前需要自签（Sideloadly 等）")
    if root + "/embedded.mobileprovision" in names:
        ok("存在 embedded.mobileprovision（有描述文件）")

    print("== verify-ipa: %s ==" % a.ipa)
    for s, m in results:
        print("[%s] %s" % (s, m))
    print("")
    if fails:
        print("=> %d 项失败" % len(fails))
        return 1
    print("=> 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
