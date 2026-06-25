"""
Crucible Runner
Orchestrates a full adversarial attack run against a target pipeline.
This is the only place that knows about all layers (engine, agents, scorer, memory, dashboard).
"""

import asyncio
import logging
import random
from typing import List, Optional, Dict
from pathlib import Path

from core.engine import CrucibleEngine  # noqa: E402
from attacks.strategies import (  # noqa: E402
    TimingAgent, EnvCorruptionAgent, StepReorderAgent,
    NetworkChaosAgent, DependencyDriftAgent, SupplyChainAgent
)
from scoring.scorer import ResilienceScorer  # noqa: E402
from scoring.darwin_scorer import DarwinScorer  # noqa: E402
from memory.trace_memory import TraceMemory  # noqa: E402
from integrations.github_actions.parser import GitHubActionsParser, create_demo_target  # noqa: E402
from integrations.gitlab.parser import GitLabCIParser  # noqa: E402
from integrations.playwright.parser import PlaywrightParser  # noqa: E402

logger = logging.getLogger(__name__)


ATTACK_REGISTRY = {
    'timing': TimingAgent,
    'env': EnvCorruptionAgent,
    'reorder': StepReorderAgent,
    'network': NetworkChaosAgent,
    'dependency': DependencyDriftAgent,
    'supply_chain': SupplyChainAgent,
}

ALL_ATTACKS = list(ATTACK_REGISTRY.keys())


