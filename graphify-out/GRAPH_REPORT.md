# Graph Report - .  (2026-06-24)

## Corpus Check
- Corpus is ~20,477 words - fits in a single context window. You may not need a graph.

## Summary
- 451 nodes · 752 edges · 34 communities (26 shown, 8 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 135 edges (avg confidence: 0.61)
- Token cost: 4,200 input · 3,100 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Adversarial Agent Base Layer|Adversarial Agent Base Layer]]
- [[_COMMUNITY_Attack Strategies and Results|Attack Strategies and Results]]
- [[_COMMUNITY_Darwinian Fitness Scoring|Darwinian Fitness Scoring]]
- [[_COMMUNITY_CI Pipeline and Community Health|CI Pipeline and Community Health]]
- [[_COMMUNITY_Playwright Target Parsing|Playwright Target Parsing]]
- [[_COMMUNITY_Terminal Dashboard UI|Terminal Dashboard UI]]
- [[_COMMUNITY_GitHub PR Integration|GitHub PR Integration]]
- [[_COMMUNITY_CLI Command Interface|CLI Command Interface]]
- [[_COMMUNITY_Demo Run Visualization|Demo Run Visualization]]
- [[_COMMUNITY_Shadow Runner Engine|Shadow Runner Engine]]
- [[_COMMUNITY_Web Dashboard Server|Web Dashboard Server]]
- [[_COMMUNITY_GitHub Actions Parser|GitHub Actions Parser]]
- [[_COMMUNITY_Shadow Agent Evolution|Shadow Agent Evolution]]
- [[_COMMUNITY_Badge and Integration Tests|Badge and Integration Tests]]
- [[_COMMUNITY_Package Initialization|Package Initialization]]
- [[_COMMUNITY_Demo Recording Script|Demo Recording Script]]
- [[_COMMUNITY_Test Dependencies|Test Dependencies]]
- [[_COMMUNITY_Crucible Roadmap|Crucible Roadmap]]
- [[_COMMUNITY_Feature Request Template|Feature Request Template]]
- [[_COMMUNITY_Crucible Gym Package|Crucible Gym Package]]
- [[_COMMUNITY_PyYAML Dependency|PyYAML Dependency]]
- [[_COMMUNITY_Rich Dependency|Rich Dependency]]

## God Nodes (most connected - your core abstractions)
1. `CrucibleRunner` - 37 edges
2. `GitHubCommenter` - 29 edges
3. `CrucibleEngine` - 28 edges
4. `AttackResult` - 27 edges
5. `BaseAdversarialAgent` - 24 edges
6. `ShadowRunner` - 24 edges
7. `ShadowAgent` - 23 edges
8. `TestDarwinScorer` - 21 edges
9. `TestPlaywrightParser` - 20 edges
10. `DarwinScorer` - 19 edges

## Surprising Connections (you probably didn't know these)
- `Demo Mode (create_demo_target)` --semantically_similar_to--> `CI Job: Crucible Self-Attack (crucible-self-check)`  [INFERRED] [semantically similar]
  crucible/README.md → .github/workflows/ci.yml
- `Parallel Agent Execution via asyncio.gather` --conceptually_related_to--> `Agent Fitness Scoring Mechanism`  [INFERRED]
  CHANGELOG.md → crucible/README.md
- `Crucible Full Reference Documentation` --references--> `Crucible Resilience Check Workflow Template`  [EXTRACTED]
  crucible/README.md → .github/workflows/crucible-template.yml
- `API Key Authentication for Web Dashboard` --rationale_for--> `Web Dashboard (FastAPI + uvicorn)`  [EXTRACTED]
  CHANGELOG.md → crucible/README.md
- `Attack Extension Protocol (Adding New Attack Types)` --conceptually_related_to--> `Attack Type: timing`  [INFERRED]
  CONTRIBUTING.md → crucible/README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CI Quality Gate: Tests + Lint + Typecheck** — ci_ci_job_test, ci_ci_job_lint, ci_ci_job_typecheck [EXTRACTED 1.00]
