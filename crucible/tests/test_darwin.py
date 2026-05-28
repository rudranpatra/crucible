"""Tests for Darwin scorer — lifetime evolutionary fitness tracking."""

import os
import sys
import json
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring.darwin_scorer import DarwinScorer


@pytest.fixture
def darwin(tmp_path):
    return DarwinScorer(state_file=str(tmp_path / "darwin_state.json"))


class TestDarwinScorer:
    def test_instantiation(self, darwin):
        assert darwin.state['species'] == {}
        assert darwin.state['promotions'] == []

    def test_record_run_creates_species(self, darwin):
        darwin.record_run('timing', 0.6)
        assert 'timing' in darwin.state['species']
        assert darwin.state['species']['timing']['runs'] == 1

    def test_record_multiple_runs(self, darwin):
        darwin.record_run('timing', 0.6)
        darwin.record_run('timing', 0.4)
        darwin.record_run('timing', 0.8)
        sp = darwin.state['species']['timing']
        assert sp['runs'] == 3
        assert abs(sp['total_trigger_rate'] - 1.8) < 0.001

    def test_fitness_zero_before_runs(self, darwin):
        assert darwin.calculate_fitness('nonexistent') == 0.0

    def test_fitness_increases_with_trigger_rate(self, darwin):
        darwin.record_run('timing', 0.8)
        darwin.record_run('timing', 0.8)
        high_fitness = darwin.calculate_fitness('timing')

        darwin2 = DarwinScorer.__new__(DarwinScorer)
        darwin2.state = {'species': {}, 'promotions': [], 'extinct': []}
        darwin2.state_file = darwin.state_file
        darwin2.record_run('timing', 0.1)
        darwin2.record_run('timing', 0.1)
        low_fitness = darwin2.calculate_fitness('timing')

        assert high_fitness > low_fitness

    def test_fitness_max_100(self, darwin):
        darwin.record_run('timing', 1.0, generation=10, lineage_depth=10)
        fitness = darwin.calculate_fitness('timing')
        assert fitness <= 100.0

    def test_fitness_min_0(self, darwin):
        darwin.record_run('timing', 0.0)
        fitness = darwin.calculate_fitness('timing')
        assert fitness >= 0.0

    def test_lineage_depth_increases_fitness(self, darwin):
        darwin.record_run('timing', 0.5, lineage_depth=0)
        base_fitness = darwin.calculate_fitness('timing')

        darwin.record_run('timing', 0.5, lineage_depth=5)
        deeper_fitness = darwin.calculate_fitness('timing')

        assert deeper_fitness >= base_fitness

    def test_get_species_report(self, darwin):
        darwin.record_run('timing', 0.8)
        darwin.record_run('env', 0.2)
        report = darwin.get_species_report()
        assert 'timing' in report
        assert 'env' in report
        assert 'fitness' in report['timing']
        assert 'is_dominant' in report['timing']
        assert 'is_extinct' in report['timing']

    def test_dominant_species_detection(self, darwin):
        for _ in range(3):
            darwin.record_run('timing', 1.0)
        report = darwin.get_species_report()
        assert report['timing']['is_dominant'] is True

    def test_extinct_species_detection(self, darwin):
        for _ in range(6):
            darwin.record_run('env', 0.0)
        report = darwin.get_species_report()
        assert report['env']['is_extinct'] is True

    def test_evolving_species_neither_dominant_nor_extinct(self, darwin):
        darwin.record_run('network', 0.3)
        darwin.record_run('network', 0.4)
        report = darwin.get_species_report()
        assert report['network']['is_dominant'] is False
        assert report['network']['is_extinct'] is False

    def test_record_promotion(self, darwin):
        darwin.record_run('timing', 0.5)
        darwin.record_promotion('timing', shadow_rate=0.7, prod_rate=0.4)
        sp = darwin.state['species']['timing']
        assert sp['generation'] == 2
        assert sp['lineage_depth'] == 1
        assert len(darwin.state['promotions']) == 1

    def test_get_evolutionary_log(self, darwin):
        darwin.record_run('timing', 0.5)
        darwin.record_promotion('timing', 0.7, 0.4)
        log = darwin.get_evolutionary_log()
        assert len(log) == 1
        assert log[0]['event'] == 'promotion'

    def test_persistence(self, tmp_path):
        state_file = str(tmp_path / "darwin_state.json")
        d1 = DarwinScorer(state_file=state_file)
        d1.record_run('timing', 0.6)
        d1.save()

        d2 = DarwinScorer(state_file=state_file)
        assert 'timing' in d2.state['species']
        assert d2.state['species']['timing']['runs'] == 1

    def test_fitness_trend_improving(self, darwin):
        for rate in [0.1, 0.3, 0.6]:
            darwin.record_run('timing', rate)
        sp = darwin.state['species']['timing']
        from scoring.darwin_scorer import DarwinScorer as DS
        trend = darwin._trend(sp['fitness_history'])
        assert trend == 'improving'

    def test_fitness_trend_declining(self, darwin):
        for rate in [0.8, 0.5, 0.2]:
            darwin.record_run('timing', rate)
        sp = darwin.state['species']['timing']
        trend = darwin._trend(sp['fitness_history'])
        assert trend == 'declining'

    def test_fitness_trend_insufficient_data(self, darwin):
        darwin.record_run('timing', 0.5)
        sp = darwin.state['species']['timing']
        trend = darwin._trend(sp['fitness_history'])
        assert trend == 'insufficient_data'

    def test_multiple_species(self, darwin):
        for species in ['timing', 'env', 'network', 'dependency', 'reorder']:
            darwin.record_run(species, 0.5)
        report = darwin.get_species_report()
        assert len(report) == 5
