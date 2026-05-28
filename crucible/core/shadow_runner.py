"""
Shadow Runner
Manages shadow/production agent pairs across a full attack run.
Tracks evolutionary pressure, logs promotions, and surfaces winning mutations.

Architecture: shadow_runner sits inside runner.py only.
Engine, agents, scorer, memory don't know it exists.
"""

import time
from typing import Dict, List, Optional, Type

from agents.base_agent import BaseAdversarialAgent
from agents.shadow_agent import ShadowAgent
from core.engine import CrucibleEngine, ExecutionTrace


class ShadowRunner:
    """
    Maintains one ShadowAgent per attack type.
    On each attack cycle, runs both production and shadow agents.
    Promotes shadow to production config when it consistently outperforms.

    Promotion rule:
      shadow_trigger_rate > production_trigger_rate * 1.20 for 3+ consecutive runs
    """

    def __init__(self, engine: CrucibleEngine):
        self.engine = engine
        self.pairs: Dict[str, ShadowAgent] = {}
        self.evolutionary_log: List[Dict] = []
        self.total_promotions: int = 0

    # ── Registration ──────────────────────────────────────────────────────────

    def register(self, attack_type: str, agent_class: Type[BaseAdversarialAgent]):
        """Register an attack type for shadow tracking."""
        self.pairs[attack_type] = ShadowAgent(agent_class, self.engine)

    def register_all(self, registry: Dict[str, Type[BaseAdversarialAgent]]):
        """Register multiple attack types at once."""
        for attack_type, agent_class in registry.items():
            self.register(attack_type, agent_class)

    # ── Run ───────────────────────────────────────────────────────────────────

    async def run_attack(
        self,
        attack_type: str,
        target: Dict,
        trace: ExecutionTrace,
    ) -> Dict:
        """
        Run paired production + shadow attack for one attack type.
        Returns comparison result including promotion flag.
        """
        if attack_type not in self.pairs:
            return {}

        shadow_agent = self.pairs[attack_type]
        result = await shadow_agent.run_paired(target, trace)

        if result.get("should_promote"):
            promotion_event = {
                "event": "shadow_promoted",
                "attack_type": attack_type,
                "shadow_trigger_rate": result["shadow"]["trigger_rate"],
                "production_trigger_rate": result["production"]["trigger_rate"],
                "promotion_count": shadow_agent.promotion_count,
                "timestamp": time.time(),
            }
            self.evolutionary_log.append(promotion_event)
            self.total_promotions += 1

        return result

    async def run_all(self, target: Dict, trace: ExecutionTrace) -> Dict:
        """Run all registered attack types with shadow tracking."""
        results: Dict[str, Dict] = {}
        promotions: List[Dict] = []

        for attack_type in self.pairs:
            comparison = await self.run_attack(attack_type, target, trace)
            results[attack_type] = comparison
            if comparison.get("should_promote"):
                promotions.append({
                    "attack_type": attack_type,
                    "shadow_rate": comparison["shadow"]["trigger_rate"],
                    "production_rate": comparison["production"]["trigger_rate"],
                })

        return {
            "attack_results": results,
            "promotions_this_run": promotions,
            "total_promotions": self.total_promotions,
            "evolutionary_log": self.evolutionary_log[-20:],
        }

    # ── Reporting ─────────────────────────────────────────────────────────────

    def get_winning_strategies(self) -> Dict[str, Dict]:
        """Return attack types where shadow consistently beats production."""
        winners = {}
        for attack_type, shadow_agent in self.pairs.items():
            history = shadow_agent.run_history
            if len(history) >= 3:
                wins = sum(1 for r in history if r["shadow_wins"])
                win_rate = wins / len(history)
                if win_rate >= 0.67:
                    winners[attack_type] = {
                        "win_rate": round(win_rate, 3),
                        "runs": len(history),
                        "should_promote": shadow_agent._should_promote(),
                    }
        return winners

    def status(self) -> Dict:
        return {
            "registered_types": list(self.pairs.keys()),
            "total_promotions": self.total_promotions,
            "winning_strategies": self.get_winning_strategies(),
            "evolutionary_events": len(self.evolutionary_log),
        }
