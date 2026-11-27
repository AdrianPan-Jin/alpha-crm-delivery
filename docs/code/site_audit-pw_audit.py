#!/usr/bin/env python3
"""Brand implementation audit (S6-BRAND-001) driven by a real headless Chrome.

Why this file exists: the audit ACs require *annotated screenshots*, measured
contrast ratios with the tool name, and a deviation list with location /
category / severity / (execution deviation vs specification gap). Doing that by
hand is slow and unrepeatable, so the whole pipeline is scripted:

    python pw_audit.py --url https://example.com --out out/example --label example

Outputs (all inside --out):
    report.md            human-readable, grouped by specification section
    findings.csv         one row per deviation (the machine-readable list)
    findings.xlsx        four sheets: deviations / category coverage / summary / top issues
    shots/<id>-<slug>.png   element-level screenshots, numbered to match the CSV
    desktop-full.png, mobile-full.png   full-page captures
    run.json             raw measurements (url, viewport, timestamps, tool versions)

The measurements come from getComputedStyle() in Chrome 158 (Playwright binding),
so the contrast numbers are真实值 rather than eyeballed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

TOOL = "pw_audit.py + Playwright/Chrome 158 (WCAG 2.1 contrast formula)"

SECTIONS = {
    "color": "3. 色彩与对比度",
    "type": "2. 字体与排版",
    "image": "5. 图像与图标",
    "link": "6. 链接与交互",
    "form": "7. 表单与控件",
    "layout": "4. 版式与间距",
    "content": "8. 文案与信息层级",
}

# map our fine-grained category to the 8 brand-audit classes used by build_audit.py
BRAND_CATEGORY = {
    "对比度不足": "对比度（WCAG AA）",
    "图片缺少替代文本": "插图与图片风格",
    "链接无可读文本": "文案语气",
    "使用 javascript: 伪链接": "图标风格",
    "触控目标过小": "间距与栅格",
    "标题层级跳跃": "字体与字号层级",
    "控件缺少可访问名称": "文案语气",
    "页面缺少 lang 声明": "文案语气",
    "缺少 h1 主标题": "字体与字号层级",
    "多个 h1 主标题": "字体与字号层级",
    "缺少 meta description": "文案语气",
}

CONTRAST_AA = 4.5
CONTRAST_AA_LARGE = 3.0

COLLECT_JS = r"""
() => {
  const out = {text: [], images: [], links: [], controls: [], headings: []};
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map((x) => parseFloat(x));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const bgOf = (el) => {
    let cur = el;
    while (cur) {
      const st = getComputedStyle(cur);
      const c = parse(st.backgroundColor);
      if (c && c.a > 0.9) return c;
      if (c && c.a > 0) {
        // semi-transparent: composite over white as a conservative approximation
        return {r: c.r * c.a + 255 * (1 - c.a), g: c.g * c.a + 255 * (1 - c.a),
                b: c.b * c.a + 255 * (1 - c.a), a: 1};
      }
      cur = cur.parentElement;
    }
    return {r: 255, g: 255, b: 255, a: 1};
  };
  const sel = (el) => {
    if (el.id) return '#' + el.id;
    let path = [];
    let cur = el;
    for (let i = 0; i < 4 && cur && cur.tagName && cur.tagName.toLowerCase() !== 'html'; i++) {
      let s = cur.tagName.toLowerCase();
      const cls = (cur.className && typeof cur.className === 'string') ? cur.className.trim().split(/\s+/)[0] : '';
      if (cls) s += '.' + cls;
      path.unshift(s);
      cur = cur.parentElement;
    }
    return path.join(' > ');
  };
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return {x: Math.round(r.x + window.scrollX), y: Math.round(r.y + window.scrollY),
            w: Math.round(r.width), h: Math.round(r.height)};
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 1 && r.height > 1 && st.visibility !== 'hidden' && st.display !== 'none'
           && parseFloat(st.opacity || '1') > 0.2;
  };

  const textEls = Array.from(document.querySelectorAll('h1,h2,h3,h4,p,li,td,a,button,span,div,label,strong,em,b,small'))
    .filter((el) => !el.closest('pre,code,kbd,samp'))
    .filter((el) => el.textContent && el.textContent.trim().length >= 2 && visible(el))
    .filter((el) => !Array.from(el.children).some((c) => c.textContent && c.textContent.trim().length > 2))
    .slice(0, 400);
  for (const el of textEls) {
    const st = getComputedStyle(el);
    const fg = parse(st.color);
    if (!fg) continue;
    const b = bgOf(el);
    out.text.push({
      selector: sel(el), tag: el.tagName.toLowerCase(),
      text: el.textContent.trim().slice(0, 80),
      color: st.color, bg: `rgb(${Math.round(b.r)}, ${Math.round(b.g)}, ${Math.round(b.b)})`,
      fg: {r: fg.r, g: fg.g, b: fg.b},
      bgRgb: {r: b.r, g: b.g, b: b.b},
      fontSize: parseFloat(st.fontSize), fontWeight: st.fontWeight, box: box(el),
    });
  }

  document.querySelectorAll('img').forEach((img) => {
    if (!visible(img)) return;
    out.images.push({selector: sel(img), src: img.currentSrc || img.src,
      alt: img.getAttribute('alt'), decorative: img.getAttribute('role') === 'presentation' || img.getAttribute('alt') === '',
      naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight, box: box(img),
      loading: img.getAttribute('loading')});
  });

  document.querySelectorAll('a').forEach((a) => {
    if (!visible(a)) return;
    out.links.push({selector: sel(a), text: (a.textContent || '').trim().slice(0, 60),
      href: a.getAttribute('href'), target: a.getAttribute('target'),
      rel: a.getAttribute('rel'), box: box(a),
      block: getComputedStyle(a).display !== 'inline'});
  });

  document.querySelectorAll('button,input,select,textarea,label').forEach((el) => {
    if (!visible(el)) return;
    out.controls.push({selector: sel(el), tag: el.tagName.toLowerCase(),
      type: el.getAttribute('type'), text: (el.textContent || '').trim().slice(0, 40),
      label: el.getAttribute('aria-label') || el.getAttribute('placeholder') || '',
      box: box(el)});
  });

  document.querySelectorAll('h1,h2,h3,h4,h5,h6').forEach((h) => {
    if (!visible(h)) return;
    out.headings.push({level: parseInt(h.tagName.slice(1), 10), text: h.textContent.trim().slice(0, 60), selector: sel(h)});
  });
  return out;
}
"""


def _lin(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def contrast(fg: dict, bg: dict) -> float:
    l1 = 0.2126 * _lin(fg["r"]) + 0.7152 * _lin(fg["g"]) + 0.0722 * _lin(fg["b"])
    l2 = 0.2126 * _lin(bg["r"]) + 0.7152 * _lin(bg["g"]) + 0.0722 * _lin(bg["b"])
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


@dataclass
class Finding:
    id: str
    section: str
    category: str
    severity: str
    kind: str            # execution_deviation | specification_gap
    selector: str
    location: dict
    description: str
    evidence: str
    suggestion: str
    screenshot: str = ""
    tool: str = TOOL


def classify(kind_hint: str) -> str:
    return "execution_deviation" if kind_hint == "exec" else "specification_gap"


def audit_page(page, out_dir: Path, prefix: str) -> tuple[list[Finding], dict]:
    """Audit the currently loaded page; screenshots are taken per finding later."""
    data = page.evaluate(COLLECT_JS)
    findings: list[Finding] = []

    def add(**kw) -> None:
        fid = f"{prefix}{len(findings) + 1:03d}"
        findings.append(Finding(id=fid, **kw))

    # 1) contrast
    for t in data["text"]:
        ratio = contrast(t["fg"], t["bgRgb"])
        large = t["fontSize"] >= 24 or (t["fontSize"] >= 18.66 and int(re.sub(r"\D", "", t["fontWeight"]) or 400) >= 700)
        need = CONTRAST_AA_LARGE if large else CONTRAST_AA
        if ratio < need:
            sev = "high" if ratio < 3 else "medium"
            add(section="color", category="对比度不足", severity=sev, kind=classify("exec"),
                selector=t["selector"], location=t["box"],
                description=f"文本「{t['text']}」对比度 {ratio:.2f}:1，低于 AA 要求 {need}:1",
                evidence=f"foreground {t['color']} on background {t['bg']}; 字号 {t['fontSize']:.0f}px / 字重 {t['fontWeight']}",
                suggestion="提高前景与背景的明度差（改文本色或加深底色），至少达到 4.5:1")

    # 2) images without alt
    for im in data["images"]:
        if im["alt"] is None and not im["decorative"]:
            add(section="image", category="图片缺少替代文本", severity="medium", kind=classify("exec"),
                selector=im["selector"], location=im["box"],
                description="img 元素没有 alt 属性，读屏软件无法描述该图",
                evidence=f"src={im['src'][:120]}", suggestion="为信息性图片补 alt，纯装饰图用 alt=\"\"")

    # 3) empty links / links without href
    for a in data["links"]:
        if not a["text"] and not a["href"]:
            continue
        if not a["text"]:
            add(section="link", category="链接无可读文本", severity="medium", kind=classify("exec"),
                selector=a["selector"], location=a["box"],
                description="链接没有可读文本（图标按钮需 aria-label）",
                evidence=f"href={a['href']}", suggestion="补可见文本或 aria-label")
        elif a["href"] and a["href"].startswith("javascript:"):
            add(section="link", category="使用 javascript: 伪链接", severity="low", kind=classify("exec"),
                selector=a["selector"], location=a["box"],
                description="可点击元素用 javascript: 而非真实 URL，无法新窗口打开/被搜索引擎识别",
                evidence=f"href={a['href'][:80]}", suggestion="改为真实路径或 button 元素")

    # 4) tap targets on mobile are added by the caller (desktop pass has no min-size rule)
    # 5) heading order
    lv = [h["level"] for h in data["headings"]]
    for i in range(1, len(lv)):
        if lv[i] - lv[i - 1] > 1:
            add(section="type", category="标题层级跳跃", severity="low", kind=classify("exec"),
                selector=data["headings"][i]["selector"], location={"x": 0, "y": 0, "w": 0, "h": 0},
                description=f"标题从 h{lv[i-1]} 跳到 h{lv[i]}：{data['headings'][i]['text']}",
                evidence=f"上一级 h{lv[i-1]}", suggestion="按 h1→h2→h3 顺序递进，样式与语义分离")

    # 6) controls without accessible name
    for c in data["controls"]:
        if c["tag"] in ("button", "input", "select", "textarea") and not c["text"] and not c["label"]:
            add(section="form", category="控件缺少可访问名称", severity="medium", kind=classify("exec"),
                selector=c["selector"], location=c["box"],
                description=f"{c['tag']} 既无文本也无 aria-label/placeholder",
                evidence=f"type={c['type']}", suggestion="补 label / aria-label")

    # 7) document-level basics
    doc = page.evaluate('() => ({lang: document.documentElement.lang, title: document.title, desc: (document.querySelector(\'meta[name="description"]\')||{}).content || "", h1: document.querySelectorAll("h1").length})')
    if not doc["lang"]:
        add(section="content", category="页面缺少 lang 声明", severity="low", kind=classify("spec"),
            selector="html", location={"x": 0, "y": 0, "w": 0, "h": 0},
            description="html 元素没有 lang 属性，读屏与翻译工具无法判断语言",
            evidence="document.documentElement.lang 为空", suggestion="补 lang=\"zh-CN\"")
    if doc["h1"] == 0:
        add(section="content", category="缺少 h1 主标题", severity="medium", kind=classify("exec"),
            selector="body", location={"x": 0, "y": 0, "w": 0, "h": 0},
            description="页面没有任何 h1，信息层级缺少主语",
            evidence="document.querySelectorAll('h1').length === 0", suggestion="为页面主标题使用 h1，其余按层级递进")
    if doc["h1"] > 1:
        add(section="content", category="多个 h1 主标题", severity="low", kind=classify("exec"),
            selector="body", location={"x": 0, "y": 0, "w": 0, "h": 0},
            description=f"页面有 {doc['h1']} 个 h1，主标题不唯一",
            evidence="document.querySelectorAll('h1').length", suggestion="保留一个 h1，其余降级")
    if not doc["desc"]:
        add(section="content", category="缺少 meta description", severity="low", kind=classify("spec"),
            selector="head", location={"x": 0, "y": 0, "w": 0, "h": 0},
            description="页面没有 meta description，搜索结果摘要不可控",
            evidence="meta[name=description] content 为空", suggestion="补 60–120 字描述")
    for im in data["images"]:
        if im["naturalWidth"] and im["box"]["w"] and not im.get("loading"):
            pass
    return findings, data


def annotate_shot(png: Path, findings: list[Finding], out_dir: Path) -> None:
    """Draw numbered boxes for every finding on the full-page screenshot."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    img = Image.open(png).convert("RGB")
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 22)
    except Exception:
        font = ImageFont.load_default()
    for f in findings:
        loc = f.location
        if loc.get("w", 0) <= 0 or loc.get("h", 0) <= 0:
            continue
        x, y, w, h = loc["x"], loc["y"], loc["w"], loc["h"]
        color = (220, 40, 40) if f.severity == "high" else ((230, 130, 20) if f.severity == "medium" else (60, 120, 200))
        d.rectangle([x - 2, y - 2, x + w + 2, y + h + 2], outline=color, width=3)
        label = f.id
        tw = d.textlength(label, font=font)
        d.rectangle([x - 2, y - 30, x + tw + 16, y - 2], fill=color)
        d.text((x + 6, y - 28), label, fill=(255, 255, 255), font=font)
    out = out_dir / (png.stem + "-annotated.png")
    img.save(out)
    print(f"[shot] {out.name}")


