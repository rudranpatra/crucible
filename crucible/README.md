# Crucible

> Run adversarial experiments against your CI/CD pipeline.  
> Measure whether it gets more resilient or less resilient over time.

[![PyPI](https://img.shields.io/pypi/v/crucible-gym)](https://pypi.org/project/crucible-gym/)
[![Tests](https://img.shields.io/badge/tests-102%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../LICENSE)

Crucible executes controlled adversarial experiments against GitHub Actions workflows and Playwright test suites. It finds failure modes your pipeline has never encountered — before production does — and tracks whether each code change makes your pipeline stronger or weaker.

**Not a scanner. Scanners ask: "Is this configured correctly?" Crucible asks: "What breaks when this is stressed?"**

---

## Install

```bash
pip install crucible-gym
```

```bash
# First run — supply-chain and dependency audit against your repo
crucible audit .

# All 6 agents against a specific workflow
crucible attack --target .github/workflows/ci.yml

# Demo — no workflow file needed
crucible attack --demo --rich
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

Replay the exact run: `crucible replay --trace trc_a2e889a909`

---

## The workflow that makes it useful

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

Every PR gets a comment showing the resilience score and any new vulnerabilities introduced. Engineers see the impact of their changes before merge.

---

## Six adversarial agents, real execution

Every agent executes real subprocesses. No simulation, no arithmetic.

| Agent | What it does | How it's real |
|---|---|---|
| **SupplyChainAgent** | Audits workflow YAML for unpinned actions, script injection, token scope | Parses actual YAML files, regex-matches `github.event.*` interpolations |
| **TimingAgent** | Injects `sleep {delay}` before each step command | `sleep 2.0 && (npm test)` via `asyncio.create_subprocess_shell`, observes exit code |
| **EnvCorruptionAgent** | Sets env vars to null, overflow, path traversal, type mismatch | Python probe script executed with corrupted `os.environ`, exit code = failure |
| **StepReorderAgent** | Runs step commands in wrong order | Executes commands in mutated sequence in `tempfile.TemporaryDirectory`, file-dep failures are real |
| **NetworkChaosAgent** | Tests network resilience under failure | Real `curl`: 1ms timeout (latency spike), NXDOMAIN (DNS flap), port 65535 (RST), `--range 0-50` (truncation) |
| **DependencyDriftAgent** | Mutates dependency specs and resolves them | `pip3 install --dry-run` on mutated `requirements.txt` — nonexistent versions fail at resolver |

All 6 run concurrently via `asyncio.gather`. Each run is deterministic via `--seed`.

---

## Resilience score

Every run produces a **0–100 score** with four components:

| Component | Weight | What it measures |
|---|---|---|
| Survival rate | 40% | % of attacks that did not trigger failures |
| Blast containment | 25% | How contained failures were when they occurred |
| Recovery speed | 20% | Estimated recovery time across all failures |
| Coverage breadth | 15% | How many attack surfaces were tested |

```
A ≥ 90   Survived adversarial pressure across all attack types
B ≥ 75   Minor vulnerabilities, low production risk
C ≥ 60   Moderate vulnerabilities, targeted hardening recommended
D ≥ 40   Significant vulnerabilities, high production risk
F < 40   Will break under realistic operational pressure
```

Scores are marked **stale** after 30 days and require a re-run.

---

## Commands

```bash
# Audit (recommended first run)
crucible audit .                                  # auto-discover workflows
crucible audit .github/workflows/ci.yml           # specific file

# Full attack
crucible attack --target .github/workflows/ci.yml # all 6 agents
crucible attack --target workflow.yml --attacks supply_chain,dependency
crucible attack --demo                            # synthetic demo target
crucible attack --demo --rich                     # rich terminal UI
crucible attack --demo --shadow                   # evolutionary shadow agents
crucible attack --target ci.yml --seed 42         # deterministic run
crucible attack --target ci.yml --github-comment  # post score to GitHub PR
crucible attack --target ci.yml --json            # full JSON output
crucible attack --target ci.yml --quiet           # just score/100

# Regression (the killer workflow)
crucible compare HEAD~1 HEAD                      # did this change make CI weaker?
crucible compare main feature-branch --target .github/workflows/ci.yml
crucible trend                                    # score history across all stored runs

# Traces
crucible replay --trace trc_abc123                # replay stored trace
crucible patterns                                 # failure patterns across all runs
crucible status                                   # stored traces summary

# Evolution
crucible evolution                                # species fitness, extinction log

# Badge
crucible badge --score 73 --output badge.svg      # README badge
crucible badge --target workflow.yml -o b.svg     # attack then badge

# Web dashboard
crucible serve                                    # http://127.0.0.1:7331
pip install fastapi uvicorn                       # required for serve
```

---

## Evolutionary mechanics

### Agent fitness

Every agent has a fitness score (0–100):
- Agents that trigger failures **gain** fitness
- Agents that find nothing **lose** fitness  
- Below fitness 20 after 5+ attempts → **extinct**, logged to failure cemetery

When the timing agent found nothing against the Node.js CI template:

```
💀 AGENT OBITUARY
   Species: timing   Agent: agent_timing_cef5f0e0
   Mutations: 5 | Failures triggered: 0 | Fitness: 2.5
   Cause: FITNESS COLLAPSE
   The pipeline survived every timing attack. This species line ends here.
```

### Shadow agents (`--shadow`)

Every production agent spawns a shadow running alternative mutations on a deep copy of the target. Shadow never touches the real target. Shadow trigger rate > production rate by 20% for 3+ consecutive runs → shadow is **promoted**. Promotion is logged as an evolutionary event.

```bash
crucible attack --demo --shadow
crucible evolution  # species fitness, promotions, extinction log
```

---

## Replayable traces

Every run writes a `.crucible` trace:

```json
{
  "trace_id": "trc_a2e889a909",
  "target": "CI",
  "attack_types": ["timing", "env", "reorder", "network", "dependency", "supply_chain"],
  "resilience_score": 30.0,
  "failure_points": [
    "Supply chain: actions/checkout@v4 uses ref 'v4' — not pinned to a commit SHA.",
    "Env corruption: GITHUB_TOKEN → null_inject triggered validation failure (exit=1)",
    "Dependency failure: requests [missing_package] — pip exit=1"
  ],
  "blast_radius": ["checkout", "workflow-level", "install", "build"],
  "replay_command": "crucible replay --trace trc_a2e889a909"
}
```

Traces are reproducible. Share them in postmortems. Use them to verify hardening worked.

---

## GitHub PR comment

Post a resilience score on every pull request — the Codecov play for pipeline resilience.

Copy [`.github/workflows/crucible-template.yml`](.github/workflows/crucible-template.yml) into your project. Every PR gets a comment:

```
🔥 Crucible Resilience Report

🟡 73/100 (C) — Moderate risk

Vulnerabilities detected:
- ⚠️  actions/checkout@v4 not pinned to a commit SHA
- ⚠️  DATABASE_URL, API_KEY lack input validation
- ⚠️  git_checkout has no retry logic

Blast radius: install, build, deploy
Trace: trc_a2e889a909

crucible replay --trace trc_a2e889a909
```

---

## Playwright integration

Attack Playwright test suites directly:

```bash
crucible attack --target tests/checkout.spec.ts
```

Extracted surfaces: page navigation sequences, network fetch/XHR calls, environment variables, assertion checkpoints.

---

## Web dashboard

```bash
pip install fastapi uvicorn
crucible serve
# Open http://127.0.0.1:7331
```

Live attack feed, score history, agent survival log, failure cemetery, vulnerability heatmap.

---

## Project structure

```
crucible/
├── core/
│   ├── engine.py           # Agent lifecycle, execution trace, event loop
│   ├── file_lock.py        # Cross-process file lock (shared by trace_memory, darwin_scorer)
│   └── shadow_runner.py    # Shadow/production agent pair management
├── agents/
│   ├── base_agent.py       # Base adversarial agent — _run_command, fitness, reflection
│   └── shadow_agent.py     # Shadow — runs alternative mutations on a deep copy
├── attacks/
│   └── strategies.py       # 6 real-execution agents
├── scoring/
│   ├── scorer.py           # Resilience scoring 0–100, grade, components
│   └── darwin_scorer.py    # Survival index — lifetime fitness across runs
├── memory/
│   └── trace_memory.py     # Persists .crucible traces, indexes, detects patterns
├── integrations/
│   ├── github_actions/
│   │   └── parser.py       # Parses GitHub Actions YAML into attack targets
│   ├── github/
│   │   └── commenter.py    # Posts resilience scores to GitHub PRs
│   └── playwright/
│       └── parser.py       # Parses Playwright test suites as attack targets
├── dashboard/
│   ├── terminal.py         # Rich terminal UI: kill screens, obituaries, report card
│   └── server.py           # FastAPI web dashboard
├── runner.py               # Orchestrates all layers (the only place that knows everything)
├── cli/crucible.py         # CLI — audit, attack, replay, patterns, evolution, badge, serve
└── tests/                  # 102 passing tests
```

**Architecture rule:** Engine, agents, scorer, memory don't import each other. Only `runner.py` orchestrates. Agents are purely algorithmic — no LLM, no external API, no cloud.

---

## Development

```bash
git clone https://github.com/rudranpatra/crucible.git
cd crucible-v0.1.0
pip install -e ".[dev]"

# Run all tests
python3 -m pytest crucible/tests/ -v
# 102 passed

# Demo
crucible attack --demo --rich
```

Tests cover: engine, all 6 attack agents (demo + real workflow mode), resilience scorer, survival index scorer, shadow agent, shadow runner, terminal dashboard, GitHub commenter, SVG badge, Playwright parser, full end-to-end run.

---

## Regression tracking

The question that matters is not "what's the score today" — it's "did this change make the pipeline weaker?"

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

## Roadmap

| Version | Status | Focus |
|---|---|---|
| **v0.1** | ✅ | 6 real-execution agents, supply-chain audit, scoring, replayable traces, shadow agents, GitHub PR comments, Playwright integration |
| **v0.2** | ✅ | `crucible compare HEAD~1 HEAD`, `crucible trend` — resilience regression and score history |
| **v0.3** | Planned | GitHub Action (`uses: crucible/action@v1`), SARIF export for GitHub Security tab, GitLab CI parser |
| **v1.0** | Planned | Sandboxed workflow execution inside real GitHub runners; blast-radius measurement |

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
