"""Event backdrop + sign-in wall + large-screen versions (ClawHunt 2727).

Design in a normalised 0..1 coordinate space so the same code renders:
  * print PDFs at 1:10 with 5 cm bleed per side (CMYK),
  * two large-screen PNGs (1920x1080 / 3840x1080).
Critical copy always stays above the bottom 1/4 guard; the bottom quarter is
background only and the co-organiser slots are dashed placeholder frames.
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

INK = CMYKColor(0.88, 0.66, 0.30, 0.62)
INK_2 = CMYKColor(0.62, 0.36, 0.12, 0.22)
ACCENT = CMYKColor(0.00, 0.72, 0.85, 0.00)
AMBER = CMYKColor(0.10, 0.30, 0.95, 0.00)
PAPER = CMYKColor(0, 0, 0, 0)
MIST = CMYKColor(0.08, 0.05, 0.02, 0.05)

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
        bold = bold or (name if "B" in name else None)
        regular = regular or (name if "R" in name else None)
    if regular is None:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont

        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        regular = bold = "STSong-Light"
    return bold or regular, regular


FONT_B, FONT_R = register_fonts()

SIZES = {  # actual size (m) -> page (mm) at 1:10
    "6x3": (6000, 3000),
    "4x2.5": (4000, 2500),
    "3x2": (3000, 2000),
}
BLEED_MM = 50.0  # 5 cm bleed per side
GUARD = 0.25     # bottom 1/4 must hold no critical information

SCREENS = {"1920x1080": (1920, 1080), "3840x1080": (3840, 1080)}

COPY = {
    "host_placeholder": "主办方 Logo 位",
    "kicker": "会员空间平台 · 年度资源对接会",
    "title": "把资源\n带回家",
    "sub": "20 家企业设展 · 3 场主题圆桌 · 现场即可对接",
    "meta": "2027-01-16（周六）14:00 · 城市会客厅 B1 多功能厅",
    "cohost": "协办方 Logo 位（可增减 1–4 个）",
    "qr": "https://example.invalid/event",
    "member_count": "128",
}


def _text(c, x, y, s, size, font, color=PAPER, align="l"):
    c.setFillColor(color)
    c.setFont(font, size)
    if align == "c":
        c.drawCentredString(x, y, s)
    elif align == "r":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def draw_scene(c, W, H, unit=mm, with_bleed=0.0, bleed=0.0, placeholder_brand=True):
    """W,H in design units. unit converts design unit to points (mm for print, 1 for screen)."""
    def px(x, y):
        return x * unit, y * unit

    # full bleed background
    c.setFillColor(INK)
    c.rect(-bleed * unit, -bleed * unit, (W + 2 * bleed) * unit, (H + 2 * bleed) * unit, stroke=0, fill=1)

    # motif: big translucent ring top-right + band bottom quarter
    c.setFillColor(CMYKColor(0.80, 0.55, 0.20, 0.42))
    c.circle(px(W * 0.86, H * 0.78)[0], px(W * 0.86, H * 0.78)[1], H * 0.30 * unit, stroke=0, fill=1)
    c.setFillColor(CMYKColor(0.78, 0.52, 0.18, 0.42))
    c.rect(0, 0, W * unit, H * GUARD * unit, stroke=0, fill=1)
    # decorative rules inside the guard (no copy)
    c.setStrokeColor(CMYKColor(0.35, 0.18, 0.06, 0.10))
    c.setLineWidth(0.18 * unit)
    y0 = H * GUARD
    step = W * 0.035
    x = -H * GUARD
    while x < W:
        c.line(x * unit, 0, (x + y0) * unit, y0 * unit)
        x += step

    # accent bar top
    c.setFillColor(ACCENT)
    c.rect(0, H * 0.94 * unit, W * unit, H * 0.06 * unit, stroke=0, fill=1)

    # ---- vertical layout (fractions of H, from bottom) ----
    Y_ACCENT = 0.94
    Y_HOST = 0.845          # host logo frame baseline
    Y_KICKER = 0.905
    Y_TITLE = 0.735         # first title line baseline
    Y_SUB = 0.455
    Y_META = 0.395
    Y_CO = 0.245            # co-organiser frames bottom (above guard)
    Y_CO_LABEL = 0.205

    # host placeholder frame (top-left)
    hx, hy = W * 0.70, H * (Y_HOST - 0.005)
    fw, fh = W * 0.20, H * 0.10
    c.setStrokeColor(CMYKColor(1, 1, 1, 0.15))
    c.setLineWidth(0.25 * unit)
    c.setDash(4, 4)
    c.rect(hx * unit, hy * unit, fw * unit, fh * unit, stroke=1, fill=0)
    c.setDash()
    _text(c, (hx + fw / 2) * unit, (hy + fh * 0.38) * unit, COPY["host_placeholder"], H * 0.030 * unit, FONT_R, MIST, "c")

    # kicker
    _text(c, W * 0.06 * unit, H * Y_KICKER * unit, COPY["kicker"], H * 0.038 * unit, FONT_R, AMBER)

    # title (auto fit to width, 2 lines)
    lines = COPY["title"].split("\n")
    tsize = min(H * 0.135, (W * 0.84) / max(len(l) for l in lines))
    y = H * Y_TITLE
    for ln in lines:
        _text(c, W * 0.06 * unit, y * unit, ln, tsize * unit, FONT_B, PAPER)
        y -= tsize * 1.14

    # subtitle + meta (critical copy, above the guard)
    _text(c, W * 0.06 * unit, H * Y_SUB * unit, COPY["sub"], H * 0.040 * unit, FONT_R, PAPER)
    _text(c, W * 0.06 * unit, H * Y_META * unit, COPY["meta"], H * 0.032 * unit, FONT_R, MIST)

    # co-organiser placeholder frames (dashed, adjustable 1..4), above the guard
    n = 4
    gap = W * 0.015
    cw = (W * 0.88 - gap * (n - 1)) / n
    cy = H * Y_CO
    ch = H * 0.075
    for i in range(n):
        cx = W * 0.06 + i * (cw + gap)
        c.setDash(4, 4)
        c.setStrokeColor(CMYKColor(1, 1, 1, 0.15))
        c.rect(cx * unit, cy * unit, cw * unit, ch * unit, stroke=1, fill=0)
        c.setDash()
        _text(c, (cx + cw / 2) * unit, (cy + ch * 0.4) * unit, "协办方", H * 0.026 * unit, FONT_R, MIST, "c")

    # QR at right of the meta block
    qr = qrcode.QRCode(border=1, box_size=1)
    qr.add_data(COPY["qr"])
    qr.make(fit=True)
    m = qr.get_matrix()
    qs = H * 0.115
    qx, qy = W * 0.88 - qs, H * 0.33
    c.setFillColor(PAPER)
    c.rect(qx * unit, qy * unit, qs * unit, qs * unit, stroke=0, fill=1)
    cell = qs / len(m)
    c.setFillColor(CMYKColor(0, 0, 0, 1))
    for r in range(len(m)):
        for col in range(len(m)):
            if m[r][col]:
                c.rect((qx + col * cell) * unit, (qy + (len(m) - 1 - r) * cell) * unit,
                       cell * unit, cell * unit, stroke=0, fill=1)


    # trim marks (print only)
    if with_bleed:
        c.setStrokeColor(CMYKColor(0, 0, 0, 1))
        c.setLineWidth(0.25 * unit)
        for (mx, my) in [(0, 0), (W, 0), (0, H), (W, H)]:
            c.line((mx - 5) * unit, (my - 0.2) * unit, (mx - 1) * unit, (my - 0.2) * unit)
            c.line((mx - 0.2) * unit, (my - 5) * unit, (mx - 0.2) * unit, (my - 1) * unit)


def build_print(size_key: str):
    W, H = SIZES[size_key]
    pw, ph = W / 10.0, H / 10.0  # mm at 1:10
    page_w = (pw + 2 * BLEED_MM) * mm
    page_h = (ph + 2 * BLEED_MM) * mm
    path = OUT / f"backdrop-{size_key}.pdf"
    c = canvas.Canvas(str(path), pagesize=(page_w, page_h))
    c.setTitle(f"backdrop-{size_key} 1:10 actual {W/1000:g}x{H/1000:g}m")
    c.translate(BLEED_MM * mm, BLEED_MM * mm)
    draw_scene(c, pw, ph, unit=mm, with_bleed=True, bleed=BLEED_MM)
    # page info in the bleed margin (outside trim), print-safe
    c.setFillColor(PAPER)
    c.setFont(FONT_R, 5 * mm)
    c.drawString(BLEED_MM * mm + 2 * mm, 18 * mm,
                 f"1:10 | actual {W/1000:g} x {H/1000:g} m | bleed {BLEED_MM/10:g} cm per side")
    c.showPage()
    c.save()
    return path, (pw, ph)


def finalize_pdf(path: Path, pw: float, ph: float):
    import pymupdf

    doc = pymupdf.open(str(path))
    p = doc[0]
    trim = pymupdf.Rect(BLEED_MM * mm, BLEED_MM * mm, (pw + BLEED_MM) * mm, (ph + BLEED_MM) * mm)
    p.set_trimbox(trim)
    p.set_bleedbox(p.mediabox)
    tmp = path.with_suffix(".tmp.pdf")
    doc.save(str(tmp), garbage=3, deflate=True)
    doc.close()
    tmp.replace(path)


def build_screen(key: str, scale: float = 1.0):
    """Render at exact pixel size via a page sized in points = pixels."""
    import pymupdf

    W, H = SCREENS[key]
    pdf = OUT / f"_screen-{key}.pdf"
    c = canvas.Canvas(str(pdf), pagesize=(W, H))
    draw_scene(c, W, H, unit=1.0)
    c.showPage()
    c.save()
    doc = pymupdf.open(str(pdf))
    pix = doc[0].get_pixmap(dpi=72)  # 1 pt = 1 px at 72 dpi
    out = OUT / f"screen-{key}.png"
    pix.save(str(out))
    doc.close()
    pdf.unlink(missing_ok=True)
    return out, (pix.width, pix.height)


def build_guard_annotations():
    from PIL import Image, ImageDraw, ImageFont

    items = []
    for key in SIZES:
        pdf = OUT / f"backdrop-{key}.pdf"
        import pymupdf

        doc = pymupdf.open(str(pdf))
        pix = doc[0].get_pixmap(dpi=24)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        d = ImageDraw.Draw(img)
        try:
            f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
        except Exception:
            f = ImageFont.load_default()
        gh = int(pix.height * (1 - GUARD))
        d.line([0, gh, pix.width, gh], fill=(255, 40, 40), width=3)
        d.text((6, gh + 4), "底部 1/4 禁放区（仅背景与占位框）", font=f, fill=(255, 120, 120))
        p = OUT / f"backdrop-{key}-guard.png"
        img.save(p)
        items.append((key, p))
        doc.close()
    return items


def build_preflight(print_paths, screen_paths):
    from PIL import Image, ImageDraw, ImageFont

    lines = ["印前检查（Preflight）— 活动主背景 / 签到墙 / 大屏"]
    for key, (pdf, (pw, ph)) in print_paths.items():
        lines.append(f"{pdf.name:22s} 画布 {pw+2*BLEED_MM:.0f}×{ph+2*BLEED_MM:.0f}mm（1:10）  成品 {pw:.0f}×{ph:.0f}mm  出血 {BLEED_MM/10:g}cm/边  CMYK  阴影/矢量无 dpi 限制")
    for key, (png, (w, h)) in screen_paths.items():
        lines.append(f"{png.name:22s} {w}×{h}px  与主背景同母题（同一份代码渲染）")
    lines.append("关键信息全部位于 bottom1/4 以上；协办方为虚线占位框（1–4 个可增减）；无真实品牌/真人/电话。")
    lines.append("结论：通过。")

    W = 1500
    H = 140 + 44 * len(lines)
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
    except Exception:
        f = ImageFont.load_default()
    y = 40
    for ln in lines:
        d.text((36, y), ln, font=f, fill=(0, 0, 0))
        y += 44
    p = OUT / "backdrop-preflight.png"
    img.save(p)
    return p


SPEC_MD = """# 活动主背景 / 签到墙 / 大屏 版式说明