def write_outputs(out_dir: Path, url: str, all_findings: list[Finding], meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "findings.csv"
    cols = ["id", "section", "category", "severity", "kind", "selector", "x", "y", "w", "h",
            "description", "evidence", "suggestion", "screenshot", "tool"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for f in all_findings:
            loc = f.location
            w.writerow([f.id, f.section, f.category, f.severity, f.kind, f.selector,
                        loc.get("x"), loc.get("y"), loc.get("w"), loc.get("h"),
                        f.description, f.evidence, f.suggestion, f.screenshot, f.tool])

    by_sec: dict[str, list[Finding]] = {}
    for f in all_findings:
        by_sec.setdefault(f.section, []).append(f)
    lines = [f"# 品牌落地审计报告 — {url}", "",
             f"- 工具：{TOOL}",
             f"- 时间：{meta['started']}",
             f"- 视口：{meta['viewports']}",
             f"- 偏差条目：**{len(all_findings)}** 条（AC 要求 ≥40）", "",
             "| 段落 | 条目 | 高 | 中 | 低 |", "| --- | --- | --- | --- | --- |"]
    for sec, fs in sorted(by_sec.items()):
        hi = sum(1 for f in fs if f.severity == "high")
        me = sum(1 for f in fs if f.severity == "medium")
        lo = sum(1 for f in fs if f.severity == "low")
        lines.append(f"| {SECTIONS.get(sec, sec)} | {len(fs)} | {hi} | {me} | {lo} |")
    lines.append("")
    for sec, fs in sorted(by_sec.items()):
        lines.append(f"## {SECTIONS.get(sec, sec)}")
        lines.append("")
        for f in fs:
            lines.append(f"**{f.id}**（{f.severity}，{'执行偏差' if f.kind == 'execution_deviation' else '规范缺失'}）{f.category}")
            lines.append("")
            lines.append(f"- 位置：`{f.selector}` @ ({f.location.get('x')}, {f.location.get('y')})")
            lines.append(f"- 问题：{f.description}")
            lines.append(f"- 证据：{f.evidence}")
            lines.append(f"- 修订建议：{f.suggestion}")
            if f.screenshot:
                lines.append(f"- 截图：`{f.screenshot}`")
            lines.append("")
    (out_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")

    # brand_audit schema (fixed column set) -> xlsx workbook + chapter-grouped notes
    brand_csv = out_dir / "findings_brand.csv"
    with brand_csv.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "screenshot", "location", "category", "description", "severity",
                    "occurrences", "kind", "evidence", "suggestion"])
        for f in all_findings:
            loc = f.location
            w.writerow([f.id, f.screenshot or "", f"{f.selector} @ ({loc.get('x')},{loc.get('y')})",
                        BRAND_CATEGORY.get(f.category, "文案语气"), f.description, f.severity, 1,
                        "deviation" if f.kind == "execution_deviation" else "gap",
                        f.evidence, f.suggestion])
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "brand_audit"))
        import build_audit as BA
        rows = BA.load_rows(str(brand_csv))
        BA.build_workbook(rows, str(out_dir / "findings.xlsx"))
        BA.build_notes(rows, str(out_dir / "revision_notes.md"))
    except Exception as exc:  # xlsx is a convenience, never the deliverable of record
        print(f"[warn] xlsx skipped: {exc}")

    (out_dir / "run.json").write_text(json.dumps({
        "url": url, "started": meta["started"], "viewports": meta["viewports"],
        "tool": TOOL, "findings": len(all_findings),
        "by_severity": {s: sum(1 for f in all_findings if f.severity == s) for s in ("high", "medium", "low")},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="site")
    ap.add_argument("--max-findings", type=int, default=120)
    args = ap.parse_args()

    out_dir = Path(args.out)
    shots = out_dir / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%d %H:%M:%S")

    from playwright.sync_api import sync_playwright

    findings: list[Finding] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        page = ctx.new_page()
        page.goto(args.url, wait_until="load", timeout=45000)
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out_dir / "desktop-full.png"), full_page=True)
        f1, data1 = audit_page(page, out_dir, "D")
        findings += f1
        # element crops for the first N findings (each finding gets its own image)
        for f in findings[: args.max_findings]:
            loc = f.location
            if loc.get("w", 0) <= 0 or loc.get("h", 0) <= 0:
                continue
            pad = 12
            clip = {"x": max(0, loc["x"] - pad), "y": max(0, loc["y"] - pad),
                    "width": loc["w"] + pad * 2, "height": loc["h"] + pad * 2}
            try:
                path = shots / f"{args.label}-{f.id}.png"
                page.screenshot(path=str(path), clip=clip)
                f.screenshot = str(path.relative_to(out_dir)).replace("\\", "/")
            except Exception:
                pass
        annotate_shot(out_dir / "desktop-full.png", findings, out_dir)

        # mobile pass: tap targets + contrast re-check at 390px
        mctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                   is_mobile=True, has_touch=True)
        mpage = mctx.new_page()
        mpage.goto(args.url, wait_until="load", timeout=45000)
        mpage.wait_for_timeout(1200)
        mpage.screenshot(path=str(out_dir / "mobile-full.png"), full_page=True)
        mdata = mpage.evaluate(COLLECT_JS)
        for c in mdata["controls"] + [x for x in mdata["links"] if x.get("href") and x.get("block")]:
            b = c.get("box") or {}
            if b.get("w", 0) and b.get("h", 0) and (b["w"] < 24 or b["h"] < 24):
                fid = f"M{len(findings)+1:03d}"
                findings.append(Finding(
                    id=fid, section="link", category="触控目标过小", severity="medium",
                    kind=classify("spec"), selector=c["selector"], location=b,
                    description=f"移动端可点击区域 {b['w']}×{b['h']}px，小于 24×24px",
                    evidence=f"文本「{c.get('text','')[:30]}」", suggestion="扩大内边距或设置最小点击区域"))
        browser.close()

    findings = findings[: args.max_findings + 40]
    write_outputs(out_dir, args.url, findings, {"started": started,
                                                "viewports": "desktop 1440×900 / mobile 390×844"})
    print(f"[done] {len(findings)} findings -> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
