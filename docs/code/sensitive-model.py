"""Model layer: a small local classifier that filters loose candidates.

It never calls a remote API.  Features are character n-grams of the candidate
plus a small context window, which lets it learn cues such as 「订单号」「联系人」
「请发到」 without a hand-written rule for每个情况.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from .schema import CATEGORIES

NEGATIVE = "none"
LABELS = CATEGORIES + (NEGATIVE,)


@dataclass
class Prediction:
    label: str
    proba: float  # probability of the argmax label
    sensitive_proba: float  # 1 - P(none)


class CandidateModel:
    def __init__(self, ngram_range=(2, 5), min_df=1, C=4.0, random_state=7):
        self.vec = TfidfVectorizer(analyzer="char_wb", ngram_range=ngram_range, min_df=min_df)
        # sklearn >=1.9 dropped `multi_class` (multinomial is the default when
        # there are more than two classes), so we no longer pass it.
        self.clf = LogisticRegression(
            C=C, max_iter=2000, class_weight="balanced", random_state=random_state
        )
        self.classes_: list[str] = []

    # ------------------------------------------------------------------ fit
    def fit(self, contexts: Sequence[str], labels: Sequence[str]) -> "CandidateModel":
        X = self.vec.fit_transform(contexts)
        self.clf.fit(X, labels)
        self.classes_ = [str(c) for c in self.clf.classes_]
        return self

    # -------------------------------------------------------------- predict
    def predict(self, contexts: Sequence[str]) -> list[Prediction]:
        if not contexts:
            return []
        X = self.vec.transform(contexts)
        proba = self.clf.predict_proba(X)
        idx = proba.argmax(axis=1)
        out = []
        for row, i in enumerate(idx):
            none_i = self.classes_.index(NEGATIVE) if NEGATIVE in self.classes_ else -1
            p_none = float(proba[row][none_i]) if none_i >= 0 else 0.0
            out.append(Prediction(self.classes_[int(i)], float(proba[row][int(i)]), 1.0 - p_none))
        return out

    # ------------------------------------------------------------- persist
    def save(self, path: str | Path) -> None:
        Path(path).write_bytes(pickle.dumps(self, protocol=5))

    @staticmethod
    def load(path: str | Path) -> "CandidateModel":
        return pickle.loads(Path(path).read_bytes())


def train_from_docs(docs: Iterable[dict], pad: int = 10) -> tuple[CandidateModel, int, int]:
    """Build (context, label) pairs from gold-annotated docs."""
    from .candidates import generate

    contexts: list[str] = []
    labels: list[str] = []
    for doc in docs:
        text = doc["text"]
        gold = doc["spans"]
        for cand in generate(text):
            label = NEGATIVE
            for g in gold:
                if g["category"] == cand.category_hint or (
                    cand.category_hint == "number"
                    and g["category"] in ("phone", "id_card", "bank_card")
                ):
                    if cand.start < g["end"] and g["start"] < cand.end:
                        label = g["category"]
                        break
            contexts.append(cand.context)
            labels.append(label)
    model = CandidateModel().fit(contexts, labels)
    return model, len(contexts), len(set(labels))
