# Crucible

> Your CI/CD pipeline has failure modes it has never encountered. Crucible finds them before production does.

Crucible is an open-source adversarial intelligence engine for CI/CD pipelines and QA workflows.
It deploys autonomous adversarial agents that mutate, stress, and attack your operational workflows —
then scores resilience, generates replayable attack traces, and builds an evolving map of where your system breaks.

This is not a testing framework. It is evolutionary pressure applied to your infrastructure.

---

## What it does

- Connects to GitHub Actions, GitLab CI, Jenkins, Playwright, Robot Framework
- Deploys adversarial agents that mutate timing, corrupt environments, inject failures, reorder steps
- Scores pipeline resilience in real time
- Generates replayable adversarial traces — exact mutation sequences you can replay, debug, and audit
- Builds a weakness graph showing blast radius and failure propagation
- Learns from every run — attack patterns compound over time

---

## Core concepts

**Adversarial agents** — autonomous agents that apply specific attack strategies to your workflows

**Resilience score** — a 0–100 score measuring how well your pipeline survives pressure

**Attack trace** — a fully replayable record of the exact mutation sequence that caused a failure

**Weakness graph** — a map of failure propagation across your pipeline components

**Survival pressure** — the foundational metaphor. Systems that survive pressure are reliable. Systems that don't reveal where they actually break.

---

## Quick start

```bash
pip install crucible-gym
crucible init
crucible attack --target .github/workflows/ci.yml --attacks timing,env,reorder
crucible score
crucible replay --trace traces/latest.json
```

---

## Architecture

```
crucible/
├── core/           # Execution engine, agent runtime, event loop
├── agents/         # Adversarial agent implementations
├── attacks/        # Attack strategy library
├── integrations/   # GitHub Actions, GitLab, Jenkins, Playwright connectors
├── scoring/        # Resilience scoring engine
├── memory/         # Attack trace storage, failure pattern memory
├── dashboard/      # Local web dashboard
├── cli/            # Command line interface
└── docs/           # Documentation
```

---

## Attack types (v0.1)

| Attack | What it does |
|--------|-------------|
| `timing` | Mutates execution timing, introduces delays, creates race conditions |
| `env` | Corrupts environment variables, injects malformed values |
| `reorder` | Reorders workflow steps to expose dependency assumptions |
| `network` | Simulates network instability, timeouts, partial failures |
| `dependency` | Injects dependency drift, version conflicts, missing packages |

---

## Resilience score

Scores are calculated from:
- Failure rate under attack
- Recovery time
- Blast radius (how many downstream steps fail)
- Reproducibility of failures
- Attack surface breadth

Score decays over time if not re-tested. A score from 6 months ago is marked stale.

---

## Replayable traces

Every attack run produces a `.crucible` trace file:

```json
{
  "trace_id": "trc_abc123",
  "target": ".github/workflows/ci.yml",
  "attack_sequence": [...],
  "mutations": [...],
  "failure_point": "step:build:timing_injection_47ms",
  "blast_radius": ["test", "deploy"],
  "resilience_score": 34,
  "replay_command": "crucible replay --trace traces/trc_abc123.crucible"
}
```

Traces are reproducible. Share them with your team. Use them in postmortems.

---

## Open source

Crucible core is fully open source under Apache 2.0:
- Runtime and execution engine
- All attack strategies
- Resilience scoring model
- Integrations
- Trace format specification

---

## Roadmap

- v0.1 — GitHub Actions, 5 attack types, resilience scoring, replayable traces
- v0.2 — Shadow agent runner, side-by-side strategy comparison
- v0.3 — Survival scoring across runs, agent fitness tracking
- v0.4 — Federated attack network (hosted), cross-deployment pattern detection
- v1.0 — Darwin Runtime — full evolutionary agent infrastructure

---

## Philosophy

Everyone is building smarter AI.

Almost nobody is building pressure-tested AI.

Trust in autonomous systems will not come from capability claims.
It will come from systems that have survived adversarial pressure and can prove it.

Crucible is that pressure.
