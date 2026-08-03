"""
Normalized Threat Schema
Framework-agnostic representation of a single threat, independent of
whatever tool produced it (Threat Dragon today; anything else later).

    Threat
     |-- id
     |-- title
     |-- description
     |-- framework      (metadata: source modeling framework, e.g. "STRIDE")
     |-- technique       (metadata: source threat category/type)
     |-- severity
     |-- attack_plan[]   (attack_type strings, filled in by the planner)
     |-- evidence[]      (filled in by the validator after execution)
     `-- status          (PASS | FAIL | UNTESTED)
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class ThreatStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    UNTESTED = "untested"


@dataclass
class Evidence:
    """A single piece of execution evidence attached to a threat."""
    attack_type: str
    trace_id: str
    failure_triggered: bool
    description: Optional[str] = None
    raw_output: Optional[str] = None
    replay_command: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Threat:
    id: str
    title: str
    description: str = ""
    framework: str = "STRIDE"
    technique: str = ""
    severity: str = "medium"
    component: str = ""
    source: Dict[str, Any] = field(default_factory=dict)
    attack_plan: List[str] = field(default_factory=list)
    plan_rationale: str = ""
    evidence: List[Evidence] = field(default_factory=list)
    status: ThreatStatus = ThreatStatus.UNTESTED

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["evidence"] = [e.to_dict() for e in self.evidence]
        return d


@dataclass
class ThreatValidationReport:
    trace_id: str
    target: str
    threats: List[Threat]
    replay_command: str
    seed: Optional[int] = None

    @property
    def passed(self) -> int:
        return sum(1 for t in self.threats if t.status == ThreatStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.threats if t.status == ThreatStatus.FAIL)

    @property
    def untested(self) -> int:
        return sum(1 for t in self.threats if t.status == ThreatStatus.UNTESTED)

    @property
    def coverage(self) -> float:
        """% of imported threats that were actually executed (pass or fail, not untested)."""
        if not self.threats:
            return 0.0
        tested = len(self.threats) - self.untested
        return round(100.0 * tested / len(self.threats), 1)

    def failure_points(self) -> List[str]:
        """Failure descriptions from FAIL threats — same shape SARIF/PR-comment already consume."""
        points = []
        for t in self.threats:
            if t.status == ThreatStatus.FAIL:
                for e in t.evidence:
                    if e.failure_triggered and e.description:
                        points.append(e.description)
        return points

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "target": self.target,
            "replay_command": self.replay_command,
            "seed": self.seed,
            "coverage": self.coverage,
            "passed": self.passed,
            "failed": self.failed,
            "untested": self.untested,
            "threats": [t.to_dict() for t in self.threats],
        }
