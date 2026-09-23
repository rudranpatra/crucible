# Crucible (crucible-gym) — GA / Enterprise Launch Readiness Report

**Product:** Adversarial Intelligence Engine for CI/CD pipelines — Apache-2.0 OSS. Since 0.5.0: a **thin client** (one static check locally + HTTP client to a full 6-agent engine that only exists as the private, undeployed `crucible-cloud`).
**Audit date:** 2026-09-22
**Verdict:** **Not GA, not enterprise-ready.** Functional and honest for the *static local* case; three systemic issues block launch (dead uploader feature, broken quality gates, false-confidence scoring).

---

## 1. Status Summary

| Dimension | Status |
|---|---|
| Local static scanning | ✅ Works (99 tests pass) |
| Version consistency | ✅ 0.5.3 across pyproject/CHANGELOG/`__init__`/wheel |
| `--publish-cloud` (headline 0.5.3 feature) | ❌ **Dead on arrival — silently drops data** |
| CI quality gates (ruff/mypy/self-check) | ❌ All fail under current tooling |
| GitHub Action | ❌ Pinned to stale 0.4.2, runs 0.4.2 engine inside consumer runners |
| Enterprise launch | ❌ Full engine unreachable (requires undeployed crucible-cloud); unsandboxed action execution |

---

## 2. What's Working

- Clean dataclass models, deterministic seeds, `yaml.safe_load` everywhere, no eval/exec/pickle in 0.5.x, stdlib-only HTTP.
- `raw_output` deliberately never transmitted on the cloud-sink path (when it works).
- CLI UX is clean; 0.5.3 JSON output is machine-readable.
- CoC, CONTRIBUTING, issue/PR templates present; `dist/` and `.venv` correctly untracked.

---

## 3. Gaps and Pending Items

### P0 — Release-blocking

| # | Gap | Evidence | Fix |
|---|---|---|---|
| P0-1 | `--publish-cloud` is dead: sink reads `result.recovery_time_ms` but `AttackResult` has no such field → `AttributeError` on every publish; runner guard swallows it silently. Test hides it by using a fake result carrying the extra attr | `crucible/sinks/crucible_cloud_sink.py:60`; `crucible/agents/base_agent.py:13-20`; `runner.py:126-130`; `tests/test_cloud_sink.py:21` | Add `recovery_time_ms` to `AttackResult` or drop the field; integration test with the real dataclass |
| P0-2 | Quality gates fail: mypy config targets EOL **Python 3.9** (`pyproject.toml:58`); ruff fails with **196 errors** (CI's exact command); `crucible-self-check` CI job crashes by design (calls `run(github_comment=True)`, no such param) | `.github/workflows/ci.yml:97-107`; `runner.py:76-84` | Pin/upgrade tool versions, update mypy python_version, fix or remove self-check |
| P0-3 | **False-confidence scoring:** GitLab/Playwright targets score **100/A with zero findings** because `basic_strategies.py` only reads `jobs[].steps[].uses` while GitLab/Playwright parsers emit jobs with no steps (verified live). A security tool that reports a clean 100 on unanalyzed targets is a credibility risk | `crucible/attacks/basic_strategies.py:21-26`; `gitlab/parser.py:91`; `playwright/parser.py:229` | Gate/flag "unsupported target" when no local agent applies — never score a non-analyzed target |

### P1 — GA-blocking

| # | Gap |
|---|---|
| P1-4 | GitHub Action pinned to stale `==0.4.2` (different engine/scoring model), `trace-id` output points at removed `crucible replay`; action's 0.4.2 agents run real adversarial subprocesses (`sleep`, env-corruption, `curl`, `pip3 install --dry-run`) **unsandboxed** in consumer CI runners with repo `GITHUB_TOKEN` |
| P1-5 | "Full" features (`validate`, `compare --engine cloud`, 6 agents) require `crucible-cloud`, which is not publicly deployed — docs promise behavior the package can't deliver. Decide: "static checker today" or "ship cloud" |
| P1-6 | Release state: main is 10 commits ahead of origin; shipped 0.5.3 wheel does not match tree (120 uncommitted sink/CLI lines); dev venv metadata frozen at 0.4.2 (`__editable__.crucible_gym-0.4.2.pth`), same drift class 0.4.1 fixed |

### P2 — Hardening

- Sandbox/annotate action execution; quote `${{ inputs.* }}` in `action.yml:64-69` (injection surface)
- `subprocess.run(check=True)` at `cli/crucible.py:237`; `.exception` not `.error(exc_info=True)`; drop blind `except Exception` (`playwright/parser.py:253`)
- Stale README claims: "97 tests" (now 99), `validate` "not available" vs shipped but cloud-locked `cmd_validate`
- Missing `SECURITY.md`; no SBOM; trusted-publisher PyPI workflow absent; wheel bundles `tests/`; `pip-audit` only scans `crucible/requirements.txt` (not the action's 0.4.2 install); classifier still "3 - Alpha"

---

## 4. Evidence Notes

- `pytest` (fresh on .venv, Python 3.12.10): **99 passed in 0.51s**. Note: `pytest-timeout` not installed (untimed run).
- `ruff check crucible/ --ignore E501` (CI command): **196 errors, exit 1** (~85% style-upgrade; some real).
- `mypy --exclude tests/` (CI command): **exit 1** (Python 3.9 target rejected by current mypy + 7 real errors in playwright/gitlab/threats importer).
- No secrets found committed; `.env.example` present; wheel built by hand in `dist/`.

---

## 5. Launch Recommendations

1. **P0-3 first** — false-confidence scoring is the worst issue (reputational). Flag unsupported targets; never emit 100/A for unanalyzed configs.
2. Fix `--publish-cloud` (P0-1) with a real-dataclass integration test, or drop/replace the feature.
3. Make CI green on pinned tooling (P0-2); wire trusted-publisher publishing + SBOM; stop shipping stale 0.4.2 action.
4. Pick a lane publicly: static local checker (ship it clean) vs full cloud engine (ship crucible-cloud or close the gap with an honest dependency statement).
5. Reconcile release state: commit the 10-ahead work or cut 0.5.4 from a clean tree; single-source `__version__`.

**One-line:** Good bones for a static checker, but the shipped 0.5.3 story is undermined by a silently-dead uploader, failing quality gates, and a tool that reports clean 100s on targets it doesn't analyze.