"""Minimal public base class for OSS/local attack agents.

Independently authored — not derived from the proprietary Cloud base agent.
No subprocess execution, no mutation-scoring, no fitness/kill logic — this is
for static-analysis-style checks that don't need those. Cloud agents that do
real execution have their own, unrelated base class.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AttackResult:
    success: bool
    failure_triggered: bool
    failure_description: Optional[str] = None
    affected_steps: List[str] = field(default_factory=list)
    attack_type: str = ""
    mutation_applied: Dict[str, Any] = field(default_factory=dict)
    # ponytail: local agents don't measure recovery time (no real subprocess
    # timing to recover from); kept as None so CrucibleCloudSink.publish
    # (crucible/sinks/crucible_cloud_sink.py) can read this attribute without
    # an AttributeError — that AttributeError was the actual --publish-cloud
    # bug (READINESS_REPORT.md P0-1). Populate for real once a local agent
    # measures it.
    recovery_time_ms: Optional[float] = None
    # True only for the explicit "this target has no structure this check
    # knows how to read" marker (see BasicSupplyChainAgent.check) — lets the
    # scorer/runner distinguish "we looked at N steps and found nothing" from
    # "we found nothing to look at", so the latter never reports a clean
    # 100/A. Never set alongside a real (failure_triggered=True) finding.
    unsupported: bool = False


class BaseLocalAgent(ABC):
    """Every local/basic agent implements a single static `check`."""

    attack_type: str = "base"
    description: str = "Base local agent"

    @abstractmethod
    def check(self, target: Dict[str, Any]) -> List[AttackResult]:
        """Run the check against a parsed target, return zero or more findings."""
        raise NotImplementedError
