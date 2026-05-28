# Crucible

> Your CI/CD pipeline has failure modes it has never encountered.  
> Crucible finds them before production does.

Adversarial agents attack your workflows. The ones that find failures survive. The ones that don't, die.
Every run produces a replayable trace. Every trace compounds into operational foresight.

**This is not a testing framework. It is evolutionary pressure applied to your infrastructure.**

[![Tests](https://img.shields.io/badge/tests-92%20passing-brightgreen)](crucible/tests/)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

---

## What Crucible found

We ran adversarial attacks against the **official GitHub Actions Node.js CI starter workflow** — the template used by millions of repos.

Score: **75/100 (B)**. Four operational weaknesses found:

| # | Finding | Attack | Blast radius |
|---|---------|--------|--------------|
| 1 | `DATABASE_URL=null` caused silent pipeline crash — tests pass, environment collapses | `env` | checkout → install → deploy |
| 2 | `API_KEY` has no validation — null injection propagates past 3 steps before failing | `env` | all authenticated steps |
| 3 | No retry logic on `git checkout` — a single connection reset kills the entire run | `network` | entire pipeline |
| 4 | `node` runtime version unpinned — any major bump breaks the build silently | `dependency` | install → build → test |

Timing agent found nothing. **It went extinct.** Fitness collapsed to 2.5 after 5 mutations with zero triggers.

```
💀 AGENT OBITUARY
   Species: timing   Agent: agent_timing_cef5f0e0
   Mutations: 5 | Failures triggered: 0 | Fitness: 2.5
   Cause: FITNESS COLLAPSE
   The pipeline survived every timing attack. This species line ends here.
```

Replay this exact run:
```bash
crucible replay --trace trc_c003093279
```

---

## See it

> **GIF coming** — record with `asciinema rec demo.cast && agg demo.cast demo.gif`

To record locally now:

```bash
# Install recorder
pip install asciinema
asciinema rec demo.cast

# In the recording:
python cli/crucible.py attack --demo --rich

# Convert to GIF (requires agg: https://github.com/asciinema/agg)
agg demo.cast demo.gif
```

The `--rich` mode shows:
- Kill screens when vulnerabilities are found
- Agent obituaries when fitness collapses
- Score bar filling as attacks complete
- Final report card with component breakdown

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/rudranpatra/crucible.git
cd crucible/crucible
pip install -r requirements.txt

# 2. Run demo (no workflow file needed)
python runner.py demo

# 3. Attack a real workflow
python cli/crucible.py attack --target .github/workflows/ci.yml --rich
```

---

## How it works

```
Your workflow  ──▶  Adversarial agents attack it  ──▶  Resilience score  ──▶  Replayable trace
                              │
              ┌───────────────┴──────────────────┐
              │                                  │
     Finds failures → survives              Finds nothing → fitness drops
     fitness grows → evolves               5+ attempts → extinct
              │                                  │
              └───────────────┬──────────────────┘
                              │
                    Every trace compounds into
                    operational foresight memory
```

Agents are **purely algorithmic** — no LLM, no external API, no cloud.
The evolutionary pressure is the intelligence.

---

## All commands

```bash
# Attack
python cli/crucible.py attack --demo                        # demo target
python cli/crucible.py attack --demo --rich                 # rich terminal UI
python cli/crucible.py attack --demo --shadow               # evolutionary shadow agents
python cli/crucible.py attack --target workflow.yml         # real workflow
python cli/crucible.py attack --demo --attacks timing,env   # specific types
python cli/crucible.py attack --demo --github-comment       # post score to GitHub PR
python cli/crucible.py attack --demo --quiet                # just score/100
python cli/crucible.py attack --demo --json                 # full JSON output

# Traces
python cli/crucible.py replay --trace trc_abc123            # replay a stored trace
python cli/crucible.py patterns                             # failure patterns across runs
python cli/crucible.py status                               # stored traces summary

# Evolution
python cli/crucible.py evolution                            # species fitness, extinction log

# Badge
python cli/crucible.py badge --score 73 --output badge.svg  # README badge
python cli/crucible.py badge --target workflow.yml -o b.svg # attack then badge

# Web dashboard
python cli/crucible.py serve                                # http://127.0.0.1:7331
python cli/crucible.py serve --port 8080
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

Every run produces a **0–100 score** with four weighted components:

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
F  < 40   Critical — will break under realistic operational pressure
```

Scores are marked **stale** after 30 days and require a re-run.

---

## Evolutionary mechanics

### Agent fitness

Every agent has a fitness score (0–100). After each run:
- Agents that trigger failures **gain** fitness
- Agents that find nothing **lose** fitness
- Below fitness 20 after 5+ attempts → **extinct**, logged to failure cemetery

### Shadow agents (`--shadow`)

Every production agent spawns a shadow running alternative mutations on a copy of the target. Shadow never touches the real target.

```bash
python cli/crucible.py attack --demo --shadow
```

Shadow trigger rate > production rate by 20% for 3+ consecutive runs → shadow is **promoted**. Promotion is logged as an evolutionary event.

### Survival index (`evolution` command)

Species fitness accumulates **across all runs** — not just the current one. Species that consistently find failures become dominant. Species that never do go extinct.

```bash
python cli/crucible.py evolution
# Species fitness, dominant/extinct status, generation, lineage depth
```

---

## Replayable traces

Every run writes a `.crucible` file to `traces/`:

```json
{
  "trace_id": "trc_c003093279",
  "target": "Node.js CI",
  "attack_types": ["timing", "env", "reorder", "network", "dependency"],
  "resilience_score": 75.9,
  "failure_points": [
    "Env corruption: DATABASE_URL → path_traversal caused pipeline failure",
    "Network chaos: connection_reset on git_checkout — no retry logic detected",
    "Dependency failure: node — major_bump (unpinned package vulnerable)"
  ],
  "blast_radius": ["step_using_api_key", "build", "git_checkout", "install"],
  "replay_command": "crucible replay --trace traces/trc_c003093279.crucible"
}
```

Replay the exact attack sequence:

```bash
python cli/crucible.py replay --trace trc_c003093279
```

Traces are reproducible. Share them in postmortems. Use them to verify hardening.

---

## GitHub PR comment

Post a resilience score on every pull request automatically — the Codecov play.

### Step 1 — Add the workflow

Copy `.github/workflows/crucible-template.yml` from this repo into your project's `.github/workflows/`.

### Step 2 — Set environment variables

| Variable | Source |
|----------|--------|
| `GITHUB_TOKEN` | Auto-available in Actions |
| `GITHUB_REPOSITORY` | Auto-set in Actions (e.g. `org/repo`) |
| `PR_NUMBER` | `${{ github.event.number }}` |

### Step 3 — Run

```bash
python cli/crucible.py attack --target .github/workflows/ci.yml --github-comment
```

Every PR gets a comment:

```
🔥 Crucible Resilience Report

🟡 73/100 (C) — Moderate risk

Vulnerabilities detected:
- ⚠️ DATABASE_URL, API_KEY lack input validation
- ⚠️ git_checkout has no retry logic

Blast radius: install, build, deploy
Trace: trc_c003093279

crucible replay --trace trc_c003093279
```

---

## README badge

```bash
python cli/crucible.py badge --score 73 --output badge.svg
```

```markdown
![Crucible Resilience](badge.svg)
```

---

## Playwright integration

Attack Playwright test suites directly — Crucible attacks the user flows themselves:

```bash
python cli/crucible.py attack --target tests/checkout.spec.ts
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
python cli/crucible.py serve
# Open http://127.0.0.1:7331
```

Live attack feed, score history, agent survival log, failure cemetery, vulnerability heatmap.

---

## Project structure

```
crucible/
├── core/
│   ├── engine.py           # Agent lifecycle, execution trace, event loop
│   └── shadow_runner.py    # Shadow/production agent pair management
├── agents/
│   ├── base_agent.py       # Base adversarial agent (all agents inherit this)
│   └── shadow_agent.py     # Shadow — runs alternative mutations on a copy
├── attacks/
│   └── strategies.py       # 5 attack agents: timing, env, reorder, network, dependency
├── scoring/
│   ├── scorer.py           # Resilience scoring 0-100, grade, components
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
│   ├── server.py           # FastAPI web dashboard
│   └── static/index.html   # Dashboard UI
├── runner.py               # Orchestrates all layers (the only file that knows everything)
├── cli/crucible.py         # CLI interface
└── tests/                  # 92 passing tests
```

---

## Architecture principles

1. **Every agent has a fitness score.** Agents below 20 after 5+ attempts die. The death mechanism is what makes this evolutionary, not just agentic.

2. **Every run produces a replayable trace.** The trace is the core data artifact. Everything else — scoring, patterns, evolution — is derived from traces.

3. **The runner is the only place that knows about all layers.** Engine, agents, scorer, memory don't import each other. Only `runner.py` orchestrates them.

4. **Demo mode always works without any real pipeline.** `create_demo_target()` produces a realistic synthetic target. Tests use this.

5. **No LLM in core logic.** Agents are algorithmic. The evolutionary pressure is the intelligence.

---

## Development

```bash
# Clone and install
git clone https://github.com/rudranpatra/crucible.git
cd crucible/crucible
pip install -r requirements.txt

# Run all tests
python3 -m pytest tests/ -v
# 92 passed in ~7s

# Run demo
python runner.py demo

# Run with rich UI
python cli/crucible.py attack --demo --rich
```

Tests cover: engine, all 5 attack agents, resilience scorer, survival index scorer, shadow agent, shadow runner, terminal dashboard, GitHub commenter, SVG badge, Playwright parser, full end-to-end run.

---

## Roadmap

- **v0.1** ✅ — 5 attack types, resilience scoring, replayable traces, rich dashboard, shadow agents, survival index, GitHub PR comments, Playwright integration
- **v0.2** — GitLab CI + Jenkins parsers, `crucible diff` to compare two traces
- **v0.3** — Federated trace sharing: opt-in anonymized corpus, cross-deployment pattern fingerprinting
- **v1.0** — Darwin Runtime: self-evolving attack strategies, full evolutionary agent infrastructure

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
