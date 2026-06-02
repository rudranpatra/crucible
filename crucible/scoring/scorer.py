"""
Resilience Scoring Engine
Produces a 0–100 score from attack results.
Score components: failure rate, blast radius, recovery time, attack surface coverage.
Scores decay over time — a 6-month-old score is marked stale.
"""

import time
from dataclasses import dataclass
from typing import List, Dict, Optional
from agents.base_agent import AttackResult


@dataclass
class ResilienceReport:
    score: float
    grade: str
    components: Dict[str, float]
    failure_points: List[str]
    blast_radius: List[str]
    attack_coverage: List[str]
    top_vulnerabilities: List[str]
    scored_at: float
    is_stale: bool = False
    stale_reason: Optional[str] = None

    def summary(self) -> str:
        lines = [
            f"Resilience Score: {self.score:.1f}/100 ({self.grade})",
            f"Failure Points: {len(self.failure_points)}",
            f"Blast Radius: {', '.join(self.blast_radius) if self.blast_radius else 'contained'}",
            f"Attack Coverage: {', '.join(self.attack_coverage)}",
            "",
            "Component Scores:",
        ]
        for k, v in self.components.items():
            lines.append(f"  {k}: {v:.1f}")
        if self.top_vulnerabilities:
            lines.append("")
            lines.append("Top Vulnerabilities:")
            for v in self.top_vulnerabilities:
                lines.append(f"  - {v}")
        if self.is_stale:
            lines.append(f"\n[STALE] {self.stale_reason}")
        return "\n".join(lines)


class ResilienceScorer:
    """
    Scores pipeline resilience from 0 (will definitely break) to 100 (survived all pressure).

    Score components:
    - survival_rate (40%): percentage of attacks that did NOT trigger failures
    - blast_containment (25%): how contained failures were when they occurred
    - recovery_speed (20%): how quickly the pipeline would recover
    - coverage_breadth (15%): how many attack types were tested
    """

    STALE_THRESHOLD_DAYS = 30
    SCORE_WEIGHTS = {
        'survival_rate': 0.40,
        'blast_containment': 0.25,
        'recovery_speed': 0.20,
        'coverage_breadth': 0.15,
    }

    GRADE_THRESHOLDS = [
        (90, 'A', 'Excellent — survived adversarial pressure across all attack types'),
        (75, 'B', 'Good — minor vulnerabilities detected, low production risk'),
        (60, 'C', 'Fair — moderate vulnerabilities, targeted hardening recommended'),
        (40, 'D', 'Poor — significant vulnerabilities, high production risk'),
        (0,  'F', 'Critical — pipeline will break under realistic operational pressure'),
    ]

    def score(self, results: List[AttackResult], attack_types_run: List[str]) -> ResilienceReport:
        if not results:
            return self._empty_report()

        triggered = [r for r in results if r.failure_triggered]
        survived = [r for r in results if not r.failure_triggered]

        survival_score = (len(survived) / len(results)) * 100

        blast_score = self._score_blast_containment(triggered)

        recovery_score = self._score_recovery(triggered)

        all_attack_types = {'timing', 'env', 'reorder', 'network', 'dependency'}
        coverage_score = (len(set(attack_types_run)) / len(all_attack_types)) * 100

        components = {
            'survival_rate': round(survival_score, 1),
            'blast_containment': round(blast_score, 1),
            'recovery_speed': round(recovery_score, 1),
            'coverage_breadth': round(coverage_score, 1),
        }

        weighted = sum(
            components[k] * self.SCORE_WEIGHTS[k]
            for k in components
        )
        final_score = round(min(100.0, max(0.0, weighted)), 1)

        failure_points = []
        blast_radius = set()
        for r in triggered:
            if r.failure_description:
                failure_points.append(r.failure_description)
            blast_radius.update(r.affected_steps)

        grade, grade_desc = self._get_grade(final_score)

        vulns = self._extract_vulnerabilities(triggered, attack_types_run)

        return ResilienceReport(
            score=final_score,
            grade=grade,
            components=components,
            failure_points=failure_points[:10],
            blast_radius=list(blast_radius),
            attack_coverage=attack_types_run,
            top_vulnerabilities=vulns,
            scored_at=time.time(),
        )

    def check_staleness(self, report: ResilienceReport) -> ResilienceReport:
        age_days = (time.time() - report.scored_at) / 86400
        if age_days > self.STALE_THRESHOLD_DAYS:
            report.is_stale = True
            report.stale_reason = f"Score is {age_days:.0f} days old. Re-run attacks to refresh."
        return report

    def _score_blast_containment(self, triggered: List[AttackResult]) -> float:
        if not triggered:
            return 100.0
        total_affected = sum(len(r.affected_steps) for r in triggered)
        avg_affected = total_affected / len(triggered)
        return max(0, 100 - (avg_affected * 15))

    def _score_recovery(self, triggered: List[AttackResult]) -> float:
        times = [r.recovery_time_ms for r in triggered if r.recovery_time_ms is not None]
        if not times:
            return 100.0 if not triggered else 50.0
        avg_ms = sum(times) / len(times)
        if avg_ms < 200:
            return 95.0
        elif avg_ms < 1000:
            return 75.0
        elif avg_ms < 3000:
            return 50.0
        elif avg_ms < 5000:
            return 25.0
        else:
            return 10.0

    def _get_grade(self, score: float):
        for threshold, grade, desc in self.GRADE_THRESHOLDS:
            if score >= threshold:
                return grade, desc
        return 'F', 'Critical'

    def _extract_vulnerabilities(self, triggered: List[AttackResult], attack_types: List[str]) -> List[str]:
        vulns = []
        timing_failures = [r for r in triggered if r.mutation_applied.get('delay_ms')]
        if timing_failures:
            vulns.append(f"Timing vulnerability: {len(timing_failures)} steps failed under delay injection")

        env_failures = [r for r in triggered if r.mutation_applied.get('variable')]
        if env_failures:
            vars_affected = [r.mutation_applied['variable'] for r in env_failures]
            vulns.append(f"Env vulnerability: {', '.join(vars_affected[:3])} lack input validation")

        network_failures = [r for r in triggered if r.mutation_applied.get('chaos_profile')]
        if network_failures:
            vulns.append(f"Network vulnerability: {len(network_failures)} calls have no retry/timeout logic")

        dep_failures = [r for r in triggered if r.mutation_applied.get('drift_type')]
        unpinned = [r for r in dep_failures if not r.mutation_applied.get('is_pinned')]
        if unpinned:
            vulns.append(f"Dependency vulnerability: {len(unpinned)} unpinned packages found")

        missing_types = {'timing', 'env', 'reorder', 'network', 'dependency'} - set(attack_types)
        if missing_types:
            vulns.append(f"Coverage gap: untested attack surfaces — {', '.join(missing_types)}")

        return vulns[:5]

    def _empty_report(self) -> ResilienceReport:
        return ResilienceReport(
            score=0.0,
            grade='?',
            components={},
            failure_points=[],
            blast_radius=[],
            attack_coverage=[],
            top_vulnerabilities=["No attacks were run"],
            scored_at=time.time()
        )
