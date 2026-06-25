"""
SARIF export for GitHub Code Scanning integration.
Converts Crucible failure_points to SARIF 2.1.0 format,
compatible with github/codeql-action/upload-sarif.
"""

import json
from typing import Dict, List, Optional

# Map failure_point string prefixes to SARIF rule definitions
_RULES = [
    ('Supply chain',    'CRU001', 'UnpinnedOrUnsafeAction',   'Unpinned or unsafe CI/CD action or dependency', 'error'),
    ('Dependency',      'CRU010', 'DependencyDrift',           'Dependency version instability detected',        'warning'),
    ('Env corruption',  'CRU020', 'EnvCorruption',             'Environment variable lacks validation',           'warning'),
    ('Timing',          'CRU030', 'TimingVulnerability',        'Step vulnerable to timing injection',             'note'),
    ('Step reorder',    'CRU040', 'StepOrderDependency',        'Hidden step ordering dependency',                 'note'),
    ('Network',         'CRU050', 'NetworkResilience',          'Step not resilient to network failure',           'warning'),
]
_DEFAULT_RULE = ('CRU099', 'AdversarialFinding', 'Adversarial finding', 'note')


def _match_rule(failure_point: str):
    lower = failure_point.lower()
    for prefix, rid, name, desc, level in _RULES:
        if prefix.lower() in lower:
            return rid, name, desc, level
    return _DEFAULT_RULE


def generate_sarif(
    failure_points: List[str],
    target_path: Optional[str] = None,
    version: str = '0.3.0',
) -> Dict:
    """
    Convert a list of Crucible failure_point strings to SARIF 2.1.0.
    Compatible with GitHub Code Scanning (upload-sarif action).
    """
    rules_seen: Dict[str, Dict] = {}
    results = []
    location = {
        'physicalLocation': {
            'artifactLocation': {'uri': target_path or 'unknown'},
        }
    }

    for fp in failure_points:
        rule_id, rule_name, rule_desc, level = _match_rule(fp)
        if rule_id not in rules_seen:
            rules_seen[rule_id] = {
                'id': rule_id,
                'name': rule_name,
                'shortDescription': {'text': rule_desc},
                'defaultConfiguration': {'level': level},
                'helpUri': 'https://github.com/rudranpatra/crucible',
            }
        results.append({
            'ruleId': rule_id,
            'level': level,
            'message': {'text': fp},
            'locations': [location],
        })

    return {
        '$schema': 'https://json.schemastore.org/sarif-2.1.0.json',
        'version': '2.1.0',
        'runs': [{
            'tool': {
                'driver': {
                    'name': 'Crucible',
                    'version': version,
                    'informationUri': 'https://github.com/rudranpatra/crucible',
                    'rules': list(rules_seen.values()),
                }
            },
            'results': results,
        }],
    }


def write_sarif(
    failure_points: List[str],
    output_path: str,
    target_path: Optional[str] = None,
) -> int:
    """Write SARIF to file. Returns count of findings written."""
    sarif = generate_sarif(failure_points, target_path=target_path)
    with open(output_path, 'w') as f:
        json.dump(sarif, f, indent=2)
    return len(sarif['runs'][0]['results'])
