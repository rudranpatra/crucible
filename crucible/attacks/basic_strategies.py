"""Basic OSS/local attack: static supply-chain check.

Independently authored — not derived from the proprietary Cloud attack
strategies. This is a static check only (no subprocess execution, no
network chaos, no dependency resolution) — those live in Cloud. It flags
GitHub Actions steps that reference a third-party action by a mutable tag
or branch instead of a pinned commit SHA.
"""
import re
from typing import Any, Dict, List

from crucible.agents.base_agent import AttackResult, BaseLocalAgent

_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class BasicSupplyChainAgent(BaseLocalAgent):
    attack_type = "supply_chain_basic"
    description = "Static check: third-party GitHub Actions not pinned to a commit SHA"

    def check(self, target: Dict[str, Any]) -> List[AttackResult]:
        findings: List[AttackResult] = []
        for job in target.get("jobs", []):
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if not uses or uses.startswith("./"):
                    continue
                action, _, ref = uses.partition("@")
                if not ref or not _FULL_SHA_RE.match(ref):
                    findings.append(AttackResult(
                        success=True,
                        failure_triggered=True,
                        failure_description=(
                            f"{action} is referenced by '{ref or '(no ref)'}', not a pinned "
                            "commit SHA — a compromised or retagged upstream action runs "
                            "in your pipeline unnoticed."
                        ),
                        affected_steps=[step.get("name", "")],
                        attack_type=self.attack_type,
                        mutation_applied={"uses": uses},
                    ))
        return findings
