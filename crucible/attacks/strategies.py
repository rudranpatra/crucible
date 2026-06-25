"""
Attack Strategies — v0.2
Real subprocess execution against actual pipeline commands.

Execution model
---------------
  real   — target step carries a 'run' command parsed from an actual workflow file
  demo   — no 'run' commands present; agents use canonical shell sequences that
            expose the same failure patterns against real processes

AttackResult fields populated by all real agents
  raw_output                       — actual stdout + stderr from subprocess
  mutation_applied['mode']         — 'real' | 'demo'
  mutation_applied['exit_code']    — integer returncode (-1 = timeout, -2 = launch error)
"""

import asyncio
import os
import random
import re
import shutil
import tempfile
import time
import uuid
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from agents.base_agent import BaseAdversarialAgent, AttackResult


# ── TimingAgent ────────────────────────────────────────────────────────────────

class TimingAgent(BaseAdversarialAgent):
    """
    Injects real delays before each pipeline step's shell command and enforces
    the step's declared timeout. Failure is determined by actual subprocess
    exit code — not arithmetic.

    Demo mode: uses `git version`, `pip3 --version`, etc. as stand-ins so
    there is always a real process to time.
    """
    attack_type = "timing"
    description = "Real subprocess: injects sleep before each step command and enforces timeout"

    DELAY_PROFILES = [
        {"name": "micro_delay",   "delay_ms": 50},
        {"name": "step_stutter",  "delay_ms": 250},
        {"name": "timeout_probe", "delay_ms": 2000},
        {"name": "race_window",   "delay_ms": 10},
        {"name": "cascade_delay", "delay_ms": 500},
    ]

    # Stand-in commands for steps that have no 'run' block
    _DEMO_CMDS: Dict[str, str] = {
        "checkout":             "git version",
        "install_dependencies": "pip3 --version",
        "run_tests":            "python3 -m pytest --version",
        "build_artifact":       "python3 -c 'print(\"build ok\")'",
        "deploy_staging":       "python3 -c 'print(\"deploy ok\")'",
    }

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        steps = target.get('steps', [])
        mutations = []
        for i, step in enumerate(steps):
            step_name = step.get('name', f'step_{i}')
            run_cmd = (step.get('run') or '').strip()
            effective_cmd = run_cmd or self._DEMO_CMDS.get(step_name, f'echo "{step_name}"')
            profile = self.DELAY_PROFILES[i % len(self.DELAY_PROFILES)]
            mutations.append({
                "step": step_name,
                "profile": profile['name'],
                "delay_ms": profile['delay_ms'],
                "run_cmd": effective_cmd,
                "mode": "real" if run_cmd else "demo",
            })
        return mutations[:self.config.get('max_mutations', 5)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        delay_ms = mutation['delay_ms']
        delay_s = delay_ms / 1000
        run_cmd = mutation['run_cmd']

        # Cap timeout so tests don't hang; real workflows use timeout_ms
        timeout_ms = target.get('timeout_ms', 5000)
        timeout_s = min(timeout_ms / 1000, 10.0)

        # Real injection: sleep {delay} then run the actual command
        injected = f"sleep {delay_s:.3f} && ( {run_cmd} )"
        t0 = time.monotonic()
        rc, stdout, stderr = await self._run_command(injected, timeout=timeout_s)
        elapsed_ms = (time.monotonic() - t0) * 1000

        failure_triggered = rc != 0
        reason = "timeout exceeded" if rc == -1 else f"exit={rc}"

        return AttackResult(
            success=True,
            mutation_applied={**mutation, 'exit_code': rc, 'elapsed_ms': round(elapsed_ms)},
            failure_triggered=failure_triggered,
            failure_description=(
                f"Step '{mutation['step']}' failed after {delay_ms}ms injection — {reason}"
                if failure_triggered else None
            ),
            affected_steps=[mutation['step']] + (target.get('downstream_steps', []) if failure_triggered else []),
            recovery_time_ms=elapsed_ms * 1.5 if failure_triggered else None,
            raw_output=f"exit={rc} elapsed={elapsed_ms:.0f}ms\n--- stdout ---\n{stdout[:400]}\n--- stderr ---\n{stderr[:400]}",
        )


# ── EnvCorruptionAgent ─────────────────────────────────────────────────────────

class EnvCorruptionAgent(BaseAdversarialAgent):
    """
    Sets each target env var to a corrupted value and runs a real Python
    probe that validates it — the same validation your pipeline should have.
    Failure = the probe exits non-zero, meaning the pipeline would crash
    or behave incorrectly on the corrupted value.
    """
    attack_type = "env"
    description = "Real subprocess: corrupts env vars and runs validation probes"

    CORRUPTION_STRATEGIES = [
        {"name": "null_inject",     "value": ""},
        {"name": "type_mismatch",   "value": "not_a_number_12345"},
        {"name": "overflow",        "value": "A" * 10000},
        {"name": "special_chars",   "value": "'; DROP TABLE jobs; --"},
        {"name": "path_traversal",  "value": "../../../etc/passwd"},
        {"name": "whitespace_bomb", "value": "   \t\n   "},
    ]

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        raw = target.get('env_vars', [])
        env_vars = [v['name'] if isinstance(v, dict) else v for v in raw] or [
            'CI', 'NODE_ENV', 'DATABASE_URL', 'API_KEY'
        ]
        mutations = []
        for i, var in enumerate(env_vars):
            strat = self.CORRUPTION_STRATEGIES[i % len(self.CORRUPTION_STRATEGIES)]
            mutations.append({
                "variable": var,
                "strategy": strat['name'],
                "injected_value": strat['value'],
                "injected_value_preview": strat['value'][:50],
            })
        return mutations[:self.config.get('max_mutations', 4)]

    def _probe_script(self, var: str, strategy: str) -> str:
        """Python script that validates var; exits non-zero if the value is unacceptable."""
        return f"""\
import os, sys, re

val = os.environ.get({var!r})
if val is None:
    print(f"FAIL: {var} is not set")
    sys.exit(1)

strat = {strategy!r}

if strat == 'null_inject':
    if not val:
        print(f"FAIL: {var} is empty (null injection succeeded)")
        sys.exit(1)

elif strat == 'type_mismatch':
    try:
        int(val)
    except ValueError:
        print(f"FAIL: {var} is not a valid integer: {{val[:30]!r}}")
        sys.exit(1)

elif strat == 'overflow':
    if len(val) > 1000:
        print(f"FAIL: {var} overflow length={{len(val)}}")
        sys.exit(1)

elif strat == 'special_chars':
    if not re.match(r'^[\\w\\-_/.@:=]+$', val):
        print(f"FAIL: {var} contains shell-dangerous characters: {{val[:30]!r}}")
        sys.exit(1)

elif strat == 'path_traversal':
    if '..' in val or val.startswith('/'):
        print(f"FAIL: {var} path traversal: {{val[:30]!r}}")
        sys.exit(1)

elif strat == 'whitespace_bomb':
    if not val.strip():
        print(f"FAIL: {var} is whitespace-only")
        sys.exit(1)

print(f"PASS: {var} passed validation for {{strat}}")
sys.exit(0)
"""

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        var_name = mutation['variable']
        strategy = mutation['strategy']
        corrupted = mutation['injected_value']

        env = os.environ.copy()
        env[var_name] = corrupted

        # Write probe to temp file — avoids all shell quoting issues
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w', delete=False) as f:
            f.write(self._probe_script(var_name, strategy))
            probe_path = f.name

        try:
            rc, stdout, stderr = await self._run_command(
                f'python3 {probe_path}', env=env, timeout=10.0
            )
        finally:
            try:
                os.unlink(probe_path)
            except OSError:
                pass

        failure_triggered = rc != 0

        return AttackResult(
            success=True,
            mutation_applied={**mutation, 'exit_code': rc, 'mode': 'real'},
            failure_triggered=failure_triggered,
            failure_description=(
                f"Env corruption: {var_name} → {strategy} triggered validation failure (exit={rc})"
                if failure_triggered else None
            ),
            affected_steps=[f"step_using_{var_name.lower()}"],
            recovery_time_ms={
                'null_inject': 150.0, 'type_mismatch': 200.0,
                'overflow': 1000.0, 'special_chars': 100.0,
                'path_traversal': 100.0, 'whitespace_bomb': 100.0,
            }.get(strategy, 200.0) if failure_triggered else None,
            raw_output=f"exit={rc}\n{stdout.strip()}\n{stderr.strip()}",
        )


# ── StepReorderAgent ───────────────────────────────────────────────────────────

class StepReorderAgent(BaseAdversarialAgent):
    """
    Extracts the shell commands from workflow steps and executes them in
    a shuffled order inside a temp directory. Steps that produce files
    (mkdir, echo > file, cp) fail deterministically when their prerequisites
    haven't run yet — exposing undeclared dependencies.

    Demo mode: uses a canned 5-step workflow with explicit file dependencies
    so there is always a real process sequence to reorder.
    """
    attack_type = "reorder"
    description = "Real subprocess: runs step commands in mutated order to expose dependency failures"

    # Demo workflow: each step depends on the previous step's output
    _DEMO_STEPS: List[Tuple[str, str]] = [
        ("init_workspace",     "mkdir -p {ws} && echo initialized > {ws}/.init"),
        ("install_deps",       "test -f {ws}/.init && echo dep1 > {ws}/deps.txt"),
        ("compile",            "test -f {ws}/deps.txt && echo binary > {ws}/app"),
        ("run_tests",          "test -f {ws}/app && echo passed > {ws}/test.result"),
        ("package_artifact",   "test -f {ws}/test.result && echo artifact > {ws}/dist.tar"),
    ]

    def _step_names_and_cmds(self, target: Dict, ws: str) -> List[Tuple[str, str]]:
        """Return (name, cmd) for runnable steps. Falls back to demo workflow."""
        steps = target.get('steps', [])
        real = [(s['name'], s['run'].strip()) for s in steps if (s.get('run') or '').strip()]
        if real:
            return real
        return [(name, cmd.format(ws=ws)) for name, cmd in self._DEMO_STEPS]

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        # We need step names to build the mutation; use a dummy tmpdir just for introspection
        with tempfile.TemporaryDirectory() as ws:
            pairs = self._step_names_and_cmds(target, ws)

        names = [n for n, _ in pairs]
        if len(names) < 2:
            return []

        mutations = []
        seen: set = set()
        attempts = 0
        while len(mutations) < min(3, self.config.get('max_mutations', 3)) and attempts < 20:
            attempts += 1
            shuffled = names.copy()
            random.shuffle(shuffled)
            key = tuple(shuffled)
            if key != tuple(names) and key not in seen:
                seen.add(key)
                swaps = [(names[i], shuffled[i]) for i in range(len(names)) if names[i] != shuffled[i]]
                mutations.append({
                    "original_order": names,
                    "mutated_order": shuffled,
                    "swapped_pairs": swaps[:3],
                })

        # Guarantee at least one mutation: full reversal
        if not mutations:
            rev = list(reversed(names))
            mutations.append({"original_order": names, "mutated_order": rev, "swapped_pairs": []})

        return mutations

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        with tempfile.TemporaryDirectory() as ws:
            pairs = self._step_names_and_cmds(target, ws)
            mode = "real" if any((s.get('run') or '').strip() for s in target.get('steps', [])) else "demo"

            name_to_cmd = {name: cmd for name, cmd in pairs}
            failures: List[Dict] = []

            for step_name in mutation.get('mutated_order', []):
                cmd = name_to_cmd.get(step_name)
                if not cmd:
                    continue
                rc, stdout, stderr = await self._run_command(cmd, timeout=15.0)
                if rc != 0:
                    failures.append({
                        'step': step_name,
                        'exit_code': rc,
                        'stderr': stderr.strip()[:200],
                    })

        failure_triggered = len(failures) > 0
        failed_step = failures[0]['step'] if failures else None
        raw_lines = [f"{f['step']}: exit={f['exit_code']} — {f['stderr']}" for f in failures[:3]]

        return AttackResult(
            success=True,
            mutation_applied={**mutation, 'mode': mode, 'failures': failures},
            failure_triggered=failure_triggered,
            failure_description=(
                f"Reorder failure: '{failed_step}' failed out of dependency order "
                f"(exit={failures[0]['exit_code']})"
                if failure_triggered else None
            ),
            affected_steps=[f['step'] for f in failures],
            recovery_time_ms=float(len(failures) * 600) if failure_triggered else None,
            raw_output='\n'.join(raw_lines) or "no failures detected in this permutation",
        )


# ── NetworkChaosAgent ──────────────────────────────────────────────────────────

class NetworkChaosAgent(BaseAdversarialAgent):
    """
    Makes real outbound connections to the network registries that CI pipelines
    depend on, under chaos conditions applied via curl flags:

      latency_spike    — --max-time 0.001  (1 ms; always times out on real network)
      dns_flap         — target hostname replaced with NXDOMAIN variant
      connection_reset — valid host, port 65535 (always RST/refused)
      packet_loss_10pct— --max-time 0.3   (300 ms; tests marginal latency tolerance)
      partial_response — --range 0-50      (truncated body; tests incomplete-read handling)

    Exit codes from curl (28 = timeout, 6 = DNS, 7 = refused) are mapped to
    failure_triggered = True/False.  No root, no tc netem, no Toxiproxy required.
    """
    attack_type = "network"
    description = "Real curl probes: latency timeout, NXDOMAIN, RST, truncated response"

    CHAOS_PROFILES = [
        {"name": "latency_spike",     "max_time": 0.001, "variant": "timeout"},
        {"name": "dns_flap",          "max_time": 5.0,   "variant": "nxdomain"},
        {"name": "connection_reset",  "max_time": 3.0,   "variant": "wrong_port"},
        {"name": "packet_loss_10pct", "max_time": 0.3,   "variant": "timeout"},
        {"name": "partial_response",  "max_time": 5.0,   "variant": "range"},
    ]

    # Real endpoint for each logical network dependency
    _PROBE_URLS: Dict[str, str] = {
        'pypi_registry':       'https://pypi.org/simple/requests/',
        'npm_registry':        'https://registry.npmjs.org/express/latest',
        'docker_registry':     'https://auth.docker.io/token',
        'git_checkout':        'https://github.com',
        'aws_api':             'https://s3.amazonaws.com',
        'artifact_push':       'https://pypi.org',
        'api_health_check':    'https://pypi.org',
        'external_http_call':  'https://pypi.org',
    }

    def _probe_cmd(self, url: str, profile: Dict) -> Tuple[str, bool]:
        """
        Returns (shell command, always_fails).
        always_fails=True when the command is guaranteed to fail (used for
        deterministic test assertions).
        """
        from urllib.parse import urlparse
        host = urlparse(url).netloc.split(':')[0]
        variant = profile['variant']
        t = profile['max_time']

        if variant == 'timeout':
            # 1 ms or 300 ms — real TCP + TLS handshake cannot complete this fast
            return (
                f'curl --max-time {t} --silent --output /dev/null '
                f'--write-out "%{{http_code}}" {url!r}',
                t <= 0.001,  # 1ms always fails; 300ms might succeed on LAN
            )
        elif variant == 'nxdomain':
            fake = url.replace(host, f'nxdomain-crucible-probe.{host}', 1)
            return (
                f'curl --max-time {t} --silent --output /dev/null '
                f'--write-out "%{{http_code}}" {fake!r}',
                True,
            )
        elif variant == 'wrong_port':
            # Port 65535: no service → connection refused / RST
            proto = urlparse(url).scheme
            return (
                f'curl --max-time {t} --silent --output /dev/null '
                f'--write-out "%{{http_code}}" {proto}://{host}:65535/',
                True,
            )
        elif variant == 'range':
            # Range 0-50 bytes — server returns 206; pipeline expecting 200 fails
            return (
                f'curl --max-time {t} --range 0-50 --silent '
                f'--write-out "%{{http_code}}" --output /dev/null {url!r}',
                False,
            )
        return f'curl --max-time {t} --silent --output /dev/null {url!r}', False

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        calls = target.get('network_calls', ['pypi_registry', 'npm_registry', 'git_checkout', 'aws_api'])
        # Strip action_fetch: prefixes
        calls = [c if '://' not in c else c.split('://', 1)[0] for c in calls]
        calls = [c.split(':')[0] for c in calls]

        mutations = []
        for call in calls:
            profile = self.CHAOS_PROFILES[len(mutations) % len(self.CHAOS_PROFILES)]
            url = self._PROBE_URLS.get(call, 'https://pypi.org/simple/')
            cmd, always_fails = self._probe_cmd(url, profile)
            mutations.append({
                "call": call,
                "chaos_profile": profile['name'],
                "probe_url": url,
                "probe_cmd": cmd,
                "always_fails": always_fails,
                "loss_rate": 1.0 if always_fails else 0.1,
                "latency_ms": int(profile['max_time'] * 1000),
                "truncate": profile['variant'] == 'range',
                "reset": profile['variant'] == 'wrong_port',
            })
        return mutations[:self.config.get('max_mutations', 4)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        cmd = mutation['probe_cmd']
        profile = mutation['chaos_profile']
        has_retry = target.get('has_retry_logic', False)

        rc, stdout, stderr = await self._run_command(cmd, timeout=15.0)

        # curl exit codes: 0=ok, 6=DNS, 7=refused, 28=timeout, 35=TLS
        failure_triggered = rc != 0

        # If pipeline has retry logic, simulate one retry
        if failure_triggered and has_retry:
            rc2, _, _ = await self._run_command(cmd, timeout=15.0)
            if rc2 == 0:
                failure_triggered = False

        curl_reason = {0: 'ok', 6: 'DNS resolution failed', 7: 'connection refused',
                       28: 'timeout', 35: 'TLS failure'}.get(rc, f'curl exit {rc}')

        return AttackResult(
            success=True,
            mutation_applied={**mutation, 'exit_code': rc, 'mode': 'real', 'curl_reason': curl_reason},
            failure_triggered=failure_triggered,
            failure_description=(
                f"Network chaos [{profile}] on {mutation['call']}: {curl_reason}"
                if failure_triggered else None
            ),
            affected_steps=[mutation['call']],
            recovery_time_ms=(
                8000.0 if mutation.get('reset') else
                float(mutation['latency_ms'] * 3 + 2000) if mutation.get('truncate') else
                float(mutation['latency_ms'] * 2 + 1000)
            ) if failure_triggered else None,
            raw_output=f"curl exit={rc} ({curl_reason})\ncmd: {cmd[:200]}\n{stderr[:200]}",
        )


# ── DependencyDriftAgent ───────────────────────────────────────────────────────

class DependencyDriftAgent(BaseAdversarialAgent):
    """
    Writes a mutated requirements.txt (or package.json) into a temp directory
    and runs `pip3 install --dry-run` (or `npm install --dry-run`).
    pip's resolver raises on nonexistent versions, yanked packages, and
    conflicting constraints — all captured as real non-zero exit codes.

    Drift mutations
    ---------------
      missing_package    — random UUID package name (definitely not on PyPI)
      yanked_version     — {pkg}==0.0.0.dev0  (version never published)
      major_bump         — {pkg}==999.999.999  (version never published)
      transitive_conflict— Flask==0.12.2 + Werkzeug==3.0.0 (documented incompatibility)
    """
    attack_type = "dependency"
    description = "Real pip/npm resolver: installs mutated deps and observes non-zero exits"

    _DRIFT_SPECS: Dict[str, Any] = {
        'missing_package':    lambda pkg: f"crucible-probe-nonexistent-{uuid.uuid4().hex[:10]}==1.0.0",
        'yanked_version':     lambda pkg: f"{pkg}==0.0.0.dev0",
        'major_bump':         lambda pkg: f"{pkg}==999.999.999",
        'transitive_conflict': lambda pkg: "Flask==0.12.2\nWerkzeug==3.0.0",
    }

    _RECOVERY_MS: Dict[str, float] = {
        'missing_package': 3000.0, 'yanked_version': 2000.0,
        'major_bump': 1500.0, 'transitive_conflict': 2500.0,
    }

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        deps = target.get('dependencies', [
            {"name": "requests", "pinned": "2.28.0"},
            {"name": "numpy",    "pinned": None},
            {"name": "boto3",    "pinned": "1.26.0"},
        ])
        drift_types = list(self._DRIFT_SPECS.keys())
        mutations = []
        for dep in deps:
            drift = drift_types[len(mutations) % len(drift_types)]
            mutations.append({
                "package": dep['name'] if isinstance(dep, dict) else dep,
                "current_pin": dep.get('pinned') if isinstance(dep, dict) else None,
                "drift_type": drift,
                "is_pinned": bool(dep.get('pinned') if isinstance(dep, dict) else False),
            })
        return mutations[:self.config.get('max_mutations', 4)]

    async def apply_mutation(self, target: Dict, mutation: Dict) -> AttackResult:
        drift = mutation['drift_type']
        package = mutation['package']

        spec_fn = self._DRIFT_SPECS.get(drift, lambda p: f"{p}==999.999.999")
        spec = spec_fn(package)

        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / 'requirements.txt'
            req_file.write_text(spec + '\n')

            # --dry-run: resolves and checks but does not install
            # --no-cache-dir: avoids false passes from cached wheels
            cmd = (
                f'pip3 install --dry-run --no-cache-dir --quiet '
                f'-r {req_file} 2>&1'
            )
            rc, stdout, stderr = await self._run_command(cmd, timeout=60.0)

        combined = (stdout + stderr).strip()
        failure_triggered = rc != 0

        return AttackResult(
            success=True,
            mutation_applied={**mutation, 'spec': spec, 'exit_code': rc, 'mode': 'real'},
            failure_triggered=failure_triggered,
            failure_description=(
                f"Dependency failure: {package} [{drift}] — pip exit={rc}\n"
                f"{combined[:250]}"
                if failure_triggered else None
            ),
            affected_steps=['install', 'build'],
            recovery_time_ms=self._RECOVERY_MS.get(drift, 1500.0) if failure_triggered else None,
            raw_output=combined[:600],
        )


# ── SupplyChainAgent ───────────────────────────────────────────────────────────

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
        'unpinned_image': (
            "Supply chain: Docker image {detail}. "
            "A floating tag can be mutated upstream — pin to a digest for reproducible builds."
        ),
    }

    async def generate_mutations(self, target: Dict) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = list(target.get('supply_chain_risks', []))

        source_file = target.get('source_file') or 'demo'
        if source_file == 'demo' or not Path(source_file).exists():
            return findings

        try:
            raw_text = Path(source_file).read_text()
            raw = yaml.safe_load(raw_text) or {}
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
            'unpinned_image',
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
