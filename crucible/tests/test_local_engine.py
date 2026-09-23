"""Tests for the OSS/local engine: LocalEngine, BasicSupplyChainAgent, BasicScorer,
and CrucibleRunner's mode selection (local vs cloud, never silent fallback)."""
import pytest

from crucible.core.local_engine import LocalEngine
from crucible.attacks.basic_strategies import BasicSupplyChainAgent
from crucible.scoring.basic_scorer import BasicScorer
from crucible.runner import CrucibleRunner, CloudExecutionError


class TestLocalEngine:
    def test_begin_trace_generates_unique_ids(self):
        engine = LocalEngine()
        t1 = engine.begin_trace("a")
        t2 = engine.begin_trace("a")
        assert t1.trace_id != t2.trace_id

    def test_finalize_trace_sets_score(self):
        engine = LocalEngine()
        trace = engine.begin_trace("a")
        engine.finalize_trace(trace, 42.0)
        assert trace.resilience_score == 42.0
        assert trace.finished_at is not None


class TestBasicSupplyChainAgent:
    def test_flags_unpinned_action(self):
        target = {"jobs": [{"steps": [{"name": "checkout", "uses": "actions/checkout@v4"}]}]}
        findings = BasicSupplyChainAgent().check(target)
        assert len(findings) == 1
        assert findings[0].failure_triggered is True
        assert "actions/checkout" in findings[0].failure_description

    def test_pinned_sha_is_not_flagged(self):
        target = {"jobs": [{"steps": [{
            "name": "checkout", "uses": "actions/checkout@" + "a" * 40,
        }]}]}
        findings = BasicSupplyChainAgent().check(target)
        assert findings == []

    def test_local_action_reference_is_not_flagged(self):
        target = {"jobs": [{"steps": [{"name": "local", "uses": "./local-action"}]}]}
        assert BasicSupplyChainAgent().check(target) == []

    def test_step_without_uses_is_skipped(self):
        target = {"jobs": [{"steps": [{"name": "run", "run": "echo hi"}]}]}
        assert BasicSupplyChainAgent().check(target) == []


class TestUnsupportedFormatsNotScoredClean:
    """Regression for the false-confidence bug: GitLab CI and Playwright
    targets have no job.steps[].uses for BasicSupplyChainAgent to read, so it
    used to silently find zero findings and the run reported a clean 100/A —
    "we didn't look" indistinguishable from "we looked and it's clean"."""

    def test_gitlab_target_is_marked_unsupported_not_clean(self):
        target = {
            "name": "real-gitlab-ci",
            "type": "gitlab_ci",
            "jobs": [{"name": "deploy", "runs_on": ["shared-runner"]}],
            "steps": [{"name": "deploy_step0", "run": "curl -X POST $DEPLOY_URL"}],
        }
        findings = BasicSupplyChainAgent().check(target)
        assert len(findings) == 1
        assert findings[0].unsupported is True
        assert findings[0].failure_triggered is False

    def test_playwright_target_is_marked_unsupported_not_clean(self):
        target = {
            "name": "checkout.spec.ts",
            "source_type": "playwright",
            "jobs": [{"name": "playwright_tests", "runs_on": "browser"}],
            "steps": [{"name": "navigate_line_1", "type": "navigate"}],
        }
        findings = BasicSupplyChainAgent().check(target)
        assert len(findings) == 1
        assert findings[0].unsupported is True

    @pytest.mark.asyncio
    async def test_runner_does_not_report_clean_score_for_gitlab_yaml(self, tmp_path):
        gitlab_yaml = tmp_path / ".gitlab-ci.yml"
        gitlab_yaml.write_text("""
stages: [build, deploy]
build:
  stage: build
  script:
    - npm ci
deploy:
  stage: deploy
  script:
    - curl -X POST $DEPLOY_URL
""")
        runner = CrucibleRunner(verbose=False)
        result = await runner.run(target_path=str(gitlab_yaml))
        assert result["format_supported"] is False
        assert result["grade"] != "A"
        assert result["resilience_score"] != 100.0
        assert result["unsupported_reasons"]

    @pytest.mark.asyncio
    async def test_runner_does_not_report_clean_score_for_playwright_spec(self, tmp_path):
        spec = tmp_path / "checkout.spec.ts"
        spec.write_text("""
test('checkout works', async ({ page }) => {
  await page.goto('https://example.com');
  await page.click('[data-testid=checkout]');
  await expect(page.locator('#confirm')).toBeVisible();
});
""")
        runner = CrucibleRunner(verbose=False)
        result = await runner.run(target_path=str(spec))
        assert result["format_supported"] is False
        assert result["grade"] != "A"
        assert result["resilience_score"] != 100.0


class TestBasicScorer:
    def test_no_findings_is_perfect_score(self):
        assert BasicScorer().score([]) == 100.0

    def test_deducts_per_triggered_finding(self):
        target = {"jobs": [{"steps": [{"uses": "a/b@v1"}, {"uses": "c/d@v2"}]}]}
        findings = BasicSupplyChainAgent().check(target)
        score = BasicScorer().score(findings)
        assert score == 70.0

    def test_score_floors_at_zero(self):
        target = {"jobs": [{"steps": [{"uses": f"a/b{i}@v1"} for i in range(10)]}]}
        findings = BasicSupplyChainAgent().check(target)
        assert BasicScorer().score(findings) == 0.0

    def test_grade_boundaries(self):
        s = BasicScorer()
        assert s.grade(95) == "A"
        assert s.grade(60) == "D"
        assert s.grade(10) == "F"


class TestRunnerModeSelection:
    def test_defaults_to_local(self):
        runner = CrucibleRunner()
        assert runner.mode == "local"

    def test_rejects_unknown_mode(self):
        with pytest.raises(ValueError):
            CrucibleRunner(mode="offline")

    def test_shadow_mode_requires_cloud(self):
        with pytest.raises(NotImplementedError):
            CrucibleRunner(use_shadow=True)

    @pytest.mark.asyncio
    async def test_cloud_mode_without_credentials_raises(self):
        runner = CrucibleRunner(mode="cloud", cloud_url=None, api_key=None)
        with pytest.raises(CloudExecutionError):
            await runner.run(demo_mode=True)

    @pytest.mark.asyncio
    async def test_local_demo_run_scores_perfectly(self):
        runner = CrucibleRunner(verbose=False)
        result = await runner.run(demo_mode=True)
        assert result["engine_mode"] == "local"
        assert result["resilience_score"] == 100.0
        assert result["grade"] == "A"

    def test_replay_patterns_evolution_require_cloud(self):
        runner = CrucibleRunner(verbose=False)
        with pytest.raises(NotImplementedError):
            runner.replay("trc_1")
        with pytest.raises(NotImplementedError):
            runner.patterns()
        with pytest.raises(NotImplementedError):
            runner.evolution()

    def test_validate_requires_cloud(self):
        runner = CrucibleRunner(verbose=False)
        with pytest.raises(NotImplementedError):
            runner.validate([{"id": "t1", "title": "x", "description": "x", "technique": "x"}])

    def test_validate_cloud_mode_without_credentials_raises(self):
        runner = CrucibleRunner(mode="cloud", cloud_url=None, api_key=None)
        with pytest.raises(CloudExecutionError):
            runner.validate([], demo_mode=True)
