# Crucible OSS/Cloud Engine Split — Codex Plan

## The idea

Move Crucible's proprietary intelligence out of the public PyPI/GitHub codebase while keeping Crucible useful as an open-source product.

### Before

Everything is public and ships on PyPI.

```text
crucible
└── Full engine
    ├── attacks
    ├── threat reasoning
    ├── scoring
    ├── agents
    ├── memory
    └── orchestration
```

### After

```text
crucible                    crucible-cloud
PUBLIC                          PRIVATE
│                               │
├── CLI                         ├── Full engine
├── API client                  ├── Advanced attacks
├── Basic local engine          ├── Threat reasoning
├── Basic attacks               ├── Proprietary scoring
├── Basic scoring               ├── Evidence intelligence
└── Integrations                └── Advanced orchestration
        │
        └────── HTTPS ───────────────►
```

The HTTPS arrow represents the `API client` / cloud mode only. The local engine and basic attacks run offline.

### Why

- Protect IP — the differentiated engine no longer ships publicly.
- Keep OSS adoption — users can still `pip install crucible-gym` and run a useful local baseline.
- Create a Cloud moat — Cloud provides the advanced capabilities.
- Keep the GitHub repo public — maintain community/distribution benefits.
- Separate future development — proprietary engine improvements happen privately.
- Avoid breaking 0.4.2 — freeze the existing full-local version; introduce the new architecture in 0.5.x.

This is not a file-move exercise. We are not hiding the existing engine; we are replacing the public engine with a new limited implementation and making the real engine private.

## Scope reality checks

- A "limited public engine" is **new code** authored independently. You cannot get it by deleting lines from `attacks/strategies.py` (31 KB, 6 agent classes), and you cannot derive the public `LocalEngine`, `BaseAgent`, or `BasicScorer` from the moved proprietary files without re-exposing the same algorithms under Apache 2.0. Someone must author a simpler public replacement and keep the real one private.
- This is forever governance overhead, not one-time migration cost. Every future improvement needs a per-release classification: OSS-local, cloud-only, or both.
- The test split is not MOVE only. `crucible-cloud/tests/test_engine.py` tests the real engine; the public repo needs **new tests** for its new simplified engine.
- Versioning plan is sound: `0.4.2` frozen → `0.5.x` transitional → `1.0.0` stable contract.

## Real dependency graph (confirmed from code)

`cli/crucible.py` performs an in-process import with a `sys.path` hack:

```python
# cli/crucible.py
sys.path.insert(0, ...)
from runner import CrucibleRunner
```

There is no subprocess boundary today. The whole tree is a flat import graph rooted at the repo directory, not a proper `crucible.*` package.

Current edges:

```text
cli/crucible.py -> runner.py
runner.py -> core.engine, attacks.strategies, scoring.scorer, scoring.darwin_scorer,
             memory.trace_memory, integrations.github_actions/gitlab/playwright parsers
core.engine -> (leaf, no internal deps)
core.shadow_runner -> agents.base_agent, agents.shadow_agent, core.engine
attacks.strategies -> agents.base_agent
threats.planner -> threats.schema
threats.validator -> core.engine, memory.trace_memory, threats.schema
threats.importer -> threats.schema
scoring.scorer -> agents.base_agent
scoring.darwin_scorer -> core.file_lock
memory.trace_memory -> core.file_lock
agents.base_agent -> core.engine
agents.shadow_agent -> agents.base_agent, core.engine
dashboard.server -> memory.trace_memory
```

### What this graph implies

1. `core/engine.py` and `agents/base_agent.py` are the two true chokepoints. Every proprietary module inherits from or instantiates one of them.
2. A public "basic engine" needs its **own** `engine`-equivalent and `base_agent`-equivalent. It cannot reuse the cloud base classes without importing proprietary code.
3. `runner.py`, `scoring/scorer.py`, and `attacks/strategies.py` each need a **NEW public-side implementation**, not a deletion or a move. That is real engineering work on top of the cloud migration.
4. `threats/importer.py` and `dashboard/server.py` need line-by-line review before deciding whether they are plumbing or leak proprietary intelligence.

