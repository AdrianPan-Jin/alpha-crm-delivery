"""Synthetic (fictional) evaluation sets.

All identifiers are synthetic: phone numbers use the 199 range, e-mails use the
reserved example.com domain, ID/bank numbers are generated digit strings that
are not issued to anyone.  The normal set is template-driven business text; the
hard set adds adversarial formatting (separators, full-width digits, uppercase
addresses) and traps (masked numbers, order numbers, timestamps, version strings,
IP addresses) that must NOT be reported.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

NAMES = ["林小满", "陈默", "周知远", "沈复", "顾青", "苏皖", "段誉", "李慕", "何夕", "方圆"]
CITIES = ["杭州", "宁波", "苏州", "合肥", "长沙", "成都"]

IDENTIFIER_RE = {
    "phone": re.compile(r"1[3-9]\d(?:[ -]?\d){8}"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "id_card": re.compile(r"\d{17}[\dXx]"),
    "bank_card": re.compile(r"\d{16,19}"),
}


def _phone(rng: random.Random) -> str:
    return "199" + "".join(str(rng.randint(0, 9)) for _ in range(8))


def _email(rng: random.Random) -> str:
    return f"user{rng.randint(100, 999)}@example.com"


def _id_card(rng: random.Random) -> str:
    # 17 digits + check char, synthetic
    return ("110101" "1990" f"{rng.randint(1, 12):02d}" f"{rng.randint(1, 28):02d}"
            f"{rng.randint(0, 999):03d}" "X")


def _bank_card(rng: random.Random) -> str:
    return "622202" + "".join(str(rng.randint(0, 9)) for _ in range(10))


def _fullwidth(s: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)


def _group(digits: str, size: int, sep: str) -> str:
    return sep.join(digits[i:i + size] for i in range(0, len(digits), size))


POSITIVE_TEMPLATES = [
    ("收件人 {name}，手机号 {phone}，地址 {city}市滨江区。", [("phone", "{phone}")]),
    ("请把发票发到 {email}，抄送财务。", [("email", "{email}")]),
    ("开户账户 {bank}，持卡人 {name}，请核对。", [("bank_card", "{bank}")]),
    ("身份证号 {id}，用于实名核验。", [("id_card", "{id}")]),
    ("客户 {name} 反馈：电话 {phone} 打不通，改用邮箱 {email}。",
     [("phone", "{phone}"), ("email", "{email}")]),
    ("联系人 {name}，手机 {phone}。", [("phone", "{phone}")]),
]

NEGATIVE_TEMPLATES = [
    "订单号 {order} 已发货，物流单号 SF{sf}。",
    "流水号 {serial}，批次 {batch}。",
    "时间戳 2026{mm}{dd}1030，任务号 {task} 完成。",
    "SKU-{sku}-001 库存 2026 件，价格 1280 元。",
    "统计：2026 年 11 月 27 日新增 1284 条，环比 +12%。",
    "服务地址 10.0.0.{ip}，端口 8080，trace {trace}。",
    "脱敏手机号 138****0000 已登记，无需再次处理。",
    "版本号 v2.11.27，构建 {build}。",
    "工单号 {task}，负责人已确认，状态 in_progress。",
]


def _neg(rng: random.Random) -> str:
    return rng.choice(NEGATIVE_TEMPLATES).format(
        order="".join(str(rng.randint(0, 9)) for _ in range(12)),
        sf="".join(str(rng.randint(0, 9)) for _ in range(12)),
        serial="".join(str(rng.randint(0, 9)) for _ in range(16)),
        batch="".join(str(rng.randint(0, 9)) for _ in range(6)),
        mm=f"{rng.randint(1, 12):02d}",
        dd=f"{rng.randint(1, 28):02d}",
        task="".join(str(rng.randint(0, 9)) for _ in range(6)),
        sku="".join(str(rng.randint(0, 9)) for _ in range(6)),
        ip=rng.randint(1, 254),
        trace="".join(str(rng.randint(0, 9)) for _ in range(8)),
        build="".join(str(rng.randint(0, 9)) for _ in range(6)),
    )


def _gold_for(sent: str) -> list[dict]:
    """Gold spans derived from the sentence itself (synthetic, unambiguous)."""
    gold = []
    for cat, rx in IDENTIFIER_RE.items():
        for m in rx.finditer(sent):
            val = m.group(0)
            if "****" in val:
                continue
            gold.append({"start": m.start(), "end": m.end(), "category": cat})
    # containment: a phone/bank-card pattern can appear inside an 18-digit ID
    # number; the longer identifier wins and the inner match is dropped.
    gold.sort(key=lambda g: (g["start"], -(g["end"] - g["start"])))
    kept: list[dict] = []
    for g in gold:
        if any(k["start"] <= g["start"] and g["end"] <= k["end"] and k is not g for k in kept):
            continue
        kept = [k for k in kept if not (g["start"] <= k["start"] and k["end"] <= g["end"])]
        kept.append(g)
    return kept


def _assemble(items: list[tuple[str, list[tuple[str, str]]]], title: str) -> dict:
    """items: [(sentence, [(category, literal_value), ...]), ...].

    Gold spans are derived from the literals we inserted (not by re-running the
    detectors), so the evaluation is not circular.
    """
    text = "。\n".join(sent for sent, _ in items)
    gold, pos = [], 0
    for sent, spans in items:
        for cat, val in spans:
            at = sent.find(val)
            if at >= 0:
                gold.append({"start": pos + at, "end": pos + at + len(val), "category": cat})
        pos += len(sent) + 2
    return {"text": text, "spans": sorted(gold, key=lambda s: s["start"]), "title": title}


def build_docs(n_docs: int = 80, seed: int = 20261127) -> list[dict]:
    rng = random.Random(seed)
    docs = []
    for i in range(n_docs):
        items = []
        for _ in range(rng.randint(4, 8)):
            if rng.random() < 0.45:
                tpl, slots = rng.choice(POSITIVE_TEMPLATES)
                vals = {
                    "name": rng.choice(NAMES), "phone": _phone(rng), "email": _email(rng),
                    "id": _id_card(rng), "bank": _bank_card(rng), "city": rng.choice(CITIES),
                }
                got = [(cat, vals[key.strip("{}")]) for cat, key in slots]
                items.append((tpl.format(**vals), got))
            else:
                items.append((_neg(rng), []))
        d = _assemble(items, f"normal-{i+1:03d}")
        d["id"] = f"doc-{i+1:03d}"
        docs.append(d)
    return docs


def build_hard_docs(n_docs: int = 40, seed: int = 20261128) -> list[dict]:
    rng = random.Random(seed)
    docs = []
    for i in range(n_docs):
        ph = _phone(rng)
        em = _email(rng)
        bc = _bank_card(rng)
        idc = _id_card(rng)
        sents = [
            f"客户电话 {ph[:3]}-{ph[3:7]}-{ph[7:]}，请电话联系",
            f"备用号 {ph[:3]} {ph[3:7]} {ph[7:]}，工作时间接听",
            f"表单里填的是 {_fullwidth(ph)}，需要清洗",
            f"打款到 {_group(bc, 4, ' ')} 这个账户",
            f"回执发 {em.upper()}，注意大小写",
            "脱敏号 138****0000 不用再报",
            f"订单号 {''.join(str(rng.randint(0, 9)) for _ in range(12))}，物流已发出",
            "时间戳 20261127103012 与版本 v2.11.27 均非个人信息",
            "服务地址 10.0.0.7，端口 8080",
            f"实名信息：身份证 {idc}",
        ]
        items = [
            (f"客户电话 {ph[:3]}-{ph[3:7]}-{ph[7:]}，请电话联系", [("phone", f"{ph[:3]}-{ph[3:7]}-{ph[7:]}")]),
            (f"备用号 {ph[:3]} {ph[3:7]} {ph[7:]}，工作时间接听", [("phone", f"{ph[:3]} {ph[3:7]} {ph[7:]}")]),
            (f"表单里填的是 {_fullwidth(ph)}，需要清洗", [("phone", _fullwidth(ph))]),
            (f"打款到 {_group(bc, 4, ' ')} 这个账户", [("bank_card", _group(bc, 4, " "))]),
            (f"回执发 {em.upper()}，注意大小写", [("email", em.upper())]),
            ("脱敏号 138****0000 不用再报", []),
            (f"订单号 {''.join(str(rng.randint(0, 9)) for _ in range(12))}，物流已发出", []),
            ("时间戳 20261127103012 与版本 v2.11.27 均非个人信息", []),
            ("服务地址 10.0.0.7，端口 8080", []),
            (f"实名信息：身份证 {idc}", [("id_card", idc)]),
        ]
        rng.shuffle(items)
        d = _assemble(items[: rng.randint(6, 9)], f"hard-{i+1:03d}")
        d["id"] = f"hard-{i+1:03d}"
        docs.append(d)
    return docs


def build_stress_docs(n_docs: int = 30, seed: int = 20261129) -> list[dict]:
    """Formats the current pipeline is NOT expected to catch.

    They are still personal data, so this set measures the honest gaps:
    landline numbers, e-mail written as user [at] example.com, ID numbers with
    spaces, phone numbers split across lines, and numbers written in Chinese.
    """
    rng = random.Random(seed)
    docs = []
    for i in range(n_docs):
        ph, em, idc, bc = _phone(rng), _email(rng), _id_card(rng), _bank_card(rng)
        items = [
            (f"座机 (0571) 8888-6666，分机 233", [("phone", "(0571) 8888-6666")]),
            (f"邮箱写成 user [at] example.com 这种形式", [("email", "user [at] example.com")]),
            (f"身份证 {idc[:6]} {idc[6:14]} {idc[14:]} 分段抄写", [("id_card", f"{idc[:6]} {idc[6:14]} {idc[14:]}")]),
            (f"手机号写在两行：{ph[:5]}\n{ph[5:]}", [("phone", f"{ph[:5]}\n{ph[5:]}")]),
            (f"卡号 {bc}（连写，应命中）", [("bank_card", bc)]),
            ("金额一万二千元整，数量 2026 件", []),
        ]
        rng.shuffle(items)
        d = _assemble(items[: rng.randint(4, 6)], f"stress-{i+1:03d}")
        d["id"] = f"stress-{i+1:03d}"
        docs.append(d)
    return docs


def write_jsonl(path: str | Path, docs: list[dict]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    return p


def load_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/eval_set.jsonl")
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--seed", type=int, default=20261127)
    ap.add_argument("--hard", action="store_true")
    ap.add_argument("--stress", action="store_true")
    a = ap.parse_args()
    if a.stress:
        docs = build_stress_docs(a.n, a.seed)
    elif a.hard:
        docs = build_hard_docs(a.n, a.seed)
    else:
        docs = build_docs(a.n, a.seed)
    write_jsonl(a.out, docs)
    print(f"wrote {len(docs)} docs / {sum(len(d['spans']) for d in docs)} spans -> {a.out}")
