"""
Attack Strategies — v0.1
Five adversarial attack types for CI/CD pipeline stress testing.

Each attack agent targets a specific failure class:
- TimingAgent: race conditions, delays, timeouts
- EnvCorruptionAgent: environment variable corruption
- StepReorderAgent: dependency order violations
- NetworkChaosAgent: network instability simulation
- DependencyDriftAgent: version conflicts, missing packages
"""

import asyncio
import random
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List
from agents.base_agent import BaseAdversarialAgent, AttackResult


class TimingAgent(BaseAdversarialAgent):
    """
    Injects timing mutations: delays, race conditions, timeout triggers.
    Finds workflows that assume steps complete within fixed windows.
    """
    attack_type = "timing"
    description = "Injects timing delays and race conditions to expose timeout assumptions"

    DELAY_PROFILES = [
        {"name": "micro_delay", "delay_ms": 50, "target": "pre_step"},
        {"name": "step_stutter", "delay_ms": 250, "target": "mid_step"},
        {"name": "timeout_probe", "delay_ms": 2000, "target": "post_step"},
        {"name": "race_window", "delay_ms": 10, "target": "concurrent_steps"},
        {"name": "cascade_delay", "delay_ms": 500, "target": "downstream"},
    ]

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        steps = target.get('steps', [])
        mutations = []
        for step in steps:
            profile = random.choice(self.DELAY_PROFILES)
            mutations.append({
                "step": step.get('name', 'unknown'),
                "profile": profile['name'],
                "delay_ms": profile['delay_ms'],
                "injection_point": profile['target'],
                "jitter_ms": random.randint(0, 50)
            })
        return mutations[:self.config.get('max_mutations', 5)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        await asyncio.sleep(mutation['delay_ms'] / 10000)

        delay = mutation['delay_ms']
        step_timeout = target.get('timeout_ms', 1000)
        failure_triggered = delay > (step_timeout * 0.8)

        return AttackResult(
            success=True,
            mutation_applied=mutation,
            failure_triggered=failure_triggered,
            failure_description=f"Step '{mutation['step']}' failed: timing injection {delay}ms exceeded timeout window" if failure_triggered else None,
            affected_steps=[mutation['step']] + (target.get('downstream_steps', []) if failure_triggered else []),
            recovery_time_ms=float(mutation['delay_ms'] * 1.5) if failure_triggered else None
        )


class EnvCorruptionAgent(BaseAdversarialAgent):
    """
    Corrupts environment variables: nulls, malformed values, type mismatches.
    Finds workflows that don't validate their environment assumptions.
    """
    attack_type = "env"
    description = "Corrupts environment variables to expose missing validation"

    CORRUPTION_STRATEGIES = [
        {"name": "null_inject", "transform": lambda v: ""},
        {"name": "type_mismatch", "transform": lambda v: "not_a_number_12345"},
        {"name": "overflow", "transform": lambda v: "A" * 10000},
        {"name": "special_chars", "transform": lambda v: "'; DROP TABLE jobs; --"},
        {"name": "path_traversal", "transform": lambda v: "../../../etc/passwd"},
        {"name": "whitespace_bomb", "transform": lambda v: "   \t\n   "},
    ]

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        raw = target.get('env_vars', ['CI', 'NODE_ENV', 'DATABASE_URL', 'API_KEY'])
        env_vars = [v['name'] if isinstance(v, dict) else v for v in raw] if raw else ['CI', 'NODE_ENV', 'DATABASE_URL', 'API_KEY']
        mutations = []
        for var in env_vars:
            strategy = random.choice(self.CORRUPTION_STRATEGIES)
            mutations.append({
                "variable": var,
                "strategy": strategy['name'],
                "original_type": "string",
                "injected_value_preview": strategy['transform']("original")[:50]
            })
        return mutations[:self.config.get('max_mutations', 4)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        await asyncio.sleep(0.01)

        high_risk_vars = {'DATABASE_URL', 'API_KEY', 'SECRET', 'TOKEN', 'PASSWORD'}
        is_critical = any(kw in mutation['variable'].upper() for kw in high_risk_vars)
        strategy = mutation['strategy']

        failure_triggered = is_critical or strategy in ['null_inject', 'type_mismatch']

        return AttackResult(
            success=True,
            mutation_applied=mutation,
            failure_triggered=failure_triggered,
            failure_description=(
                f"Env corruption: {mutation['variable']} → {strategy} caused pipeline failure"
                if failure_triggered else None
            ),
            affected_steps=[f"step_using_{mutation['variable'].lower()}"],
            recovery_time_ms={
                'null_inject': 150.0, 'type_mismatch': 200.0,
                'overflow': 1000.0, 'special_chars': 100.0,
                'path_traversal': 100.0, 'whitespace_bomb': 100.0,
            }.get(strategy, 200.0) if failure_triggered else None
        )


class StepReorderAgent(BaseAdversarialAgent):
    """
    Reorders workflow steps to expose hidden dependency assumptions.
    Finds steps that silently depend on previous step side effects.
    """
    attack_type = "reorder"
    description = "Reorders steps to expose undeclared dependencies"

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        steps = target.get('steps', [])
        if len(steps) < 2:
            return []

        mutations = []
        indices = list(range(len(steps)))

        for _ in range(min(3, self.config.get('max_mutations', 3))):
            shuffled = indices.copy()
            random.shuffle(shuffled)
            mutations.append({
                "original_order": [steps[i].get('name', f'step_{i}') for i in indices],
                "mutated_order": [steps[i].get('name', f'step_{i}') for i in shuffled],
                "swapped_pairs": [(indices[i], shuffled[i]) for i in range(len(indices)) if indices[i] != shuffled[i]][:3]
            })

        return mutations

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        await asyncio.sleep(0.02)

        critical_steps = target.get('critical_order_steps', ['build', 'test', 'deploy'])
        mutated_order = mutation.get('mutated_order', [])

        failure_triggered = False
        failed_step = None

        for i, step_name in enumerate(mutated_order):
            for critical in critical_steps:
                if critical in step_name.lower():
                    original_pos = mutation['original_order'].index(step_name) if step_name in mutation['original_order'] else i
                    if original_pos != i:
                        failure_triggered = True
                        failed_step = step_name
                        break

        return AttackResult(
            success=True,
            mutation_applied=mutation,
            failure_triggered=failure_triggered,
            failure_description=(
                f"Reorder failure: '{failed_step}' executed out of dependency order"
                if failure_triggered else None
            ),
            affected_steps=[failed_step] if failed_step else [],
            recovery_time_ms=float(len(mutation.get('swapped_pairs', [])) * 600) if failure_triggered else None
        )


class NetworkChaosAgent(BaseAdversarialAgent):
    """
    Simulates network instability: packet loss, latency spikes, DNS failures, partial responses.
    """
    attack_type = "network"
    description = "Simulates network chaos to expose missing retry and timeout logic"

    CHAOS_PROFILES = [
        {"name": "packet_loss_10pct", "loss_rate": 0.1, "latency_ms": 0},
        {"name": "latency_spike", "loss_rate": 0, "latency_ms": 3000},
        {"name": "dns_flap", "loss_rate": 0.5, "latency_ms": 100},
        {"name": "partial_response", "loss_rate": 0, "latency_ms": 500, "truncate": True},
        {"name": "connection_reset", "loss_rate": 1.0, "latency_ms": 0, "reset": True},
    ]

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        network_calls = target.get('network_calls', ['registry_pull', 'artifact_push', 'api_health_check'])
        mutations = []
        for call in network_calls:
            profile = random.choice(self.CHAOS_PROFILES)
            mutations.append({
                "call": call,
                "chaos_profile": profile['name'],
                "loss_rate": profile['loss_rate'],
                "latency_ms": profile['latency_ms'],
                "truncate": profile.get('truncate', False),
                "reset": profile.get('reset', False)
            })
        return mutations[:self.config.get('max_mutations', 4)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        await asyncio.sleep(mutation['latency_ms'] / 10000)

        has_retry = target.get('has_retry_logic', False)
        has_timeout = target.get('has_timeout', False)

        loss_rate = mutation['loss_rate']
        is_reset = mutation.get('reset', False)

        failure_triggered = (
            (loss_rate > 0.3 and not has_retry) or
            (mutation['latency_ms'] > 2000 and not has_timeout) or
            is_reset
        )

        return AttackResult(
            success=True,
            mutation_applied=mutation,
            failure_triggered=failure_triggered,
            failure_description=(
                f"Network chaos: {mutation['chaos_profile']} on {mutation['call']} — "
                f"{'no retry logic detected' if not has_retry else 'timeout exceeded'}"
                if failure_triggered else None
            ),
            affected_steps=[mutation['call']],
            recovery_time_ms=(
                8000.0 if mutation.get('reset') else
                float(mutation['latency_ms'] * 3 + 2000) if mutation.get('truncate') else
                float(mutation['latency_ms'] * 2 + 1000)
            ) if failure_triggered else None
        )


class DependencyDriftAgent(BaseAdversarialAgent):
    """
    Injects dependency drift: version conflicts, missing packages, yanked releases.
    """
    attack_type = "dependency"
    description = "Injects dependency drift to expose version pinning and lockfile gaps"

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        deps = target.get('dependencies', [
            {"name": "requests", "pinned": "2.28.0"},
            {"name": "numpy", "pinned": "1.24.0"},
            {"name": "boto3", "pinned": None},
        ])

        mutations = []
        drift_types = ['major_bump', 'yanked_version', 'missing_package', 'transitive_conflict']

        for dep in deps:
            drift = random.choice(drift_types)
            mutations.append({
                "package": dep['name'],
                "current_pin": dep.get('pinned'),
                "drift_type": drift,
                "is_pinned": dep.get('pinned') is not None
            })

        return mutations[:self.config.get('max_mutations', 4)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        await asyncio.sleep(0.01)

        drift = mutation['drift_type']
        is_pinned = mutation['is_pinned']

        failure_triggered = (
            drift == 'missing_package' or
            drift == 'yanked_version' or
            (drift == 'major_bump' and not is_pinned) or
            (drift == 'transitive_conflict')
        )

        return AttackResult(
            success=True,
            mutation_applied=mutation,
            failure_triggered=failure_triggered,
            failure_description=(
                f"Dependency failure: {mutation['package']} — {drift}"
                + (" (unpinned package vulnerable)" if not is_pinned else "")
                if failure_triggered else None
            ),
            affected_steps=['install', 'build'],
            recovery_time_ms={
                'missing_package': 3000.0, 'yanked_version': 2000.0,
                'major_bump': 1500.0, 'transitive_conflict': 2500.0,
            }.get(drift, 1500.0) if failure_triggered else None
        )


class SupplyChainAgent(BaseAdversarialAgent):
    """
    Audits GitHub Actions workflows for supply chain attack vectors via static analysis.
    Unlike other agents, findings here are real vulnerabilities — not probabilistic models.

    Checks:
    - Actions not pinned to a full commit SHA (tag mutation = silent RCE)
    - pull_request_target + PR head checkout (the canonical supply chain escalation)
    - User-controlled github.event values interpolated into run: blocks (script injection)
    - Missing or overly permissive GITHUB_TOKEN permissions block
    """
    attack_type = "supply_chain"
    description = "Static audit: unpinned Actions SHA, script injection, token scope, pull_request_target abuse"

    _SHA_RE = re.compile(r'^[a-f0-9]{40}$')
    _INJECT_RE = re.compile(
        r'\$\{\{[^}]*github\.event\.'
        r'(?:issue|pull_request|comment|review|discussion)'
        r'\.(?:title|body|name|comment)[^}]*\}\}'
    )
    _RECOVERY_BY_SEVERITY: Dict[str, float] = {
        'critical': 14400000.0,   # 4hr — requires PR + review cycle to fix safely
        'high':      7200000.0,   # 2hr — config change + re-test
        'medium':    3600000.0,   # 1hr — quick fix but needs review
        'low':        900000.0,   # 15min
    }
    _DESCRIPTIONS: Dict[str, str] = {
        'unpinned_action': (
            "Supply chain: {action} uses ref '{ref}' — not pinned to a commit SHA. "
            "A compromised upstream repo or tag mutation makes this silent RCE in your pipeline."
        ),
        'pull_request_target_checkout': (
            "CRITICAL: pull_request_target + checkout of PR head ({ref}) = untrusted contributor code "
            "runs with write-scoped GITHUB_TOKEN. This is the canonical GitHub Actions supply chain attack."
        ),
        'script_injection': (
            "CRITICAL: github.event user-controlled value interpolated directly into a run: block "
            "({matches} occurrence(s)). An attacker crafts an issue/PR title to execute arbitrary shell commands."
        ),
        'overpermissive_token': (
            "Token scope: permissions:{permissions} violates least-privilege. "
            "Every step in every job inherits full repo write access — one compromised step = full repo."
        ),
        'missing_permissions_block': (
            "No permissions block. On push/workflow_dispatch GITHUB_TOKEN defaults include contents:write. "
            "Add 'permissions: read-all' at workflow level and scope up only where explicitly needed."
        ),
    }

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = list(target.get('supply_chain_risks', []))

        source_file = target.get('source_file', 'demo')
        if source_file == 'demo' or not Path(source_file).exists():
            return findings

        try:
            with open(source_file) as f:
                raw = yaml.safe_load(f) or {}
            raw_text = Path(source_file).read_text()
        except (OSError, yaml.YAMLError):
            return findings

        # 1. Unpinned action refs
        for job_cfg in (raw.get('jobs') or {}).values():
            for step in (job_cfg.get('steps') or []):
                uses = step.get('uses', '')
                if uses and '@' in uses:
                    ref = uses.split('@', 1)[-1]
                    if not self._SHA_RE.match(ref):
                        findings.append({
                            'finding_type': 'unpinned_action',
                            'action': uses,
                            'step': step.get('name', uses),
                            'ref': ref,
                            'severity': 'high',
                        })

        # 2. pull_request_target + PR head checkout
        triggers = raw.get('on') or {}
        if isinstance(triggers, dict) and 'pull_request_target' in triggers:
            for job_cfg in (raw.get('jobs') or {}).values():
                for step in (job_cfg.get('steps') or []):
                    if 'checkout' in step.get('uses', '').lower():
                        ref_val = str((step.get('with') or {}).get('ref', ''))
                        if 'head' in ref_val.lower() or 'event' in ref_val.lower():
                            findings.append({
                                'finding_type': 'pull_request_target_checkout',
                                'step': step.get('name', 'checkout'),
                                'ref': ref_val,
                                'severity': 'critical',
                            })

        # 3. Script injection via github.event user-controlled fields
        matches = self._INJECT_RE.findall(raw_text)
        if matches:
            findings.append({
                'finding_type': 'script_injection',
                'matches': len(matches),
                'severity': 'critical',
            })

        # 4. Token permissions
        perms = raw.get('permissions')
        if perms == 'write-all':
            findings.append({
                'finding_type': 'overpermissive_token',
                'permissions': 'write-all',
                'severity': 'high',
            })
        elif perms is None:
            findings.append({
                'finding_type': 'missing_permissions_block',
                'severity': 'medium',
            })

        return findings[:self.config.get('max_mutations', 20)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        finding_type = mutation.get('finding_type', 'unknown')
        severity = mutation.get('severity', 'medium')

        failure = finding_type in {
            'unpinned_action', 'pull_request_target_checkout',
            'script_injection', 'overpermissive_token', 'missing_permissions_block',
        }

        template = self._DESCRIPTIONS.get(finding_type, "Supply chain finding: {finding_type}")
        description = template.format(**{**mutation, 'finding_type': finding_type}) if failure else None

        return AttackResult(
            success=True,
            mutation_applied=mutation,
            failure_triggered=failure,
            failure_description=description,
            affected_steps=[mutation.get('step', 'workflow-level')],
            recovery_time_ms=self._RECOVERY_BY_SEVERITY.get(severity) if failure else None,
        )
