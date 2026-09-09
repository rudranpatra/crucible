# Crucible

> Run adversarial experiments against your CI/CD pipeline.  
> Measure whether it gets more resilient or less resilient over time.

[![PyPI](https://img.shields.io/pypi/v/crucible-gym)](https://pypi.org/project/crucible-gym/)
[![Tests](https://img.shields.io/badge/tests-97%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](../LICENSE)

> **0.5.0 architecture change.** `crucible-gym` is now a thin client with
> two engines: **local** (`pip install crucible-gym`, no signup, one basic
> supply-chain check) and **cloud** (`--engine cloud`, the full 6-agent
> engine, requires a self-hosted `crucible-cloud` — not yet publicly
> deployed). `validate`, `trend`, `replay`, `patterns`, `evolution`, and
> `serve` are not available in this release. If you need the old
> all-local behavior, pin `crucible-gym==0.4.2`. Full details:
> [CHANGELOG.md](../CHANGELOG.md#050--osscloud-engine-split).

Traditional scanners validate configuration. Crucible validates behavior under adversarial conditions. The two approaches are complementary — scanners find misconfigurations, Crucible finds what breaks when the pipeline is stressed.

```bash
pip install crucible-gym
```

Three questions every platform team asks:

| Question | Command |
|---|---|
| Is my pipeline vulnerable? | `crucible audit .` |
| What breaks under stress? | `crucible attack --target .github/workflows/ci.yml` (add `--engine cloud` for the full engine) |
| Did this PR make things worse? | `crucible compare HEAD~1 HEAD` |

---

## What it found on our own repo

Local mode (`crucible audit`, no signup) — one real check, unpinned GitHub Actions:

```
Auditing: .github/workflows/ci.yml
------------------------------------------------------------
Resilience: 0/100  [F] ❌

Findings:
  [MEDIUM] actions/checkout is referenced by 'v4', not a pinned commit SHA — a
           compromised or retagged upstream action runs in your pipeline unnoticed.
  [MEDIUM] actions/setup-python is referenced by 'v5', not a pinned commit SHA —
           a compromised or retagged upstream action runs in your pipeline unnoticed.
  ... (repeated per job using the same unpinned action)

Trace: local_a287e54b52  (replay: not available — requires --engine cloud)
```

`--engine cloud` (self-hosted `crucible-cloud`) runs the full 6-agent engine
against the same file for real subprocess/dependency/network findings, not
just static YAML analysis.

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

`crucible compare` uses `git show` to extract each workflow at the specified ref — no checkout, no working-tree mutation. Score history across runs (`crucible trend`) is not available in this release — trace persistence moved server-side and Cloud doesn't expose it yet (see CHANGELOG.md).

---

## GitHub PR comment workflow

Post a resilience score on every pull request — the Codecov play for pipeline resilience.

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

Every PR gets a comment with the score and findings. In local mode, findings
are limited to the basic supply-chain check; add `--engine cloud` (with
`CRUCIBLE_CLOUD_URL`/`CRUCIBLE_API_KEY` env vars) for the full 6-agent
findings set shown in [Six adversarial agents](#six-adversarial-agents)
below.

Engineers see the impact of their changes before merge.

---

## Six adversarial agents

**Local mode ships one of these.** `BasicSupplyChainAgent` — static check
only, flags a GitHub Actions step referencing a third-party action by tag/
branch instead of a pinned commit SHA. No subprocess execution, no network
calls, no dependency resolution.

**The other five, and the full-fidelity supply-chain check below, run only
through `--engine cloud`** (self-hosted `crucible-cloud`, not yet publicly
deployed):

| Agent | What it does | Execution method |
|---|---|---|
| **SupplyChainAgent** | Audits workflow YAML for unpinned actions, script injection, token scope | Parses actual YAML files, regex-matches `github.event.*` interpolations |
| **TimingAgent** | Injects `sleep {delay}` before each step command | `sleep 2.0 && (npm test)` via `asyncio.create_subprocess_shell`, observes real exit code |
| **EnvCorruptionAgent** | Sets env vars to null, overflow, path traversal, type mismatch | Python probe script executed with corrupted `os.environ` |
| **StepReorderAgent** | Runs step commands in wrong order | Commands executed in mutated sequence in `tempfile.TemporaryDirectory`; file-dep failures are real |
| **NetworkChaosAgent** | Tests network resilience under failure | Real `curl`: 1ms timeout (latency spike), NXDOMAIN (DNS flap), port 65535 (RST), `--range 0-50` (truncation) |
| **DependencyDriftAgent** | Mutates dependency specs and resolves them | `pip3 install --dry-run` on mutated `requirements.txt` — nonexistent versions fail at resolver |

All 6 run concurrently via `asyncio.gather`. Each run is deterministic via `--seed`. Crucible does not currently execute inside GitHub-hosted runners — sandboxed runner execution is planned for v1.0.

---

## Threat model execution (not available in 0.5.0)

`crucible validate` executed an [OWASP Threat Dragon](https://github.com/owasp/threat-dragon)
JSON export against a real target — every threat became PASS/FAIL/UNTESTED
evidence instead of a static line item. Its backing `ThreatPlanner`/
`ThreatValidator` moved to Cloud with the 0.5.0 split, and Cloud does not
yet expose an endpoint for it, so the subcommand was removed rather than
shipped broken (see CHANGELOG.md). The importer (`threats/importer.py`)
and schema (`threats/schema.py`) are still here and still public — only the
CLI command to run it end-to-end is gone until Cloud adds `/v1/validate`.

A worked example threat model still lives at
[`examples/threat-model.json`](examples/threat-model.json) for whenever
this returns.

---

## Resilience score

**Local mode:** a flat 15-point deduction per triggered finding, floored at
0 — deliberately simple and transparent, not a weighted formula.

**`--engine cloud`:** a 0–100 score with four weighted components:

| Component | Weight | What it measures |
|---|---|---|
| Survival rate | 40% | % of attacks that did not trigger failures |
| Blast containment | 25% | How contained failures were when they occurred |
| Recovery speed | 20% | Estimated recovery time across all failures |
| Coverage breadth | 15% | How many attack surfaces were tested |

Grade bands differ by mode — scores are not comparable between local and
cloud, or between 0.5.0 local mode and 0.4.x:

```
Local:  A ≥ 90   B ≥ 80   C ≥ 70   D ≥ 60   F < 60
Cloud:  A ≥ 90   B ≥ 75   C ≥ 60   D ≥ 40   F < 40
```

---

## Commands

```bash
# Audit (recommended first run) — local, basic supply-chain check only
crucible audit .                                  # auto-discover workflows
crucible audit .github/workflows/ci.yml           # specific file

# Attack — local mode: basic supply-chain check only
crucible attack --target .github/workflows/ci.yml
crucible attack --demo                            # synthetic demo target
crucible attack --target ci.yml --seed 42         # deterministic run
crucible attack --target ci.yml --github-comment  # post score to GitHub PR
crucible attack --target ci.yml --json            # full JSON output
crucible attack --target ci.yml --quiet           # just score/100
crucible attack --target ci.yml --publish-cloud   # also stream result to Crucible Cloud's ingest API

# Attack — full engine (all 6 agents, real resilience scoring), requires
# CRUCIBLE_CLOUD_URL + CRUCIBLE_API_KEY (self-hosted crucible-cloud)
crucible attack --target ci.yml --engine cloud
crucible audit . --engine cloud
crucible compare HEAD~1 HEAD --engine cloud

# Regression — local mode uses the basic engine on both refs
crucible compare HEAD~1 HEAD                      # did this change make CI weaker?
crucible compare main feature-branch --target .github/workflows/ci.yml

# Badge
crucible badge --score 73 --output badge.svg      # README badge
crucible badge --target workflow.yml -o b.svg     # attack then badge

# Status
crucible status

# Not available in 0.5.0 (see CHANGELOG.md): validate, trend, replay,
# patterns, evolution, serve, --rich, --shadow.
```

---

## Replayable traces (not available in 0.5.0)

Trace persistence and `crucible replay` required `memory.trace_memory`,
which moved to Cloud with no CLI-callable endpoint yet. `--json` on
`attack`/`audit`/`compare` still gives you the full result of a single run
(`resilience_score`, `grade`, `failure_points`, ...) — there's just nothing
to replay across runs right now. `result['replay_command']` is `None` in
local mode; see CHANGELOG.md.

---

## Playwright integration

`crucible attack --target tests/checkout.spec.ts` still parses the spec
file (`PlaywrightParser` is unchanged and public), but **the local basic
engine finds nothing against it** — `BasicSupplyChainAgent` only looks for
`jobs[].steps[].uses`, a GitHub Actions shape that Playwright targets don't
have. Meaningful results here require `--engine cloud`.

---

## Web dashboard (not available in 0.5.0)

`crucible serve` depended on `dashboard/server.py`, which read
`memory.trace_memory` — moved to Cloud, and Cloud doesn't expose a
dashboard yet. `dashboard/terminal.py` (used internally for CLI output
formatting) is unaffected.

---

## Project structure

```
crucible/
├── core/
│   ├── local_engine.py     # Minimal local trace/event recorder — no fitness, no darwin state
│   └── file_lock.py        # Cross-process file lock
├── agents/
│   └── base_agent.py       # BaseLocalAgent, AttackResult — local-only, independent of Cloud's base class
├── attacks/
│   └── basic_strategies.py # BasicSupplyChainAgent — the one local check (static, unpinned actions)
├── threats/
│   ├── schema.py           # Normalized Threat / Evidence / ThreatValidationReport (shared contract)
│   ├── importer.py         # Threat Dragon JSON -> normalized threats
│   └── basic_catalog.py    # Public threat definitions matched to the local basic agent
├── examples/
│   └── threat-model.json   # Worked Threat Dragon example
├── scoring/
│   └── basic_scorer.py     # Flat per-finding deduction, not the Cloud resilience formula
├── integrations/
│   ├── github_actions/
│   │   └── parser.py       # Parses GitHub Actions YAML into attack targets
│   ├── github/
│   │   ├── commenter.py    # Posts resilience scores to GitHub PRs
│   │   └── sarif.py        # SARIF 2.1.0 export
│   ├── gitlab/
│   │   └── parser.py       # Parses GitLab CI YAML into attack targets
│   └── playwright/
│       └── parser.py       # Parses Playwright test suites (local engine can't act on the result yet)
├── dashboard/
│   └── terminal.py         # Rich terminal UI formatting used by CLI output
├── sinks/
│   └── crucible_cloud_sink.py  # --publish-cloud: streams per-attack results to Cloud's ingest API
├── runner.py               # Mode-aware: local basic engine, or HTTP client to Cloud's /v1/runs
├── cli/crucible.py         # CLI — audit, attack, compare, badge, status
└── tests/                  # 97 passing tests

# Moved to crucible-cloud/app/engine/ (not in this repo):
# core/engine.py, core/shadow_runner.py, attacks/strategies.py (5 of 6
# agents), threats/planner.py, threats/validator.py, scoring/scorer.py,
# scoring/darwin_scorer.py, memory/trace_memory.py, agents/shadow_agent.py,
# dashboard/server.py — see CHANGELOG.md.
```

**Architecture rule:** the local engine and the Cloud engine are independent implementations — `crucible/agents/base_agent.py` is not a subset of the Cloud base class, it's a separate, deliberately simpler one. Only `runner.py` chooses which to call. No LLM, no external API calls other than Cloud itself.

---

## Development

```bash
git clone https://github.com/rudranpatra/crucible.git
cd crucible
pip install -e ".[dev]"

# Run all tests (local-only; the full engine's tests live in crucible-cloud)
python3 -m pytest crucible/tests/ -v
# 97 passed

# Demo
crucible attack --demo
```

Tests cover: the local basic engine, basic scorer, basic supply-chain agent, mode-selection on `CrucibleRunner` (including that shadow/rich modes fail explicitly rather than silently), GitHub commenter, SVG badge, SARIF export, GitLab CI parser, Playwright parser, and the `--publish-cloud` sink.

---

## Evolutionary mechanics (Cloud only)

The full engine applies evolutionary pressure to agents across runs — fitness tracking, extinction, shadow-mode promotion. None of this exists in the local basic engine (`crucible/core/local_engine.py` has no fitness state at all), and the CLI commands that surfaced it (`evolution`, `--shadow`) are not available in this release (see CHANGELOG.md). Kept here as a description of what the full engine does, not something you can currently run from this CLI.

### Agent fitness

Every agent has a fitness score (0–100):
- Agents that trigger failures **gain** fitness
- Agents that find nothing **lose** fitness
- Below fitness 20 after 5+ attempts → **extinct**, logged to failure cemetery

```
💀 AGENT OBITUARY
   Species: timing   Agent: agent_timing_cef5f0e0
   Mutations: 5 | Failures triggered: 0 | Fitness: 2.5
   Cause: FITNESS COLLAPSE
   The pipeline survived every timing attack. This species line ends here.
```

### Shadow agents

Every production agent spawns a shadow running alternative mutations on a deep copy of the target. Shadow trigger rate > production rate by 20% for 3+ consecutive runs → shadow is **promoted**. `--shadow` and `crucible evolution` are not available in this release (Cloud-only capability, no CLI wiring yet).

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
          fail-below: '60'          # fail PR if score drops below 60
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Findings appear in the GitHub Security tab via SARIF upload. The `fail-below` input quality-gates the PR.

**Note:** this Action currently pins `crucible-gym==0.4.2` internally (the
full local engine), deliberately not upgraded to 0.5.0 yet — the scoring
formula and `fail-below` semantics change between them, and that shouldn't
happen silently to anyone using this Action. It will get its own version
bump and changelog entry once Cloud is deployed and the Action can offer
`--engine cloud` as an opt-in.

---

## GitLab CI support

```bash
crucible audit .                        # auto-discovers .gitlab-ci.yml
crucible attack --target .gitlab-ci.yml # local mode: basic check only
crucible attack --target .gitlab-ci.yml --engine cloud  # all 6 agents
```

GitLab CI targets are parsed into the same format as GitHub Actions.
Local mode's `BasicSupplyChainAgent` only looks at `jobs[].steps[].uses`
(the GitHub Actions shape) — it does not currently check GitLab's
unpinned-image findings that the parser itself detects
(`target['supply_chain_risks']`). Full coverage requires `--engine cloud`.

---

## SARIF export

```bash
crucible attack --target ci.yml --sarif results.sarif
crucible audit . --sarif findings.sarif
```

SARIF 2.1.0 output is compatible with `github/codeql-action/upload-sarif`. Findings appear in the GitHub Security tab alongside CodeQL, Dependabot, and secret scanning results. In local mode, findings are limited to the basic supply-chain check.

---

## Roadmap

| Version | Status | Focus |
|---|---|---|
| **v0.1** | ✅ | 6 agents, supply-chain audit, scoring, replayable traces, shadow agents, GitHub PR comments, Playwright integration |
| **v0.2** | ✅ | Real subprocess execution for all agents, `crucible compare HEAD~1 HEAD`, `crucible trend` |
| **v0.3** | ✅ | GitHub Action (`uses: rudranpatra/crucible@v0.3.0`), SARIF export, GitLab CI parser |
| **v0.4** | ✅ | Phase A: `crucible validate` — Threat Dragon importer, threat schema, threat planner, threat → evidence mapping onto the existing 6 agents |
| **v0.5** | ✅ | OSS/Cloud engine split — public client + basic local engine, full engine behind `--engine cloud` |
| **Next** | Planned | `/v1/validate` on Cloud (restores `validate`), Cloud-side `trend`/`replay`/`patterns`/`evolution` endpoints, public Cloud deployment, sandboxed workflow execution inside real GitHub runners |

---

## License

Apache 2.0 — see [LICENSE](../LICENSE)
