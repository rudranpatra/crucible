# Crucible

> Your CI/CD pipeline has failure modes it has never encountered. Crucible finds them before production does.

Crucible is an open-source **adversarial intelligence engine** for CI/CD pipelines.
It deploys autonomous adversarial agents that mutate, stress, and attack your workflows —
scores resilience 0–100, generates replayable attack traces, and applies evolutionary pressure
so agents that find failures survive and agents that don't go extinct.

**This is not a testing framework. It is evolutionary pressure applied to your infrastructure.**

[![Tests](https://img.shields.io/badge/tests-92%20passing-brightgreen)](crucible/tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## How it works

```
Your workflow  →  Adversarial agents attack it  →  Resilience score  →  Replayable trace
                        ↓
                 Agents that find failures → survive → evolve
                 Agents that find nothing  → fitness drops → die
                        ↓
                 Every run adds to an operational foresight graph
                 that predicts failures before they reach production
```

Agents are **algorithmic** — no LLM, no external API calls, no cloud dependency.
The evolutionary pressure is the intelligence.

---

## Setup

### Requirements

- Python 3.9+
- No external services required (runs fully local)

### Install from source

```bash
git clone https://github.com/rudranpatra/crucible.git
cd crucible/crucible
pip install -r requirements.txt
```

### Install as package

```bash
pip install crucible-gym
```

---

## Quick start

### Demo run (no workflow file needed)

```bash
cd crucible/crucible
python runner.py demo
```

### Rich terminal UI (screenshot-worthy)

```bash
python cli/crucible.py attack --demo --rich
```

This shows a live attack dashboard with:
- Kill screens when vulnerabilities are found
- Agent obituaries when an agent's fitness collapses
- Score bar filling as attacks complete
- Final report card with component breakdown

### Attack a real workflow

```bash
python cli/crucible.py attack --target .github/workflows/ci.yml
```

### Run specific attack types

```bash
python cli/crucible.py attack --demo --attacks timing,env,network
```

---

## All commands

```bash
# Core attacks
crucible attack --demo                          # demo target
crucible attack --target workflow.yml           # real workflow
crucible attack --demo --rich                   # rich terminal UI
crucible attack --demo --shadow                 # evolutionary shadow agents
crucible attack --demo --attacks timing,env     # specific attack types
crucible attack --demo --github-comment         # post score to GitHub PR
crucible attack --demo --quiet                  # just print score/100

# Traces
crucible replay --trace trc_abc123              # replay a stored trace
crucible patterns                               # failure patterns across all traces
crucible status                                 # stored traces summary

# Evolution
crucible evolution                              # species fitness, dominance, extinction

# Badge
crucible badge --score 73 --output badge.svg   # generate README badge from score
crucible badge --target workflow.yml -o b.svg  # run attack then generate badge

# Web dashboard
crucible serve                                  # local dashboard at http://127.0.0.1:7331
crucible serve --port 8080

# Output formats
crucible attack --demo --json                   # full JSON result
```

---

## Attack types

| Attack | What it targets | What failure looks like |
|--------|----------------|------------------------|
| `timing` | Delays, race conditions, timeout assumptions | Step exceeds timeout window → cascade failure |
| `env` | Environment variable validation | `DATABASE_URL=null` → pipeline crash |
| `reorder` | Hidden step dependency order | `deploy` runs before `build` → broken artifact |
| `network` | Retry logic, timeout handling | No retry on 50% packet loss → silent failure |
| `dependency` | Version pinning, lockfile coverage | Unpinned package yanked → build breaks |

---

## Resilience score

Every run produces a **0–100 resilience score** with four weighted components:

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| Survival rate | 40% | % of attacks that did NOT trigger failures |
| Blast containment | 25% | How contained failures were when they occurred |
| Recovery speed | 20% | How fast the pipeline would recover |
| Coverage breadth | 15% | How many attack surfaces were tested |

```
A  ≥ 90   Excellent — survived adversarial pressure across all attack types
B  ≥ 75   Good — minor vulnerabilities, low production risk
C  ≥ 60   Fair — moderate vulnerabilities, targeted hardening recommended
D  ≥ 40   Poor — significant vulnerabilities, high production risk
F  < 40   Critical — pipeline will break under realistic operational pressure
```

Scores are marked **stale** after 30 days and require a re-run.

---

## Evolutionary mechanics

Crucible implements actual evolutionary pressure — not just scoring.

### Agent fitness

Every agent has a fitness score (0–100). After each run:
- Agents that trigger failures gain fitness
- Agents that trigger nothing lose fitness
- Agents below fitness 20 after 5+ attempts **die** — they are removed and logged to the failure cemetery

```bash
crucible attack --demo
# Output includes:
# 💀 AGENT OBITUARY
#   Species: timing | Agent: agent_timing_a3f2
#   Mutations: 8 | Failures triggered: 0 | Fitness: 12.5
#   Cause: FITNESS COLLAPSE — The pipeline survived every timing attack.
```

### Shadow agents (--shadow)

Every production agent spawns a shadow that runs alternative mutations on a copy of the target.
The shadow never touches the real target.

```bash
crucible attack --demo --shadow
```

If shadow trigger rate > production rate by 20% for 3+ consecutive runs → shadow is **promoted**.
Promotions are logged as evolutionary events.

### Darwin scoring (lifetime)

Species fitness accumulates across all runs — not just the current one.

```bash
crucible evolution
# Shows: species fitness, dominant/extinct status, generation, lineage depth
```

---

## Replayable traces

Every run writes a `.crucible` file to `traces/`:

```json
{
  "trace_id": "trc_8f3a2b91c4",
  "target": "demo_ci_pipeline",
  "attack_types": ["timing", "env", "network", "dependency", "reorder"],
  "resilience_score": 61.4,
  "failure_points": [
    "Env corruption: DATABASE_URL → null_inject caused pipeline failure",
    "Network chaos: connection_reset on aws_api — no retry logic detected"
  ],
  "blast_radius": ["step_using_database_url", "aws_api"],
  "replay_command": "crucible replay --trace traces/trc_8f3a2b91c4.crucible"
}
```

Replay the exact attack sequence:

```bash
crucible replay --trace trc_8f3a2b91c4
```

---

## GitHub PR comment integration

Post a resilience score on every pull request automatically — the Codecov play.

### Step 1: Add to your workflow

Copy `.github/workflows/crucible-template.yml` from this repo into your project's `.github/workflows/`.

### Step 2: Set environment variables

The commenter reads from:
- `GITHUB_TOKEN` — automatically available in GitHub Actions
- `GITHUB_REPOSITORY` — automatically set in Actions (e.g. `org/repo`)
- `PR_NUMBER` — set from `${{ github.event.number }}`

### Step 3: Run

```bash
# In CI
crucible attack --target .github/workflows/ci.yml --github-comment

# Locally (with env vars set)
GITHUB_TOKEN=... GITHUB_REPOSITORY=org/repo PR_NUMBER=42 \
  crucible attack --demo --github-comment
```

Every PR gets a comment like:

```
🔥 Crucible Resilience Report

🟡 73/100 (C) — Moderate risk

Vulnerabilities detected:
- ⚠️ Env vulnerability: DATABASE_URL, API_KEY lack input validation
- ⚠️ Network vulnerability: 2 calls have no retry/timeout logic

Blast radius: step_using_database_url, aws_api
Failures triggered: 4

Replay this run:
crucible replay --trace trc_8f3a2b91c4
```

---

## README badge

Generate an SVG badge for your project's README:

```bash
crucible badge --score 73 --output badge.svg
```

Add to your README:
```markdown
![Crucible Resilience](badge.svg)
```

---

## Playwright integration

Attack Playwright test suites as targets — Crucible attacks the user flows themselves:

```bash
crucible attack --target tests/checkout.spec.ts
```

Extracted attack surfaces:
- Page navigation sequences → `timing`, `reorder` attacks
- Network fetch/XHR calls → `network` chaos
- Environment variables → `env` corruption
- Assertion checkpoints → blast radius mapping

---

## Web dashboard

```bash
pip install fastapi uvicorn
crucible serve
# Open http://127.0.0.1:7331
```

Shows: live attack feed, score history, agent survival log, failure cemetery, vulnerability heatmap.

---

## Project structure

```
crucible/
├── core/
│   ├── engine.py           # Agent lifecycle, execution trace, event loop
│   └── shadow_runner.py    # Shadow/production agent pair management
├── agents/
│   ├── base_agent.py       # Base adversarial agent (all agents inherit this)
│   └── shadow_agent.py     # Shadow agent — runs alternative mutations on a copy
├── attacks/
│   └── strategies.py       # 5 attack agents: timing, env, reorder, network, dependency
├── scoring/
│   ├── scorer.py           # Resilience scoring 0-100, grade, components
│   └── darwin_scorer.py    # Lifetime fitness across runs, species evolution
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
│   ├── server.py           # FastAPI web dashboard
│   └── static/index.html   # Dashboard UI
├── runner.py               # Orchestrates all layers (only file that knows everything)
├── cli/crucible.py         # CLI interface
└── tests/                  # 92 passing tests
```

---

## Architecture principles

1. **Every agent has a fitness score.** Agents below 20 after 5+ attempts die. The death mechanism is what makes this evolutionary, not just agentic.

2. **Every run produces a replayable trace.** The trace is the core data artifact. Everything else — scoring, patterns, evolution — is derived from traces.

3. **The runner is the only place that knows about all layers.** Engine, agents, scorer, memory don't import each other. Only `runner.py` orchestrates them.

4. **Demo mode always works without any real pipeline.** `create_demo_target()` produces a realistic synthetic target.

5. **No LLM in core logic.** Agents are algorithmic. The evolutionary pressure is the intelligence.

---

## Development

```bash
# Clone and install dev dependencies
git clone https://github.com/rudranpatra/crucible.git
cd crucible/crucible
pip install -r requirements.txt

# Run all tests
python3 -m pytest tests/ -v

# Run demo
python runner.py demo

# Run with rich UI
python cli/crucible.py attack --demo --rich
```

### Running tests

```
92 passed in ~7s
```

Tests cover: engine, all 5 attack agents, resilience scorer, Darwin scorer, shadow agent, shadow runner, terminal dashboard, GitHub commenter, SVG badge, Playwright parser, full end-to-end run.

---

## Roadmap

- **v0.1** ✅ — 5 attack types, resilience scoring, replayable traces, rich dashboard, shadow agents, Darwin scoring, GitHub PR comments, Playwright integration
- **v0.2** — GitLab CI parser, Jenkins integration, `crucible diff` (compare two traces)
- **v0.3** — LLM-driven mutation generation (smarter attack surface discovery)
- **v0.4** — Federated attack network: opt-in anonymized trace sharing, cross-deployment pattern detection
- **v1.0** — Darwin Runtime: full evolutionary agent infrastructure, self-evolving attack strategies

---

## Philosophy

Everyone is building smarter AI.

Almost nobody is building pressure-tested AI.

Trust in autonomous systems will not come from capability claims.
It will come from systems that have survived adversarial pressure and can prove it.

Crucible is that pressure.

---

## License

Apache 2.0 — see [LICENSE](LICENSE)