## File split table

| Current file | Current role | IP sensitivity | Action | Destination | Public replacement | Dependencies | Tests affected |
|---|---|---|---|---|---|---|---|
| `core/engine.py` | Trace/agent state machine, `CrucibleEngine` class — everything funnels through this | High | MOVE | crucible-cloud | NEW: minimal `LocalEngine` (single-pass, no darwin/evolution state) | none (leaf) | `test_crucible.py`, `test_shadow.py`, `test_threats.py` (all import via engine) |
| `core/shadow_runner.py` | Shadow-mode dual execution | High | MOVE | crucible-cloud | none — cut from OSS entirely | `agents.base_agent`, `agents.shadow_agent`, `core.engine` | `test_shadow.py` |
| `core/file_lock.py` | Generic file locking util | None | KEEP | public | itself | none (leaf) | none named, low risk |
| `attacks/strategies.py` | 6 attack agents (Timing/EnvCorruption/StepReorder/NetworkChaos/DependencyDrift/SupplyChain) | High | MOVE + NEW | crucible-cloud (full) + crucible (thin) | NEW: 1–2 basic agents only (e.g. SupplyChain static-only, already the "not real execution" one) | `agents.base_agent` | `test_crucible.py`, `test_integrations.py` |
| `threats/planner.py` | Threat generation/planning | High | MOVE | crucible-cloud | none | `threats.schema` | `test_threats.py` |
| `threats/validator.py` | Validates threats against execution trace | High | MOVE | crucible-cloud | none | `core.engine`, `memory.trace_memory`, `threats.schema` | `test_threats.py` |
| `threats/importer.py` | Imports threat definitions | Medium | REVIEW | likely KEEP public (format/adapter, not intelligence) | itself | `threats.schema` | `test_threats.py` |
| `threats/schema.py` | Threat/Evidence dataclasses | Low | KEEP | public | itself — this is the API contract | none (leaf) | shared by threats tests |
| `scoring/scorer.py` | ResilienceScorer — the actual scoring algorithm | High | MOVE + NEW | crucible-cloud (full) + crucible (thin) | NEW: basic pass/fail or simple weighted count, not the real formula | `agents.base_agent` | `test_crucible.py`, `test_darwin.py` |
| `scoring/darwin_scorer.py` | Evolutionary/darwin scoring | High | MOVE | crucible-cloud | none | `core.file_lock` | `test_darwin.py` |
| `memory/trace_memory.py` | Persisted trace storage | Medium-High | MOVE | crucible-cloud | NEW: thin local trace cache (just enough for `replay` on local runs, if kept) | `core.file_lock` | `test_darwin.py`, `test_threats.py`, `test_dashboard.py` |
| `agents/base_agent.py` | `BaseAdversarialAgent`, `AttackResult` — base class everything inherits | High | MOVE + NEW | crucible-cloud (full) + crucible (thin) | NEW: minimal base class for the 1–2 public agents — **cannot be shared**, or OSS imports proprietary base | `core.engine` | `test_crucible.py`, `test_shadow.py`, `test_integrations.py` |
| `agents/shadow_agent.py` | Shadow-mode agent | High | MOVE | crucible-cloud | none | `agents.base_agent`, `core.engine` | `test_shadow.py` |
| `runner.py` | Orchestrator — the architectural seam | High | REWRITE | split: thin `runner.py` stays public, mode-aware; real orchestration logic MOVEs to cloud as the `/v1/runs` handler | new public `runner.py`: local mode calls `LocalEngine` in-process, cloud mode POSTs to `/v1/runs`; selection explicit via `--cloud`/config, never silent fallback | today: `core.engine`, `attacks.strategies`, `scoring.scorer`, `scoring.darwin_scorer`, `memory.trace_memory`, 3 integration parsers | `test_crucible.py`, `test_v03.py`, `test_integrations.py` — need full rewrite, not move |
| `cli/crucible.py` | CLI entrypoint, `sys.path` hack, direct in-process `CrucibleRunner` import | Medium | REWRITE | public | itself, rewritten: remove `sys.path.insert` hack, `from runner import CrucibleRunner` → HTTP client call, add auth/API-key handling | `runner.py` | `test_crucible.py` (CLI-level tests) |
| `dashboard/server.py` | Reads `TraceMemory` for live dashboard | Medium | REVIEW | depends on whether local-run dashboard survives | if local mode kept minimal, NEW thin version reading from local cache only | `memory.trace_memory` | `test_dashboard.py` |
| `dashboard/terminal.py` | Terminal rendering | Low | KEEP | public | itself — pure presentation, no IP | none | none named |
| `sinks/crucible_cloud_sink.py` | Already an API-client-shaped sink (per-attack push to cloud) | Low | KEEP, extend | public | this is your existing template for the HTTP client pattern — reuse its shape for the new `runner.py` | none internal | `test_cloud_sink.py` |
| `integrations/github/*`, `integrations/gitlab/*`, `integrations/github_actions/*`, `integrations/playwright/*` | Target-format parsers | Low | KEEP | public | itself | none of the above depend on them; `runner.py` depends on them | `test_integrations.py` |

