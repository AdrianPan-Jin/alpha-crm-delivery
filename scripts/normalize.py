"""Normalisation rules shared by the migration reconciliation script.

Rules (kept deliberately small and tested):
  1. strip leading/trailing whitespace, including the full-width space U+3000
  2. convert full-width ASCII (U+FF01..U+FF5E) to half-width, and U+3000 to a space
  3. drop a leading country code (+86 / 0086 / 86) from phone numbers
  4. collapse internal runs of whitespace to a single space
"""
from __future__ import annotations

import re

_FULLWIDTH_START = 0xFF01
_FULLWIDTH_END = 0xFF5E
_OFFSET = 0xFEE0

_PHONE_PREFIX = re.compile(r"^(\+?86|0086)")
_SPACES = re.compile(r"\s+")


def to_halfwidth(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if _FULLWIDTH_START <= code <= _FULLWIDTH_END:
            out.append(chr(code - _OFFSET))
        elif code == 0x3000:  # ideographic space
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def clean(text: str | None) -> str:
    if text is None:
        return ""
    return _SPACES.sub(" ", to_halfwidth(text)).strip()


def phone(raw: str | None) -> str:
    value = clean(raw).replace("-", "").replace(" ", "")
    value = _PHONE_PREFIX.sub("", value)
    return value


def credit_code(raw: str | None) -> str:
    return clean(raw).upper()


def mask_phone(value: str) -> str:
    """13800138000 / +8613800138000 -> 138****8000 (keeps the 4-digit tail)."""
    digits = phone(value)
    if len(digits) != 11:
        return value
    return f"{digits[:3]}****{digits[7:]}"
