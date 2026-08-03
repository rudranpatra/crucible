"""
Threat Planner
Maps a normalized Threat onto an attack_plan — a list of Crucible's
existing attack_type strings (see runner.ATTACK_REGISTRY). No new agents
are created here; a threat either maps onto the six that exist, or it
stays UNTESTED.

Two-stage mapping, most specific first:

  1. Keyword rules   — substring match against title + description + technique.
                        Lets a threat like "OAuth Replay" route to the agents
                        that actually exercise replay-shaped conditions
                        (network + timing) even though no ReplayAgent exists.
  2. STRIDE fallback — the threat's `technique` (source category) maps to a
                        default set of agents for that STRIDE class.

Repudiation has no fallback: none of the six agents produce audit/logging
evidence, so repudiation threats are always UNTESTED unless a keyword rule
matches. That is a deliberate, honest gap — not a bug.
"""

import re
from typing import Dict, List, Pattern, Tuple

from threats.schema import Threat

# Ordered: first match wins ties are resolved by union, order doesn't gate correctness.
_KEYWORD_RULES: List[Tuple[Pattern, List[str]]] = [
    (re.compile(r"replay"), ["network", "timing"]),
    (re.compile(r"race condition|reorder|out[- ]of[- ]order|sequenc"), ["reorder"]),
    (re.compile(r"timing|timeout|delay"), ["timing"]),
    (re.compile(r"denial of service|\bdos\b|flood|latency"), ["network", "timing"]),
    (re.compile(r"network|man[- ]in[- ]the[- ]middle|\bmitm\b"), ["network"]),
    (re.compile(r"supply chain|third[- ]party|pinned|commit sha|unpinned"), ["supply_chain"]),
    (re.compile(r"dependency|package|transitive|resolver"), ["dependency"]),
    (re.compile(r"privilege|permission|token scope|rbac|least[- ]privilege"), ["supply_chain"]),
    (re.compile(r"injection"), ["supply_chain", "env"]),
    (re.compile(r"secret|credential|api key|environment variable|\benv\b"), ["env"]),
]

# STRIDE technique -> default attack types when no keyword rule matches.
_STRIDE_FALLBACK: Dict[str, List[str]] = {
    "spoofing": ["supply_chain"],
    "tampering": ["supply_chain", "dependency"],
    "repudiation": [],
    "informationdisclosure": ["env"],
    "denialofservice": ["network", "timing"],
    "elevationofprivilege": ["supply_chain"],
}


def _normalize_technique(raw: str) -> str:
    return re.sub(r"[\s_-]+", "", raw.strip().lower())


class ThreatPlanner:
    """Builds attack_plan[] for a list of threats. Never invents new agents."""

    def plan(self, threat: Threat) -> Threat:
        text = f"{threat.title} {threat.description} {threat.technique}".lower()

        matched: List[str] = []
        matched_rules: List[str] = []
        for pattern, attack_types in _KEYWORD_RULES:
            if pattern.search(text):
                for at in attack_types:
                    if at not in matched:
                        matched.append(at)
                matched_rules.append(pattern.pattern)

        if matched:
            threat.attack_plan = matched
            threat.plan_rationale = f"keyword match: {', '.join(matched_rules)}"
            return threat

        technique_key = _normalize_technique(threat.technique)
        fallback = _STRIDE_FALLBACK.get(technique_key)

        if fallback:
            threat.attack_plan = list(fallback)
            threat.plan_rationale = f"STRIDE fallback: {technique_key}"
        elif technique_key in _STRIDE_FALLBACK:
            # Recognized technique (e.g. repudiation) with no agent coverage.
            threat.attack_plan = []
            threat.plan_rationale = f"no agent covers technique: {technique_key}"
        else:
            threat.attack_plan = []
            threat.plan_rationale = f"unrecognized framework/technique: {threat.technique!r}"

        return threat

    def plan_all(self, threats: List[Threat]) -> List[Threat]:
        return [self.plan(t) for t in threats]