- **Evolutionary Mechanics: Fitness + Shadow + Extinction** — crucible_readme_agent_fitness, crucible_readme_shadow_agents, readme_evolutionary_pressure_concept [EXTRACTED 1.00]
- **Five Attack Types Portfolio** — crucible_readme_attack_timing, crucible_readme_attack_env, crucible_readme_attack_reorder, crucible_readme_attack_network, crucible_readme_attack_dependency [EXTRACTED 1.00]

## Communities (34 total, 8 thin omitted)

### Community 0 - "Adversarial Agent Base Layer"
Cohesion: 0.06
Nodes (26): ABC, BaseAdversarialAgent, Base Adversarial Agent All attack agents inherit from this. Each agent has a str, Post-attack reflection.         What worked? What didn't? Should strategy change, Every adversarial agent:     - Has a specific attack strategy     - Executes mut, Generate a list of mutations to apply to the target workflow., Apply a single mutation and return the result., Full attack cycle:         1. Generate mutations         2. Apply each mutation (+18 more)

### Community 1 - "Attack Strategies and Results"
Cohesion: 0.07
Nodes (22): AttackResult, Any, DependencyDriftAgent, EnvCorruptionAgent, NetworkChaosAgent, Attack Strategies — v0.1 Five adversarial attack types for CI/CD pipeline stress, Reorders workflow steps to expose hidden dependency assumptions.     Finds steps, Simulates network instability: packet loss, latency spikes, DNS failures, partia (+14 more)

### Community 2 - "Darwinian Fitness Scoring"
Cohesion: 0.06
Nodes (9): DarwinScorer, Darwin Scorer Evolutionary pressure applied across runs, not just within a singl, Tracks agent species performance across all runs.      Fitness = survival_score, Record one run result for an agent species., Log a shadow→production promotion as an evolutionary event., Lifetime fitness score 0–100.         Weighted: trigger_rate (40%) + lineage_dep, darwin(), Tests for Darwin scorer — lifetime evolutionary fitness tracking. (+1 more)

### Community 3 - "CI Pipeline and Community Health"
Cohesion: 0.07
Nodes (40): Bug Report Issue Template, API Key Authentication for Web Dashboard, Crucible Changelog, Parallel Agent Execution via asyncio.gather, CI Job: Lint and Format (ruff), CI Job: Security Audit (pip-audit), CI Job: Crucible Self-Attack (crucible-self-check), CI Job: Tests Matrix (Python 3.9–3.12) (+32 more)

### Community 4 - "Playwright Target Parsing"
Cohesion: 0.07
Nodes (8): create_demo_playwright_target(), PlaywrightParser, Playwright Integration Parses Playwright test suites as Crucible attack targets., Converts Playwright test files into Crucible attack targets.      Extracts:, Demo Playwright target for testing without a real test file., Extract ordered interaction steps from JS/TS content., Target from Playwright parser should work with Crucible attack agents., TestPlaywrightParser

### Community 5 - "Terminal Dashboard UI"
Cohesion: 0.08
Nodes (7): CrucibleDashboard, Crucible Rich Terminal Dashboard Screenshot-worthy output: kill screens, agent o, The death announcement — designed to be screenshot-worthy., Printed when a critical vulnerability is discovered. Screenshot bait., Rich terminal UI for Crucible runs.     Prints styled panels as events happen —, Tests for Rich terminal dashboard., TestCrucibleDashboard

### Community 6 - "GitHub PR Integration"
Cohesion: 0.14
Nodes (5): GitHubCommenter, Posts a formatted Crucible report as a GitHub PR comment.      Reads from env va, Post (or update) a Crucible report comment on the PR.         Returns True on su, Request, TestGitHubCommenter

### Community 7 - "CLI Command Interface"
Cohesion: 0.13
Nodes (12): cmd_attack(), cmd_badge(), cmd_evolution(), cmd_patterns(), cmd_replay(), cmd_status(), _score_to_grade(), CrucibleRunner (+4 more)

