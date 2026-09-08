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
