"""
Crucible Runner — mode-aware.

Local mode runs the basic OSS engine in-process (crucible.core.local_engine +
crucible.attacks.basic_strategies). Cloud mode POSTs to Crucible Cloud's
`/v1/runs` and returns its result unchanged. Mode selection is always
explicit — via `mode=` / `--engine cloud`, or the `CRUCIBLE_ENGINE` env var —
never a silent automatic fallback between the two.
"""
import json
import logging
import os
import random
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from crucible import __version__ as CRUCIBLE_VERSION
from crucible.core.local_engine import LocalAttackEvent, LocalEngine
from crucible.attacks.basic_strategies import BasicSupplyChainAgent
from crucible.scoring.basic_scorer import BasicScorer
from crucible.integrations.github_actions.parser import GitHubActionsParser, create_demo_target
from crucible.integrations.gitlab.parser import GitLabCIParser
from crucible.integrations.playwright.parser import PlaywrightParser

logger = logging.getLogger(__name__)

# Local names kept close to the legacy attack-type names so existing
# `--attacks supply_chain,...` invocations still find a match. Attack types
# with no local equivalent (dependency, env, timing, network, reorder) are
# silently skipped in local mode — same "unknown attack type, skipping"
# behavior the engine already had, now also covering "known to Cloud, not
# available locally".
LOCAL_ATTACK_REGISTRY = {
    "supply_chain": BasicSupplyChainAgent,
    "supply_chain_basic": BasicSupplyChainAgent,
}
ALL_ATTACKS = list(LOCAL_ATTACK_REGISTRY.keys())


class CloudExecutionError(RuntimeError):
    pass


class CrucibleRunner:
    def __init__(
        self,
        traces_dir: str = "traces",
        verbose: bool = True,
        use_dashboard: bool = False,
        use_shadow: bool = False,
        agent_timeout: float = 30.0,
        mode: Optional[str] = None,
        cloud_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.verbose = verbose
        self.mode = mode or os.environ.get("CRUCIBLE_ENGINE", "local")
        if self.mode not in ("local", "cloud"):
            raise ValueError(f"unknown engine mode: {self.mode!r} (expected 'local' or 'cloud')")
        self.cloud_url = cloud_url or os.environ.get("CRUCIBLE_CLOUD_URL")
        self.api_key = api_key or os.environ.get("CRUCIBLE_API_KEY")

        if use_shadow:
            raise NotImplementedError("shadow mode is a Cloud capability; run with mode='cloud'")
        if use_dashboard:
            raise NotImplementedError(
                "--rich is not implemented in this release for either engine mode — "
                "it rendered live per-agent progress in the old in-process engine, "
                "which no longer applies to a single request/response run"
            )

        self.engine = LocalEngine()
        self.scorer = BasicScorer()

    async def run(
        self,
        target_path: Optional[str] = None,
        attacks: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        demo_mode: bool = False,
        github_comment: bool = False,
        seed: Optional[int] = None,
        on_attack_result: Optional[Callable[[str, int, Any], None]] = None,
    ) -> Dict:
        if seed is None:
            seed = random.randint(0, 2 ** 32 - 1)
        random.seed(seed)

        if self.mode == "cloud":
            return self._run_cloud(target_path, attacks, demo_mode, seed)
        return self._run_local(target_path, attacks, demo_mode, seed, on_attack_result)

    # ── Local execution ──────────────────────────────────────────────────────

    def _run_local(self, target_path, attacks, demo_mode, seed, on_attack_result=None) -> Dict:
        attacks = attacks or ALL_ATTACKS
        if demo_mode or not target_path:
            target = create_demo_target()
        else:
            target = self._parse_target(target_path)

        trace = self.engine.begin_trace(target["name"])

        valid_attacks = [a for a in attacks if a in LOCAL_ATTACK_REGISTRY]
        skipped = [a for a in attacks if a not in LOCAL_ATTACK_REGISTRY]
        for name in skipped:
            self._log(f"'{name}' is not available in local mode — run with mode='cloud' for full coverage")

        findings = []
        index = 0
        for attack_name in dict.fromkeys(valid_attacks):  # de-dupe, keep order
            agent = LOCAL_ATTACK_REGISTRY[attack_name]()
            agent_findings = agent.check(target)
            findings.extend(agent_findings)
            for f in agent_findings:
                self.engine.record_event(trace, LocalAttackEvent(
                    agent_id=self.engine.spawn_agent_id(attack_name),
                    attack_type=attack_name,
                    success=f.success,
                    failure_triggered=f.failure_triggered,
                    description=f.failure_description,
                ))
                if on_attack_result:
                    try:
                        on_attack_result(trace.trace_id, index, f)
                    except Exception:
                        logger.exception("on_attack_result callback failed; continuing run")
                index += 1

        score = self.scorer.score(findings)
        grade = self.scorer.grade(score)
        self.engine.finalize_trace(trace, score)

        failure_points = [f.failure_description for f in findings if f.failure_triggered and f.failure_description]
        blast_radius = list({step for f in findings if f.failure_triggered for step in f.affected_steps})

        result = {
            "trace_id": trace.trace_id,
            "crucible_version": CRUCIBLE_VERSION,
            "engine_mode": "local",
            "target": target["name"],
            "resilience_score": score,
            "grade": grade,
            "components": {},
            "failure_count": len(failure_points),
            "blast_radius": blast_radius,
            "top_vulnerabilities": failure_points,
            "replay_command": None,  # local mode has no trace persistence; not available in this release
            "engine_status": {},
            "agent_reflections": [],
            "shadow_summary": {},
            "seed": seed,
            "failure_points": failure_points,
        }
        self._log("=" * 50)
        self._log(f"Resilience: {score:.0f}/100  [{grade}]  (local mode, {len(valid_attacks)} attack(s))")
        self._log("=" * 50)
        return result

    # ── Cloud execution ──────────────────────────────────────────────────────

    def _run_cloud(self, target_path, attacks, demo_mode, seed) -> Dict:
        if not self.cloud_url or not self.api_key:
            raise CloudExecutionError(
                "mode='cloud' requires CRUCIBLE_CLOUD_URL and CRUCIBLE_API_KEY "
                "(env vars, or cloud_url=/api_key= to CrucibleRunner)"
            )
        payload = json.dumps({
            "target_path": target_path,
            "attacks": attacks,
            "demo_mode": demo_mode,
            "seed": seed,
        }).encode()
        req = urllib.request.Request(
            self.cloud_url.rstrip("/") + "/v1/runs",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json", "x-api-key": self.api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
        except urllib.error.URLError as e:
            raise CloudExecutionError(f"cloud run failed: {e}") from e
        result.setdefault("engine_mode", "cloud")
        return result

    # ── Replay & patterns (Cloud-only — trace analytics live server-side) ────

    def replay(self, trace_id: str) -> Dict:
        raise NotImplementedError("replay requires mode='cloud' — local mode does not persist traces")

    def patterns(self) -> Dict:
        raise NotImplementedError("patterns requires mode='cloud'")

    def evolution(self) -> Dict:
        raise NotImplementedError("evolution requires mode='cloud'")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _parse_target(self, target_path: str) -> Dict:
        from pathlib import Path
        path = Path(target_path)
        playwright_suffixes = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py"}

        if path.suffix.lower() in playwright_suffixes:
            return PlaywrightParser().parse_file(target_path)
        if "gitlab-ci" in path.name.lower():
            return GitLabCIParser().parse_file(target_path)
        return GitHubActionsParser().parse_file(target_path)

    def _log(self, msg: str):
        if self.verbose:
            print(msg)
