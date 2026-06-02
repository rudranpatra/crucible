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
            recovery_time_ms=random.uniform(100, 2000) if failure_triggered else None
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
            recovery_time_ms=random.uniform(50, 500) if failure_triggered else None
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
            recovery_time_ms=random.uniform(200, 3000) if failure_triggered else None
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
            recovery_time_ms=random.uniform(500, 5000) if failure_triggered else None
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
            recovery_time_ms=random.uniform(100, 1000) if failure_triggered else None
        )
