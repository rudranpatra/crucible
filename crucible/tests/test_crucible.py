"""
Crucible Test Suite
Tests for core engine, attack agents, and scoring.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import CrucibleEngine
from attacks.strategies import (
    TimingAgent, EnvCorruptionAgent, StepReorderAgent,
    NetworkChaosAgent, DependencyDriftAgent, SupplyChainAgent,
)
from scoring.scorer import ResilienceScorer
from integrations.github_actions.parser import create_demo_target, GitHubActionsParser
from runner import CrucibleRunner


@pytest.fixture
def engine():
    return CrucibleEngine()

@pytest.fixture
def demo_target():
    return create_demo_target()

@pytest.fixture
def real_workflow(tmp_path):
    """A real GitHub Actions workflow YAML with known supply chain issues."""
    wf = tmp_path / "ci.yml"
    wf.write_text("""\
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      NODE_ENV: production
      DATABASE_URL: ${{ secrets.DATABASE_URL }}
      API_KEY: ${{ secrets.API_KEY }}
    steps:
      - name: checkout
        uses: actions/checkout@v4
      - name: setup_node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: install_dependencies
        run: npm ci
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
      - name: run_tests
        run: npm test
      - name: build_artifact
        run: npm run build
      - name: deploy_staging
        run: |
          echo "deploying..."
          curl -X POST https://api.staging.example.com/deploy