### Community 8 - "Demo Run Visualization"
Cohesion: 0.13
Nodes (24): Dependency Attack Agent (agent_dependency_99ad74e9), Env Attack Agent (agent_env_a5629a5c), Network Attack Agent (agent_network_5c6b0cfa), Agent Obituary: timing agent DEAD (fitness 2.5/100, fitness collapse), Timing Attack Agent (agent_timing_cef5f0e0), Dependency Attack Type (Dependency Drift), Env Attack Type (Environment Variable Corruption), Network Attack Type (Network Chaos) (+16 more)

### Community 9 - "Shadow Runner Engine"
Cohesion: 0.14
Nodes (8): Return attack types where shadow consistently beats production., Maintains one ShadowAgent per attack type.     On each attack cycle, runs both p, Register an attack type for shadow tracking., Register multiple attack types at once., Run paired production + shadow attack for one attack type.         Returns compa, Run all registered attack types with shadow tracking., ShadowRunner, TestShadowRunner

### Community 10 - "Web Dashboard Server"
Cohesion: 0.16
Nodes (9): cmd_serve(), create_app(), Crucible Web Dashboard Local FastAPI server: live attack feed, score history, ag, serve(), Attack Trace Memory Stores, indexes, and retrieves adversarial traces. Traces ar, Cluster failure patterns across all traces.         This is the beginning of the, Persists attack traces to disk.     Each trace is a replayable record of exactly, StoredTrace (+1 more)

### Community 11 - "GitHub Actions Parser"
Cohesion: 0.18
Nodes (8): create_demo_target(), GitHubActionsParser, parse_workflow(), GitHub Actions Integration Parses GitHub Actions workflow YAML files into Crucib, Converts a GitHub Actions workflow file into a structured target     that Crucib, Creates a demo target for testing without a real workflow file., demo_target(), demo_target()

### Community 12 - "Shadow Agent Evolution"
Cohesion: 0.20
Nodes (5): Slightly alter the shadow target's parameters so the shadow agent         explor, Wraps a production agent class and runs an alternative mutant strategy     on a, Run production and shadow agents.         Shadow works on a perturbed copy so it, ShadowAgent, TestShadowAgent

### Community 13 - "Badge and Integration Tests"
Cohesion: 0.21
Nodes (5): generate_svg_badge(), GitHub PR Commenter Posts Crucible resilience scores as PR comments on every run, Generate a Shields.io-style SVG badge for README embedding., Tests for GitHub commenter, badge generator, and Playwright parser., TestBadgeGenerator

## Knowledge Gaps
- **24 isolated node(s):** `crucible-gym`, `record_demo.sh script`, `Bug Report Issue Template`, `Feature Request Issue Template`, `Crucible Changelog` (+19 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CrucibleRunner` connect `CLI Command Interface` to `Adversarial Agent Base Layer`, `Attack Strategies and Results`, `Darwinian Fitness Scoring`, `Terminal Dashboard UI`, `GitHub PR Integration`, `Shadow Runner Engine`, `Web Dashboard Server`, `GitHub Actions Parser`?**
  _High betweenness centrality (0.417) - this node is a cross-community bridge._
- **Why does `GitHubCommenter` connect `GitHub PR Integration` to `Playwright Target Parsing`, `Badge and Integration Tests`, `CLI Command Interface`?**
  _High betweenness centrality (0.173) - this node is a cross-community bridge._
- **Why does `DarwinScorer` connect `Darwinian Fitness Scoring` to `Web Dashboard Server`, `CLI Command Interface`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `CrucibleRunner` (e.g. with `cmd_attack()` and `cmd_badge()`) actually correct?**
  _`CrucibleRunner` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `GitHubCommenter` (e.g. with `CrucibleRunner` and `._post_github_comment()`) actually correct?**
  _`GitHubCommenter` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `CrucibleEngine` (e.g. with `AttackResult` and `BaseAdversarialAgent`) actually correct?**
  _`CrucibleEngine` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AttackResult` (e.g. with `AttackEvent` and `AttackStatus`) actually correct?**
  _`AttackResult` has 12 INFERRED edges - model-reasoned connections that need verification._