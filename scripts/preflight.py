#!/usr/bin/env python3
"""推 CI 之前的本地体检：配置语法、图标完整性、占位符残留、站点连通性。

用法:
  python scripts/preflight.py [项目根目录]

全绿 exit 0；有问题 exit 1 并逐条列出 —— 直接当 push 前的守门脚本。
"""
import json
import os
import plistlib
import re
import struct
import sys
import urllib.error
import urllib.request

OK, BAD, WARN = "  OK  ", " FAIL ", " WARN "
problems = []
warnings = []


def line(status, msg):
    print("[%s] %s" % (status, msg))


def check_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            json.load(fh)
        line(OK, "JSON 语法 %s" % path)
    except Exception as e:
        problems.append("%s: %s" % (path, e))
        line(BAD, "JSON 语法 %s -> %s" % (path, e))


def check_plist(path):
    try:
        with open(path, "rb") as fh:
            plistlib.load(fh)
        line(OK, "plist 语法 %s" % path)
    except Exception as e:
        problems.append("%s: %s" % (path, e))
        line(BAD, "plist 语法 %s -> %s" % (path, e))


def check_yaml(path):
    try:
        import yaml
    except ImportError:
        warnings.append("未装 PyYAML，跳过 YAML 校验: " + path)
        line(WARN, "YAML 跳过（pip install pyyaml 后生效）: %s" % path)
        return
    try:
        with open(path, encoding="utf-8") as fh:
            yaml.safe_load(fh)
        line(OK, "YAML 语法 %s" % path)
    except Exception as e:
        problems.append("%s: %s" % (path, e))
        line(BAD, "YAML 语法 %s -> %s" % (path, e))


def png_header(path):
    with open(path, "rb") as fh:
        head = fh.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    w, h = struct.unpack(">II", head[16:24])
    return w, h, head[25]


def check_icons(root):
    ic_dir = os.path.join(root, "ios-templates", "AppIcon.appiconset")
    cfg = os.path.join(ic_dir, "Contents.json")
    if not os.path.exists(cfg):
        problems.append("缺 appiconset: " + cfg)
        line(BAD, "appiconset 缺失")
        return
    with open(cfg, encoding="utf-8") as fh:
        d = json.load(fh)
    bad = []
    for rec in d["images"]:
        p = os.path.join(ic_dir, rec["filename"])
        if not os.path.exists(p):
            bad.append("%s 不存在" % rec["filename"])
            continue
        w, h, ct = png_header(p)
        want = int(float(rec["size"].split("x")[0]) * float(rec["scale"][0]))
        if (w, h) != (want, want):
            bad.append("%s 期望 %dx%d 实际 %dx%d" % (rec["filename"], want, want, w, h))
        if ct not in (2, 6):
            bad.append("%s color type=%s" % (rec["filename"], ct))
        if rec["idiom"] == "ios-marketing" and ct != 2:
            bad.append("marketing icon 带 alpha，App Store 会拒: " + rec["filename"])
    if bad:
        problems.extend(bad)
        line(BAD, "appiconset: %d 项异常" % len(bad))
        for b in bad[:8]:
            print("        - " + b)
    else:
        line(OK, "appiconset %d 项 尺寸/通道 全部正确" % len(d["images"]))

    icon = os.path.join(root, "assets", "icon.png")
    if os.path.exists(icon):
        w, h, ct = png_header(icon)
        if (w, h) != (1024, 1024) or ct != 2:
            problems.append("assets/icon.png 应为 1024x1024 color type 2")
            line(BAD, "assets/icon.png %dx%d color type=%d" % (w, h, ct))
        else:
            line(OK, "assets/icon.png 1024x1024 无 alpha")
    for s in ("splash.png", "splash-brand.png", "splash-dark.png"):
        p = os.path.join(root, "assets", s)
        if os.path.exists(p):
            w, h, _ = png_header(p)
            if (w, h) != (2732, 2732):
                warnings.append("%s 不是 2732x2732" % s)
                line(WARN, "%s %dx%d（Capacitor 建议 2732）" % (s, w, h))
            else:
                line(OK, "assets/%s 2732x2732" % s)


