"""
v0.3.0 tests: GitLab CI parser, SARIF export, agent compatibility.
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.gitlab.parser import GitLabCIParser, create_demo_gitlab_target
from integrations.github.sarif import generate_sarif, write_sarif


# ── GitLab CI Parser ──────────────────────────────────────────────────────────

class TestGitLabParser:
    def test_parse_content_returns_target(self):
        target = GitLabCIParser().parse_content("""
stages: [build, test]
variables:
  NODE_ENV: production
build:
  stage: build
  script: npm ci
test:
  stage: test
  script: npm test
""", 'myproject')
        assert target['name'] == 'myproject'
        assert target['type'] == 'gitlab_ci'
        assert len(target['steps']) >= 2

    def test_extracts_global_env_vars(self):
        target = GitLabCIParser().parse_content("""
variables:
  DATABASE_URL: postgres://localhost/db
  API_KEY: $CI_SECRET
build:
  script: echo build
""")
        names = {v['name'] for v in target['env_vars']}
        assert 'DATABASE_URL' in names
        assert 'API_KEY' in names

    def test_secret_vars_flagged(self):
        target = GitLabCIParser().parse_content("""
variables:
  API_KEY: $CI_TOKEN
  NODE_ENV: production
build:
  script: echo hi
""")
        api = next(v for v in target['env_vars'] if v['name'] == 'API_KEY')
        node = next(v for v in target['env_vars'] if v['name'] == 'NODE_ENV')
        assert api['is_secret'] is True
        assert node['is_secret'] is False

    def test_unpinned_image_flagged(self):
        target = GitLabCIParser().parse_content("""
image: node
build:
  script: npm ci
""")
        types = {r['finding_type'] for r in target['supply_chain_risks']}
        assert 'unpinned_image' in types

    def test_tagged_image_not_flagged(self):
        target = GitLabCIParser().parse_content("""
image: node:20.11.0
build:
  script: npm ci
""")
        image_risks = [r for r in target['supply_chain_risks'] if r['finding_type'] == 'unpinned_image']
        assert len(image_risks) == 0

    def test_steps_have_required_fields(self):
        target = GitLabCIParser().parse_content("""
build:
  script:
    - npm ci
    - npm run build
""")
        for step in target['steps']:
            assert 'name' in step
            assert 'run' in step
            assert 'index' in step

    def test_parse_file(self, tmp_path):
        wf = tmp_path / '.gitlab-ci.yml'
        wf.write_text("""
stages: [build]
variables:
  NODE_ENV: production
build:
  stage: build
  script: npm ci
""")
        target = GitLabCIParser().parse_file(str(wf))
        assert target['type'] == 'gitlab_ci'
        assert len(target['steps']) > 0

    def test_network_calls_detected(self):
        target = GitLabCIParser().parse_content("""
build:
  script:
    - npm ci
    - curl https://api.example.com/health
""")
        assert 'npm_registry' in target['network_calls']
        assert 'external_http_call' in target['network_calls']

    def test_demo_target_has_all_required_fields(self):
        target = create_demo_gitlab_target()
        for field in ('steps', 'env_vars', 'dependencies', 'supply_chain_risks', 'network_calls',
                      'critical_order_steps', 'downstream_steps', 'has_retry_logic', 'timeout_ms'):
            assert field in target, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_gitlab_target_compatible_with_timing_agent(self):
        from core.engine import CrucibleEngine
        from attacks.strategies import TimingAgent
        engine = CrucibleEngine()
        target = create_demo_gitlab_target()
        trace = engine.begin_trace(target['name'])
        results = await TimingAgent(engine).attack(target, trace)
        assert len(results) > 0
        assert all(r.raw_output is not None for r in results)

    @pytest.mark.asyncio
    async def test_gitlab_target_compatible_with_env_agent(self):
        from core.engine import CrucibleEngine
        from attacks.strategies import EnvCorruptionAgent
        engine = CrucibleEngine()
        target = create_demo_gitlab_target()
        trace = engine.begin_trace(target['name'])
        results = await EnvCorruptionAgent(engine).attack(target, trace)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_gitlab_target_compatible_with_supply_chain_agent(self):
        from core.engine import CrucibleEngine
        from attacks.strategies import SupplyChainAgent
        engine = CrucibleEngine()
        target = create_demo_gitlab_target()
        trace = engine.begin_trace(target['name'])
        results = await SupplyChainAgent(engine).attack(target, trace)
        # supply_chain_risks are pre-populated by GitLabCIParser, so there should be findings
        assert len(results) > 0


# ── SARIF Export ──────────────────────────────────────────────────────────────

class TestSARIF:
    def test_sarif_schema_version(self):
        sarif = generate_sarif(['Supply chain: actions/checkout@v4 not pinned'])
        assert sarif['version'] == '2.1.0'
        assert '$schema' in sarif
        assert 'runs' in sarif

    def test_failure_points_become_results(self):
        fps = [
            'Supply chain: actions/checkout@v4 not pinned to SHA',
            'Env corruption: API_KEY null_inject triggered failure (exit=1)',
        ]
        results = generate_sarif(fps)['runs'][0]['results']
        assert len(results) == 2

    def test_rules_deduplicated(self):
        fps = [
            'Supply chain: actions/checkout@v4 not pinned',
            'Supply chain: actions/setup-node@v3 not pinned',
        ]
        sarif = generate_sarif(fps)
        rule_ids = [r['id'] for r in sarif['runs'][0]['tool']['driver']['rules']]
        assert len(rule_ids) == len(set(rule_ids)), "Duplicate rule IDs"

    def test_tool_metadata(self):
        sarif = generate_sarif(['test'])
        driver = sarif['runs'][0]['tool']['driver']
        assert driver['name'] == 'Crucible'
        assert 'version' in driver
        assert 'informationUri' in driver

    def test_empty_failure_points(self):
        sarif = generate_sarif([])
        assert sarif['runs'][0]['results'] == []
        assert sarif['runs'][0]['tool']['driver']['rules'] == []

    def test_target_path_in_location(self):
        sarif = generate_sarif(['Network: curl probe failed'], target_path='.github/workflows/ci.yml')
        uri = sarif['runs'][0]['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri']
        assert uri == '.github/workflows/ci.yml'

    def test_write_sarif_returns_count(self, tmp_path):
        out = str(tmp_path / 'results.sarif')
        count = write_sarif(
            ['Supply chain: unpinned action', 'Dependency: pip exit=1'],
            out,
            target_path='ci.yml',
        )
        assert count == 2

    def test_write_sarif_valid_json(self, tmp_path):
        out = str(tmp_path / 'results.sarif')
        write_sarif(['Supply chain: unpinned action'], out)
        with open(out) as f:
            data = json.load(f)
        assert data['version'] == '2.1.0'

    def test_supply_chain_mapped_to_error(self):
        sarif = generate_sarif(['Supply chain: actions/checkout@v4 not pinned'])
        result = sarif['runs'][0]['results'][0]
        assert result['level'] == 'error'
        assert result['ruleId'] == 'CRU001'

    def test_dependency_mapped_to_warning(self):
        sarif = generate_sarif(['Dependency failure: requests pip exit=1'])
        result = sarif['runs'][0]['results'][0]
        assert result['level'] == 'warning'
        assert result['ruleId'] == 'CRU010'
