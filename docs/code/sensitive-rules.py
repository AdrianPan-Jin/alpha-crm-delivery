"""Rule layer: deterministic, auditable detectors with context exclusions.

Design notes
------------
* Full-width characters (１２３，＠ etc.) are folded to ASCII before matching.
  The translation is 1:1 in Python string terms (each source char becomes one
  char), so span offsets stay valid for the original text.
* Phone numbers, ID cards and bank cards share one "digit run" scanner: a run of
  digits optionally joined by single spaces/hyphens.  The stripped length and
  the leading digits decide the category, so "138-0013-8000" and "13800138000"
  are the same finding and "6222 0200 0000 0000" is a bank card.
* MASKED numbers (138****0000) are never reported again, and technical
  identifiers (订单号/流水号/trace/...) are dropped by context prefix.
"""

from __future__ import annotations

import re
from typing import Final

from .schema import Span

# --------------------------------------------------------------- normalising
_FW_MAP = {c: chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F)}  # ！-～ -> !-~
_FW_MAP[0x3000] = " "  # 全角空格


def normalize_width(text: str) -> str:
    return text.translate(_FW_MAP)


# ---------------------------------------------------------------- patterns
EMAIL: Final[re.Pattern] = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DIGIT_RUN: Final[re.Pattern] = re.compile(r"(?<!\d)\d(?:[ -]?\d)*(?!\d)")
MASKED: Final[re.Pattern] = re.compile(r"1[3-9]\d\*{4}\d{4}")
# 座机：(0571) 8888-6666 / 0571-88886666 / 0571 88886666
LANDLINE: Final[re.Pattern] = re.compile(
    r"(?<![\d(（])(?:"
    r"\(0\d{2,3}\)[ -]?\d{3,4}[ -]?\d{4}"      # (0571) 8888-6666
    r"|（0\d{2,3}）[ -]?\d{3,4}[ -]?\d{4}"        # （0571）8888-6666
    r"|0\d{2,3}-\d{7,8}"                          # 0571-88886666
    r"|0\d{2,3} \d{7,8}"                          # 0571 88886666
    r")(?!\d)"
)
# 邮箱变形：user [at] example.com / user(at)example.com / user （at） example.com
OBF_EMAIL: Final[re.Pattern] = re.compile(
    r"[A-Za-z0-9._%+-]+\s*[\[\(（【]\s*(?:at|AT|艾特)\s*[\]\)）】]\s*[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
# 手机号跨行：1380013\n8000
SPLIT_PHONE: Final[re.Pattern] = re.compile(r"(?<!\d)(1[3-9]\d{2,6})[ \t]*\r?\n[ \t]*(\d{4,6})(?!\d)")
PHONE_HEAD: Final[re.Pattern] = re.compile(r"1[3-9]\d{9}")

DENY_PREFIXES: Final[tuple[str, ...]] = (
    "订单号", "运单号", "流水号", "工单号", "任务号", "版本号", "批次号", "编号",
    "timestamp", "trace", "uuid", "sku", "order_no", "v2.", "v1.",
)


def _denied(text: str, start: int) -> bool:
    head = text[max(0, start - 10):start].lower()
    return any(p in head for p in DENY_PREFIXES)


def _classify_digits(digits: str, next_char: str = "") -> str | None:
    n = len(digits)
    if n == 11:
        return "phone" if PHONE_HEAD.fullmatch(digits) else None
    if n == 18:
        return "id_card"
    if n == 17 and next_char in ("X", "x"):
        return "id_card"          # 17 digits + check char
    if 16 <= n <= 19:
        return "bank_card"
    return None


def scan(text: str) -> list[Span]:
    """Return rule-based spans in document order (no duplicates)."""
    norm = normalize_width(text)
    spans: list[Span] = []
    taken: list[tuple[int, int]] = []

    def push(s: int, e: int, category: str) -> None:
        if any(s < te and ts < e for ts, te in taken):
            return
        taken.append((s, e))
        spans.append(Span(s, e, category, text[s:e]))

    # 跨行手机号先扫（跨度覆盖两段数字，避免被 DIGIT_RUN 拆开）
    for m in SPLIT_PHONE.finditer(norm):
        digits = re.sub(r"\D", "", m.group(0))
        if len(digits) == 11 and PHONE_HEAD.fullmatch(digits):
            push(m.start(), m.end(), "phone")

    # 座机
    for m in LANDLINE.finditer(norm):
        if _denied(norm, m.start()):
            continue
        push(m.start(), m.end(), "phone")

    # 变形邮箱
    for m in OBF_EMAIL.finditer(norm):
        if _denied(norm, m.start()):
            continue
        push(m.start(), m.end(), "email")

    # identifiers
    for m in DIGIT_RUN.finditer(norm):
        s, e = m.group(0), norm[m.start():m.end()]
        digits = re.sub(r"[ -]", "", s)
        if MASKED.fullmatch(norm[max(0, m.start() - 1):m.end() + 1]) or MASKED.fullmatch(digits):
            continue
        if _denied(norm, m.start()):
            continue
        nxt = norm[m.end():m.end() + 1]
        cat = _classify_digits(digits, nxt)
        if cat == "id_card" and nxt in ("X", "x") and not digits.endswith(("X", "x")):
            push(m.start(), m.end() + 1, cat)      # include the check character
        elif cat:
            push(m.start(), m.end(), cat)

    # e-mail
    for m in EMAIL.finditer(norm):
        if _denied(norm, m.start()):
            continue
        push(m.start(), m.end(), "email")

    spans.sort(key=lambda x: (x.start, -x.end))
    return spans