def check_placeholders(root):
    pats = ("TARGET_DOMAIN", "TARGET_HOST", "com.example", "YOUR_TEAM_ID")
    skip_dirs = {"node_modules", "build", ".git", "ios", "android"}
    skip_files = ("web2ipa.config.md", os.path.join("scripts", "preflight.py"))
    hits = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for n in names:
            if not n.endswith((".json", ".md", ".xml", ".swift", ".html", ".py", ".sh", ".yml", ".plist")):
                continue
            p = os.path.join(base, n)
            rel = os.path.relpath(p, root)
            if rel.startswith("ios-templates") or rel in skip_files:
                continue          # 模板文件里保留占位符是故意的
            txt = open(p, encoding="utf-8", errors="ignore").read()
            for k in pats:
                if k in txt:
                    hits.append("%s 里还有 %s" % (rel, k))
    if hits:
        problems.extend(hits)
        line(BAD, "占位符残留: " + "; ".join(hits))
    else:
        line(OK, "无占位符残留（TARGET_DOMAIN / com.example / TEAM_ID）")


def check_capacitor(root):
    p = os.path.join(root, "capacitor.config.json")
    if not os.path.exists(p):
        problems.append("缺 capacitor.config.json")
        return None
    with open(p, encoding="utf-8") as fh:
        c = json.load(fh)
    bid = c.get("appId", "")
    if not re.fullmatch(r"[A-Za-z0-9.\-]{3,}", bid) or bid.count(".") < 2:
        problems.append("appId 不规范: " + bid)
        line(BAD, "appId %s 不像合法 Bundle ID（建议 com.公司.应用）" % bid)
    else:
        line(OK, "appId %s / appName %s" % (bid, c.get("appName")))
    srv = c.get("server", {})
    url, host = srv.get("url", ""), srv.get("hostname", "")
    if url and host and host not in url:
        problems.append("server.url 与 hostname 不一致")
        line(BAD, "server.url=%s 但 hostname=%s" % (url, host))
    nav = srv.get("allowNavigation", [])
    if host and not any(host in x for x in nav):
        problems.append("allowNavigation 没放行站点域名")
        line(BAD, "allowNavigation 未包含 %s" % host)
    else:
        line(OK, "allowNavigation 已放行 %s" % host)

    if url:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "preflight/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                line(OK, "站点可达 %s -> HTTP %s" % (url, r.status))
        except urllib.error.HTTPError as e:
            warnings.append("站点返回 HTTP %s" % e.code)
            line(WARN, "站点 %s -> HTTP %s（不影响出包）" % (url, e.code))
        except Exception as e:
            warnings.append("站点不可达: %s" % e)
            line(WARN, "站点探测失败 %s -> %s" % (url, e))
    return c


def check_swift(root, cfg):
    p = os.path.join(root, "ios-templates", "WebViewApp.swift")
    if not os.path.exists(p):
        warnings.append("没有 WebViewApp.swift（纯 Capacitor 路线可忽略）")
        line(WARN, "WebViewApp.swift 不存在")
        return
    txt = open(p, encoding="utf-8").read()
    host = cfg.get("server", {}).get("hostname", "") if cfg else ""
    if host and host in txt:
        line(OK, "WebViewApp.swift 目标域名 = %s" % host)
    else:
        problems.append("WebViewApp.swift 里的域名与 capacitor 配置不一致")
        line(BAD, "WebViewApp.swift 未指向 %s" % host)
    for need in ("WKNavigationDelegate", "allowHosts", "runJavaScriptAlertPanelWithMessage"):
        if need not in txt:
            warnings.append("WebViewApp.swift 缺 %s" % need)
            line(WARN, "WebViewApp.swift 缺 %s" % need)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    print("== preflight: %s ==" % os.path.abspath(root))
    for f in ("capacitor.config.json", "package.json", "ios-templates/AppIcon.appiconset/Contents.json"):
        p = os.path.join(root, f)
        if os.path.exists(p):
            check_json(p)
    p = os.path.join(root, "ExportOptions.plist")
    if os.path.exists(p):
        check_plist(p)
    p = os.path.join(root, ".github/workflows/build-ipa.yml")
    if os.path.exists(p):
        check_yaml(p)
    check_icons(root)
    check_placeholders(root)
    cfg = check_capacitor(root)
    check_swift(root, cfg)

    print("")
    print("== 结论 ==")
    for w in warnings:
        print("  WARN  " + w)
    if problems:
        for b in problems:
            print("  FAIL  " + b)
        print("=> %d 个问题，先修再 push" % len(problems))
        return 1
    print("=> 全部通过（%d 条警告）" % len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