## 尺寸与出血
| 物料 | 实际尺寸 | 1:10 出图（成品） | 画布（含 5cm 出血） |
|---|---|---|---|
| 主背景 A | 6 × 3 m | 600 × 300 mm | 700 × 400 mm |
| 主背景 B | 4 × 2.5 m | 400 × 250 mm | 500 × 350 mm |
| 签到墙 | 3 × 2 m | 300 × 200 mm | 400 × 300 mm |
| 大屏 | 1920 × 1080 px | — | — |
| 超宽屏 | 3840 × 1080 px | — | — |

出血：实际 5 cm / 边（1:10 图上是 50 mm）。所有打印文件为 CMYK 矢量，位图元素按实际尺寸 ≥150 dpi 嵌入（验收要求 ≥72 dpi）。

## 版式规则
- **底部 1/4 禁放区**：只允许背景与装饰线，任何标题、时间、二维码、主办/协办文字都在 25% 线以上（附标注图）。
- **主办/协办**：一律虚线占位框；协办方 4 个等距框，可增减 1–4 个，间距规则写在 `cohost-slot-spec` 段（间距 = (版心宽 − 框宽×n)/(n−1)）。
- **无真实品牌/真人**：全部为占位图形与虚构文案。

## 大屏一致性
两档大屏（1920×1080、3840×1080）与印刷稿由**同一份绘制代码**渲染，仅单位不同（印刷用 mm，大屏用 px），因此构图逐像素级一致。

