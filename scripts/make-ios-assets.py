#!/usr/bin/env python3
"""从一张方形源图生成 iOS 全套资源：AppIcon.appiconset + 1024 单图 + 启动图 + 预览图。

用法:
  python scripts/make-ios-assets.py [源图.png] [输出根目录]

产物:
  assets/icon.png            1024x1024 RGB 无 alpha（@capacitor/assets 吃的格式）
  assets/splash.png          2732x2732 白底 居中 logo
  assets/splash-brand.png    2732x2732 品牌色底
  assets/splash-dark.png     2732x2732 深色底
  assets/preview-icon.png    蒙上 iOS squircle 遮罩的预览（核对圆角/白边用）
  ios-templates/AppIcon.appiconset/   Xcode 直接拖进去的完整图标集 + Contents.json
"""
import json
import math
import os
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    sys.exit("[-] 需要 Pillow: python -m pip install Pillow")


def brand_color(im):
    """取品牌底色：四条边中点内侧的中位色，比单点采样稳。"""
    rgb = im.convert("RGB")
    w, h = rgb.size
    pts = [(w // 2, 4), (w // 2, h - 5), (4, h // 2), (w - 5, h // 2),
           (w // 4, 4), (w * 3 // 4, h - 5)]
    px = sorted(rgb.getpixel(p) for p in pts)
    return px[len(px) // 2]


def bleed_corners(im, brand):
    """源图是"圆角方 + 白底"时，把四角留白洪填成品牌色。

    iOS 用的是超椭圆(squircle)遮罩，和源图的圆角弧度不完全一致，
    不处理的话四个角会露出白月牙。
    """
    rgb = im.convert("RGB")
    w, h = rgb.size
    filled = 0
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        r, g, b = rgb.getpixel(xy)
        if min(r, g, b) > 225:                      # 接近纯白 => 是留白角
            ImageDraw.floodfill(rgb, xy, brand, thresh=48)
            filled += 1
    return rgb, filled


def squircle_mask(size, n=5.0, inset=0.0):
    """近似 Apple 的连续圆角遮罩（超椭圆 |x|^n + |y|^n = 1）。"""
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    r = size / 2.0 - inset
    pts = []
    steps = 720
    for i in range(steps):
        t = 2 * math.pi * i / steps
        ct, st = math.cos(t), math.sin(t)
        x = math.copysign(abs(ct) ** (2.0 / n), ct) * r
        y = math.copysign(abs(st) ** (2.0 / n), st) * r
        pts.append((size / 2.0 + x, size / 2.0 + y))
    d.polygon(pts, fill=255)
    return mask


SIZES = [
    ("iphone", "20x20", "2x", 40), ("iphone", "20x20", "3x", 60),
    ("iphone", "29x29", "2x", 58), ("iphone", "29x29", "3x", 87),
    ("iphone", "40x40", "2x", 80), ("iphone", "40x40", "3x", 120),
    ("iphone", "60x60", "2x", 120), ("iphone", "60x60", "3x", 180),
    ("ipad", "20x20", "1x", 20), ("ipad", "20x20", "2x", 40),
    ("ipad", "29x29", "1x", 29), ("ipad", "29x29", "2x", 58),
    ("ipad", "40x40", "1x", 40), ("ipad", "40x40", "2x", 80),
    ("ipad", "76x76", "1x", 76), ("ipad", "76x76", "2x", 152),
    ("ipad", "83.5x83.5", "2x", 167),
    ("ios-marketing", "1024x1024", "1x", 1024),
]


def splash(master, side, bg, out):
    im = Image.new("RGB", (side, side), bg)
    logo_px = int(side * 0.35)
    im.paste(master.resize((logo_px, logo_px), Image.LANCZOS), ((side - logo_px) // 2, (side - logo_px) // 2))
    im.save(out, "PNG", optimize=True)
    return im


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "assets/icon-source.png"
    out = sys.argv[2] if len(sys.argv) > 2 else "."
    if not os.path.exists(src):
        sys.exit("[-] 找不到源图: " + src)

    raw = Image.open(src)
    brand = brand_color(raw)
    print("[i] src %s %s  brand=#%02X%02X%02X" % (raw.size, raw.mode, brand[0], brand[1], brand[2]))

    canvas, filled = bleed_corners(raw, brand)
    print("[i] 圆角留白处理: %d 个角已填品牌色" % filled)

    os.makedirs(os.path.join(out, "assets"), exist_ok=True)
    master = canvas.resize((1024, 1024), Image.LANCZOS)
    master.save(os.path.join(out, "assets", "icon.png"), "PNG", optimize=True)   # RGB, 无 alpha
    print("[+] assets/icon.png 1024x1024 RGB (no alpha)")

    iconset = os.path.join(out, "ios-templates", "AppIcon.appiconset")
    os.makedirs(iconset, exist_ok=True)
    images, made = [], {}
    for idiom, size, scale, px in SIZES:
        pt = int(float(size.split("x")[0]))
        if px in made:
            name = made[px]
        else:
            name = "icon-%d@%s%s.png" % (pt, scale, "-ipad" if idiom == "ipad" else "")
            canvas.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, name), "PNG", optimize=True)
            made[px] = name
        images.append({"size": size, "idiom": idiom, "filename": name, "scale": scale})
    with open(os.path.join(iconset, "Contents.json"), "w", encoding="utf-8") as fh:
        json.dump({"images": images, "info": {"version": 1, "author": "xcode"}}, fh, indent=2, ensure_ascii=False)
    print("[+] ios-templates/AppIcon.appiconset/  %d entries / %d png" % (len(images), len(made)))

    side = 2732
    splash(master, side, (255, 255, 255), os.path.join(out, "assets", "splash.png"))
    splash(master, side, brand, os.path.join(out, "assets", "splash-brand.png"))
    splash(master, side, (17, 17, 17), os.path.join(out, "assets", "splash-dark.png"))
    print("[+] assets/splash{,-brand,-dark}.png %dx%d  logo 35%% centered" % (side, side))

    # 预览：把 1024 图标蒙上 squircle 放到灰底上，肉眼检查四角有没有露白
    prev = Image.new("RGB", (1180, 1180), (128, 128, 132))
    masked = master.copy()
    masked.putalpha(squircle_mask(1024))
    prev.paste(masked, (78, 78), masked)
    prev.save(os.path.join(out, "assets", "preview-icon.png"), "PNG", optimize=True)
    print("[+] assets/preview-icon.png  squircle 预览")

    # 桌面合成预览：按真实 60pt / 40pt / 27pt 尺寸合成，顺便看小尺寸下还认不认得出
    home = Image.new("RGB", (1200, 560), (24, 26, 32))
    for px, x in [(180, 120), (120, 380), (80, 570)]:
        m = master.resize((px, px), Image.LANCZOS)
        m.putalpha(squircle_mask(px))
        home.paste(m, (x, 120), m)
    home.save(os.path.join(out, "assets", "preview-homescreen.png"), "PNG", optimize=True)
    print("[+] assets/preview-homescreen.png  60pt/40pt/27pt 实尺寸预览")

    bad = []
    for rec in images:
        with Image.open(os.path.join(iconset, rec["filename"])) as t:
            expect = int(float(rec["size"].split("x")[0]) * float(rec["scale"][0]))
            if t.size != (expect, expect) or t.mode != "RGB":
                bad.append((rec["filename"], t.size, t.mode))
    print("[i] self-check: %s" % ("ALL OK" if not bad else "MISMATCH " + str(bad)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
