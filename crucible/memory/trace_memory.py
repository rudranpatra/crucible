"""
Attack Trace Memory
Stores, indexes, and retrieves adversarial traces.
Traces are the core data asset — replayable, auditable, shareable.
"""

import json
import time
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any
from pathlib import Path
from core.file_lock import FileLock as _FileLock


@dataclass
class StoredTrace:
    trace_id: str
    target: str
    attack_types: List[str]
    resilience_score: float
    failure_count: int
    blast_radius: List[str]
    failure_points: List[str]
    mutations: List[Dict]
    replay_command: str
    created_at: float
    tags: List[str]
    raw_trace: Dict


class TraceMemory:
    """
    Persists attack traces to disk.
    Each trace is a replayable record of exactly what happened.
    This is debugging gold, learning signal, and governance artifact.
    """

    def __init__(self, traces_dir: str = "traces"):
        self.traces_dir = Path(traces_dir)
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.index: Dict[str, StoredTrace] = {}
        self._load_index()

    def store(self, trace: Dict, tags: Optional[List[str]] = None) -> StoredTrace:
        trace_id = trace.get('trace_id', f"trc_{uuid.uuid4().hex[:10]}")
        tags = tags or []

        events = trace.get('events', [])
        failure_count = sum(
            1 for e in events
            if e.get('result', {}).get('failure_triggered') is True
        )

        attack_types = list(set(e.get('attack_type') for e in events if e.get('attack_type')))

        stored = StoredTrace(
            trace_id=trace_id,
            target=trace.get('target', 'unknown'),
            attack_types=attack_types,
            resilience_score=trace.get('resilience_score', 0.0),
            failure_count=failure_count,
            blast_radius=trace.get('blast_radius', []),
            failure_points=trace.get('failure_points', []),
            mutations=[e.get('mutation', {}) for e in events],
            replay_command=trace.get('replay_command', f"crucible replay --trace traces/{trace_id}.crucible"),
            created_at=time.time(),
            tags=tags,
            raw_trace=trace
        )

        trace_path = self.traces_dir / f"{trace_id}.crucible"
        with open(trace_path, 'w') as f:
            json.dump(asdict(stored), f, indent=2)

        self.index[trace_id] = stored
        self._save_index()
        return stored

    def load(self, trace_id: str) -> Optional[StoredTrace]:
        trace_path = self.traces_dir / f"{trace_id}.crucible"
        if not trace_path.exists():
            return None
        with open(trace_path) as f:
            data = json.load(f)
        return StoredTrace(**data)

    def search(self, target: Optional[str] = None,
               attack_type: Optional[str] = None,
               min_score: Optional[float] = None,
               max_score: Optional[float] = None,
               tags: Optional[List[str]] = None) -> List[StoredTrace]:
        results = list(self.index.values())

        if target:
            results = [t for t in results if target.lower() in t.target.lower()]
        if attack_type:
            results = [t for t in results if attack_type in t.attack_types]
        if min_score is not None:
            results = [t for t in results if t.resilience_score >= min_score]
        if max_score is not None:
            results = [t for t in results if t.resilience_score <= max_score]
        if tags:
            results = [t for t in results if any(tag in t.tags for tag in tags)]

        return sorted(results, key=lambda t: t.created_at, reverse=True)

    def get_failure_patterns(self) -> Dict[str, Any]:
        """
        Cluster failure patterns across all traces.
        This is the beginning of the operational foresight graph.
        """
        all_traces = list(self.index.values())
        if not all_traces:
            return {}

        attack_failure_rates = {}
        step_failure_counts = {}
        score_history = []

        for trace in all_traces:
            score_history.append({
                'trace_id': trace.trace_id,
                'score': trace.resilience_score,
                'created_at': trace.created_at,
            })

            for attack_type in trace.attack_types:
                if attack_type not in attack_failure_rates:
                    attack_failure_rates[attack_type] = {'runs': 0, 'failures': 0}
                attack_failure_rates[attack_type]['runs'] += 1
                if trace.failure_count > 0:
                    attack_failure_rates[attack_type]['failures'] += 1

            for step in trace.blast_radius:
                step_failure_counts[step] = step_failure_counts.get(step, 0) + 1

        most_vulnerable_steps = sorted(
            step_failure_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        avg_score = sum(t.resilience_score for t in all_traces) / len(all_traces)
        sorted_history = sorted(score_history, key=lambda x: x['created_at'])
        score_trend = (
            "improving" if len(sorted_history) > 1 and sorted_history[-1]['score'] > sorted_history[0]['score']
            else "declining" if len(sorted_history) > 1 and sorted_history[-1]['score'] < sorted_history[0]['score']
            else "stable"
        )

        return {
            "total_traces": len(all_traces),
            "average_resilience_score": round(avg_score, 1),
            "score_trend": score_trend,
            "attack_failure_rates": {
                k: round(v['failures'] / v['runs'], 3) if v['runs'] > 0 else 0
                for k, v in attack_failure_rates.items()
            },
            "most_vulnerable_steps": [
                {"step": step, "failure_count": count}
                for step, count in most_vulnerable_steps
            ],
            "score_history": score_history[-20:]
        }

    def _load_index(self):
        index_path = self.traces_dir / "index.json"
        if index_path.exists():
            with open(index_path) as f:
                raw = json.load(f)
            for trace_id, data in raw.items():
                try:
                    self.index[trace_id] = StoredTrace(**data)
                except Exception:
                    pass

    def _save_index(self):
        index_path = self.traces_dir / "index.json"
        tmp = index_path.with_suffix('.tmp')
        with _FileLock(index_path):
            with open(tmp, 'w') as f:
                json.dump(
                    {tid: asdict(t) for tid, t in self.index.items()},
                    f, indent=2
                )
            tmp.replace(index_path)