## Versioning plan

| Phase | Version | Meaning |
|---|---|---|
| Baseline | `0.4.2` | Frozen last unified release. |
| Transitional | `0.5.x` | Public repo contains thin local engine + cloud client. Cloud repo contains full engine. API contract settles. |
| Stable contract | `1.0.0` | Public OSS API is stable; cloud can evolve independently. |

## Complete flow of work

### 1. Pre-work

- Tag `crucible` `0.4.2` as the baseline release and freeze it.
- Create `cloud-split` feature branches on both `crucible` and `crucible-cloud`.
- Decide the exact OSS capability set: which 1–2 attack agents, scoring formula, replay behavior, and local dashboard scope.
- Line-by-line review of `threats/importer.py` and `dashboard/server.py` to finalize KEEP vs MOVE.
- Decide cloud auth/signup model for OSS users (free-tier signup gate vs. fully open with rate limits) — gates the `/v1/runs` API design in step 2, not just the CLI in step 3.
- `core/file_lock.py` sharing: **decided — duplicate it into `crucible-cloud` as a private utility.** It is generic locking code; the cost of duplication is trivial next to the risk of `crucible-cloud` depending on the public `crucible-gym` package at runtime (which would make cloud depend on the package whose CLI depends on cloud).

### 2. Cloud-side migration (MOVE)

- Move the following files into `crucible-cloud` and repackage them under a proper `crucible_cloud.*` namespace:
  - `core/engine.py`
  - `core/shadow_runner.py`
  - `attacks/strategies.py`
  - `threats/planner.py`
  - `threats/validator.py`
  - `scoring/scorer.py`
  - `scoring/darwin_scorer.py`
  - `memory/trace_memory.py`
  - `agents/base_agent.py`
  - `agents/shadow_agent.py`
  - the orchestration half of `runner.py`
  - a duplicated `core/file_lock.py` (private copy, see decision above)
- Remove any `sys.path` hacks; use package-qualified imports inside `crucible-cloud`.
- Build a `/v1/runs` handler or service that encapsulates the moved `CrucibleRunner` orchestration logic.

### 3. Public-side rewrites (NEW code)

Create new, independent modules in `crucible`:

- `core/local_engine.py` — minimal `LocalEngine` with single-pass execution and no darwin/evolution state.
- `agents/base_agent.py` — minimal public base class and `AttackResult` for the 1–2 public agents.
- `attacks/basic_strategies.py` — 1–2 basic agents only, e.g. a static SupplyChain agent.
- `scoring/basic_scorer.py` — basic pass/fail or simple weighted count.
- `threats/basic_catalog.py` (or `.yaml`) — public threat definitions using `threats/schema.py`, matched to the basic attack agents. Without this, `threats/schema.py` is a contract with no public data using it.
- `runner.py` — mode-aware: local mode calls the new `LocalEngine` in-process, cloud mode POSTs to `/v1/runs`. Selection is explicit (`--cloud` flag or config), never a silent automatic fallback between the two — that ambiguity is exactly the failure mode this split rejected. Remove `sys.path` hack; add API-key/auth handling for cloud mode.
- `cli/crucible.py` — rewrite to import the new `runner.py`, add `--api-key` / env auth handling.
- `memory/local_trace_memory.py` — thin local trace cache if `replay` is kept in the OSS build.
- `dashboard/server.py` — if local dashboard survives, a thin version reading local cache only.

**Re-implementation rule, non-negotiable:** `LocalEngine`, the public `base_agent.py`, `basic_strategies.py`, and `basic_scorer.py` must be authored independently from scratch. They cannot be derived by copying and trimming the moved proprietary files — the public repo is Apache-2.0, so any logic carried over from the proprietary versions gets re-exposed under an open license, defeating the entire purpose of the split.

### 4. Public plumbing to keep

Leave unchanged or extend only:

- `core/file_lock.py`
- `threats/schema.py`
- `threats/importer.py` (after review)
- `dashboard/terminal.py`
- `sinks/crucible_cloud_sink.py` (reuse as the HTTP-client pattern template)
- `integrations/github/*`, `integrations/gitlab/*`, `integrations/github_actions/*`, `integrations/playwright/*`

### 5. Test split

- Move cloud-only tests to `crucible-cloud/tests/`.
- Write **new** public tests for the new public modules (`LocalEngine`, `BasicScorer`, `BasicStrategies`, public `Runner`).
- Rewrite `test_crucible.py`, `test_v03.py`, and `test_integrations.py` to exercise the new public CLI/runner against mocked cloud responses.
- Keep `test_cloud_sink.py` in public and extend it to cover the new runner HTTP-client pattern.

### 5a. Packaging and entry-point wiring

- Update `crucible/pyproject.toml`: `[tool.setuptools.packages.find] include` currently matches `crucible*`, which is how the full engine ships today (confirmed by building the 0.4.2 wheel and inspecting it — `engine.py`, `strategies.py`, `scorer.py`, etc. are all present). Once proprietary modules are removed from the tree, this setting doesn't need to change, but it must be re-verified, not assumed.
- Confirm `[project.scripts] crucible = "crucible.cli.crucible:main"` still resolves after the CLI rewrite.
- Add `httpx` (or equivalent) to `dependencies` for the new cloud-mode HTTP client in `runner.py`.

### 6. Governance and release

- Establish per-release classification: each engine improvement is OSS-local, cloud-only, or both.
- Release `crucible-gym` `0.5.x` with a deprecation path and compatibility shims.
- Stabilize the public API contract at `1.0.0`.

### 7. Validation

- `pip install -e .` and `pytest` pass in the public repo.
- `python -m build` produces a clean wheel for `crucible-gym`; installing it in a fresh venv confirms the `crucible` console script resolves and `crucible --help` works.
- In `crucible-cloud`, `pip install -e .` and `pytest` pass with `crucible-gym` **not** installed, confirming the private `file_lock` copy breaks the circular dependency.
- Integration test: public CLI builds a request, a mocked cloud `/v1/runs` returns a result, and the CLI renders it.
- Smoke test backward-compatible commands (`crucible audit`, `crucible attack`, `crucible compare`).
- Artifact firewall: `python -m build`, then `unzip -l dist/*.whl` and `tar -tf dist/*.tar.gz`, grep for the moved proprietary filenames (`engine.py`, `shadow_runner.py`, `strategies.py`, `planner.py`, `validator.py`, `scorer.py`, `darwin_scorer.py`, `trace_memory.py` under `agents`/`core`/`attacks`/`threats`/`scoring`/`memory`) — must return nothing before publishing `0.5.0`.

