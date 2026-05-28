# Claude Code: Crucible Development Prompt

## What this project is

Crucible is an open-source adversarial intelligence engine for CI/CD pipelines.
It deploys autonomous adversarial agents that attack, stress, and mutate operational
workflows — then scores resilience, generates replayable attack traces, and builds
an evolving map of where systems break under pressure.

This is NOT a testing framework. It is evolutionary pressure applied to infrastructure.

The long-term vision: a self-evolving system where agents that find failures survive,
agents that don't get killed, and the accumulated attack traces become an operational
foresight graph that predicts failures before they reach production.

## Project structure

```
crucible/
├── core/engine.py              # Execution engine, agent lifecycle, event loop
├── agents/base_agent.py        # Base adversarial agent (all agents inherit this)
├── attacks/strategies.py       # 5 attack agents: timing, env, reorder, network, dependency
├── integrations/
│   └── github_actions/
│       └── parser.py           # Parses GitHub Actions YAML into attack targets
├── scoring/scorer.py           # Resilience scoring 0-100, grade, components
├── memory/trace_memory.py      # Persists traces, indexes them, detects patterns
├── runner.py                   # Orchestrates a full attack run
├── cli/crucible.py             # CLI: attack, replay, patterns, status
├── tests/test_crucible.py      # 14 passing tests
├── requirements.txt
├── setup.py
└── README.md
```

## Current state (v0.1.0)

Working:
- All 5 attack agents (timing, env, reorder, network, dependency)
- Resilience scoring with 4 components
- Replayable trace storage (.crucible files)
- Failure pattern analysis across traces
- GitHub Actions YAML parser
- Demo mode (no real pipeline needed)
- CLI interface
- 14 passing tests

## How to run

```bash
pip install -r requirements.txt

# Demo run (no real pipeline needed)
python runner.py demo

# Attack a real workflow
python cli/crucible.py attack --target .github/workflows/ci.yml

# Run specific attacks
python cli/crucible.py attack --demo --attacks timing,env,network

# Replay a trace
python cli/crucible.py replay --trace trc_abc123

# See failure patterns
python cli/crucible.py patterns

# Run tests
python -m pytest tests/ -v
```

## What to build next — in priority order

### Priority 1: Rich terminal dashboard (this week)
Replace plain print output with a rich terminal UI using the `rich` library.

What it should show:
- Live attack progress with agent IDs and status
- Resilience score bar that fills as attacks complete
- Agent survival table (alive/dead, fitness scores)
- Failure cemetery with cause of death
- Weakness graph as a tree view
- Final report card

File to create: `dashboard/terminal.py`
Integrate into: `runner.py` (add `--rich` flag to CLI)

### Priority 2: Shadow agent runner
Every production agent spawns a shadow that tries a different strategy.
Shadow never touches the target directly — it runs alternative mutations on a copy.
When shadow consistently outperforms production, it stages for promotion.

Files to create:
- `agents/shadow_agent.py` — wraps any BaseAdversarialAgent, runs alternative strategies
- `core/shadow_runner.py` — manages shadow/production pairs, tracks deltas, triggers promotions

Logic:
- Shadow tries mutations in a different order, with different parameters
- Compare trigger rates: shadow vs production
- If shadow trigger_rate > production trigger_rate by >20% for 3+ runs → promote shadow
- Log promotions as evolutionary events

### Priority 3: Darwin scoring layer
Add evolutionary pressure over time. Agents aren't scored per-run only —
they're scored across their entire lifetime.

Extend `core/engine.py`:
- `generation` counter per agent
- `lineage_depth` (how many ancestor agents this one descended from)
- `mutation_history` (what strategy changes were made)

Add `scoring/darwin_scorer.py`:
- Fitness score weighted by: success rate + lineage depth + generation age
- Agents in later generations that outperform ancestors get promoted
- Add `species` concept: agents of the same type that share mutation history

### Priority 4: Local web dashboard
A local FastAPI + HTML dashboard that shows:
- Live attack feed
- Agent survival graph (fitness over time, line chart)
- Failure cemetery (table of dead agents)
- Resilience score history (line chart per target)
- Weakness heatmap (which steps fail most often)

Files to create:
- `dashboard/server.py` — FastAPI app
- `dashboard/static/index.html` — single-file dashboard

Keep it dependency-light. FastAPI + uvicorn + vanilla JS only.

### Priority 5: Playwright integration
Parse Playwright test suites as attack targets.
Playwright tests already define user flows — Crucible attacks the flows themselves.

File to create: `integrations/playwright/parser.py`

What to extract from Playwright tests:
- Page navigation sequences
- Element interaction chains
- Network request patterns
- Assertion checkpoints

Attack strategies specific to Playwright:
- `timing` attacks on page load waits
- `network` chaos on fetch/XHR calls
- `reorder` on navigation sequences

### Priority 6: Federated attack network (future moat)
This is the long-term moat — do NOT build this until v0.3+.

When ready:
- Each deployment can opt-in to share anonymized attack traces
- Shared traces go to a central pattern graph
- Pattern graph surfaces cross-company failure fingerprints
- Hosted version gets the full graph; self-hosted gets local only

This is what turns Crucible from a tool into a platform.

## Architecture principles to preserve

1. Every agent has a fitness score. Agents that don't trigger failures lose fitness.
   Agents that hit fitness < 20 after 5+ attempts die. This is non-negotiable.
   The death mechanism is what makes this evolutionary, not just agentic.

2. Every run produces a replayable trace. The trace is the core data artifact.
   Everything else — scoring, patterns, evolution — is derived from traces.
   Traces are stored as `.crucible` JSON files. Format must stay stable.

3. The runner is the only place that knows about all layers.
   Engine, agents, scorer, memory don't import each other.
   Only runner.py orchestrates them. Keep this clean.

4. Demo mode must always work without any real pipeline.
   `create_demo_target()` in the GitHub Actions parser produces a realistic
   synthetic target. Tests use this. New features should support demo mode.

5. The biological metaphor is intentional and load-bearing.
   Use: species, lineage, fitness, mutation, generation, extinction, survival.
   Do NOT use: "worker", "task", "job", "pipeline stage" as agent vocabulary.
   The framing is what makes this memorable and viral.

## Code style

- Python 3.9+
- Type hints on all function signatures
- Dataclasses for data structures
- async/await for all agent execution
- No external LLM calls in core logic (agents are algorithmic, not LLM-driven in v0.1)
- Tests in tests/ using pytest + pytest-asyncio
- Every new module gets at least 2 tests

## The thing that must stay true

The attack traces are the product. Not the agents. Not the scoring.
Every feature decision should ask: does this make traces more valuable,
more replayable, more useful as evidence in a postmortem?

If yes, build it. If not, question it.
