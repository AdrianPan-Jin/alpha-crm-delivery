# -*- coding: utf-8 -*-
"""S4-BRAND-026 楼层导视 + 模块化会员企业名录墙

交付：
  * wall-floor.pdf / wall-industry.pdf / wall-pinyin.pdf  三种排布方案的 A0 版式图（1189×841 mm）
  * plate-templates.pdf   单块名牌模板（含替换示意与滑轨说明）
  * directory-landscape.pdf / directory-portrait.pdf  电子名录（每页 ≤20 家，横/竖版分页轮播）
  * names.csv             100 家虚构企业（2–20 字，含楼层/行业/首字母）
全部虚构名称、无真实楼宇与地址；所有版面由参数化脚本生成。
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from reportlab.lib.colors import CMYKColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

MM = 72 / 25.4
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

INK = CMYKColor(0.92, 0.76, 0.42, 0.78)
INK_2 = CMYKColor(0.62, 0.36, 0.12, 0.22)
ACCENT = CMYKColor(0.00, 0.62, 0.86, 0.00)
PAPER = CMYKColor(0, 0, 0, 0)
MIST = CMYKColor(0.08, 0.04, 0.02, 0.00)
LINE = CMYKColor(0.30, 0.18, 0.10, 0.10)

FONT_R, FONT_B = "YaHei", "YaHei-Bold"
FONT_DIR = Path("C:/Windows/Fonts")

# 名录墙：10 × 10 网格；80 个已用位 + 20 个预留扩展位（20%）
COLS = ROWS = 10
PLATE_W, PLATE_H = 108.0, 62.0     # mm，含可视缝
GAP = 2.0
WALL_W, WALL_H = 1189.0, 841.0     # A0 横

FLOORS = ["1F", "2F", "3F", "5F", "8F"]
INDUSTRIES = ["数据与软件", "智能制造", "文创与投资", "供应链物流", "医疗健康", "金融服务", "教育培训", "能源环保"]


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont(FONT_R, str(FONT_DIR / "msyh.ttc"), subfontIndex=0))
    pdfmetrics.registerFont(TTFont(FONT_B, str(FONT_DIR / "msyhbd.ttc"), subfontIndex=0))


def fit(s: str, width: float, base: float, min_size: float, font=FONT_B) -> float:
    size = base
    while size > min_size and pdfmetrics.stringWidth(s, font, size) > width:
        size -= 0.5
    return size


def wrap(s: str, size: float, width: float, font=FONT_B) -> list[str]:
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


def name_layout(name: str, width: float, height: float) -> tuple[float, list[str]]:
    """返回 (字号, 行列表)：先缩字号，缩到 7pt 仍超宽则折行（最多 2 行，超出用省略号）。"""
    size = fit(name, width, 13, 7)
    if pdfmetrics.stringWidth(name, FONT_B, size) <= width:
        return size, [name]
    size = max(7.0, fit(name[:8] + "…", width, 11, 7))
    lines = wrap(name, size, width)
    if len(lines) > 2:
        lines = [lines[0], lines[1][: max(1, len(lines[1]) - 1)] + "…"]
    return size, lines


def text(c, x, y, s, size, font=FONT_R, color=INK, align="l"):
    c.setFillColor(color)
    c.setFont(font, size)
    if align == "c":
        c.drawCentredString(x, y, s)
    elif align == "r":
        c.drawRightString(x, y, s)
    else:
        c.drawString(x, y, s)


def make_names(seed: int = 42) -> list[dict]:
    rnd = random.Random(seed)
    prefix = ["杭州", "上海", "深圳", "苏州", "宁波", "成都", "北京", "南京", "合肥", "武汉"]
    core = ["云栖", "临港", "前海", "恒远", "港联", "天府", "中关村", "甬城", "鹿鸣", "栖木", "青岚", "澄海"]
    suffix = ["数据科技", "智能装备", "文创投资", "供应链管理", "国际物流", "医疗器械", "金融服务", "教育科技", "环保工程", "文化传播"]
    tail = ["有限公司", "集团", "研究院", "工作室", "中心", "合伙企业"]
    out = []
    for i in range(100):
        style = i % 5
        if style == 0:          # 2 字
            nm = rnd.choice(["韧行", "光屿", "青棠", "白鹭", "知微"])
        elif style == 1:        # 6–10 字
            nm = rnd.choice(prefix) + rnd.choice(core) + rnd.choice(suffix)
        elif style == 2:        # 11–16 字
            nm = rnd.choice(prefix) + rnd.choice(core) + rnd.choice(suffix) + rnd.choice(["", "有限"]) + rnd.choice(tail)
        elif style == 3:        # 17–20 字
            nm = (rnd.choice(prefix) + rnd.choice(["临港新片区", "高新区", "经济技术开发区"]) +
                  rnd.choice(core) + rnd.choice(suffix) + rnd.choice(["产业协同创新", "数字技术应用"]) + rnd.choice(["中心", "研究院"]))
        else:                   # 短名 + 工作室
            nm = rnd.choice(core) + rnd.choice(["文化", "设计", "咨询"]) + "工作室"
        if len(nm) > 20:
            nm = nm[:20]
        out.append({
            "id": i + 1,
            "name": nm,
            "chars": len(nm),
            "floor": FLOORS[i % len(FLOORS)],
            "industry": INDUSTRIES[(i // 3) % len(INDUSTRIES)],
            "initial": nm[0],
        })
    return out


def draw_plate(c, x, y, w, h, item: dict | None, idx: str, theme: CMYKColor):
    if item is None:      # 预留扩展位
        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        c.setDash(2, 1.6)
        c.rect(x, y, w, h, stroke=1, fill=0)
        c.setDash()
        text(c, x + w / 2, y + h / 2 - 2.5, "预留扩展位", 7, FONT_R, LINE, "c")
        text(c, x + w / 2, y + h / 2 - 9, idx, 5.5, FONT_R, LINE, "c")
        return
    c.setFillColor(MIST)
    c.rect(x, y, w, h, stroke=0, fill=1)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.25)
    c.rect(x, y, w, h, stroke=1, fill=0)
    c.setFillColor(theme)
    c.rect(x, y, 3.2, h, stroke=0, fill=1)
    size, lines = name_layout(item["name"], (w - 16), h - 24)
    block_h = size * 1.15 * len(lines)
    ty = y + (h + block_h) / 2 - size * 0.85
    for ln in lines:
        text(c, x + 8, ty, ln, size, FONT_B, INK)
        ty -= size * 1.15
    text(c, x + 8, y + 6, f"{item['floor']} · {item['industry']}", 6, FONT_R, INK_2)
    text(c, x + w - 5, y + 6, idx, 5.5, FONT_R, LINE, "r")


def wall(page_title: str, subtitle: str, items: list[dict], theme: CMYKColor, path: Path, order: str):
    c = canvas.Canvas(str(path), pagesize=(WALL_W * MM, WALL_H * MM))
    c.setFillColor(PAPER)
    c.rect(0, 0, WALL_W * MM, WALL_H * MM, stroke=0, fill=1)
    # 顶部
    c.setFillColor(INK)
    c.rect(0, (WALL_H - 92) * MM, WALL_W * MM, 92 * MM, stroke=0, fill=1)
    c.setFillColor(theme)
    c.rect(0, (WALL_H - 92) * MM, WALL_W * MM, 6 * MM, stroke=0, fill=1)
    text(c, 24 * MM, (WALL_H - 40) * MM, page_title, 26, FONT_B, PAPER)
    text(c, 24 * MM, (WALL_H - 56) * MM, subtitle, 10, FONT_R, MIST)
    text(c, (WALL_W - 24) * MM, (WALL_H - 40) * MM, "MEMBER DIRECTORY · 会员企业名录", 8, FONT_R, MIST, "r")
    text(c, (WALL_W - 24) * MM, (WALL_H - 52) * MM, "10×10 模块化网格 · 20% 预留扩展 · 单块可替换", 6.5, FONT_R, MIST, "r")

    # 网格区域
    grid_w = COLS * PLATE_W + (COLS - 1) * GAP
    grid_h = ROWS * PLATE_H + (ROWS - 1) * GAP
    x0 = (WALL_W - grid_w) / 2
    y0 = 70.0
    letters = "ABCDEFGHIJ"
    used = items[:80]
    pool = items[80:]
    k = 0
    for r in range(ROWS):
        for col in range(COLS):
            x = (x0 + col * (PLATE_W + GAP)) * MM
            y = (y0 + (ROWS - 1 - r) * (PLATE_H + GAP)) * MM
            idx = f"{letters[col]}{r + 1}"
            slot = None
            if r * COLS + col < 80:
                slot = used[r * COLS + col] if r * COLS + col < len(used) else None
            draw_plate(c, x, y, PLATE_W * MM, PLATE_H * MM, slot, idx, theme)
            k += 1
    # 底部说明
    text(c, 24 * MM, 40 * MM, f"排布方案：{order}", 9, FONT_B, INK)
    text(c, 24 * MM, 30 * MM, "编号规则：列字母 A–J + 行号 1–10（左下为 A1），编号与电子名录、替换记录一一对应。", 7, FONT_R, INK_2)
    text(c, 24 * MM, 22 * MM, "20% 预留：每 5 个连续位保留 1 个扩展位（图中虚线框），新会员按最近空位顺序占位，不重排既有名牌。", 7, FONT_R, INK_2)
    text(c, (WALL_W - 24) * MM, 30 * MM, "尺寸：A0 横版 1189×841 mm ｜ 单块名牌 108×62 mm（可视）｜ 建议材质 2 mm 拉丝铝板 + UV 打印", 7, FONT_R, INK_2, "r")
    c.save()


def plate_templates(items: list[dict], path: Path):
    c = canvas.Canvas(str(path), pagesize=(WALL_W * MM, WALL_H * MM))
    c.setFillColor(PAPER)
    c.rect(0, 0, WALL_W * MM, WALL_H * MM, stroke=0, fill=1)
    text(c, 24 * MM, (WALL_H - 40) * MM, "单块名牌模板与替换示意", 24, FONT_B, INK)
    text(c, 24 * MM, (WALL_H - 54) * MM, "单块 108×62 mm；背板预留 110×64 mm 卡槽，名牌从上方滑入，正面无螺钉", 9, FONT_R, INK_2)

    # 模板三例：2 字 / 10 字 / 20 字
    samples = [items[0], items[1], items[2]]
    labels = ["2 字名称", "10 字左右名称", "20 字极限名称"]
    for i, (it, lab) in enumerate(zip(samples, labels)):
        bx = 24 + i * 150
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.rect(bx * MM, (WALL_H - 196) * MM, 110 * MM, 64 * MM, stroke=1, fill=0)
        draw_plate(c, (bx + 1) * MM, (WALL_H - 195) * MM, 108 * MM, 62 * MM, it, f"{'ABC'[i]}1", INK_2)
        text(c, bx * MM, (WALL_H - 210) * MM, lab, 7.5, FONT_R, INK_2)

    # 替换示意
    y = 520
    text(c, 24 * MM, y * MM, "替换流程（单块可独立更换，不影响相邻名牌）", 12, FONT_B, INK)
    steps = [
        "1. 用吸盘或塑料撬片沿名牌上沿轻推 2–3 mm，向上滑出旧名牌（卡槽内无胶）。",
        "2. 新名牌按 A1–J10 编号对位，沿卡槽自上而下插入到底。",
        "3. 更新电子名录对应页（目录页与实体编号共用同一编号），并在替换记录表登记日期与经办人。",
        "4. 旧名牌按编号归档，便于二次使用或恢复。",
    ]
    yy = y - 12
    for s in steps:
        text(c, 24 * MM, yy * MM, s, 8, FONT_R, INK_2)
        yy -= 9
    # 剖面示意
    c.setStrokeColor(INK_2)
    c.setLineWidth(0.6)
    c.rect(24 * MM, 330 * MM, 200 * MM, 60 * MM, stroke=1, fill=0)
    text(c, 30 * MM, 372 * MM, "剖面示意：背板 10 mm 铝型材 + 3 mm 卡槽", 8, FONT_B, INK)
    for i in range(5):
        c.line((30 + i * 38) * MM, 340 * MM, (30 + i * 38) * MM, 360 * MM)
    text(c, 24 * MM, 316 * MM, "尺寸公差：卡槽比名牌大 1.5 mm；建议名牌四角 R2 圆角，避免刮手。", 7, FONT_R, INK_2)
    c.save()


def directory_pages(items: list[dict], path: Path, w: float, h: float, per_page: int = 20):
    c = canvas.Canvas(str(path), pagesize=(w * MM, h * MM))
    letters = "ABCDEFGHIJ"
    pages = [items[i:i + per_page] for i in range(0, len(items), per_page)]
    total = len(pages)
    for pi, page in enumerate(pages, 1):
        c.setFillColor(PAPER)
        c.rect(0, 0, w * MM, h * MM, stroke=0, fill=1)
        c.setFillColor(INK)
        c.rect(0, (h - 46) * MM, w * MM, 46 * MM, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(0, (h - 46) * MM, w * MM, 3 * MM, stroke=0, fill=1)
        text(c, 14 * MM, (h - 24) * MM, "会员企业名录", 16, FONT_B, PAPER)
        text(c, (w - 14) * MM, (h - 22) * MM, f"第 {pi} / {total} 页", 9, FONT_R, MIST, "r")
        text(c, (w - 14) * MM, (h - 31) * MM, f"本页 {len(page)} 家 · 每页不超过 20 家 · 15 秒自动轮播", 6.5, FONT_R, MIST, "r")

        cols = 2 if w > h else 1
        rows_per_col = (per_page + cols - 1) // cols
        col_w = (w - 28) / cols
        row_h = (h - 96) / rows_per_col
        for i, it in enumerate(page):
            col = i // rows_per_col
            row = i % rows_per_col
            x = 14 + col * col_w
            y = h - 62 - (row + 1) * row_h
            c.setStrokeColor(LINE)
            c.setLineWidth(0.3)
            c.line(x * MM, (y + row_h * 0.18) * MM, (x + col_w - 10) * MM, (y + row_h * 0.18) * MM)
            size, lines = name_layout(it["name"], (col_w - 34) * MM, row_h * MM - 6)
            ty = (y + row_h * 0.55)
            for ln in lines:
                text(c, (x + 2) * MM, ty * MM, ln, min(size, 12), FONT_B, INK)
                ty -= min(size, 12) * 1.1
            text(c, (x + col_w - 22) * MM, (y + row_h * 0.36) * MM,
                 f"{it['id']:03d} {it['floor']} {it['industry']}", 6, FONT_R, INK_2, "r")
        text(c, 14 * MM, 10 * MM, "本名录为虚构样例数据；编号与实体名牌 A1–J10 对应，支持按楼层 / 行业 / 首字母三种排序切换。",
             6.5, FONT_R, INK_2)
        c.showPage()
    c.save()


def build() -> dict:
    register_fonts()
    items = make_names()
    with open(OUT / "names.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "chars", "floor", "industry", "initial"])
        w.writeheader()
        w.writerows(items)

    # 三种排布：楼层 / 行业 / 首字母
    wall("会员企业名录墙 · 按楼层", "同层企业相邻展示，便于到访者按楼层动线检索", sorted(items, key=lambda it: (FLOORS.index(it["floor"]), it["id"])),
         ACCENT, OUT / "wall-floor.pdf", "按楼层（1F→8F 升序，同层按入驻时间）")
    wall("会员企业名录墙 · 按行业", "行业聚类，便于商务对接时同频检索", sorted(items, key=lambda it: (it["industry"], it["id"])),
         CMYKColor(0.62, 0.20, 0.10, 0.05), OUT / "wall-industry.pdf", "按行业（8 个行业大类，类内按入驻时间）")
    wall("会员企业名录墙 · 按首字母", "按企业名首字母（拼音）排序，便于电话与前台检索", sorted(items, key=lambda it: (it["initial"], it["id"])),
         CMYKColor(0.20, 0.55, 0.10, 0.10), OUT / "wall-pinyin.pdf", "按首字母（拼音 A–Z，同字母按笔画）")

    plate_templates(items, OUT / "plate-templates.pdf")

    # 电子名录：横版 16:9（338.7×190.5 mm）与竖版 9:16
    directory_pages(items, OUT / "directory-landscape.pdf", 338.7, 190.5, per_page=20)
    directory_pages(items, OUT / "directory-portrait.pdf", 190.5, 338.7, per_page=20)

    stats = {
        "companies": len(items),
        "chars_min": min(i["chars"] for i in items),
        "chars_max": max(i["chars"] for i in items),
        "over_20": sum(1 for i in items if i["chars"] > 20),
        "files": ["wall-floor.pdf", "wall-industry.pdf", "wall-pinyin.pdf", "plate-templates.pdf",
                  "directory-landscape.pdf", "directory-portrait.pdf", "names.csv"],
    }
    return stats


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False))