class CrucibleRunner:
    """
    Runs a complete adversarial attack cycle:
    1. Parse target
    2. Spawn agents
    3. Execute attacks  (+ optional shadow tracking)
    4. Score resilience (+ optional darwin scoring)
    5. Store trace
    6. Return report

    Architecture rule: runner is the ONLY place that orchestrates all layers.
    Engine, agents, scorer, memory don't import each other.
    """

    def __init__(
        self,
        traces_dir: str = "traces",
        verbose: bool = True,
        use_dashboard: bool = False,
        use_shadow: bool = False,
        agent_timeout: float = 30.0,
    ):
        self.engine = CrucibleEngine()
        self.scorer = ResilienceScorer()
        self.memory = TraceMemory(traces_dir=traces_dir)
        self.darwin = DarwinScorer(
            state_file=str(Path(traces_dir) / "darwin_state.json")
        )
        self.verbose = verbose
        self._agent_timeout = agent_timeout

        self.dashboard = None
        if use_dashboard:
            from dashboard.terminal import CrucibleDashboard
            self.dashboard = CrucibleDashboard()

        self.shadow_runner = None
        if use_shadow:
            from core.shadow_runner import ShadowRunner
            self.shadow_runner = ShadowRunner(self.engine)
            self.shadow_runner.register_all(ATTACK_REGISTRY)

    # ── Main run ──────────────────────────────────────────────────────────────

    async def run(
        self,
        target_path: Optional[str] = None,
        attacks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        demo_mode: bool = False,
        github_comment: bool = False,
        seed: Optional[int] = None,
    ) -> Dict:
        attacks = attacks or ALL_ATTACKS
        tags = tags or []

        if seed is None:
            seed = random.randint(0, 2 ** 32 - 1)
        random.seed(seed)

        if demo_mode or not target_path:
            target = create_demo_target()
            self._log("Running in demo mode with synthetic CI/CD pipeline")
        else:
            target = self._parse_target(target_path)
            self._log(
                f"Loaded target: {target['name']} "
                f"({len(target['steps'])} steps, {len(attacks)} attack types)"
            )

        trace = self.engine.begin_trace(target['name'])

        if self.dashboard:
            self.dashboard.print_banner(target['name'], trace.trace_id)
        else:
            self._log(f"Trace ID: {trace.trace_id}")
            self._log(f"Attack types: {', '.join(attacks)}")
            self._log("")

        all_results = []
        agent_reflections = []
        shadow_summary = {}

        # ── Filter unknown attack types upfront ───────────────────────────────
        valid_attacks = []
        for attack_name in attacks:
            if attack_name not in ATTACK_REGISTRY:
                self._log(f"Unknown attack type: {attack_name} — skipping")
            else:
                valid_attacks.append(attack_name)

        if self.shadow_runner:
            # Shadow mode: run sequentially (shadow runner manages its own pairing)
            for attack_name in valid_attacks:
                comparison = await self.shadow_runner.run_attack(attack_name, target, trace)
                if comparison:
                    prod = comparison.get("production", {})
                    results = prod.get("results", [])
                    shadow_summary[attack_name] = comparison
                    if comparison.get("should_promote"):
                        self.darwin.record_promotion(
                            attack_name,
                            comparison["shadow"]["trigger_rate"],
                            comparison["production"]["trigger_rate"],
                        )
                        if self.dashboard:
                            self.dashboard.print_shadow_promotion(
                                attack_name,
                                comparison["shadow"]["trigger_rate"],
                                comparison["production"]["trigger_rate"],
                            )
                    all_results.extend(results)
        else:
            # Standard mode: spawn all agents, run attacks concurrently
            agents_to_run = [
                (name, ATTACK_REGISTRY[name](self.engine))
                for name in valid_attacks
            ]

            for _, agent in agents_to_run:
                if self.dashboard:
                    self.dashboard.print_agent_deployed(
                        agent.agent_id, agent.attack_type, agent.description
                    )
                else:
                    self._log(f"Deploying {agent.attack_type} agent [{agent.agent_id}]...")
                    self._log(f"  {agent.description}")

            async def _run_one(attack_name: str, agent):
                try:
                    return attack_name, agent, await asyncio.wait_for(
                        agent.attack(target, trace),
                        timeout=self._agent_timeout,
                    ), None
                except asyncio.TimeoutError:
                    logger.warning("agent_timeout agent_id=%s attack=%s", agent.agent_id, attack_name)
                    return attack_name, agent, [], "timeout"
                except Exception as exc:
                    logger.exception("agent_error agent_id=%s attack=%s", agent.agent_id, attack_name)
                    return attack_name, agent, [], str(exc)

            gathered = await asyncio.gather(*[_run_one(n, a) for n, a in agents_to_run])

            for attack_name, agent, results, error in gathered:
                agent_id = agent.agent_id
                agent_state = self.engine.agents[agent_id]

                if error:
                    self._log(f"  Agent {agent_id} [{attack_name}] aborted: {error}")
                    all_results.extend(results)
                    continue

                triggered = [r for r in results if r.failure_triggered]
                fitness = agent_state.fitness_score
                is_alive = agent_state.is_alive()

                if self.dashboard:
                    critical_hits = [r for r in results if r.failure_triggered]
                    for hit in critical_hits[:1]:
                        self.dashboard.print_kill_screen(
                            agent_id, attack_name,
                            hit.failure_description or "unknown failure",
                            trace.trace_id,
                        )
                    failure_descs = [r.failure_description for r in triggered if r.failure_description]
                    self.dashboard.print_attack_complete(
                        agent_id, attack_name, len(results),
                        len(triggered), fitness, is_alive, failure_descs
                    )
                    if not is_alive:
                        self.dashboard.print_agent_obituary(
                            agent_id, attack_name, fitness, len(results), len(triggered)
                        )
                else:
                    self._log(
                        f"  Mutations: {len(results)} | Failures triggered: {len(triggered)}"
                    )
                    if triggered:
                        for r in triggered[:2]:
                            self._log(f"  ! {r.failure_description}")

                reflection = agent.reflect(results)
                agent_reflections.append(reflection)

                trigger_rate = len(triggered) / max(1, len(results))
                self.darwin.record_run(attack_name, trigger_rate)

                if not is_alive:
                    self._log(f"  Agent {agent_id} terminated. Fitness: {fitness}")
                else:
                    self._log(f"  Agent fitness: {fitness} [ALIVE]")
                self._log("")

                all_results.extend(results)

        # ── Scoring ───────────────────────────────────────────────────────────

        if self.dashboard:
            self.dashboard.print_section("Scoring resilience...")
        else:
            self._log("Scoring resilience...")

        attack_types_run = list(set(r.attack_type for r in all_results if r.attack_type)) or attacks

        report = self.scorer.score(all_results, attack_types_run)

        failure_points = [
            r.failure_description for r in all_results
            if r.failure_triggered and r.failure_description
        ]
        blast_radius = list(set(
            step
            for r in all_results if r.failure_triggered
            for step in r.affected_steps
        ))

        finalized = self.engine.finalize_trace(
            trace,
            score=report.score,
            failure_points=failure_points,
            blast_radius=blast_radius,
        )

        trace_dict = finalized.to_dict()
        trace_dict['resilience_score'] = report.score
        trace_dict['failure_points'] = failure_points
        trace_dict['blast_radius'] = blast_radius
        trace_dict['agent_reflections'] = agent_reflections
        trace_dict['seed'] = seed

        stored = self.memory.store(trace_dict, tags=tags)

        result = {
            "trace_id": finalized.trace_id,
            "target": target['name'],
            "resilience_score": report.score,
            "grade": report.grade,
            "components": report.components,
            "failure_count": len(failure_points),
            "blast_radius": blast_radius,
            "top_vulnerabilities": report.top_vulnerabilities,
            "replay_command": finalized.replay_command,
            "engine_status": self.engine.engine_status(),
            "agent_reflections": agent_reflections,
            "shadow_summary": shadow_summary,
            "seed": seed,
            "failure_points": failure_points,
        }

        # ── Output ────────────────────────────────────────────────────────────

        darwin_report = self.darwin.get_species_report() if self.darwin.state["species"] else None

        if self.dashboard:
            self.dashboard.print_score_update(report.score, report.grade)
            self.dashboard.print_final_report(result, self.engine.engine_status(), darwin_report)
        else:
            self._log("=" * 50)
            self._log(report.summary())
            self._log("=" * 50)
            self._log(f"\nTrace saved: {stored.replay_command}")

            dead_agents = self.engine.get_dead_agents()
            if dead_agents:
                self._log(f"\nAgent cemetery: {len(dead_agents)} agent(s) terminated")
                for dead in dead_agents:
                    self._log(f"  RIP {dead.agent_id} — fitness: {dead.fitness_score}")

        # ── GitHub PR comment ─────────────────────────────────────────────────

        if github_comment:
            self._post_github_comment(result)

        return result

    # ── Replay & patterns ─────────────────────────────────────────────────────

    def replay(self, trace_id: str) -> Dict:
        stored = self.memory.load(trace_id)
        if not stored:
            return {"error": f"Trace {trace_id} not found"}
        return {
            "trace_id": stored.trace_id,
            "target": stored.target,
            "attack_types": stored.attack_types,
            "resilience_score": stored.resilience_score,
            "failure_count": stored.failure_count,
            "blast_radius": stored.blast_radius,
            "failure_points": stored.failure_points,
            "created_at": stored.created_at,
            "replay_command": stored.replay_command,
            "tags": stored.tags,
            "seed": stored.raw_trace.get('seed'),
        }

    def patterns(self) -> Dict:
        return self.memory.get_failure_patterns()

    def evolution(self) -> Dict:
        return {
            "species": self.darwin.get_species_report(),
            "dominant": self.darwin.get_dominant_species(),
            "extinct": self.darwin.get_extinct_species(),
            "promotions": self.darwin.get_evolutionary_log(),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_target(self, target_path: str) -> Dict:
        path = Path(target_path)
        playwright_suffixes = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py"}

        if path.suffix.lower() in playwright_suffixes:
            return PlaywrightParser().parse_file(target_path)

        if path.name.startswith('.gitlab-ci') or path.name == 'gitlab-ci.yml':
            return GitLabCIParser().parse_file(target_path)

        return GitHubActionsParser().parse_file(target_path)

    def _log(self, msg: str):
        if self.verbose and not self.dashboard:
            logger.info(msg)

    def _post_github_comment(self, result: Dict):
        try:
            from integrations.github.commenter import GitHubCommenter
            commenter = GitHubCommenter()
            if commenter.is_configured():
                ok = commenter.post_pr_comment(result)
                if ok:
                    self._log("GitHub PR comment posted.")
                else:
                    self._log("GitHub PR comment failed (check GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER).")
            else:
                self._log("GitHub commenter not configured (set GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER).")
        except Exception as e:
            self._log(f"GitHub comment error: {e}")


async def main():
    import sys
    runner = CrucibleRunner()

    if len(sys.argv) > 1 and sys.argv[1] == 'demo':
        result = await runner.run(demo_mode=True)
    elif len(sys.argv) > 1:
        result = await runner.run(target_path=sys.argv[1])
    else:
        result = await runner.run(demo_mode=True)

    return result


if __name__ == "__main__":
    asyncio.run(main())
