"""
Base Adversarial Agent
All attack agents inherit from this. Each agent has a strategy,
executes mutations, scores itself, and can be killed if underperforming.
"""

import uuid
import time
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from core.engine import AttackEvent, AttackStatus, ExecutionTrace, CrucibleEngine


@dataclass
class AttackResult:
    success: bool
    mutation_applied: Dict[str, Any]
    failure_triggered: bool
    failure_description: Optional[str]
    affected_steps: List[str]
    recovery_time_ms: Optional[float]
    raw_output: Optional[str] = None


class BaseAdversarialAgent(ABC):
    """
    Every adversarial agent:
    - Has a specific attack strategy
    - Executes mutations against a target
    - Records results to the trace
    - Gets scored on effectiveness
    - Can die if consistently ineffective
    """

    attack_type: str = "base"
    description: str = "Base adversarial agent"

    def __init__(self, engine: CrucibleEngine, config: Optional[Dict] = None):
        self.engine = engine
        self.config = config or {}
        self.agent_state = engine.spawn_agent(self.attack_type)
        self.agent_id = self.agent_state.agent_id

    @abstractmethod
    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        """Generate a list of mutations to apply to the target workflow."""
        pass

    @abstractmethod
    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        """Apply a single mutation and return the result."""
        pass

    async def attack(self, target: Dict, trace: ExecutionTrace) -> List[AttackResult]:
        """
        Full attack cycle:
        1. Generate mutations
        2. Apply each mutation
        3. Record events
        4. Return results
        """
        if not self.agent_state.is_alive():
            return []

        mutations = await self.generate_mutations(target)
        results = []

        for mutation in mutations:
            event_id = f"evt_{uuid.uuid4().hex[:8]}"

            event = AttackEvent(
                event_id=event_id,
                agent_id=self.agent_id,
                attack_type=self.attack_type,
                target=target.get('name', 'unknown'),
                mutation=mutation,
                timestamp=time.time(),
                status=AttackStatus.RUNNING
            )

            try:
                result = await self.apply_mutation(target, mutation)
                event.status = AttackStatus.SUCCESS if result.failure_triggered else AttackStatus.FAILED
                event.result = {
                    "failure_triggered": result.failure_triggered,
                    "failure_description": result.failure_description,
                    "affected_steps": result.affected_steps,
                    "recovery_time_ms": result.recovery_time_ms,
                }
                results.append(result)

            except Exception as e:
                event.status = AttackStatus.ABORTED
                event.error = str(e)

            self.engine.record_event(trace, event)

        return results

    def reflect(self, results: List[AttackResult]) -> Dict:
        """
        Post-attack reflection.
        What worked? What didn't? Should strategy change?
        """
        if not results:
            return {"insight": "no_results", "strategy_change": False}

        triggered = [r for r in results if r.failure_triggered]
        rate = len(triggered) / len(results)

        insight = {
            "attack_type": self.attack_type,
            "total_mutations": len(results),
            "failures_triggered": len(triggered),
            "trigger_rate": round(rate, 3),
            "most_vulnerable_steps": self._find_vulnerable_steps(triggered),
            "strategy_change": rate < 0.1,
            "recommendation": self._recommend(rate)
        }
        return insight

    def _find_vulnerable_steps(self, triggered: List[AttackResult]) -> List[str]:
        steps = []
        for r in triggered:
            steps.extend(r.affected_steps)
        return list(set(steps))

    def _recommend(self, trigger_rate: float) -> str:
        if trigger_rate > 0.6:
            return "high_vulnerability_detected_prioritize_hardening"
        elif trigger_rate > 0.3:
            return "moderate_vulnerability_targeted_hardening_recommended"
        elif trigger_rate > 0.1:
            return "low_vulnerability_monitor_under_load"
        else:
            return "resilient_under_this_attack_type_expand_attack_surface"
