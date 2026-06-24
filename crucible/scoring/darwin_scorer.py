"""
Darwin Scorer
Evolutionary pressure applied across runs, not just within a single run.

Agents aren't scored on one performance — they're scored on their entire lifetime.
Species that consistently trigger failures dominate. Species that don't, go extinct.
"""

import fcntl
import json
import time
from pathlib import Path
from typing import Dict, List, Optional


class _FileLock:
    """Cross-process exclusive file lock using fcntl. Prevents concurrent write corruption."""
    def __init__(self, path: Path):
        self._lock_path = path.with_suffix('.lock')
        self._fh = None

    def __enter__(self):
        self._fh = open(self._lock_path, 'w')
        fcntl.flock(self._fh, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        fcntl.flock(self._fh, fcntl.LOCK_UN)
        self._fh.close()


class DarwinScorer:
    """
    Tracks agent species performance across all runs.

    Fitness = survival_score (40%) + lineage_depth_bonus (30%) + generation_bonus (30%)

    Species with lifetime fitness > 60: DOMINANT
    Species with lifetime fitness < 10 after 5+ runs: EXTINCT
    """

    DOMINANT_THRESHOLD = 60.0
    EXTINCT_THRESHOLD = 10.0
    EXTINCT_MIN_RUNS = 5
    MAX_HISTORY = 20

    def __init__(self, state_file: str = "traces/darwin_state.json"):
        self.state_file = Path(state_file)
        self.state: Dict = self._load()

    # ── Recording ─────────────────────────────────────────────────────────────

    def record_run(
        self,
        agent_type: str,
        trigger_rate: float,
        generation: int = 1,
        lineage_depth: int = 0,
        mutation_key: Optional[str] = None,
    ):
        """Record one run result for an agent species."""
        species = self._get_or_create_species(agent_type)
        species["runs"] += 1
        species["total_trigger_rate"] += trigger_rate
        species["generation"] = max(species["generation"], generation)
        species["lineage_depth"] = max(species["lineage_depth"], lineage_depth)
        species["fitness_history"].append(round(trigger_rate, 4))
        species["fitness_history"] = species["fitness_history"][-self.MAX_HISTORY:]

        if mutation_key and mutation_key not in species["mutation_history"]:
            species["mutation_history"].append(mutation_key)
            species["mutation_history"] = species["mutation_history"][-10:]

        species["last_run"] = time.time()
        self.save()

    def record_promotion(self, agent_type: str, shadow_rate: float, prod_rate: float):
        """Log a shadow→production promotion as an evolutionary event."""
        species = self._get_or_create_species(agent_type)
        species["generation"] += 1
        species["lineage_depth"] += 1

        event = {
            "event": "promotion",
            "agent_type": agent_type,
            "shadow_rate": round(shadow_rate, 4),
            "production_rate": round(prod_rate, 4),
            "new_generation": species["generation"],
            "timestamp": time.time(),
        }
        self.state["promotions"].append(event)
        self.state["promotions"] = self.state["promotions"][-50:]
        self.save()

    # ── Fitness calculation ───────────────────────────────────────────────────

    def calculate_fitness(self, agent_type: str) -> float:
        """
        Lifetime fitness score 0–100.
        Weighted: trigger_rate (40%) + lineage_depth (30%) + generation (30%)
        """
        if agent_type not in self.state["species"]:
            return 0.0

        sp = self.state["species"][agent_type]
        runs = sp["runs"]
        if runs == 0:
            return 0.0

        avg_rate = sp["total_trigger_rate"] / runs
        success_score = avg_rate * 100 * 0.60

        lineage_bonus = min(20.0, sp.get("lineage_depth", 0) * 4.0)
        gen_bonus = min(20.0, (sp.get("generation", 1) - 1) * 7.0)

        return round(min(100.0, success_score + lineage_bonus + gen_bonus), 2)

    # ── Species report ────────────────────────────────────────────────────────

    def get_species_report(self) -> Dict[str, Dict]:
        report = {}
        for name, sp in self.state["species"].items():
            fitness = self.calculate_fitness(name)
            runs = sp["runs"]
            report[name] = {
                "fitness": fitness,
                "runs": runs,
                "avg_trigger_rate": round(sp["total_trigger_rate"] / max(1, runs), 4),
                "generation": sp.get("generation", 1),
                "lineage_depth": sp.get("lineage_depth", 0),
                "is_dominant": fitness >= self.DOMINANT_THRESHOLD,
                "is_extinct": runs >= self.EXTINCT_MIN_RUNS and fitness < self.EXTINCT_THRESHOLD,
                "fitness_trend": self._trend(sp["fitness_history"]),
            }
        return report

    def get_dominant_species(self) -> List[str]:
        return [
            name for name, data in self.get_species_report().items()
            if data["is_dominant"]
        ]

    def get_extinct_species(self) -> List[str]:
        return [
            name for name, data in self.get_species_report().items()
            if data["is_extinct"]
        ]

    def get_evolutionary_log(self) -> List[Dict]:
        return self.state.get("promotions", [])

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_or_create_species(self, agent_type: str) -> Dict:
        if agent_type not in self.state["species"]:
            self.state["species"][agent_type] = {
                "runs": 0,
                "total_trigger_rate": 0.0,
                "generation": 1,
                "lineage_depth": 0,
                "mutation_history": [],
                "fitness_history": [],
                "last_run": None,
            }
        return self.state["species"][agent_type]

    def _trend(self, history: List[float]) -> str:
        if len(history) < 3:
            return "insufficient_data"
        recent = history[-3:]
        if recent[-1] > recent[0] * 1.1:
            return "improving"
        elif recent[-1] < recent[0] * 0.9:
            return "declining"
        return "stable"

    def _load(self) -> Dict:
        if self.state_file.exists():
            try:
                with _FileLock(self.state_file):
                    with open(self.state_file) as f:
                        return json.load(f)
            except (json.JSONDecodeError, KeyError, OSError):
                pass
        return {"species": {}, "promotions": [], "extinct": []}

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix('.tmp')
        with _FileLock(self.state_file):
            with open(tmp, 'w') as f:
                json.dump(self.state, f, indent=2)
            tmp.replace(self.state_file)
