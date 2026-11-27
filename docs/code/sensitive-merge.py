"""Merge layer: rules + model -> deduplicated, quote-verified findings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from . import rules as rules_mod
from .rules import normalize_width
from .candidates import generate
from .model import CandidateModel, NEGATIVE
from .schema import Finding, MergeStats, Span


@dataclass
class ModelSpan:
    """What a model adapter returns.  An LLM adapter would fill `quote` with the
    text it claims to have matched; the merge layer verifies that quote against
    the source before it is allowed to write a finding."""

    start: int
    end: int
    category: str
    quote: str | None = None
    score: float = 1.0


_PHONE_RX = __import__("re").compile(r"1[3-9]\d{9}")
_EMAIL_RX = __import__("re").compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def structurally_valid(text: str, span: Span) -> bool:
    """A model span must at least look like the category it claims."""
    raw = normalize_width(span.text)
    digits = __import__("re").sub(r"[ -]", "", raw)
    if span.category == "phone":
        return bool(_PHONE_RX.fullmatch(digits))
    if span.category == "email":
        return bool(_EMAIL_RX.fullmatch(raw))
    if span.category == "id_card":
        return len(raw) == 18 and raw[:17].isdigit()
    if span.category == "bank_card":
        return digits.isdigit() and 16 <= len(digits) <= 19
    return False


def verify_quote(text: str, span: Span, quote: str | None) -> bool:
    if quote is None:
        return True
    if quote.strip() != span.text.strip():
        return False
    return text[span.start:span.end] == span.text


def merge(
    doc_id: str,
    text: str,
    model: CandidateModel,
    *,
    threshold: float = 0.5,
    extra_model_spans: Sequence[ModelSpan] | None = None,
) -> MergeStats:
    stats = MergeStats()

    # 1) rules
    rule_spans = rules_mod.scan(text)
    stats.rule_hits = len(rule_spans)
    by_key: dict[str, Finding] = {}
    for sp in rule_spans:
        f = Finding(doc_id, sp, ("rule",), 1.0)
        by_key[f.key] = f

    # 2) model over generated candidates
    cands = generate(text)
    stats.model_candidates = len(cands)
    preds = model.predict([c.context for c in cands])
    for cand, pred in zip(cands, preds):
        if pred.label == NEGATIVE or pred.sensitive_proba < threshold:
            continue
        sp = Span(cand.start, cand.end, pred.label, cand.text)
        if not structurally_valid(text, sp):
            stats.dropped_unverifiable += 1
            continue
        stats.model_accepted += 1
        f = Finding(doc_id, sp, ("model",), pred.sensitive_proba)
        key = f.key
        if key in by_key:
            prev = by_key[key]
            prev.sources = tuple(sorted(set(prev.sources) | {"model"}))
            prev.score = max(prev.score, f.score)
            stats.merged_duplicates += 1
            continue
        # 同一位置被规则以另一类别命中时，保留规则（规则可审计）
        if any(
            other.span.start == sp.start and other.span.end == sp.end for other in by_key.values()
        ):
            stats.merged_duplicates += 1
            continue
        by_key[key] = f

    # 3) external model spans (e.g. an LLM adapter) — must survive quote verification
    for ms in extra_model_spans or []:
        sp = Span(ms.start, ms.end, ms.category, text[ms.start:ms.end])
        if not verify_quote(text, sp, ms.quote):
            stats.dropped_unverifiable += 1
            continue
        f = Finding(doc_id, sp, ("model",), ms.score)
        if f.key in by_key:
            prev = by_key[f.key]
            prev.sources = tuple(sorted(set(prev.sources) | {"model"}))
            stats.merged_duplicates += 1
            continue
        by_key[f.key] = f

    stats.findings = sorted(by_key.values(), key=lambda f: (f.span.start, -f.span.end))
    return stats
