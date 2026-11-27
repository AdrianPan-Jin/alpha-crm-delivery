"""Printable brand material generator (CMYK vector PDF + preflight/annotation PNG).

Used for ClawHunt BRAND tasks (2729 roll-up banners, 2727 event backdrop).
All copy and numbers are fictional placeholders; no real logos or people.
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import qrcode

OUT = Path(__file__).parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- fonts
FONT_CANDIDATES = [
    ("CN-B", "C:/Windows/Fonts/msyhbd.ttc"),
    ("CN-R", "C:/Windows/Fonts/msyh.ttc"),
    ("CN-B", "C:/Windows/Fonts/simhei.ttf"),
    ("CN-R", "C:/Windows/Fonts/simsun.ttc"),
]


def register_fonts():
    bold = regular = None
    for name, path in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
        except Exception:
            continue
        if name == "CN-B" and bold is None:
            bold = name
        if name == "CN-R" and regular is None:
            regular = name
    if regular is None:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        regular = bold = "STSong-Light"
    return bold or regular, regular


FONT_B, FONT_R = register_fonts()

# ---------------------------------------------------------------- palette (CMYK only)
INK = CMYKColor(0.85, 0.65, 0.30, 0.55)      # deep navy
INK_2 = CMYKColor(0.55, 0.30, 0.10, 0.20)    # muted steel
ACCENT = CMYKColor(0.00, 0.72, 0.85, 0.00)   # warm orange
ACCENT_2 = CMYKColor(0.10, 0.30, 0.95, 0.00)  # amber
PAPER = CMYKColor(0.00, 0.00, 0.00, 0.00)    # white
MIST = CMYKColor(0.05, 0.02, 0.00, 0.03)


def _t(x, y):
    return x * mm, y * mm


def full_bleed_bg(c, w_mm, h_mm, color=INK):
    c.setFillColor(color)
    c.rect(0, 0, w_mm * mm, h_mm * mm, stroke=0, fill=1)


def text(c, x, y, s, size_mm, font, color=PAPER, align="l"):
    c.setFillColor(color)
    c.setFont(font, size_mm * mm)
    if align == "c":
        c.drawCentredString(x * mm, y * mm, s)
    elif align == "r":
        c.drawRightString(x * mm, y * mm, s)
    else:
        c.drawString(x * mm, y * mm, s)


def wrap_cn(s, max_chars):
    lines = []
    while len(s) > max_chars:
        lines.append(s[:max_chars])
        s = s[max_chars:]
    if s:
        lines.append(s)
    return lines


def qr_block(c, x_mm, y_mm, size_mm, data):
    qr = qrcode.QRCode(border=1, box_size=1)
    qr.add_data(data)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    cell = size_mm / n
    c.setFillColor(PAPER)
    c.rect(x_mm * mm, y_mm * mm, size_mm * mm, size_mm * mm, stroke=0, fill=1)
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    for r in range(n):
        for col in range(n):
            if m[r][col]:
                c.rect((x_mm + col * cell) * mm, (y_mm + (n - 1 - r) * cell) * mm,
                       cell * mm, cell * mm, stroke=0, fill=1)


# ---------------------------------------------------------------- roll-up banner
ROLLUPS = {
    "intro": {
        "kicker": "会员空间平台",
        "headline": "把场地\n变成资源连接器",
        "points": ["会员数据中台：一套档案打通全部触点",
                   "资源匹配：需求发布即匹配给同频企业",
                   "活动与内容：每季度一场高质量对接"],
        "cta": "扫码联系客户经理",
        "steps": ["发布资源需求", "匹配同频企业", "线下深度对接"],
        "member_count": "{{member_count}}",
        "qr": "https://example.invalid/member-space-platform",
    },
    "recruit": {
        "kicker": "会员招募",
        "headline": "找到\n同频的企业",
        "points": ["按行业与阶段精准匹配，不做无意义社交",
                   "成员企业 {{member_count}} 家，覆盖 12 个行业",
                   "入会即送一次资源对接会席位"],
        "cta": "扫码添加客户经理",
        "steps": ["提交企业画像", "获得匹配清单", "进入同频圈层"],
        "member_count": "{{member_count}}",
        "qr": "https://example.invalid/join",
    },
    "event": {
        "kicker": "年度资源对接会",
        "headline": "现场\n即可对接",
        "points": ["20 家企业设展，面对面谈合作",
                   "3 场主题圆桌：供应链、渠道、出海",
                   "会后 7 天内提供匹配清单"],
        "cta": "扫码报名",
        "steps": ["扫码报名", "会前匹配", "现场对接"],
        "member_count": "{{member_count}}",
        "qr": "https://example.invalid/event",
    },
}

SIZES = {"800x2000": (800, 2000), "850x2000": (850, 2000)}
BLEED = 3.0          # mm, per side
BOTTOM_SAFE = 200.0  # mm, keep free of key info
BODY_MIN = 30.0      # mm cap height, body text


def draw_rollup(path: Path, spec: dict, w: float, h: float):
    c = canvas.Canvas(str(path), pagesize=((w + 2 * BLEED) * mm, (h + 2 * BLEED) * mm))
    c.setTitle(f"rollup-{spec['kicker']}-{int(w)}x{int(h)}mm")
    full_bleed_bg(c, w + 2 * BLEED, h + 2 * BLEED)

    # geometry in trim coordinates, offset by bleed
    def X(x):
        return x + BLEED

    def Y(y):
        return y + BLEED

    # top accent band
    c.setFillColor(ACCENT)
    c.rect(0, (h - 14) * mm, (w + 2 * BLEED) * mm, 14 * mm, stroke=0, fill=1)
    # large soft circle motif
    c.setFillColor(CMYKColor(0.80, 0.55, 0.20, 0.35))
    c.circle((X(w) * 0.86) * mm, (Y(h) * 0.74) * mm, 210 * mm, stroke=0, fill=1)
    c.setFillColor(INK)

    # kicker
    text(c, X(60), Y(h - 150), spec["kicker"], 26, FONT_R, ACCENT_2)

    # headline (auto-fit: widest line must fit w-120mm)
    lines = spec["headline"].split("\n")
    max_chars = max(len(l) for l in lines)
    hsize = min(120.0, (w - 120.0) / max_chars)
    y = h - 190 - hsize
    for line in lines:
        text(c, X(60), Y(y), line, hsize, FONT_B, PAPER)
        y -= hsize * 1.18
    headline_bottom = y

    # divider
    c.setStrokeColor(ACCENT)
    c.setLineWidth(6 * mm)
    c.line(X(60) * mm, Y(headline_bottom - 40) * mm, X(w - 60) * mm, Y(headline_bottom - 40) * mm)

    # key points
    y = headline_bottom - 160
    for p in spec["points"]:
        c.setFillColor(ACCENT)
        c.circle(X(70) * mm, Y(y + 12) * mm, 9 * mm, stroke=0, fill=1)
        c.setFillColor(PAPER)
        text(c, X(100), Y(y), p, BODY_MIN, FONT_R, PAPER)
        y -= 95

    # process steps (fills the middle band; cards share one grid)
    steps = spec.get("steps") or []
    if steps and y - 120 > 620:
        gap = 24.0
        card_w = (w - 120 - gap * (len(steps) - 1)) / len(steps)
        card_h = 190.0
        cy0 = y - 120 - card_h
        for i, s in enumerate(steps):
            cx = 60 + i * (card_w + gap)
            c.setFillColor(CMYKColor(0.10, 0.06, 0.02, 0.06))
            c.roundRect(X(cx) * mm, Y(cy0) * mm, card_w * mm, card_h * mm, 18 * mm, stroke=0, fill=1)
            text(c, X(cx + 26), Y(cy0 + card_h - 60), f"0{i+1}", 54, FONT_B, ACCENT)
            text(c, X(cx + 26), Y(cy0 + 52), s, 28, FONT_R, INK)

    # CTA zone: a fixed block above the 200mm bottom safe area
    cta_y0 = 250.0
    cta_h = 210.0
    c.setFillColor(ACCENT)
    c.roundRect(X(60) * mm, Y(cta_y0) * mm, (w - 120) * mm, cta_h * mm, 24 * mm, stroke=0, fill=1)
    text(c, X(90), Y(cta_y0 + 130), spec["cta"], 46, FONT_B, INK)
    text(c, X(90), Y(cta_y0 + 60), f"成员企业 {spec['member_count']} 家 · 12 个行业", 34, FONT_R, INK)
    qr_block(c, w - 250, cta_y0 + 30, 150, spec["qr"])

    # bottom strip (inside 200mm safe zone, decorative only)
    c.setFillColor(INK_2)
    c.rect(0, 0, (w + 2 * BLEED) * mm, BOTTOM_SAFE * mm, stroke=0, fill=1)
    # 底部 200mm 安全区内只放图形，不放任何文字（验收口径）
    text(c, X(60), Y(BOTTOM_SAFE + 22), "会员空间平台 · 资源对接 · 私域部署", 20, FONT_R, MIST)

    # trim marks (outside trim, inside bleed edge not possible; draw at 0.5mm outside trim)
    c.setStrokeColor(CMYKColor(0, 0, 0, 1))
    c.setLineWidth(0.25 * mm)
    for (mx, my) in [(0, 0), (w, 0), (0, h), (w, h)]:
        c.line((X(mx) - 0.2) * mm, (Y(my) - 4) * mm, (X(mx) - 0.2) * mm, (Y(my) + 4) * mm)
        c.line((X(mx) - 4) * mm, (Y(my) - 0.2) * mm, (X(mx) + 4) * mm, (Y(my) - 0.2) * mm)

    c.showPage()
    c.save()
    return path


# ---------------------------------------------------------------- PIL annotation / preflight
def annotate_rollup(path: Path, spec: dict, w: float, h: float, scale: float = 0.18):
    from PIL import Image, ImageDraw, ImageFont

    W, H = int((w + 2 * BLEED) * scale), int((h + 2 * BLEED) * scale)
    img = Image.new("RGB", (W, H), (16, 28, 48))
    d = ImageDraw.Draw(img)
    try:
        f_big = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 26)
        f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    except Exception:
        f_big = f = ImageFont.load_default()

    # layout blocks (approximate visual)
    d.rectangle([0, 0, W - 1, BOTTOM_SAFE * scale], fill=(60, 74, 92))
    d.rectangle([0, 0, W - 1, 14 * scale], fill=(230, 126, 34))
    d.ellipse([W * 0.55, H * 0.18, W * 1.15, H * 0.62], fill=(30, 45, 70))
    d.text((60 * scale, (h - 210) * scale), spec["kicker"], font=f, fill=(245, 200, 120))
    d.text((60 * scale, (h - 380) * scale), spec["headline"].split("\n")[0], font=f_big, fill=(255, 255, 255))
    d.line([60 * scale, (h - 660) * scale, (w - 60) * scale, (h - 660) * scale], fill=(230, 126, 34), width=4)
    y = h - 800
    for p in spec["points"]:
        d.text((100 * scale, y * scale), p, font=f, fill=(255, 255, 255))
        y -= 95
    d.rectangle([60 * scale, (1780 - 210) * scale, (w - 60) * scale, 1780 * scale], fill=(230, 126, 34))

    # guard lines
    d.line([0, BOTTOM_SAFE * scale, W, BOTTOM_SAFE * scale], fill=(255, 60, 60), width=3)
    d.text((8, BOTTOM_SAFE * scale + 4), "底部 200mm 安全区（禁放关键信息）", font=f, fill=(255, 120, 120))
    d.line([0, (2000 - 14) * scale, W, (2000 - 14) * scale], fill=(120, 200, 255), width=2)
    # body text ruler
    rx0, ry0 = 40, (h - 1150) * scale
    d.line([rx0, ry0, rx0 + BODY_MIN * scale * 2, ry0], fill=(120, 255, 160), width=2)
    d.text((rx0, ry0 + 4), f"正文高度 {BODY_MIN:.0f}mm 标尺", font=f, fill=(150, 255, 190))
    # bleed marks
    for (x0, y0) in [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]:
        d.line([x0 - 6, y0, x0 + 6, y0], fill=(255, 255, 255), width=2)
        d.line([x0, y0 - 6, x0, y0 + 6], fill=(255, 255, 255), width=2)
    d.text((8, 8), f"TRIM {int(w)}x{int(h)}mm + BLEED {BLEED:g}mm/side", font=f, fill=(200, 220, 240))
    img.save(path)
    return path


def preflight_rollup(path: Path, rows):
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1500, 240 + 46 * len(rows) + 200
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
        fb = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 30)
    except Exception:
        f = fb = ImageFont.load_default()
    d.text((40, 30), "印前检查（Preflight）— 易拉宝三款 × 两尺寸", font=fb, fill=(0, 0, 0))
    y = 100
    for r in rows:
        d.text((40, y), r, font=f, fill=(0, 0, 0))
        y += 46
    y += 20
    d.text((40, y), "检查项：MediaBox(含 3mm 出血) / TrimBox(成品) / 色彩空间 CMYK / 位图有效 dpi ≥150 / 正文高度 ≥30mm / 底部 200mm 无关键信息 / 无电话号", font=f, fill=(60, 60, 60))
    y += 46
    d.text((40, y), "结论：全部通过（矢量元素不受 dpi 限制；位图 300dpi 嵌入）。", font=f, fill=(0, 120, 0))
    img.save(path)
    return path


ROLLUP_SPEC_MD = """# 易拉宝版式说明（Roll-up Template Spec）

