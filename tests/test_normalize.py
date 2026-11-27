from __future__ import annotations

import pytest

from scripts.normalize import clean, credit_code, mask_phone, phone, to_halfwidth


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  杭州云帆科技  ", "杭州云帆科技"),
        ("\u3000上海禾木\u3000", "上海禾木"),
        ("ＡＢＣ１２３", "ABC123"),
        ("深圳市  南山区", "深圳市 南山区"),
        (None, ""),
    ],
)
def test_clean(raw, expected):
    assert clean(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("13800138000", "13800138000"),
        ("+8613800138000", "13800138000"),
        ("008613800138000", "13800138000"),
        ("8613800138000", "13800138000"),
        (" 138-0013-8000 ", "13800138000"),
        ("１３８００１３８０００", "13800138000"),
    ],
)
def test_phone(raw, expected):
    assert phone(raw) == expected


def test_credit_code_uppercases_and_strips():
    assert credit_code(" 91440300ma5f7y6q2c ") == "91440300MA5F7Y6Q2C"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("13800138000", "138****8000"),
        ("+8613800138000", "138****8000"),
        ("123", "123"),
    ],
)
def test_mask_phone(raw, expected):
    assert mask_phone(raw) == expected


def test_to_halfwidth_keeps_chinese():
    assert to_halfwidth("中国Ａ１\u3000!") == "中国A1 !"
