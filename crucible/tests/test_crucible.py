"""
Crucible Test Suite
Tests for core engine, attack agents, and scoring.
"""

import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import CrucibleEngine, AttackStatus, AgentStatus
from attacks.strategies import TimingAgent, EnvCorruptionAgent, StepReorderAgent, NetworkChaosAgent, DependencyDriftAgent
from scoring.scorer import ResilienceScorer
from integrations.github_actions.parser import create_demo_target
from runner import CrucibleRunner


@pytest.fixture
def engine():
    return CrucibleEngine()

@pytest.fixture
def demo_target():
    return create_demo_target()


class TestEngine:
    def test_spawn_agent(self, engine):
        agent = engine.spawn_agent("timing")
        assert agent.agent_id in engine.agents
        assert agent.is_alive()
        assert agent.fitness_score == 100.0

    def test_agent_lineage(self, engine):
        parent = engine.spawn_agent("timing")
        child = engine.spawn_agent("timing", parent_id=parent.agent_id)
        assert parent.agent_id in child.lineage

    def test_kill_agent(self, engine):
        agent = engine.spawn_agent("timing")
        engine.kill_agent(agent.agent_id, "test")
        assert not engine.agents[agent.agent_id].is_alive()

    def test_begin_trace(self, engine):
        trace = engine.begin_trace("test_pipeline")
        assert trace.trace_id in engine.active_traces
        assert trace.target == "test_pipeline"

    def test_engine_status(self, engine):
        engine.spawn_agent("timing")
        engine.spawn_agent("env")
        status = engine.engine_status()
        assert status['total_agents'] == 2
        assert status['alive'] == 2
        assert status['dead'] == 0


class TestAttackAgents:
    @pytest.mark.asyncio
    async def test_timing_agent(self, engine, demo_target):
        agent = TimingAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0
        assert all(hasattr(r, 'failure_triggered') for r in results)

    @pytest.mark.asyncio
    async def test_env_agent(self, engine, demo_target):
        agent = EnvCorruptionAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_network_agent(self, engine, demo_target):
        agent = NetworkChaosAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_dependency_agent(self, engine, demo_target):
        agent = DependencyDriftAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_agent_reflection(self, engine, demo_target):
        agent = TimingAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        reflection = agent.reflect(results)
        assert 'trigger_rate' in reflection
        assert 'recommendation' in reflection


class TestScoring:
    @pytest.mark.asyncio
    async def test_score_from_results(self, engine, demo_target):
        agent = TimingAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)

        scorer = ResilienceScorer()
        report = scorer.score(results, ['timing'])

        assert 0 <= report.score <= 100
        assert report.grade in ['A', 'B', 'C', 'D', 'F']
        assert isinstance(report.failure_points, list)

    def test_empty_results(self):
        scorer = ResilienceScorer()
        report = scorer.score([], [])
        assert report.score == 0.0


class TestFullRun:
    @pytest.mark.asyncio
    async def test_demo_run(self, tmp_path):
        runner = CrucibleRunner(traces_dir=str(tmp_path / "traces"), verbose=False)
        result = await runner.run(demo_mode=True)

        assert 'trace_id' in result
        assert 'resilience_score' in result
        assert 0 <= result['resilience_score'] <= 100
        assert 'replay_command' in result

    @pytest.mark.asyncio
    async def test_trace_stored(self, tmp_path):
        runner = CrucibleRunner(traces_dir=str(tmp_path / "traces"), verbose=False)
        result = await runner.run(demo_mode=True)

        trace_id = result['trace_id']
        replayed = runner.replay(trace_id)
        assert replayed['trace_id'] == trace_id
        assert replayed['resilience_score'] == result['resilience_score']
        assert replayed['failure_count'] == result['failure_count']

    @pytest.mark.asyncio
    async def test_playwright_target_run(self, tmp_path):
        target = tmp_path / "checkout.spec.ts"
        target.write_text(
            """
import { test, expect } from '@playwright/test';

test('checkout flow', async ({ page }) => {
  await page.goto('https://example.com/checkout');
  await page.click('#buy');
  await page.waitForResponse('https://api.example.com/order');
  expect(page.locator('.done')).toBeVisible();
});
"""
        )

        runner = CrucibleRunner(traces_dir=str(tmp_path / "traces"), verbose=False)
        result = await runner.run(target_path=str(target), attacks=['timing', 'network'])

        assert result['target'] == 'checkout.spec'
        assert 'resilience_score' in result
