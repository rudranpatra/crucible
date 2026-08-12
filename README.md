# Crucible

> Run adversarial experiments against your CI/CD pipeline.  
> Measure whether it gets more resilient or less resilient over time.

[![PyPI](https://img.shields.io/pypi/v/crucible-gym)](https://pypi.org/project/crucible-gym/)
[![Tests](https://img.shields.io/badge/tests-159%20passing-brightgreen)](crucible/tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Crucible](badge.svg)](CHANGELOG.md) — Crucible attacking its own CI (`crucible badge --target .github/workflows/ci.yml`); regenerated periodically, not live per-commit yet

Traditional scanners validate configuration. Crucible validates behavior under adversarial conditions. The two approaches are complementary.

```bash
pip install crucible-gym
```

Three questions every platform team asks:

| Question | Command |
|---|---|
| Is my pipeline vulnerable? | `crucible audit .` |
| What breaks under stress? | `crucible attack --target .github/workflows/ci.yml` |
| Did this PR make things worse? | `crucible compare HEAD~1 HEAD` |
| Are my threat model's threats actually exploitable? | `crucible validate threatmodel.json --target ci.yml` |

---

## Regression tracking

```bash
crucible compare HEAD~1 HEAD

Resilience: 84 → 67  (↓17)
Grade:      B → D

⚠  Regression detected
New vulnerabilities:
  - Supply chain: actions/deploy@v2 not pinned to a commit SHA
  - Dependency: requests pinned to 2.28.0 — known CVE in resolver path
```

```bash
crucible trend

Resilience Trend  (8 runs)
--------------------------------------------------
  2026-06-01    92/100 (A)  ██████████████████
  2026-06-08    88/100 (B)  █████████████████
  2026-06-15    76/100 (C)  ███████████████
  2026-06-22    67/100 (D)  █████████████

Overall: ↓25 pts  (declining)
```

---

## What it found on our own repo

```
Auditing: .github/workflows/ci.yml
------------------------------------------------------------
Resilience: 30/100  [F] ❌

Findings:
  [HIGH]   Supply chain: unpinned_action — actions/checkout@v4, actions/setup-python@v4
           not pinned to a commit SHA. Tag mutation = silent RCE in your pipeline.
  [HIGH]   Dependency: 2 unpinned packages. Any yanked version breaks the build silently.
  [MEDIUM] Env: GITHUB_TOKEN, PR_NUMBER lack input validation

Trace: trc_a2e889a909  (replay: crucible replay --trace trc_a2e889a909)
```

---

## Six adversarial agents

All agents execute real subprocesses, dependency resolution, command execution, network probes, or workflow analysis.

| Agent | What it does | Execution method |
|---|---|---|
| **SupplyChainAgent** | Unpinned actions, script injection, token scope | Parses actual YAML, regex-matches `github.event.*` |
| **TimingAgent** | Injects `sleep {delay}` before each step | `asyncio.create_subprocess_shell`, real exit code |
| **EnvCorruptionAgent** | Null, overflow, type mismatch on env vars | Python probe script with corrupted `os.environ` |
| **StepReorderAgent** | Runs step commands in wrong order | Commands in mutated sequence, real file-dep failures |
| **NetworkChaosAgent** | Latency, DNS, connection failures | Real `curl`: 1ms timeout, NXDOMAIN, port 65535 |
| **DependencyDriftAgent** | Mutated dependency versions | `pip3 install --dry-run` on mutated `requirements.txt` |

---

## Threat models backed by evidence

`crucible validate` executes an [OWASP Threat Dragon](https://github.com/owasp/threat-dragon) threat model instead of just documenting it — every threat is mapped onto the 6 agents above and comes back `PASS`, `FAIL`, or `UNTESTED`, with a replayable trace as evidence.

```bash
crucible validate threatmodel.json --target .github/workflows/ci.yml
```

```
Threat Validation Report — CI
------------------------------------------------------------
Coverage: 80%  (0 passed, 4 failed, 1 untested)

  ❌ [critical] Unpinned Third-Party Actions Allow Supply Chain Tampering  (Tampering -> supply_chain)
        ! Supply chain: actions/checkout@v4 uses ref 'v4' — not pinned to a commit SHA.
  ⬜ [medium  ] Pipeline Actions Are Not Attributable to an Individual  (Repudiation -> none)

Trace: trc_e8add5347b  (replay: crucible replay --trace traces/trc_e8add5347b.crucible)
```

`UNTESTED` means Crucible has no agent that can test that threat yet — it says so rather than silently marking it safe. See [crucible/README.md](crucible/README.md#threat-model-execution) for the importer/planner details and a worked example.

---

## GitHub Action

```yaml
# .github/workflows/crucible.yml
on: pull_request
jobs:
  resilience:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: rudranpatra/crucible@v0.3.0
        with:
          target: .github/workflows/ci.yml
          github-comment: 'true'
          sarif-output: crucible-results.sarif
          fail-below: '60'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Every PR gets a resilience score comment. Findings appear in the GitHub Security tab via SARIF. The `fail-below` input quality-gates the PR.

---

## Full documentation

See [crucible/README.md](crucible/README.md) — all commands, scoring breakdown, threat model execution, evolutionary mechanics, replayable traces, web dashboard, and architecture.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
