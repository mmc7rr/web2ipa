#!/usr/bin/env python3
"""生成 xcodebuild -exportArchive 用的 ExportOptions.plist（CI 里按 secret 动态生成）。

用法:
  python scripts/make-export-options.py --method development --team ABCDE12345 \
      --bundle com.zaloranice.skroutz --out ExportOptions.plist
  python scripts/make-export-options.py --method ad-hoc --team ABCDE12345 --signing manual \
      --profile "Skroutz AdHoc" --bundle com.zaloranice.skroutz
"""
import argparse
import plistlib
import sys

METHODS = ["development", "ad-hoc", "app-store-connect", "release-testing", "enterprise"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="development", choices=METHODS)
    ap.add_argument("--team", required=True, help="Apple Developer Team ID，10 位")
    ap.add_argument("--bundle", required=True, help="Bundle Identifier")
    ap.add_argument("--signing", default="automatic", choices=["automatic", "manual"])
    ap.add_argument("--profile", default="", help="manual 模式下的描述文件名称")
    ap.add_argument("--out", default="ExportOptions.plist")
    ap.add_argument("--upload-symbols", action="store_true")
    a = ap.parse_args()

    if a.team in ("TEAM_ID", ""):
        sys.exit("[-] --team 需要真实的 10 位 Team ID")

    d = {
        "method": a.method,
        "teamID": a.team,
        "signingStyle": a.signing,
        "compileBitcode": False,
        "stripSwiftSymbols": True,
        "uploadSymbols": bool(a.upload_symbols),
        "destination": "export",
        "manageAppVersionAndBuildNumber": False,
    }
    if a.method == "app-store-connect":
        d["destination"] = "upload"
    if a.signing == "manual":
        if not a.profile:
            sys.exit("[-] manual 模式需要 --profile 描述文件名")
        d["provisioningProfiles"] = {a.bundle: a.profile}

    with open(a.out, "wb") as fh:
        plistlib.dump(d, fh)
    print("[+] %s  method=%s signing=%s team=%s" % (a.out, a.method, a.signing, a.team))
    return 0


if __name__ == "__main__":
    sys.exit(main())