## Implementation log

- **Phase 0** (freeze): `v0.4.2` was already tagged in `crucible` before this work started — no action needed. `cloud-split` branches created in both `crucible` and `crucible-cloud`.
- **Phase 2** (cloud migration): done and verified. Moved files live under `crucible-cloud/app/engine/{core,attacks,threats,scoring,memory,agents}/`, repackaged under `app.engine.*`. `core/file_lock.py` and the 3 integration parsers (`github_actions`, `gitlab`, `playwright`) were duplicated into `app/engine/` rather than importing them from the public `crucible-gym` package, per the file_lock decision in §1 (avoids `crucible-cloud` depending on the public package). New `/v1/runs`, `/v1/runs/{id}`, `/v1/runs/{id}/evidence`, `/v1/runs/{id}/report` endpoints added in `app/runs.py`, wired into `app/main.py`. Verified end-to-end: `POST /v1/runs` with `demo_mode=true` executes the real engine and returns a genuine score (not stubbed). 87 moved engine tests + 15 pre-existing app tests pass.
- **New finding, not in the original table:** `cli/crucible.py` has a `validate` subcommand (`cmd_validate`) that directly instantiates `ThreatPlanner`/`ThreatValidator` in-process — a third proprietary entry point beyond `attack`/`compare`, missed in the original file-split table because it wasn't in the dependency graph traced from `runner.py`. Its CLI-level tests (`TestCLI` in the old `test_threats.py`) were removed from the cloud-side test copy (they test the CLI, not the engine) and must be rebuilt in Phase 3 against the new public `validate` command, which now has to call the cloud API rather than running `ThreatValidator` locally.
- **Public threat catalog scope decision:** given the CLI's basic capability set is a single static `SupplyChainAgent`, the public `threats/basic_catalog.py` should ship threat definitions that this one agent can actually attempt (supply-chain/tampering techniques), not a full STRIDE catalog — otherwise most public threats would show as permanently "untested."

