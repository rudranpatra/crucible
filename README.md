# Crucible

> Run adversarial experiments against your CI/CD pipeline.  
> Measure whether it gets more resilient or less resilient over time.

[![PyPI](https://img.shields.io/pypi/v/crucible-gym)](https://pypi.org/project/crucible-gym/)
[![Tests](https://img.shields.io/badge/tests-102%20passing-brightgreen)](crucible/tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

**Not a scanner.** Scanners ask: "Is this configured correctly?" Crucible asks: "What breaks when this is stressed?"

```bash
pip install crucible-gym

crucible audit .                          # supply-chain + dependency audit
crucible attack --target ci.yml           # all 6 agents, real subprocesses
crucible compare HEAD~1 HEAD              # did this change make CI weaker?
crucible trend                            # score history across all runs
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

## Six adversarial agents, real execution

| Agent | What it does | How it's real |
|---|---|---|
| **SupplyChainAgent** | Audits for unpinned actions, script injection, token scope | Parses actual YAML, regex-matches `github.event.*` interpolations |
| **TimingAgent** | Injects `sleep {delay}` before each step command | `asyncio.create_subprocess_shell`, observes exit code |
| **EnvCorruptionAgent** | Sets env vars to null, overflow, type mismatch | Python probe script executed with corrupted `os.environ` |
| **StepReorderAgent** | Runs step commands in wrong order | Executes in mutated sequence in `tempfile.TemporaryDirectory` |
| **NetworkChaosAgent** | Tests network resilience under failure | Real `curl`: 1ms timeout, NXDOMAIN, port 65535, truncation |
| **DependencyDriftAgent** | Mutates dependency specs | `pip3 install --dry-run` on mutated `requirements.txt` |

All 6 run concurrently via `asyncio.gather`. Every run is deterministic via `--seed`.

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

Every PR gets a comment showing the resilience score and any new vulnerabilities introduced.

---

## Full documentation

See [crucible/README.md](crucible/README.md) — all commands, scoring breakdown, evolutionary mechanics, shadow agents, replayable traces, web dashboard, and architecture.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
