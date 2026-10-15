#!/usr/bin/env python3
"""把 .app / .xcarchive 打成 .ipa（跨平台，不依赖 bash / zip / ditto）。

.ipa 的本质: zip 包，内部唯一顶层目录 Payload/，其中放 <AppName>.app。
  WebWrapper.ipa
  └── Payload/
      └── WebWrapper.app/
          ├── WebWrapper        (Mach-O 可执行文件)
          ├── Info.plist
          ├── Frameworks/...    (含符号链接，必须保留)
          └── ...

用法:
  python3 scripts/pack-ipa.py                                   # 默认从 build/App.xcarchive 里找
  python3 scripts/pack-ipa.py build/App.xcarchive/Products/Applications/App.app build/ipa/WebWrapper.ipa
  python3 scripts/pack-ipa.py --list build/ipa/WebWrapper.ipa   # 只列内容，不打包

注意: 在 Windows 上打包只能保证"结构正确"；Mach-O 可执行权限位与符号链接
      Windows 的 zip 实现不保证完整，签名后的包请在 macOS 上出。此脚本用于
      结构核对、CI 外的手工兜底、以及打给重签流程用的中间包。
"""
import argparse
import os
import sys
import zipfile


def resolve_app(path):
    """.xcarchive → 其中的 .app；.app 直接返回。"""
    if path.endswith(".xcarchive") and os.path.isdir(path):
        cand = os.path.join(path, "Products", "Applications")
        if os.path.isdir(cand):
            apps = sorted(d for d in os.listdir(cand) if d.endswith(".app"))
            if apps:
                return os.path.join(cand, apps[0])
        sys.exit("[-] xcarchive 里找不到 .app: " + cand)
    return path


def list_ipa(ipa):
    with zipfile.ZipFile(ipa) as z:
        infos = z.infolist()
        for i in infos[:60]:
            print("%9d  %s" % (i.file_size, i.filename))
        if len(infos) > 60:
            print("... 共 %d 个条目" % len(infos))
    return 0


def pack(src, dst):
    src = resolve_app(src)
    if not os.path.isdir(src):
        sys.exit("[-] 找不到 .app: " + src)

    app_name = os.path.basename(src)
    payload = "Payload/" + app_name
    dst = os.path.abspath(dst)
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    if os.path.exists(dst):
        os.remove(dst)

    files = links = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(payload + "/", b"")
        for base, dirs, names in os.walk(src):
            rel = os.path.relpath(base, src)
            arc = payload if rel == "." else payload + "/" + rel.replace(os.sep, "/")
            for d in sorted(dirs):
                z.writestr(arc + "/" + d + "/", b"")
            for n in sorted(names):
                p = os.path.join(base, n)
                if os.path.islink(p):
                    # 符号链接以链接目标形式存储，保留 iOS framework 结构
                    info = zipfile.ZipInfo(arc + "/" + n)
                    info.external_attr = (0o120777 << 16)
                    info.create_system = 3
                    z.writestr(info, os.readlink(p))
                    links += 1
                else:
                    zi = zipfile.ZipInfo.from_file(p, arc + "/" + n)
                    with open(p, "rb") as fh, z.open(zi, "w") as out:
                        out.write(fh.read())
                    files += 1

    print("[+] IPA: " + dst)
    print("[i] 普通文件 %d 个, 符号链接 %d 个, 包体 %.1f KB" % (files, links, os.path.getsize(dst) / 1024.0))
    print("[i] 核对: python3 scripts/pack-ipa.py --list " + dst)
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("input", nargs="?",
                    default="build/App.xcarchive/Products/Applications/App.app",
                    help=".app 目录或 .xcarchive")
    ap.add_argument("output", nargs="?", default="build/ipa/WebWrapper.ipa", help="输出 .ipa 路径")
    ap.add_argument("--list", metavar="IPA", help="列出 ipa 内条目后退出")
    a = ap.parse_args()

    if a.list:
        return list_ipa(a.list)
    return pack(a.input, a.output)


if __name__ == "__main__":
    sys.exit(main())
