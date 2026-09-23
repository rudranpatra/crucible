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

# Formats whose parsers put jobs/steps in a shape this check doesn't
# understand at all (GitLab CI has no "uses" concept; Playwright tests
# aren't CI jobs). Identified by the marker fields those parsers set on
# their target dict — see crucible/integrations/gitlab/parser.py:88
# ('type': 'gitlab_ci') and crucible/integrations/playwright/parser.py:225
# ('source_type': 'playwright'). GitHub Actions targets (real or the
# --demo-mode fixture) set neither.
_UNSUPPORTED_TARGET_TYPES = {"gitlab_ci"}
_UNSUPPORTED_SOURCE_TYPES = {"playwright"}


class BasicSupplyChainAgent(BaseLocalAgent):
    attack_type = "supply_chain_basic"
    description = "Static check: third-party GitHub Actions not pinned to a commit SHA"

    def check(self, target: Dict[str, Any]) -> List[AttackResult]:
        if (
            target.get("type") in _UNSUPPORTED_TARGET_TYPES
            or target.get("source_type") in _UNSUPPORTED_SOURCE_TYPES
        ):
            # ponytail: this check only ever looks at job.steps[].uses (a
            # GitHub-Actions-only concept), so on these formats it has
            # nothing to analyze. Say so explicitly instead of silently
            # returning zero findings, which the scorer would otherwise read
            # as a clean 100/A. Add a real GitLab/Playwright-shaped check
            # here when this agent needs to score those formats for real.
            return [AttackResult(
                success=False,
                failure_triggered=False,
                failure_description=(
                    f"target format {target.get('type') or target.get('source_type')!r} "
                    "is not supported by local static analysis: this check only "
                    "understands GitHub Actions job.steps[].uses references"
                ),
                attack_type=self.attack_type,
                unsupported=True,
            )]

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
