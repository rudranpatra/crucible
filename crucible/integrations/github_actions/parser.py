"""
GitHub Actions Integration
Parses GitHub Actions workflow YAML files into Crucible's target format.
Produces attack-ready workflow representations.
"""

import yaml
from pathlib import Path
from typing import Dict, List


class GitHubActionsParser:
    """
    Converts a GitHub Actions workflow file into a structured target
    that Crucible's adversarial agents can attack.
    """

    def parse_file(self, workflow_path: str) -> Dict:
        path = Path(workflow_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {workflow_path}")

        with open(path) as f:
            raw = yaml.safe_load(f)

        return self.parse(raw, source_file=str(path))

    def parse(self, raw: Dict, source_file: str = "unknown") -> Dict:
        target = {
            "name": raw.get('name', source_file),
            "source_file": source_file,
            "triggers": list(raw.get('on', {}).keys()) if isinstance(raw.get('on'), dict) else [str(raw.get('on', ''))],
            "jobs": [],
            "steps": [],
            "env_vars": [],
            "network_calls": [],
            "dependencies": [],
            "timeout_ms": 3600000,
            "has_retry_logic": False,
            "has_timeout": False,
            "critical_order_steps": [],
            "downstream_steps": []
        }

        jobs = raw.get('jobs', {})
        for job_name, job_config in jobs.items():
            job = self._parse_job(job_name, job_config)
            target['jobs'].append(job)
            target['steps'].extend(job['steps'])
            target['env_vars'].extend(job['env_vars'])
            target['network_calls'].extend(job['network_calls'])
            target['dependencies'].extend(job['dependencies'])

            if job.get('has_timeout'):
                target['has_timeout'] = True
            if job.get('has_retry'):
                target['has_retry_logic'] = True

            timeout = job_config.get('timeout-minutes')
            if timeout:
                target['timeout_ms'] = min(target['timeout_ms'], timeout * 60000)

        target['env_vars'] = list({v['name']: v for v in target['env_vars']}.values())
        target['network_calls'] = list(set(target['network_calls']))
        target['dependencies'] = list({d['name']: d for d in target['dependencies']}.values())
        target['critical_order_steps'] = self._identify_critical_order(target['steps'])
        target['downstream_steps'] = self._identify_downstream(target['steps'])

        return target

    def _parse_job(self, job_name: str, job_config: Dict) -> Dict:
        job = {
            "name": job_name,
            "runs_on": job_config.get('runs-on', 'ubuntu-latest'),
            "steps": [],
            "env_vars": [],
            "network_calls": [],
            "dependencies": [],
            "has_timeout": False,
            "has_retry": False,
        }

        if job_config.get('timeout-minutes'):
            job['has_timeout'] = True

        env = job_config.get('env', {})
        for key, value in env.items():
            job['env_vars'].append({
                "name": key,
                "pinned": str(value) if not str(value).startswith('${{') else None,
                "is_secret": 'secret' in str(value).lower() or 'token' in key.lower()
            })

        steps = job_config.get('steps', [])
        for i, step in enumerate(steps):
            parsed_step = self._parse_step(step, i)
            job['steps'].append(parsed_step)
            job['env_vars'].extend(parsed_step.get('env_vars', []))
            job['network_calls'].extend(parsed_step.get('network_calls', []))
            job['dependencies'].extend(parsed_step.get('dependencies', []))

            if parsed_step.get('has_retry'):
                job['has_retry'] = True

        return job

    def _parse_step(self, step: Dict, index: int) -> Dict:
        name = step.get('name', f'step_{index}')
        uses = step.get('uses', '')
        run = step.get('run', '')

        parsed = {
            "name": name,
            "index": index,
            "uses": uses,
            "run": run,
            "env_vars": [],
            "network_calls": [],
            "dependencies": [],
            "has_retry": False,
            "is_critical": False,
        }

        env = step.get('env', {})
        for key, value in env.items():
            parsed['env_vars'].append({
                "name": key,
                "pinned": None,
                "is_secret": 'secret' in str(value).lower() or 'token' in key.lower()
            })

        if uses:
            parsed['network_calls'].append(f"action_fetch:{uses}")
            self._extract_action_deps(uses, parsed)

        if run:
            self._extract_run_deps(run, parsed)

        critical_keywords = ['deploy', 'release', 'publish', 'migrate', 'build', 'test']
        if any(kw in name.lower() for kw in critical_keywords):
            parsed['is_critical'] = True

        if 'retry' in str(step).lower() or 'continue-on-error' in step:
            parsed['has_retry'] = True

        return parsed

    def _extract_action_deps(self, uses: str, parsed: Dict):
        if 'actions/checkout' in uses:
            parsed['network_calls'].append('git_checkout')
        elif 'actions/setup-node' in uses:
            parsed['network_calls'].append('npm_registry')
            parsed['dependencies'].append({"name": "node", "pinned": None})
        elif 'actions/setup-python' in uses:
            parsed['network_calls'].append('pypi_registry')
        elif 'docker' in uses.lower():
            parsed['network_calls'].append('docker_registry')
        elif 'aws' in uses.lower():
            parsed['network_calls'].append('aws_api')

    def _extract_run_deps(self, run: str, parsed: Dict):
        run_lower = run.lower()

        if 'pip install' in run_lower or 'pip3 install' in run_lower:
            parsed['network_calls'].append('pypi_registry')
            self._extract_pip_deps(run, parsed)

        if 'npm install' in run_lower or 'npm ci' in run_lower:
            parsed['network_calls'].append('npm_registry')

        if 'curl' in run_lower or 'wget' in run_lower:
            parsed['network_calls'].append('external_http_call')

        if 'docker pull' in run_lower or 'docker build' in run_lower:
            parsed['network_calls'].append('docker_registry')

        if 'pytest' in run_lower or 'jest' in run_lower or 'go test' in run_lower:
            parsed['is_critical'] = True

    def _extract_pip_deps(self, run: str, parsed: Dict):
        import re
        packages = re.findall(r'pip(?:3)? install\s+([\w\-\[\]>=<~!,\s]+?)(?:\s|$|\n|&&)', run)
        for pkg_group in packages:
            for pkg in pkg_group.split():
                clean = re.split(r'[>=<!~\[]', pkg)[0].strip()
                if clean and not clean.startswith('-'):
                    has_pin = any(op in pkg for op in ['==', '>=', '~='])
                    parsed['dependencies'].append({
                        "name": clean,
                        "pinned": pkg if has_pin else None
                    })

    def _identify_critical_order(self, steps: List[Dict]) -> List[str]:
        critical = []
        for step in steps:
            if step.get('is_critical') or any(
                kw in step['name'].lower()
                for kw in ['checkout', 'install', 'build', 'test', 'deploy']
            ):
                critical.append(step['name'])
        return critical

    def _identify_downstream(self, steps: List[Dict]) -> List[str]:
        return [s['name'] for s in steps if 'deploy' in s['name'].lower() or 'release' in s['name'].lower()]


def parse_workflow(path: str) -> Dict:
    return GitHubActionsParser().parse_file(path)


def create_demo_target() -> Dict:
    """Creates a demo target for testing without a real workflow file."""
    return {
        "name": "demo_ci_pipeline",
        "source_file": "demo",
        "triggers": ["push", "pull_request"],
        "jobs": [{"name": "build_and_test", "runs_on": "ubuntu-latest"}],
        "steps": [
            {"name": "checkout", "index": 0, "is_critical": True},
            {"name": "install_dependencies", "index": 1, "is_critical": True},
            {"name": "run_tests", "index": 2, "is_critical": True},
            {"name": "build_artifact", "index": 3, "is_critical": True},
            {"name": "deploy_staging", "index": 4, "is_critical": True},
        ],
        "env_vars": [
            {"name": "NODE_ENV", "pinned": "production", "is_secret": False},
            {"name": "DATABASE_URL", "pinned": None, "is_secret": True},
            {"name": "API_KEY", "pinned": None, "is_secret": True},
            {"name": "DEPLOY_TOKEN", "pinned": None, "is_secret": True},
        ],
        "network_calls": ["git_checkout", "npm_registry", "pypi_registry", "aws_api"],
        "dependencies": [
            {"name": "requests", "pinned": "2.28.0"},
            {"name": "numpy", "pinned": None},
            {"name": "boto3", "pinned": "1.26.0"},
        ],
        "timeout_ms": 1800000,
        "has_retry_logic": False,
        "has_timeout": True,
        "critical_order_steps": ["checkout", "install_dependencies", "run_tests", "build_artifact", "deploy_staging"],
        "downstream_steps": ["deploy_staging"],
        "supply_chain_risks": [
            {
                "finding_type": "unpinned_action",
                "action": "actions/checkout@v4",
                "step": "Checkout code",
                "ref": "v4",
                "severity": "high",
            },
            {
                "finding_type": "missing_permissions_block",
                "severity": "medium",
                "detail": "No permissions block — GITHUB_TOKEN defaults grant contents:write on push events",
            },
        ],
    }
