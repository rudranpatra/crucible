"""Basic OSS/local resilience scorer.

Independently authored — not derived from the proprietary Cloud scoring
formula (`ResilienceScorer`/`DarwinScorer`). Simple and transparent on
purpose: a flat deduction per triggered finding, floored at 0. Cloud's
scoring accounts for attack severity weighting, historical drift, and
evolutionary agent fitness — none of that is reproduced here.
"""
from typing import Any, List

DEDUCTION_PER_FINDING = 15.0


class BasicScorer:
    def score(self, findings: List[Any]) -> float:
        triggered = sum(1 for f in findings if getattr(f, "failure_triggered", False))
        return max(0.0, 100.0 - triggered * DEDUCTION_PER_FINDING)

    @staticmethod
    def grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"
