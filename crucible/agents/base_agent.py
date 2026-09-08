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


class BaseLocalAgent(ABC):
    """Every local/basic agent implements a single static `check`."""

    attack_type: str = "base"
    description: str = "Base local agent"

    @abstractmethod
    def check(self, target: Dict[str, Any]) -> List[AttackResult]:
        """Run the check against a parsed target, return zero or more findings."""
        raise NotImplementedError
