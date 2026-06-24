"""
Shadow Agent
Mirrors a production agent with alternative mutations on a target copy.
When shadow consistently outperforms production (>20% over 3+ runs), it stages
for promotion — making this evolutionary, not just adversarial.
"""

import copy
import random
import time
from typing import Dict, List, Type

from agents.base_agent import BaseAdversarialAgent, AttackResult
from core.engine import CrucibleEngine, ExecutionTrace


class ShadowAgent:
    """
    Wraps a production agent class and runs an alternative mutant strategy
    on a deep copy of the target so the real target is never touched.

    On each run, compares trigger_rate of shadow vs production.
    Records history. Flags promotion when shadow consistently wins.
    """

    PROMOTION_THRESHOLD = 0.20   # shadow must outperform by this margin
    PROMOTION_MIN_RUNS = 3       # consecutive wins needed to promote

    def __init__(
        self,
        agent_class: Type[BaseAdversarialAgent],
        engine: CrucibleEngine,
        perturbation: float = 0.25,
    ):
        self.agent_class = agent_class
        self.engine = engine
        self.perturbation = perturbation
        self.run_history: List[Dict] = []
        self.promotion_count: int = 0

        self.production = agent_class(engine)
        self.shadow = agent_class(engine)
        self._last_perturbation: Dict = {}
        self.winning_perturbation_configs: List[Dict] = []

    # ── Core run ──────────────────────────────────────────────────────────────

    async def run_paired(self, target: Dict, trace: ExecutionTrace) -> Dict:
        """
        Run production and shadow agents.
        Shadow works on a perturbed copy so it never touches the real target.
        Returns a comparison dict including whether shadow should be promoted.
        """
        shadow_target = self._perturb_target(copy.deepcopy(target))

        prod_results = await self.production.attack(target, trace)
        shadow_results = await self.shadow.attack(shadow_target, trace)

        prod_rate = self._trigger_rate(prod_results)
        shadow_rate = self._trigger_rate(shadow_results)
        shadow_wins = shadow_rate > prod_rate * (1 + self.PROMOTION_THRESHOLD)

        run_record = {
            "timestamp": time.time(),
            "production_trigger_rate": round(prod_rate, 4),
            "shadow_trigger_rate": round(shadow_rate, 4),
            "shadow_wins": shadow_wins,
            "perturbation_applied": self._last_perturbation,
        }
        self.run_history.append(run_record)

        if shadow_wins and self._last_perturbation:
            self.winning_perturbation_configs.append(self._last_perturbation)
            self.winning_perturbation_configs = self.winning_perturbation_configs[-5:]

        should_promote = self._should_promote()
        if should_promote:
            self.promotion_count += 1

        return {
            "attack_type": self.production.attack_type,
            "production": {
                "agent_id": self.production.agent_id,
                "results": prod_results,
                "trigger_rate": prod_rate,
                "reflection": self.production.reflect(prod_results),
            },
            "shadow": {
                "agent_id": self.shadow.agent_id,
                "results": shadow_results,
                "trigger_rate": shadow_rate,
                "reflection": self.shadow.reflect(shadow_results),
            },
            "shadow_wins": shadow_wins,
            "should_promote": should_promote,
            "promotion_count": self.promotion_count,
            "run_history": self.run_history[-10:],
        }

    # ── Promotion logic ───────────────────────────────────────────────────────

    def _should_promote(self) -> bool:
        if len(self.run_history) < self.PROMOTION_MIN_RUNS:
            return False
        recent = self.run_history[-self.PROMOTION_MIN_RUNS:]
        return all(r["shadow_wins"] for r in recent)

    # ── Target perturbation ───────────────────────────────────────────────────

    def _perturb_target(self, target: Dict) -> Dict:
        """
        Perturb the shadow target. When we have winning perturbation configs, exploit
        that direction (with small random variation) rather than exploring blindly.
        This closes the evolutionary feedback loop: wins inform subsequent runs.
        """
        config: Dict = {}

        if "timeout_ms" in target and isinstance(target["timeout_ms"], (int, float)):
            if self.winning_perturbation_configs:
                # Exploit: perturb in the direction that previously won, with small jitter
                base_delta = self.winning_perturbation_configs[-1].get('timeout_delta', 0.0)
                exploration = self.perturbation * 0.3
                delta = base_delta + random.uniform(-exploration, exploration)
            else:
                delta = random.uniform(-self.perturbation, self.perturbation)
            target["timeout_ms"] = max(100, int(target["timeout_ms"] * (1 + delta)))
            config['timeout_delta'] = round(delta, 4)

        if "steps" in target and isinstance(target["steps"], list):
            steps = target["steps"][:]
            random.shuffle(steps)
            target["steps"] = steps

        new_retry = not target.get("has_retry_logic", False)
        target["has_retry_logic"] = new_retry
        config['has_retry_logic'] = new_retry

        self._last_perturbation = config
        return target

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _trigger_rate(results: List[AttackResult]) -> float:
        if not results:
            return 0.0
        return sum(1 for r in results if r.failure_triggered) / len(results)