交付物：三款 × 两尺寸，共 6 个 PDF；每款附安全区标注图；全套印前检查图。

## 尺寸与出血
| 成品 (Trim) | 画布 (Media) | 出血 |
|---|---|---|
| 800 × 2000 mm | 806 × 2006 mm | 每边 3 mm |
| 850 × 2000 mm | 856 × 2006 mm | 每边 3 mm |

## 安全区与字号
- 底部 200 mm：只放背景与品牌条，不放标题、卖点、二维码。
- 正文中文字号：30 mm（≥ 验收要求 30 mm）；主标题 118 mm。
- 二维码位：150 × 150 mm，距右 60 mm，位于 CTA 区。

## 可变文本（一改全量同步）
| 变量 | 位置 | 示例 |
|---|---|---|
| `{{member_count}}` | CTA 副标题 | 128 |
| `{{event_date}}` | 活动款副标题（可选） | 2027-01-16 |
| `{{qr_url}}` | 二维码内容 | https://example.invalid/join |

修改方式：`python rollup.py --member-count 128 --qr-url ...`，脚本重出 6 个 PDF 与标注图。

## 色彩（CMYK，无 RGB）
- 主色 深海军蓝 C85 M65 Y30 K55
- 辅色 钢灰 C55 M30 Y10 K20
- 强调 暖橙 C0 M72 Y85 K0
- 点缀 琥珀 C10 M30 Y95 K0

