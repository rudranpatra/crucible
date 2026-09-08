"""Minimal local engine for crucible-gym's OSS/offline mode.

Independently authored — not derived from the proprietary Cloud engine.
Single-pass only: no agent fitness tracking, no kill/promote logic, no
darwin/evolution state. It exists to give the local basic attacks somewhere
to record a trace; the interesting orchestration (survival scoring, shadow
mode, threat validation) is a Cloud capability.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LocalAttackEvent:
    agent_id: str
    attack_type: str
    success: bool
    failure_triggered: bool
    description: Optional[str]
    timestamp: float = field(default_factory=time.time)


@dataclass
class LocalTrace:
    trace_id: str
    target: str
    started_at: float = field(default_factory=time.time)
    events: List[LocalAttackEvent] = field(default_factory=list)
    finished_at: Optional[float] = None
    resilience_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "target": self.target,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "resilience_score": self.resilience_score,
            "events": [
                {
                    "agent_id": e.agent_id,
                    "attack_type": e.attack_type,
                    "success": e.success,
                    "failure_triggered": e.failure_triggered,
                    "description": e.description,
                    "timestamp": e.timestamp,
                }
                for e in self.events
            ],
        }


class LocalEngine:
    """Records a single attack run. No cross-run state, no scoring logic —
    that lives in `scoring/basic_scorer.py`."""

    def begin_trace(self, target: str) -> LocalTrace:
        return LocalTrace(trace_id=f"local_{uuid.uuid4().hex[:10]}", target=target)

    def spawn_agent_id(self, attack_type: str) -> str:
        return f"{attack_type}_{uuid.uuid4().hex[:6]}"

    def record_event(self, trace: LocalTrace, event: LocalAttackEvent) -> None:
        trace.events.append(event)

    def finalize_trace(self, trace: LocalTrace, score: float) -> LocalTrace:
        trace.finished_at = time.time()
        trace.resilience_score = score
        return trace
