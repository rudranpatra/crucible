# Changelog

All notable changes to Crucible follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- Parallel agent execution via `asyncio.gather` — all attack types now run concurrently
- Per-agent timeout enforcement (default 30 s, configurable via `agent_timeout=`)
- Structured logging throughout (`logging` module, replaces bare `print()` in engine/runner/server)
- API key authentication for the web dashboard (`CRUCIBLE_API_KEY` env var)
- `requirements.lock` — pinned transitive dependency versions for reproducible installs
- `pip-audit` job in CI — automated CVE scanning on every push
- Blocking `mypy` type-check job in CI (was non-blocking before)
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, GitHub issue/PR templates
- `.env.example` documenting all required environment variables

### Changed
- CI lint job (`ruff check`) is now **blocking** — removed `|| true`
- CI self-check no longer runs the demo twice (was running `python runner.py demo` then a second `asyncio.run`)
- `pyproject.toml` entry point corrected to `crucible.cli.crucible:main`
- `pyproject.toml` packages discovery updated to `include = ["crucible*"]`
- `mypy` config tightened: `no_implicit_optional = true`, `warn_unused_ignores = true`
- Exception handling in `base_agent.py` now logs full traceback and re-raises `CancelledError`
- Dashboard `serve()` warns explicitly when `CRUCIBLE_API_KEY` is not set

### Removed
- `crucible/setup.py` — superseded by root `pyproject.toml`

### Fixed
- Duplicate attack-run execution in `crucible-self-check` CI job

---

## [0.1.0] — 2026-05-01

### Added
- Initial release: adversarial CI/CD pipeline testing engine
- Five attack types: `timing`, `env`, `reorder`, `network`, `dependency`
- Resilience scoring (0–100, grades A–F) with four weighted components
- Evolutionary mechanics: fitness tracking, shadow agents, species extinction
- Replayable trace files (`.crucible` JSON format)
- GitHub Actions integration: PR comments, SVG badge generation
- Playwright test file parser
- Rich terminal UI and FastAPI web dashboard
- `--seed` flag for deterministic replay
- 93 passing tests across all modules
- Apache 2.0 license
