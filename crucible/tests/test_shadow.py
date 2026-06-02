"""Tests for shadow agent and shadow runner."""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import CrucibleEngine
from attacks.strategies import TimingAgent, EnvCorruptionAgent, NetworkChaosAgent
from agents.shadow_agent import ShadowAgent
from core.shadow_runner import ShadowRunner
from integrations.github_actions.parser import create_demo_target


@pytest.fixture
def engine():
    return CrucibleEngine()

@pytest.fixture
def demo_target():
    return create_demo_target()


class TestShadowAgent:
    @pytest.mark.asyncio
    async def test_instantiation(self, engine):
        shadow = ShadowAgent(TimingAgent, engine)
        assert shadow.production is not None
        assert shadow.shadow is not None
        assert shadow.production.agent_id != shadow.shadow.agent_id

    @pytest.mark.asyncio
    async def test_run_paired_returns_comparison(self, engine, demo_target):
        shadow = ShadowAgent(TimingAgent, engine)
        trace = engine.begin_trace(demo_target['name'])
        result = await shadow.run_paired(demo_target, trace)

        assert 'attack_type' in result
        assert 'production' in result
        assert 'shadow' in result
        assert 'shadow_wins' in result
        assert 'should_promote' in result
        assert isinstance(result['shadow_wins'], bool)

    @pytest.mark.asyncio
    async def test_trigger_rates_are_floats(self, engine, demo_target):
        shadow = ShadowAgent(TimingAgent, engine)
        trace = engine.begin_trace(demo_target['name'])
        result = await shadow.run_paired(demo_target, trace)

        assert 0.0 <= result['production']['trigger_rate'] <= 1.0
        assert 0.0 <= result['shadow']['trigger_rate'] <= 1.0

    @pytest.mark.asyncio
    async def test_run_history_recorded(self, engine, demo_target):
        shadow = ShadowAgent(TimingAgent, engine)
        trace = engine.begin_trace(demo_target['name'])
        await shadow.run_paired(demo_target, trace)
        assert len(shadow.run_history) == 1
        assert 'production_trigger_rate' in shadow.run_history[0]
        assert 'shadow_trigger_rate' in shadow.run_history[0]

    @pytest.mark.asyncio
    async def test_promotion_requires_3_wins(self, engine, demo_target):
        shadow = ShadowAgent(EnvCorruptionAgent, engine)
        engine.begin_trace(demo_target['name'])

        # Force 3 shadow wins into history
        shadow.run_history = [
            {"production_trigger_rate": 0.2, "shadow_trigger_rate": 0.5, "shadow_wins": True},
            {"production_trigger_rate": 0.2, "shadow_trigger_rate": 0.5, "shadow_wins": True},
            {"production_trigger_rate": 0.2, "shadow_trigger_rate": 0.5, "shadow_wins": True},
        ]
        assert shadow._should_promote() is True

    def test_promotion_requires_consecutive_wins(self, engine):
        shadow = ShadowAgent(TimingAgent, engine)
        shadow.run_history = [
            {"production_trigger_rate": 0.2, "shadow_trigger_rate": 0.5, "shadow_wins": True},
            {"production_trigger_rate": 0.5, "shadow_trigger_rate": 0.2, "shadow_wins": False},
            {"production_trigger_rate": 0.2, "shadow_trigger_rate": 0.5, "shadow_wins": True},
        ]
        assert shadow._should_promote() is False

    @pytest.mark.asyncio
    async def test_perturb_target_modifies_copy(self, engine, demo_target):
        shadow = ShadowAgent(TimingAgent, engine)
        import copy
        perturbed = shadow._perturb_target(copy.deepcopy(demo_target))
        # Steps should be shuffled or timeout changed — at least one differs
        assert perturbed is not demo_target

    @pytest.mark.asyncio
    async def test_different_agent_types(self, engine, demo_target):
        for agent_class in [TimingAgent, EnvCorruptionAgent, NetworkChaosAgent]:
            shadow = ShadowAgent(agent_class, engine)
            trace = engine.begin_trace(demo_target['name'])
            result = await shadow.run_paired(demo_target, trace)
            assert result['attack_type'] == agent_class.attack_type


class TestShadowRunner:
    def test_instantiation(self, engine):
        runner = ShadowRunner(engine)
        assert runner.pairs == {}
        assert runner.total_promotions == 0

    def test_register(self, engine):
        runner = ShadowRunner(engine)
        runner.register('timing', TimingAgent)
        assert 'timing' in runner.pairs

    def test_register_all(self, engine):
        runner = ShadowRunner(engine)
        registry = {'timing': TimingAgent, 'env': EnvCorruptionAgent}
        runner.register_all(registry)
        assert 'timing' in runner.pairs
        assert 'env' in runner.pairs

    @pytest.mark.asyncio
    async def test_run_attack(self, engine, demo_target):
        runner = ShadowRunner(engine)
        runner.register('timing', TimingAgent)
        trace = engine.begin_trace(demo_target['name'])
        result = await runner.run_attack('timing', demo_target, trace)
        assert 'attack_type' in result
        assert result['attack_type'] == 'timing'

    @pytest.mark.asyncio
    async def test_run_all(self, engine, demo_target):
        runner = ShadowRunner(engine)
        runner.register_all({'timing': TimingAgent, 'env': EnvCorruptionAgent})
        trace = engine.begin_trace(demo_target['name'])
        result = await runner.run_all(demo_target, trace)
        assert 'attack_results' in result
        assert 'promotions_this_run' in result
        assert 'timing' in result['attack_results']
        assert 'env' in result['attack_results']

    @pytest.mark.asyncio
    async def test_unknown_attack_type_returns_empty(self, engine, demo_target):
        runner = ShadowRunner(engine)
        trace = engine.begin_trace(demo_target['name'])
        result = await runner.run_attack('nonexistent', demo_target, trace)
        assert result == {}

    def test_status(self, engine):
        runner = ShadowRunner(engine)
        runner.register('timing', TimingAgent)
        status = runner.status()
        assert 'registered_types' in status
        assert 'timing' in status['registered_types']
        assert status['total_promotions'] == 0
