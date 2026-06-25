# Changelog

All notable changes to Crucible follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [0.2.0] — 2026-06-25

### Added
- **Real subprocess execution for all 5 non-static agents** — no more arithmetic or probability; every agent runs actual OS processes:
  - `TimingAgent`: `sleep {delay_s} && ({run_cmd})` via `asyncio.create_subprocess_shell`
  - `EnvCorruptionAgent`: Python probe script written to tempfile, executed with corrupted `os.environ`
  - `StepReorderAgent`: step commands executed in mutated order in `tempfile.TemporaryDirectory`; file-dependency failures are real
  - `NetworkChaosAgent`: real `curl` probes — 1ms timeout (latency spike), NXDOMAIN hostname (DNS flap), port 65535 (connection reset), `--range 0-50` (truncated response)
  - `DependencyDriftAgent`: `pip3 install --dry-run --no-cache-dir` on mutated `requirements.txt`; nonexistent versions fail at the resolver
- `BaseAdversarialAgent._run_command(cmd, env, cwd, timeout)` — shared async subprocess executor; returns `(returncode, stdout, stderr)`; `rc=-1` = timeout, `rc=-2` = launch error
- `AttackResult.raw_output` — actual stdout+stderr from subprocess (was `None` for all agents in v0.1)
- `AttackResult.mutation_applied['mode']` — `'real'` (from parsed workflow `run:` block) or `'demo'` (canonical fallback)
- `AttackResult.mutation_applied['exit_code']` — integer returncode from subprocess
- `crucible audit .` — new focused supply-chain + dependency + env audit; auto-discovers workflow files; recommended first command
- `crucible compare <ref1> <ref2>` — resilience regression between two git refs; uses `git show ref:path` (no working-tree mutation); diffs scores and failure points
- `crucible trend` — score history from stored traces with ASCII bar chart and overall direction
- `core/file_lock.py` — `FileLock` extracted from duplicate `_FileLock` in `trace_memory.py` and `darwin_scorer.py`
- 7 new tests (102 total, was 95): real-workflow execution for all 6 agents, `attack_type` stamp assertion, full 6-agent run against parsed YAML

### Changed
- All agents now stamp `attack_type` on every `AttackResult` (was missing on some paths)
- `ShadowAgent.winning_perturbation_configs` changed from `List + [-5:]` slice to `deque(maxlen=5)`
- `SupplyChainAgent` reads the source YAML file once per attack cycle (was re-reading per mutation)
- `pyproject.toml` build backend fixed: `setuptools.backends.legacy:build` → `setuptools.build_meta` (required for setuptools 68.x)
- `pyproject.toml` readme now points to `crucible/README.md` (full reference docs on PyPI)
- README rewritten: leads with `pip install crucible-gym && crucible audit .`; all commands use `crucible` binary; "not a scanner" framing; 6-agent table with "how it's real" column

### Removed
- Probabilistic simulation in TimingAgent, EnvCorruptionAgent, StepReorderAgent, NetworkChaosAgent, DependencyDriftAgent — replaced with real subprocess execution

### Fixed
- `pip install crucible-gym` was broken on setuptools 68.x (`ModuleNotFoundError: No module named 'setuptools.backends'`)

---

## [0.1.0] — 2026-05-01

### Added
- Parallel agent execution via `asyncio.gather` — all attack types run concurrently
- Per-agent timeout enforcement (default 30 s, configurable via `agent_timeout=`)
- Structured logging throughout (`logging` module, replaces bare `print()` in engine/runner/server)
- API key authentication for the web dashboard (`CRUCIBLE_API_KEY` env var)
- `pip-audit` job in CI — automated CVE scanning on every push
- Blocking `mypy` type-check job in CI
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, GitHub issue/PR templates

### Added
- Initial release: adversarial CI/CD pipeline testing engine
- Six attack types: `timing`, `env`, `reorder`, `network`, `dependency`, `supply_chain`
- Resilience scoring (0–100, grades A–F) with four weighted components
- Evolutionary mechanics: fitness tracking, shadow agents, species extinction
- Replayable trace files (`.crucible` JSON format)
- GitHub Actions integration: PR comments, SVG badge generation
- Playwright test file parser
- Rich terminal UI and FastAPI web dashboard
- `--seed` flag for deterministic replay
- 93 passing tests across all modules
- Apache 2.0 license
