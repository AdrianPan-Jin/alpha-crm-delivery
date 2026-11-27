# -*- coding: utf-8 -*-
"""S4-BRAND-022 会员身份识别物料：会员证 / 胸牌 / 台卡 / 企业名牌

一份参数化脚本出全部稿件：
  * 会员证 85.5 × 54 mm（含 2 mm 出血），三档（金/银/普通）用「颜色 + 图形」双重区分
  * 胸牌 85.5 × 54 mm（挂绳孔位标注）
  * 台卡 100 × 150 mm（对折成型，含 3 mm 出血）
  * 企业名牌 200 × 80 mm（含 3 mm 出血）
  * 10 家虚构企业的批量样例（2 / 10 / 20 字名称各覆盖）

全部 CMYK、字体子集嵌入、TrimBox/BleedBox 正确，可直接送印。
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.colors import CMYKColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

MM = 72 / 25.4
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

INK = CMYKColor(0.92, 0.76, 0.42, 0.78)
INK_2 = CMYKColor(0.62, 0.36, 0.12, 0.22)
ACCENT = CMYKColor(0.00, 0.62, 0.86, 0.00)
ACCENT_2 = CMYKColor(0.02, 0.20, 0.72, 0.00)
PAPER = CMYKColor(0, 0, 0, 0)
MIST = CMYKColor(0.08, 0.04, 0.02, 0.00)
GOLD = CMYKColor(0.05, 0.18, 0.72, 0.06)
SILVER = CMYKColor(0.06, 0.03, 0.03, 0.12)

FONT_DIR = Path("C:/Windows/Fonts")
FONT_R, FONT_B = "YaHei", "YaHei-Bold"


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT_R, str(FONT_DIR / "msyh.ttc"), subfontIndex=0))
    pdfmetrics.registerFont(TTFont(FONT_B, str(FONT_DIR / "msyhbd.ttc"), subfontIndex=0))


def text(c, x, y, s, size, font=FONT_R, color=INK, align="l"):
    c.setFillColor(color)
    c.setFont(font, size)
    if align == "c":
        c.drawCentredString(x, y, s)
    elif align == "r":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def ctext(c, x, y, s, size, font=FONT_R, color=INK):
    text(c, x, y, s, size, font, color, "c")


def fit_size(s: str, width: float, base: float, min_size: float) -> float:
    """把字号缩到能放进 width 为止（不换行）。"""
    size = base
    while size > min_size and pdfmetrics.stringWidth(s, FONT_B, size) > width:
        size -= 0.5
    return size


def wrap_lines(s: str, size: float, width: float, font=FONT_B) -> list[str]:
    """按字符折行（中文无空格）。"""
    lines, cur = [], ""
    for ch in s:
        if pdfmetrics.stringWidth(cur + ch, font, size) <= width:
            cur += ch
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


@dataclass
class Tier:
    key: str
    name: str
    color: CMYKColor
    glyph: str      # 图形区分（不只靠颜色）
    motif: str


TIERS = [
    Tier("gold", "金卡", GOLD, "◆", "rings"),
    Tier("silver", "银卡", SILVER, "■", "grid"),
    Tier("standard", "标准卡", INK_2, "●", "dots"),
]


def _bleed_box(c, w, h, bleed):
    c.setFillColor(PAPER)
    c.rect(-bleed * MM, -bleed * MM, (w + 2 * bleed) * MM, (h + 2 * bleed) * MM, stroke=0, fill=1)


def _card_front(c, tier: Tier, company: str, member: str, title: str, w=85.5, h=54):
    """会员证正面：色带 + 图形母题 + 企业名自适应 2–20 字。"""
    _bleed_box(c, w, h, 2)
    c.setFillColor(INK)
    c.rect(0, 0, w * MM, h * MM, stroke=0, fill=1)
    # 顶部色带（颜色区分）
    c.setFillColor(tier.color)
    c.rect(0, (h - 7) * MM, w * MM, 7 * MM, stroke=0, fill=1)
    # 图形母题（图形区分，与颜色叠加）
    c.saveState()
    c.setFillColor(CMYKColor(tier.color.cyan, tier.color.magenta, tier.color.yellow, 0.55))
    if tier.motif == "rings":
        c.setStrokeColor(CMYKColor(tier.color.cyan, tier.color.magenta, tier.color.yellow, 0.55))
        c.setLineWidth(1.2)
        for r in (6.4, 4.0, 1.6):
            c.circle((w - 13) * MM, (h - 15) * MM, r * MM, stroke=1, fill=0)
    elif tier.motif == "grid":
        for gx in range(3):
            for gy in range(3):
                c.rect((w - 20 + gx * 5) * MM, (h - 24 + gy * 5) * MM, 3 * MM, 3 * MM, stroke=0, fill=1)
    else:
        for i in range(6):
            c.circle((w - 17 + (i % 3) * 5) * MM, (h - 22 + (i // 3) * 5) * MM, 1.3 * MM, stroke=0, fill=1)
    c.restoreState()

    text(c, 6 * MM, (h - 12) * MM, "MEMBER", 6, FONT_B, PAPER)
    text(c, 6 * MM, (h - 17.5) * MM, "会员空间平台", 6.5, FONT_R, PAPER)

    # 企业名：2–20 字自适应（先缩字号，缩到底仍超宽则折两行）
    size = fit_size(company, 52 * MM, 10, 6)
    lines = [company]
    if pdfmetrics.stringWidth(company, FONT_B, size) > 52 * MM:
        lines = wrap_lines(company, size, 52 * MM)
    y = 30 * MM if len(lines) == 1 else 33 * MM
    for ln in lines[:2]:
        text(c, 6 * MM, y, ln, size, FONT_B, PAPER)
        y -= size * 1.15

    text(c, 6 * MM, 12 * MM, f"{tier.glyph} {tier.name}", 6, FONT_B, tier.color)
    text(c, 6 * MM, 7.5 * MM, f"{member} · {title}", 6, FONT_R, MIST)
    # 卡号与二维码占位
    c.setStrokeColor(PAPER)
    c.setLineWidth(0.35)
    c.rect((w - 21) * MM, 5.5 * MM, 14 * MM, 14 * MM, stroke=1, fill=0)
    ctext(c, (w - 14) * MM, 11.2 * MM, "QR", 5, FONT_R, MIST)


def _card_back(c, tier: Tier, w=85.5, h=54):
    _bleed_box(c, w, h, 2)
    c.setFillColor(PAPER)
    c.rect(0, 0, w * MM, h * MM, stroke=0, fill=1)
    c.setFillColor(tier.color)
    c.rect(0, (h - 3) * MM, w * MM, 3 * MM, stroke=0, fill=1)
    text(c, 6 * MM, (h - 12) * MM, "使用说明", 7, FONT_B, INK)
    body = [
        "凭此卡参加会员空间平台的线下对接会、资源发布与培训。",
        "卡面信息由平台统一维护，遗失请通过企业管理员挂失并补办。",
        "本卡仅限本人使用，不得转借；二维码用于现场签到与身份核验。",
    ]
    y = (h - 20) * MM
    for ln in body:
        for seg in wrap_lines(ln, 6, 72 * MM, FONT_R):
            text(c, 6 * MM, y, seg, 6, FONT_R, INK_2)
            y -= 7
        y -= 1.5
    ctext(c, (w / 2) * MM, 5 * MM, "会员空间平台 · 资源对接 · 私域部署", 5, FONT_R, INK_2)


def _badge(c, tier: Tier, company: str, member: str, title: str):
    """胸牌：竖版 54 × 85.5 mm，顶部挂绳孔。"""
    w, h = 54, 85.5
    _bleed_box(c, w, h, 2)
    c.setFillColor(PAPER)
    c.rect(0, 0, w * MM, h * MM, stroke=0, fill=1)
    c.setFillColor(INK)
    c.rect(0, (h - 26) * MM, w * MM, 26 * MM, stroke=0, fill=1)
    c.setFillColor(tier.color)
    c.rect(0, (h - 26) * MM, w * MM, 2 * MM, stroke=0, fill=1)
    text(c, 6 * MM, (h - 9) * MM, "会员空间平台", 6, FONT_R, MIST)
    ctext(c, (w / 2) * MM, (h - 15) * MM, tier.name, 8, FONT_B, PAPER)
    ctext(c, (w / 2) * MM, (h - 20) * MM, f"{tier.glyph}  MEMBER", 5.5, FONT_R, tier.color)

    # 挂绳孔
    c.setStrokeColor(INK_2)
    c.setLineWidth(0.4)
    c.circle((w / 2) * MM, (h - 4) * MM, 1.6 * MM, stroke=1, fill=0)

    size = fit_size(company, 42 * MM, 11, 6)
    lines = [company] if pdfmetrics.stringWidth(company, FONT_B, size) <= 42 * MM else wrap_lines(company, size, 42 * MM)
    y = (h - 36) * MM
    for ln in lines[:2]:
        ctext(c, (w / 2) * MM, y, ln, size, FONT_B, INK)
        y -= size * 1.2
    ctext(c, (w / 2) * MM, (h - 52) * MM, member, 8, FONT_B, INK_2)
    ctext(c, (w / 2) * MM, (h - 58) * MM, title, 6.5, FONT_R, INK_2)
    c.setStrokeColor(MIST)
    c.setLineWidth(0.3)
    c.rect(8 * MM, 8 * MM, w * MM - 16 * MM, 12 * MM, stroke=1, fill=0)
    ctext(c, (w / 2) * MM, 12.5 * MM, "现场签到二维码位", 5, FONT_R, INK_2)


def _table_tent(c, company: str, tier: Tier, w=100, h=150):
    """台卡（对折成型）：展开 100 × 150，上下各 75 mm 为两个展示面。"""
    _bleed_box(c, w, h, 3)
    c.setFillColor(PAPER)
    c.rect(0, 0, w * MM, h * MM, stroke=0, fill=1)
    # 上半（展示面 A）
    c.setFillColor(INK)
    c.rect(0, 75 * MM, w * MM, 75 * MM, stroke=0, fill=1)
    c.setFillColor(tier.color)
    c.rect(0, 142 * MM, w * MM, 8 * MM, stroke=0, fill=1)
    ctext(c, (w / 2) * MM, 130 * MM, "会员空间平台", 6.5, FONT_R, MIST)
    size = fit_size(company, 80 * MM, 16, 8)
    lines = [company] if pdfmetrics.stringWidth(company, FONT_B, size) <= 80 * MM else wrap_lines(company, size, 80 * MM)
    y = 108 * MM
    for ln in lines[:2]:
        ctext(c, (w / 2) * MM, y, ln, size, FONT_B, PAPER)
        y -= size * 1.25
    ctext(c, (w / 2) * MM, 90 * MM, f"{tier.glyph} {tier.name}会员", 7, FONT_R, tier.color)
    ctext(c, (w / 2) * MM, 82 * MM, "扫码查看企业名片", 5.5, FONT_R, MIST)
    # 折线
    c.setStrokeColor(MIST)
    c.setLineWidth(0.4)
    c.setDash(3, 2)
    c.line(0, 75 * MM, w * MM, 75 * MM)
    c.setDash()
    # 下半（展示面 B）：对折后朝向另一侧观众，故在本张纸上旋转 180° 印刷
    c.saveState()
    c.translate(0, 75 * MM)
    c.rotate(180)
    ctext(c, (w / 2) * MM, 40 * MM, "会员空间平台", 7, FONT_B, INK)
    ctext(c, (w / 2) * MM, 32 * MM, "资源对接 · 私域部署 · 企业会员服务", 5.5, FONT_R, INK_2)
    c.setStrokeColor(MIST)
    c.setLineWidth(0.3)
    c.rect(35 * MM, 8 * MM, 30 * MM, 14 * MM, stroke=1, fill=0)
    ctext(c, (w / 2) * MM, 13 * MM, "二维码位", 5, FONT_R, INK_2)
    c.restoreState()


def _plaque(c, company: str, tier: Tier, w=200, h=80):
    """企业名牌：铝板/亚克力 200 × 80 mm。"""
    _bleed_box(c, w, h, 3)
    c.setFillColor(INK)
    c.rect(0, 0, w * MM, h * MM, stroke=0, fill=1)
    c.setFillColor(tier.color)
    c.rect(0, 0, 6 * MM, h * MM, stroke=0, fill=1)
    text(c, 14 * MM, 58 * MM, "MEMBER SPACE PLATFORM", 6, FONT_R, MIST)
    size = fit_size(company, 150 * MM, 22, 10)
    lines = [company] if pdfmetrics.stringWidth(company, FONT_B, size) <= 150 * MM else wrap_lines(company, size, 150 * MM)
    y = 38 * MM if len(lines) == 1 else 44 * MM
    for ln in lines[:2]:
        text(c, 14 * MM, y, ln, size, FONT_B, PAPER)
        y -= size * 1.2
    text(c, 14 * MM, 12 * MM, f"{tier.glyph} {tier.name}会员企业 · 编号 MS-0001", 7, FONT_R, tier.color)


COMPANIES = [
    ("韧行", "李倩", "设计顾问"),
    ("成都天府文创投资集团", "赵磊", "文创投资"),
    ("上海临港智能装备制造产业协同创新中心有限", "王海涛", "智能制造"),
    ("杭州云栖数据科技有限公司", "张明", "数据中台"),
    ("苏州恒远供应链管理", "陈曦", "供应链"),
    ("宁波港联国际物流", "孙悦", "物流"),
    ("北京中关村医疗器械创新联盟", "钱峰", "医疗器械"),
    ("深圳前海跨境数字营销", "刘洋", "跨境营销"),
    ("甬城智能装备研究院", "周敏", "工业软件"),
    ("鹿鸣文化传播工作室", "吴迪", "内容运营"),
]


def build() -> list[str]:
    register_fonts()
    made = []
    OUT.mkdir(exist_ok=True)

    def new_canvas(name: str, w: float, h: float, bleed: float):
        path = OUT / name
        c = canvas.Canvas(str(path), pagesize=((w + 2 * bleed) * MM, (h + 2 * bleed) * MM))
        c.translate(bleed * MM, bleed * MM)
        return path, c

    def next_page(c, bleed: float):
        c.showPage()
        c.translate(bleed * MM, bleed * MM)

    for tier in TIERS:
        path, c = new_canvas(f"card-{tier.key}-front.pdf", 85.5, 54, 2)
        for company, member, title in COMPANIES[:3]:
            _card_front(c, tier, company, member, title)
            next_page(c, 2)
        c.save()
        made.append(str(path))

        path, c = new_canvas(f"card-{tier.key}-back.pdf", 85.5, 54, 2)
        _card_back(c, tier)
        c.save()
        made.append(str(path))

        path, c = new_canvas(f"badge-{tier.key}.pdf", 54, 85.5, 2)
        for company, member, title in COMPANIES[:2]:
            _badge(c, tier, company, member, title)
            next_page(c, 2)
        c.save()
        made.append(str(path))

        path, c = new_canvas(f"table-tent-{tier.key}.pdf", 100, 150, 3)
        for company, _, _ in COMPANIES[:2]:
            _table_tent(c, company, tier)
            next_page(c, 3)
        c.save()
        made.append(str(path))

        path, c = new_canvas(f"plaque-{tier.key}.pdf", 200, 80, 3)
        for company, _, _ in COMPANIES:
            _plaque(c, company, tier)
            next_page(c, 3)
        c.save()
        made.append(str(path))
    return made


def finalize(pdf: Path, bleed_mm: float) -> None:
    """设置 TrimBox = 页面内缩 bleed；BleedBox = 页面本身。"""
    import pymupdf

    doc = pymupdf.open(pdf)
    for page in doc:
        r = page.rect
        trim = pymupdf.Rect(r.x0 + bleed_mm * MM, r.y0 + bleed_mm * MM, r.x1 - bleed_mm * MM, r.y1 - bleed_mm * MM)
        page.set_trimbox(trim)
        page.set_bleedbox(r)
    doc.saveIncr()
    doc.close()


if __name__ == "__main__":
    files = build()
    for f in files:
        finalize(Path(f), 3)
    # 会员证与胸牌是 2mm 出血，单独修正
    for f in files:
        if "/card-" in f.replace("\\", "/") or "/badge-" in f.replace("\\", "/"):
            finalize(Path(f), 2)
    print(json.dumps({"files": len(files), "out": str(OUT)}, ensure_ascii=False))