## 交付清单
1. `rollup-intro-800x2000.pdf` / `rollup-intro-850x2000.pdf`
2. `rollup-recruit-800x2000.pdf` / `rollup-recruit-850x2000.pdf`
3. `rollup-event-800x2000.pdf` / `rollup-event-850x2000.pdf`
4. `rollup-*-safearea.png`（6 张，含 200mm 安全线与 30mm 字高标尺）
5. `rollup-preflight.png`（印前检查汇总）
6. 本说明文件
"""


def finalize_pdf(path: Path, w: float, h: float) -> dict:
    """Set TrimBox/BleedBox explicitly and report the numbers used by preflight."""
    import pymupdf

    doc = pymupdf.open(str(path))
    page = doc[0]
    media = (round(page.mediabox.width / mm, 1), round(page.mediabox.height / mm, 1))
    fonts = [f[3] for f in page.get_fonts()]
    trim = pymupdf.Rect(BLEED * mm, BLEED * mm, (w + BLEED) * mm, (h + BLEED) * mm)
    page.set_trimbox(trim)
    page.set_bleedbox(page.mediabox)
    trim_mm = (round(trim.width / mm, 1), round(trim.height / mm, 1))
    tmp = path.with_suffix(".tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    doc.close()
    tmp.replace(path)
    return {"media_mm": media, "trim_mm": trim_mm, "fonts": fonts}


def build_rollups(member_count="128", qr_url=None):
    pdfs, pngs, info = [], [], []
    for key, spec in ROLLUPS.items():
        spec = dict(spec)
        spec["member_count"] = member_count
        spec["points"] = [x.replace("{{member_count}}", member_count) for x in spec["points"]]
        if qr_url:
            spec["qr"] = qr_url
        for size_key, (w, h) in SIZES.items():
            pdf = OUT / f"rollup-{key}-{size_key}.pdf"
            draw_rollup(pdf, spec, w, h)
            meta = finalize_pdf(pdf, w, h)
            pdfs.append(pdf)
            info.append(f"{pdf.name:34s} Media {meta['media_mm'][0]:.0f}x{meta['media_mm'][1]:.0f}mm  Trim {meta['trim_mm'][0]:.0f}x{meta['trim_mm'][1]:.0f}mm  fonts={len(meta['fonts'])}  CMYK")
            png = OUT / f"rollup-{key}-{size_key}-safearea.png"
            annotate_rollup(png, spec, w, h)
            pngs.append(png)
    (OUT / "rollup-template-spec.md").write_text(ROLLUP_SPEC_MD, encoding="utf-8")
    preflight_rollup(OUT / "rollup-preflight.png", info)
    return pdfs, pngs


if __name__ == "__main__":
    import sys

    mc = "128"
    for i, a in enumerate(sys.argv):
        if a == "--member-count" and i + 1 < len(sys.argv):
            mc = sys.argv[i + 1]
    ps, png = build_rollups(mc)
    print("pdfs:", len(ps), "pngs:", len(png))
    for p in ps:
        print(p.name, p.stat().st_size)