- **Phase 3** (public rewrites, independently authored): done and verified. New `crucible/core/local_engine.py` (`LocalEngine`, single-pass, no fitness/darwin state), `crucible/agents/base_agent.py` (renamed `BaseLocalAgent`/`AttackResult` — deliberately different class name from the proprietary `BaseAdversarialAgent`, no shared inheritance), `crucible/attacks/basic_strategies.py` (`BasicSupplyChainAgent` — fresh regex/logic, not copied from `attacks/strategies.py`), `crucible/scoring/basic_scorer.py` (flat 15-point deduction, not the real formula), `crucible/threats/basic_catalog.py`. New mode-aware `crucible/runner.py`: local mode runs the above in-process; cloud mode POSTs to `/v1/runs` via stdlib `urllib` (no new dependency needed — httpx was considered in §5a but wasn't necessary). Mode selection is explicit only (`--engine {local,cloud}` on `attack`/`audit`/`compare`/`badge`, or `CRUCIBLE_ENGINE` env var) — never automatic fallback.
  - `cli/crucible.py` rewritten: package-qualified imports throughout (`crucible.*`, no more `sys.path.insert`), `--engine` wired into the 4 subcommands that construct a runner. `validate`/`replay`/`patterns`/`evolution`/`trend`/`serve` — all depend on capabilities that moved to Cloud (`ThreatValidator`, `TraceMemory`, `DarwinScorer`, `dashboard/server.py`) with no local replacement built in this pass — now fail fast with a clear "requires Crucible Cloud" message instead of crashing on a missing import. `validate` additionally can't be wired to Cloud yet because Cloud has no `/v1/validate` endpoint (not built — see open questions).
  - Verified live end-to-end: same CLI binary, `crucible attack --demo` (local, real `BasicSupplyChainAgent`) and `crucible attack --demo --engine cloud` (real HTTP call to a running `crucible-cloud` instance, real moved engine, real score) both produce genuine results from the same command surface. `crucible audit`, `crucible compare`, `crucible badge` verified against the real repo history.
- **Phase 5** (test split): done. 4 engine-dependent test files (`test_crucible.py`, `test_shadow.py`, `test_darwin.py`, `test_threats.py`) removed from public — their content lives in `crucible-cloud/tests/engine/` (see Phase 2 log entry). New `crucible/tests/test_local_engine.py` covers `LocalEngine`/`BasicSupplyChainAgent`/`BasicScorer`/`CrucibleRunner` mode selection (16 tests). Remaining public tests (`test_dashboard.py`, `test_v03.py`, `test_integrations.py`, `test_cloud_sink.py`) fixed to package-qualified imports; 3 sub-tests in `test_v03.py` that exercised the full attack-agent set against GitLab targets were removed (that coverage now belongs with the moved agents in Cloud). `test_cloud_sink.py`'s per-attack callback tests were updated to exercise `supply_chain` against a real unpinned-action fixture instead of the no-longer-available `env` attack type — and a real gap this surfaced was fixed: the new local runner wasn't invoking `on_attack_result` at all (existing `crucible attack --cloud` per-attack ingestion would have silently stopped working); it now does, with the callback wrapped in try/except so a failing sink can't crash the run (matches prior behavior). Full public suite: **97/97 passing.**
- **Phase 5a** (packaging): done. No new dependency needed (cloud HTTP call uses stdlib `urllib`, not `httpx`). Version bumped to `0.5.0` in `pyproject.toml` and `crucible/__init__.py` (not yet released — this is the working tree on the `cloud-split` branch only).
- **Phase 6** (cut proprietary files from public repo): done, via `git rm` on the `cloud-split` branch (not `main`, not pushed). Also removed: `dashboard/server.py` (its only dependency, `memory.trace_memory`, moved to Cloud, and `cmd_serve` no longer calls it).
- **Phase 7** (validation + artifact firewall): done. `pip install -e .` + full `pytest` pass (97/97). Built the real `crucible_gym-0.5.0` wheel and grepped its contents: confirmed **none** of `core/engine.py`, `core/shadow_runner.py`, `attacks/strategies.py`, `threats/planner.py`, `threats/validator.py`, `scoring/scorer.py`, `scoring/darwin_scorer.py`, `memory/trace_memory.py`, `agents/shadow_agent.py`, or `dashboard/server.py` are present — only the new public modules and existing KEEP files. This is the same technique used earlier in this session to find that 0.4.2 shipped everything; now verified it doesn't.

## Post-push Codex review (pushed commits d389e7d / f1af4ab)

High-risk findings, all verified and fixed:
1. **Grade-boundary divergence** — `cli/crucible.py::_score_to_grade` (90/75/60/40) disagreed with `BasicScorer.grade` (90/80/70/60); `crucible badge --score` could show a different grade than the engine. Fixed: deleted `_score_to_grade`, `cmd_badge` now calls `BasicScorer().grade()`.
2. **`--github-comment` dead on `attack`** — confirmed: `runner.run(github_comment=...)` accepted the flag and never used it. Root cause is architectural, not just "wire it through": `GitHubCommenter` reads `GITHUB_TOKEN`/`GITHUB_REPOSITORY`/`PR_NUMBER` from the *process* environment. Threading `github_comment` into the Cloud API's `RunRequest` would only work if the Cloud server's own process happened to have the calling CI job's env vars — true by accident in a single-tenant self-host, silently wrong for any real multi-tenant deploy. Fixed instead by having the CLI (`cmd_attack`) post the comment itself after getting a result from either engine, matching the pattern `cmd_compare` already used correctly. `runner.run()`'s `github_comment` param and `RunRequest.github_comment` were both removed as a result — the API never had a working version to preserve.
3. **`crucible audit`'s attack list** — local mode only has `supply_chain`, so `dependency`/`env` were silently skipped, producing a "clean" audit that wasn't. Fixed: `cmd_audit` uses `['supply_chain']` in local mode, `['supply_chain', 'dependency', 'env']` under `--engine cloud`.
4. **`/v1/runs/{id}/evidence` always `[]`** — confirmed: the engine's result dict never had an `attack_results` key (checked the real `CrucibleRunner.run()` return statement). Fixed: `/evidence` now returns `failure_points`/`agent_reflections`/`blast_radius`, which the result dict actually has. Verified live against a real cloud run.

Medium-risk findings, reviewed:
- **API key hashing (plain SHA-256)** — reviewed and disagreed with the "fix this" framing. The key itself is `secrets.token_urlsafe(32)` (256 bits of entropy) — for a high-entropy random token, fast hashing is the correct choice (this is how GitHub/Stripe/AWS hash API keys); slow password-hashing algorithms (bcrypt/argon2) solve a different problem (low-entropy human passwords) and would only add per-request latency here with no security benefit. Not changed.
- **`record_audit` call in `/login`** — checked the actual signature (`record_audit(db, event, org=None, success=True, details=None)`) against both call sites: `record_audit(db, "auth.login", success=False)` uses a keyword arg correctly; `record_audit(db, "auth.login", org.name)` passes `org.name` positionally into `org`, also correct. Not a bug — Codex's own writeup hedged this ("may be"), and it wasn't.
- **In-memory `_RUNS` store**, **`--cloud`/`--publish-cloud` alias** — both already documented (ponytail comment; CHANGELOG deprecation note respectively). No new action.
- **`threats/importer.py` duplication** — already verified earlier this session: public copy is a pure local-file format adapter, no external corpus. No drift risk.

Low-risk nits: emoji in `cmd_audit`'s grade indicator was flagged as against "project style" — reviewed and declined. The project's actual established style (PR comments, terminal dashboard, README) uses emoji extensively and deliberately; stripping it from one CLI line while leaving it everywhere else would be inconsistent, and this isn't the project's real style guide. Lazy engine/scorer instantiation in cloud mode and stale `noqa: E402` comments in the moved Cloud engine file: left as-is — trivial, no functional impact, and the latter touches proprietary moved code unnecessarily.

97/97 public tests + 102/102 cloud tests passing after fixes.

## Open questions carried forward (resolve during implementation, not blocking the plan)

- `sinks/crucible_cloud_sink.py` vs. the new mode-aware `runner.py`: **resolved by keeping both, for different jobs.** `runner.py --engine cloud` decides WHERE the attack executes (full engine on Cloud vs. basic engine locally); `--cloud` + `CrucibleCloudSink` decides whether each attack result is also streamed to Cloud's ingest API for historical tracking, regardless of which engine ran it. They compose (`crucible attack --engine cloud --cloud` is a valid, sensible combination). Not a collision once the two questions are named separately, but the flag names being both "cloud" is a legitimate point of confusion — worth renaming one of them before release (e.g. `--engine cloud` vs. `--publish`).
- `threats/importer.py`: **resolved — KEEP public, confirmed.** Read in full: it only parses a local Threat Dragon JSON file path (`Path(path).read_text()`), no external corpus fetch. No proprietary intelligence.
- The "After" diagram's HTTPS arrow: **resolved**, updated in the diagram above.
- **New, found during implementation:** `crucible validate` cannot be wired to Cloud yet — `crucible-cloud` has no `/v1/validate` endpoint (Phase 4/2's `/v1/runs` work didn't include it, since the original file-split table missed `cmd_validate`'s direct dependency on `ThreatPlanner`/`ThreatValidator` until Phase 2 testing surfaced it). Currently fails fast with a clear message rather than attempting a broken call. Building `/v1/validate` (mirroring `/v1/runs`'s shape: accept `threats` + `target`, return a `ThreatValidationReport`) is the next real gap to close before `validate` is usable again in any mode.
