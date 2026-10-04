# Confidence scorer for Local AI responses
"""Confidence scoring for small-model answers (no logprobs needed).

Combines two signals:
  - retrieval score: how well the knowledge base matched the question (0..1)
  - self-rating: the model's own 0-9 score for how well CONTEXT supports its answer
A hedged answer ("not sure", "text OP") is capped low so Claude gets a chance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
#
# _HEDGE = re.compile(
#     r"\b(not sure|don'?t know|do not know|cannot|can'?t (say|answer|help)|unable|"
#     r"no information|text op)\b",
#     re.I,
# )

_HEDGE = re.compile(
    r"\b(not sure|don'?t know|do not know|cannot|can'?t (say|answer|help)|unable|"
    r"no information|text op|jani na|sure na|pata nei|pata nahi|pata nahin|malum nahi)\b",
    re.I,
)

@dataclass(frozen=True)
class Confidence:
    score: float        # 0..1
    escalate: bool
    reason: str


def evaluate(
    text: str,
    retrieval_score: float,
    self_rating: int | None,
    threshold: float,
) -> Confidence:
    if not text.strip():
        return Confidence(0.0, True, "empty answer")

    r = max(0.0, min(1.0, retrieval_score))
    if self_rating is None:
        # Model skipped the CONF line: the answer is unverified, so it can't pass alone.
        score = 0.9 * r
        reason = f"retrieval={r:.2f}, no self-rating"
    else:
        s = max(0, min(9, self_rating))
        score = 0.5 * r + 0.5 * (s / 9)
        reason = f"retrieval={r:.2f}, self={s}/9"

    if _HEDGE.search(text):
        score = min(score, 0.3)
        reason += ", hedged"

    score = round(score, 3)
    return Confidence(score, score < threshold, reason)