""")
    return str(wf)

@pytest.fixture
def real_workflow_target(real_workflow):
    return GitHubActionsParser().parse_file(real_workflow)


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
    # ── Smoke tests (demo mode, real subprocesses) ────────────────────────────

    @pytest.mark.asyncio
    async def test_timing_agent_demo(self, engine, demo_target):
        agent = TimingAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0
        assert all(hasattr(r, 'failure_triggered') for r in results)
        # All results carry raw_output from real subprocess
        assert all(r.raw_output is not None for r in results)
        assert all('exit_code' in r.mutation_applied for r in results)

    @pytest.mark.asyncio
    async def test_env_agent_demo(self, engine, demo_target):
        agent = EnvCorruptionAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0
        assert all(r.raw_output is not None for r in results)
        # null_inject on empty string must fail; type_mismatch on non-int must fail
        failures = [r for r in results if r.failure_triggered]
        assert len(failures) > 0, "EnvCorruption must trigger at least one real validation failure"

    @pytest.mark.asyncio
    async def test_network_agent_demo(self, engine, demo_target):
        agent = NetworkChaosAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0
        assert all(r.raw_output is not None for r in results)
        assert all('exit_code' in r.mutation_applied for r in results)
        # Profiles with always_fails=True must trigger failures
        guaranteed = [r for r in results if r.mutation_applied.get('always_fails')]
        assert all(r.failure_triggered for r in guaranteed), \
            "Guaranteed-fail probes (1ms timeout, NXDOMAIN, wrong port) must all fail"

    @pytest.mark.asyncio
    async def test_dependency_agent_demo(self, engine, demo_target):
        agent = DependencyDriftAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0
        assert all(r.raw_output is not None for r in results)
        assert all('exit_code' in r.mutation_applied for r in results)
        # Nonexistent packages and nonexistent versions always fail on PyPI
        real_failures = [r for r in results if r.mutation_applied.get('exit_code', 0) != 0]
        assert len(real_failures) > 0, "pip must reject nonexistent packages/versions"

    @pytest.mark.asyncio
    async def test_reorder_agent_demo(self, engine, demo_target):
        agent = StepReorderAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0
        assert all(r.raw_output is not None for r in results)
        # Shuffled demo workflow has file dependencies → at least one permutation fails
        failures = [r for r in results if r.failure_triggered]
        assert len(failures) > 0, "Step reordering must break file-dependency chain"

    @pytest.mark.asyncio
    async def test_supply_chain_agent_demo(self, engine, demo_target):
        agent = SupplyChainAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        assert len(results) > 0
        assert all(r.attack_type == 'supply_chain' for r in results)
        finding_types = {r.mutation_applied.get('finding_type') for r in results}
        assert 'unpinned_action' in finding_types

    @pytest.mark.asyncio
    async def test_agent_reflection(self, engine, demo_target):
        agent = TimingAgent(engine)
        trace = engine.begin_trace(demo_target['name'])
        results = await agent.attack(demo_target, trace)
        reflection = agent.reflect(results)
        assert 'trigger_rate' in reflection
        assert 'recommendation' in reflection

    # ── Real workflow file tests ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_timing_agent_real_workflow(self, engine, real_workflow_target):
        """TimingAgent uses real 'run' commands from parsed workflow."""
        agent = TimingAgent(engine)
        trace = engine.begin_trace(real_workflow_target['name'])
        results = await agent.attack(real_workflow_target, trace)
        assert len(results) > 0
        # At least some steps have real run commands
        real_mode = [r for r in results if r.mutation_applied.get('mode') == 'real']
        assert len(real_mode) > 0, "Parsed workflow must have real 'run' steps"

    @pytest.mark.asyncio
    async def test_env_agent_real_workflow(self, engine, real_workflow_target):
        """EnvCorruptionAgent corrupts env vars from the parsed workflow."""
        agent = EnvCorruptionAgent(engine)
        trace = engine.begin_trace(real_workflow_target['name'])
        results = await agent.attack(real_workflow_target, trace)
        var_names = {r.mutation_applied['variable'] for r in results}
        # Parsed workflow has NODE_ENV, DATABASE_URL, API_KEY, NPM_TOKEN
        assert len(var_names) > 0
        assert all(r.mutation_applied.get('mode') == 'real' for r in results)

    @pytest.mark.asyncio
    async def test_reorder_agent_real_workflow(self, engine, real_workflow_target):
        """StepReorderAgent executes real npm/curl commands in wrong order."""
        agent = StepReorderAgent(engine)
        trace = engine.begin_trace(real_workflow_target['name'])
        results = await agent.attack(real_workflow_target, trace)
        assert len(results) > 0
        real_mode = [r for r in results if r.mutation_applied.get('mode') == 'real']
        assert len(real_mode) > 0, "Reorder must detect real run commands in parsed workflow"

    @pytest.mark.asyncio
    async def test_supply_chain_real_workflow(self, engine, real_workflow):
        """SupplyChainAgent finds unpinned actions in the real workflow file."""
        target = {'name': 'real_ci', 'source_file': real_workflow, 'supply_chain_risks': []}
        agent = SupplyChainAgent(engine)
        trace = engine.begin_trace('real_ci')
        results = await agent.attack(target, trace)
        assert len(results) > 0
        finding_types = {r.mutation_applied.get('finding_type') for r in results}
        # actions/checkout@v4 and actions/setup-node@v3 are both unpinned
        assert 'unpinned_action' in finding_types
        # No permissions block in the fixture workflow
        assert 'missing_permissions_block' in finding_types

    @pytest.mark.asyncio
    async def test_dependency_agent_real_workflow(self, engine, real_workflow_target):
        """DependencyDriftAgent picks up deps parsed from workflow."""
        agent = DependencyDriftAgent(engine)
        trace = engine.begin_trace(real_workflow_target['name'])
        results = await agent.attack(real_workflow_target, trace)
        assert len(results) > 0
        assert all(r.mutation_applied.get('mode') == 'real' for r in results)

    # ── attack_type stamp ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_all_agents_stamp_attack_type(self, engine, demo_target):
        """Every result must carry the agent's attack_type."""
        agents = [
            TimingAgent(engine), EnvCorruptionAgent(engine), StepReorderAgent(engine),
            NetworkChaosAgent(engine), DependencyDriftAgent(engine), SupplyChainAgent(engine),
        ]
        trace = engine.begin_trace(demo_target['name'])
        for agent in agents:
            results = await agent.attack(demo_target, trace)
            assert all(r.attack_type == agent.attack_type for r in results), \
                f"{agent.attack_type}: result missing attack_type stamp"


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
        runner = CrucibleRunner(
            traces_dir=str(tmp_path / "traces"),
            verbose=False,
            agent_timeout=120.0,
        )
        result = await runner.run(demo_mode=True)

        assert 'trace_id' in result
        assert 'resilience_score' in result
        assert 0 <= result['resilience_score'] <= 100
        assert 'replay_command' in result

    @pytest.mark.asyncio
    async def test_trace_stored(self, tmp_path):
        runner = CrucibleRunner(
            traces_dir=str(tmp_path / "traces"),
            verbose=False,
            agent_timeout=120.0,
        )
        result = await runner.run(demo_mode=True)

        trace_id = result['trace_id']
        replayed = runner.replay(trace_id)
        assert replayed['trace_id'] == trace_id
        assert replayed['resilience_score'] == result['resilience_score']
        assert replayed['failure_count'] == result['failure_count']

    @pytest.mark.asyncio
    async def test_real_workflow_full_run(self, tmp_path, real_workflow):
        """All 6 agents against a real parsed GitHub Actions workflow."""
        runner = CrucibleRunner(
            traces_dir=str(tmp_path / "traces"),
            verbose=False,
            agent_timeout=180.0,
        )
        result = await runner.run(target_path=real_workflow)

        assert result['target'] == 'CI'
        assert 0 <= result['resilience_score'] <= 100
        assert result['failure_count'] > 0, \
            "Real workflow must have at least one failure (unpinned action, timing, env, network)"
        # All 6 attack types should have run
        assert len(result.get('components', {})) > 0

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

        runner = CrucibleRunner(
            traces_dir=str(tmp_path / "traces"),
            verbose=False,
            agent_timeout=120.0,
        )
        result = await runner.run(target_path=str(target), attacks=['timing', 'network'])

        assert result['target'] == 'checkout.spec'
        assert 'resilience_score' in result
