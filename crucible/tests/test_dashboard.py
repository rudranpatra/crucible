"""Tests for Rich terminal dashboard."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from io import StringIO
from dashboard.terminal import CrucibleDashboard


class TestCrucibleDashboard:
    def _dashboard(self):
        from rich.console import Console
        d = CrucibleDashboard()
        d.console = Console(file=StringIO(), highlight=False, width=120)
        return d

    def test_instantiation(self):
        d = self._dashboard()
        assert d is not None
        assert d._agent_stats == {}

    def test_print_banner(self):
        d = self._dashboard()
        d.print_banner("my-pipeline", "trc_test123")
        # No exception raised

    def test_print_agent_deployed(self):
        d = self._dashboard()
        d.print_agent_deployed("agent_timing_abc", "timing", "Injects delays")
        assert "agent_timing_abc" in d._agent_stats
        assert d._agent_stats["agent_timing_abc"]["type"] == "timing"

    def test_print_attack_complete_alive(self):
        d = self._dashboard()
        d.print_agent_deployed("agent_env_abc", "env", "Corrupts env vars")
        d.print_attack_complete("agent_env_abc", "env", 4, 2, 75.0, True, ["DB failed"])
        assert d._agent_stats["agent_env_abc"]["mutations"] == 4
        assert d._agent_stats["agent_env_abc"]["triggered"] == 2

    def test_print_attack_complete_dead(self):
        d = self._dashboard()
        d.print_agent_deployed("agent_net_abc", "network", "Network chaos")
        d.print_attack_complete("agent_net_abc", "network", 5, 0, 10.0, False, [])
        # No exception

    def test_print_agent_obituary(self):
        d = self._dashboard()
        d.print_agent_obituary("agent_timing_abc", "timing", 12.5, 8, 0)
        # Should print without raising

    def test_print_kill_screen(self):
        d = self._dashboard()
        d.print_kill_screen(
            "agent_env_abc", "env",
            "DATABASE_URL → null_inject", "trc_abc123"
        )
        # No exception

    def test_print_score_update(self):
        d = self._dashboard()
        d.print_score_update(73.0, "C")
        # No exception

    def test_print_final_report(self):
        d = self._dashboard()
        d.print_agent_deployed("agent_timing_abc", "timing", "desc")
        d.print_attack_complete("agent_timing_abc", "timing", 5, 2, 80.0, True, [])

        result = {
            "resilience_score": 65.0,
            "grade": "C",
            "components": {
                "survival_rate": 60.0,
                "blast_containment": 70.0,
                "recovery_speed": 55.0,
                "coverage_breadth": 80.0,
            },
            "top_vulnerabilities": ["timing vuln detected"],
            "blast_radius": ["deploy_staging"],
            "replay_command": "crucible replay --trace trc_abc123",
            "trace_id": "trc_abc123",
        }
        engine_status = {"total_agents": 1, "alive": 1, "dead": 0}
        d.print_final_report(result, engine_status)
        # No exception

    def test_print_shadow_promotion(self):
        d = self._dashboard()
        d.print_shadow_promotion("timing", 0.65, 0.40)
        # No exception

    def test_multiple_agents_tracked(self):
        d = self._dashboard()
        for agent_type in ["timing", "env", "network"]:
            d.print_agent_deployed(f"agent_{agent_type}_x", agent_type, "desc")
        assert len(d._agent_stats) == 3
