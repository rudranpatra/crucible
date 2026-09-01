"""
Crucible Cloud sink — publishes one AttackResult at a time to Crucible Cloud.

Stdlib urllib only: crucible-gym depends on pyyaml and rich, nothing else, and a
sink is not a good enough reason to put `requests` in every OSS user's install.

This sink raises on transport failure. CrucibleRunner.run() catches and logs it,
so a sink can never fail an attack run — the guard lives at the one call site
rather than being duplicated into every sink.
"""

import json
import logging
import os
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CrucibleCloudSink:
    """Publishes each completed AttackResult to POST /results/{trace_id}/attacks."""

    def __init__(self, url: str, api_key: str, timeout: float = 10.0):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> Optional["CrucibleCloudSink"]:
        """Build a sink from CRUCIBLE_CLOUD_URL + CRUCIBLE_API_KEY, or None.

        Same two variables the crucible-cloud uploader already uses. Credentials
        stay out of argv, where they would land in shell history and CI logs.
        """
        url = os.environ.get("CRUCIBLE_CLOUD_URL")
        api_key = os.environ.get("CRUCIBLE_API_KEY")
        if not url or not api_key:
            return None
        return cls(url, api_key)

    def publish(self, trace_id: str, index: int, result: Any) -> None:
        """POST one AttackResult. Signature matches CrucibleRunner.run(on_attack_result=...).

        `result` is an agents.base_agent.AttackResult — read by attribute rather
        than imported, so this module stays off the core.engine import chain.

        result.raw_output is never sent: it is raw subprocess output from attacks
        that corrupt the target's environment, so it can contain the target's
        secrets. Everything needed to analyse or reproduce the attack is in
        mutation_applied and failure_description.
        """
        body = {
            "attack_id": f"atk_{index:04d}",
            "attack_type": result.attack_type,
            "success": result.success,
            "failure_triggered": result.failure_triggered,
            "failure_description": result.failure_description,
            "affected_steps": result.affected_steps,
            "recovery_time_ms": result.recovery_time_ms,
            "mutation_applied": result.mutation_applied,
        }
        request = urllib.request.Request(
            f"{self.url}/results/{trace_id}/attacks",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-API-Key": self.api_key},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            response.read()
        logger.debug("attack_published trace=%s attack=%s", trace_id, body["attack_id"])
