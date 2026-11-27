"""WCAG 2.1 AA contrast measurement for the brand audit.

Two modes:
  colors  --fg "#1a1a1a" --bg "#ffffff"        direct hex pairs
  sample  --image shot.png --fg 120,44 --bg 400,44   sample pixels at x,y

Thresholds (WCAG 2.1 AA):
  normal text  >= 4.5
  large text   >= 3.0   (>=18.66px bold, or >=24px regular)

Output: CSV rows ready to paste into the audit workbook, plus a PASS/FAIL verdict.
"""
from __future__ import annotations

import argparse
import csv
import sys

THRESHOLD_NORMAL = 4.5
THRESHOLD_LARGE = 3.0


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (_srgb_to_linear(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    l1, l2 = luminance(fg), luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def parse_hex(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    if len(v) != 6:
        raise ValueError(f"not a hex color: {value}")
    return tuple(int(v[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def parse_point(value: str) -> tuple[int, int]:
    x, y = value.split(",")
    return int(x), int(y)


def sample(image, point: tuple[int, int], radius: int = 1) -> tuple[int, int, int]:
    """Average a small square around the point to damp JPEG ringing."""
    x, y = point
    px = image.convert("RGB").load()
    total = [0, 0, 0]
    n = 0
    for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
            xx, yy = x + dx, y + dy
            if 0 <= xx < image.width and 0 <= yy < image.height:
                p = px[xx, yy]
                total[0] += p[0]
                total[1] += p[1]
                total[2] += p[2]
                n += 1
    return (total[0] // n, total[1] // n, total[2] // n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["colors", "sample"], default="colors")
    ap.add_argument("--fg", required=True)
    ap.add_argument("--bg", required=True)
    ap.add_argument("--image")
    ap.add_argument("--label", default="")
    ap.add_argument("--position", default="")
    ap.add_argument("--large", action="store_true", help="sample is large text (>=24px or >=18.66px bold)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.mode == "sample":
        from PIL import Image  # only needed for pixel sampling

        if not args.image:
            print("--image is required in sample mode", file=sys.stderr)
            return 2
        img = Image.open(args.image)
        fg = sample(img, parse_point(args.fg))
        bg = sample(img, parse_point(args.bg))
        coords = f"fg@{args.fg};bg@{args.bg}"
    else:
        fg = parse_hex(args.fg)
        bg = parse_hex(args.bg)
        coords = f"fg=#{args.fg.lstrip('#')};bg=#{args.bg.lstrip('#')}"

    ratio = contrast_ratio(fg, bg)
    threshold = THRESHOLD_LARGE if args.large else THRESHOLD_NORMAL
    verdict = "PASS" if ratio >= threshold else "FAIL"
    row = [
        args.label or args.image or "",
        args.position,
        f"#{fg[0]:02x}{fg[1]:02x}{fg[2]:02x}",
        f"#{bg[0]:02x}{bg[1]:02x}{bg[2]:02x}",
        coords,
        f"{ratio:.2f}",
        f"{threshold:.1f}",
        verdict,
    ]
    if args.out:
        with open(args.out, "a", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(row)
    print(",".join(row))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
