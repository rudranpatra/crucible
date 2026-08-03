"""
Threat Validator
Executes each threat's attack_plan using Crucible's existing attack agents
and existing trace infrastructure, then attributes the resulting evidence
back to the threats that requested it.

Agents are deduplicated and run once per attack_type needed across the
whole threat set — not once per threat — then results are re-attributed.
This reuses the exact same agent/engine/trace machinery `crucible attack`
uses; no new evidence format, no new execution model.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from core.engine import CrucibleEngine
from runner import ATTACK_REGISTRY
from memory.trace_memory import TraceMemory
from threats.schema import Evidence, Threat, ThreatStatus, ThreatValidationReport

logger = logging.getLogger(__name__)


class ThreatValidator:
    """
    Runs the attack agents a threat model calls for and turns the results
    into PASS / FAIL / UNTESTED evidence per threat.
    """

    def __init__(self, traces_dir: str = "traces", agent_timeout: float = 30.0):
        self.engine = CrucibleEngine()
        self.memory = TraceMemory(traces_dir=traces_dir)
        self._agent_timeout = agent_timeout

    async def validate(
        self,
        threats: List[Threat],
        target: Dict,
        seed: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> ThreatValidationReport:
        needed_attacks = sorted({
            at for t in threats for at in t.attack_plan if at in ATTACK_REGISTRY
        })

        trace = self.engine.begin_trace(target.get("name", "unknown"))
        results_by_type = await self._run_agents(needed_attacks, target, trace)

        for threat in threats:
            self._attribute(threat, results_by_type, trace.trace_id)

        all_results = [r for rs in results_by_type.values() for r in rs]
        failure_points = [
            r.failure_description for r in all_results
            if r.failure_triggered and r.failure_description
        ]
        blast_radius = list({
            step for r in all_results if r.failure_triggered for step in r.affected_steps
        })

        tested = len(threats) - sum(1 for t in threats if t.status == ThreatStatus.UNTESTED)
        passed = sum(1 for t in threats if t.status == ThreatStatus.PASS)
        pass_rate = round(100.0 * passed / tested, 1) if tested else 0.0

        finalized = self.engine.finalize_trace(
            trace, score=pass_rate, failure_points=failure_points, blast_radius=blast_radius,
        )

        report = ThreatValidationReport(
            trace_id=finalized.trace_id,
            target=target.get("name", "unknown"),
            threats=threats,
            replay_command=finalized.replay_command,
            seed=seed,
        )

        for threat in report.threats:
            for evidence in threat.evidence:
                evidence.replay_command = finalized.replay_command

        trace_dict = finalized.to_dict()
        trace_dict["resilience_score"] = pass_rate
        trace_dict["failure_points"] = failure_points
        trace_dict["blast_radius"] = blast_radius
        trace_dict["seed"] = seed
        trace_dict["threats"] = report.to_dict()["threats"]
        trace_dict["threat_coverage"] = report.coverage

        self.memory.store(trace_dict, tags=(tags or []) + ["threat-validation"])

        return report

    # ── internals ─────────────────────────────────────────────────────────────

    async def _run_agents(self, attack_names: List[str], target: Dict, trace) -> Dict[str, list]:
        results_by_type: Dict[str, list] = {name: [] for name in attack_names}
        if not attack_names:
            return results_by_type

        agents = [(name, ATTACK_REGISTRY[name](self.engine)) for name in attack_names]

        async def _run_one(name: str, agent):
            try:
                results = await asyncio.wait_for(
                    agent.attack(target, trace), timeout=self._agent_timeout,
                )
                return name, results
            except asyncio.TimeoutError:
                logger.warning("threat_validation_timeout agent_id=%s attack=%s", agent.agent_id, name)
                return name, []
            except Exception:
                logger.exception("threat_validation_agent_error attack=%s", name)
                return name, []

        gathered = await asyncio.gather(*[_run_one(name, agent) for name, agent in agents])
        for name, results in gathered:
            results_by_type[name] = results
        return results_by_type

    def _attribute(self, threat: Threat, results_by_type: Dict[str, list], trace_id: str):
        if not threat.attack_plan:
            threat.status = ThreatStatus.UNTESTED
            return

        evidence: List[Evidence] = [
            Evidence(
                attack_type=attack_type,
                trace_id=trace_id,
                failure_triggered=r.failure_triggered,
                description=r.failure_description,
                raw_output=r.raw_output,
            )
            for attack_type in threat.attack_plan
            for r in results_by_type.get(attack_type, [])
        ]

        threat.evidence = evidence

        if not evidence:
            threat.status = ThreatStatus.UNTESTED
            threat.plan_rationale += " (agent execution produced no evidence)"
        elif any(e.failure_triggered for e in evidence):
            threat.status = ThreatStatus.FAIL
        else:
            threat.status = ThreatStatus.PASS