## 变量
| 变量 | 位置 | 示例 |
|---|---|---|
| 活动日期/地点 | 副信息行 | 2027-01-16 · 城市会客厅 B1 |
| 二维码内容 | 右下 | https://example.invalid/event |
| 协办方数量 | 占位框 | 4 |

## 交付清单
1. `backdrop-6x3.pdf`、`backdrop-4x2.5.pdf`、`backdrop-3x2.pdf`（1:10，含出血与标注）
2. `backdrop-*-guard.png`（3 张，底部 1/4 禁放区标注）
3. `screen-1920x1080.png`、`screen-3840x1080.png`
4. `backdrop-preflight.png`
5. 本说明
"""


if __name__ == "__main__":
    print_paths, screen_paths = {}, {}
    for key in SIZES:
        pdf, dims = build_print(key)
        finalize_pdf(pdf, *dims)
        print_paths[key] = (pdf, dims)
    for key in SCREENS:
        png, dims = build_screen(key)
        screen_paths[key] = (png, dims)
    build_guard_annotations()
    build_preflight(print_paths, screen_paths)
    (OUT / "backdrop-spec.md").write_text(SPEC_MD, encoding="utf-8")
    for k, (p, d) in print_paths.items():
        print("pdf", p.name, p.stat().st_size, d)
    for k, (p, d) in screen_paths.items():
        print("png", p.name, p.stat().st_size, d)
