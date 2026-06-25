# Crucible

> Run adversarial experiments against your CI/CD pipeline.  
> Measure whether it gets more resilient or less resilient over time.

[![PyPI](https://img.shields.io/pypi/v/crucible-gym)](https://pypi.org/project/crucible-gym/)
[![Tests](https://img.shields.io/badge/tests-102%20passing-brightgreen)](crucible/tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

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

## GitHub PR comment workflow

Add to `.github/workflows/crucible.yml`:

```yaml
on: pull_request
jobs:
  resilience:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install crucible-gym
      - run: crucible attack --target .github/workflows/ci.yml --github-comment
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          PR_NUMBER: ${{ github.event.number }}
```

Every PR gets a resilience score comment. Engineers see the impact before merge.

---

## Full documentation

See [crucible/README.md](crucible/README.md) — all commands, scoring breakdown, evolutionary mechanics, replayable traces, web dashboard, and architecture.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
