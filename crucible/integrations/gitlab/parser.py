"""
GitLab CI Integration
Parses .gitlab-ci.yml files into Crucible attack targets.
Produces the same target dict format as GitHubActionsParser so all 6 agents work unchanged.
"""

import yaml
from pathlib import Path
from typing import Dict, List


class GitLabCIParser:
    """
    Converts a GitLab CI configuration file into a structured target
    that Crucible's adversarial agents can attack.

    Output format is identical to GitHubActionsParser so all 6 agents
    work without modification.
    """

    # Top-level keys that are config, not job definitions
    RESERVED = {
        'stages', 'variables', 'image', 'services', 'before_script',
        'after_script', 'include', 'workflow', 'default', 'cache', 'pages',
    }

    _SECRET_PATTERNS = ('TOKEN', 'KEY', 'SECRET', 'PASSWORD', 'PASS', 'CREDENTIALS')
    _DEP_FILES = ('requirements.txt', 'package.json', 'Gemfile', 'go.mod', 'Cargo.toml', 'poetry.lock')

    def parse_file(self, path: str) -> Dict:
        with open(path) as f:
            config = yaml.safe_load(f) or {}
        return self._build_target(config, name=Path(path).stem, source_file=str(path))

    def parse_content(self, content: str, name: str = 'gitlab-ci') -> Dict:
        config = yaml.safe_load(content) or {}
        return self._build_target(config, name=name)

    def _build_target(self, config: Dict, name: str, source_file: str = None) -> Dict:
        jobs = {
            k: v for k, v in config.items()
            if isinstance(v, dict) and k not in self.RESERVED and not k.startswith('.')
        }

        env_vars, seen_vars = [], set()
        global_vars = config.get('variables', {}) or {}
        for k, v in global_vars.items():
            env_vars.append(self._make_env_var(k, v))
            seen_vars.add(k)

        steps, network_calls, dependencies = [], [], []

        for job_name, job in jobs.items():
            script_lines = self._collect_scripts(config, job)
            for i, line in enumerate(script_lines):
                step = {
                    'name': f'{job_name}_step{i}',
                    'run': line,
                    'index': len(steps),
                    'is_critical': job.get('stage') in ('deploy', 'release', 'publish'),
                    'env_vars': [],
                    'network_calls': [],
                    'dependencies': [],
                    'has_retry': bool(job.get('retry')),
                }
                net = self._detect_network(line)
                step['network_calls'].extend(net)
                network_calls.extend(net)
                steps.append(step)

            for k, v in (job.get('variables', {}) or {}).items():
                if k not in seen_vars:
                    env_vars.append(self._make_env_var(k, v))
                    seen_vars.add(k)

            for line in script_lines:
                for dep_file in self._DEP_FILES:
                    dep_name = dep_file.split('.')[0]
                    if dep_file in line and not any(d['name'] == dep_name for d in dependencies):
                        dependencies.append({'name': dep_name, 'pinned': None})

        supply_chain_risks = self._check_supply_chain(config, jobs)

        critical = [s['name'] for s in steps if s.get('is_critical')]

        return {
            'name': name,
            'type': 'gitlab_ci',
            'source_file': source_file,
            'triggers': ['push', 'merge_request'],
            'jobs': [{'name': jn, 'runs_on': j.get('tags', ['shared-runner'])} for jn, j in jobs.items()],
            'steps': steps,
            'env_vars': env_vars,
            'network_calls': list(set(network_calls)),
            'dependencies': dependencies,
            'timeout_ms': 3600000,
            'has_retry_logic': any(j.get('retry') for j in jobs.values() if isinstance(j, dict)),
            'has_timeout': any(j.get('timeout') for j in jobs.values() if isinstance(j, dict)),
            'critical_order_steps': critical,
            'downstream_steps': [s['name'] for s in steps if s.get('is_critical')],
            'supply_chain_risks': supply_chain_risks,
        }

    def _make_env_var(self, key: str, value) -> Dict:
        is_secret = any(pat in key.upper() for pat in self._SECRET_PATTERNS)
        raw = str(value) if value is not None else ''
        pinned = raw if raw and not raw.startswith('$') else None
        return {'name': key, 'pinned': pinned, 'is_secret': is_secret}

    def _collect_scripts(self, config: Dict, job: Dict) -> List[str]:
        lines = []
        global_before = config.get('before_script', [])
        for section in (global_before, job.get('before_script', []), job.get('script', []), job.get('after_script', [])):
            if isinstance(section, str):
                lines.append(section)
            else:
                lines.extend(section or [])
        return lines

    def _detect_network(self, line: str) -> List[str]:
        calls = []
        lower = line.lower()
        if 'curl' in lower or 'wget' in lower:
            calls.append('external_http_call')
        if 'npm' in lower:
            calls.append('npm_registry')
        if 'pip' in lower:
            calls.append('pypi_registry')
        if 'docker pull' in lower or 'docker push' in lower:
            calls.append('docker_registry')
        return calls

    def _check_supply_chain(self, config: Dict, jobs: Dict) -> List[Dict]:
        risks = []

        def flag_image(img, context):
            if isinstance(img, dict):
                img = img.get('name', '')
            if isinstance(img, str) and img:
                if ':' not in img or img.endswith(':latest'):
                    risks.append({
                        'finding_type': 'unpinned_image',
                        'detail': f"{img} — not pinned to a specific tag or digest",
                        'context': context,
                        'severity': 'medium',
                    })

        if 'image' in config:
            flag_image(config['image'], 'global')
        for job_name, job in jobs.items():
            if 'image' in job:
                flag_image(job['image'], job_name)

        if not config.get('variables'):
            risks.append({
                'finding_type': 'missing_global_variables',
                'detail': 'No global variables block — secrets may be inlined in scripts',
                'severity': 'low',
            })

        return risks


def create_demo_gitlab_target() -> Dict:
    """Demo GitLab CI target for testing without a real config file."""
    content = """
stages:
  - build
  - test
  - deploy

variables:
  DATABASE_URL: postgres://localhost/mydb
  API_KEY: $CI_API_TOKEN
  NODE_ENV: production

image: node

build:
  stage: build
  script:
    - npm ci
    - npm run build

test:
  stage: test
  script:
    - npm test

deploy:
  stage: deploy
  script:
    - echo "deploying..."
    - curl -X POST $DEPLOY_URL
  environment:
    name: production
"""
    return GitLabCIParser().parse_content(content, 'demo-gitlab-ci')
