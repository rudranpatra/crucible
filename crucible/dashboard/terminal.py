"""
Crucible Rich Terminal Dashboard
Screenshot-worthy output: kill screens, agent obituaries, live progress, report card.
"""

import time
from typing import Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich import box


GRADE_COLORS = {"A": "bright_green", "B": "green", "C": "yellow", "D": "orange3", "F": "red"}

CRUCIBLE_BANNER = r"""
   ██████╗██████╗ ██╗   ██╗ ██████╗██╗██████╗ ██╗     ███████╗
  ██╔════╝██╔══██╗██║   ██║██╔════╝██║██╔══██╗██║     ██╔════╝
  ██║     ██████╔╝██║   ██║██║     ██║██████╔╝██║     █████╗
  ██║     ██╔══██╗██║   ██║██║     ██║██╔══██╗██║     ██╔══╝
  ╚██████╗██║  ██║╚██████╔╝╚██████╗██║██████╔╝███████╗███████╗
   ╚═════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝╚═╝╚═════╝ ╚══════╝╚══════╝
"""


class CrucibleDashboard:
    """
    Rich terminal UI for Crucible runs.
    Prints styled panels as events happen — screenshot-worthy by design.
    """

    def __init__(self, quiet: bool = False):
        self.console = Console(highlight=False)
        self.quiet = quiet
        self._agent_stats: Dict[str, Dict] = {}
        self._start_time = time.time()

    # ── Banner ────────────────────────────────────────────────────────────────

    def print_banner(self, target: str, trace_id: str):
        banner_text = Text(CRUCIBLE_BANNER, style="bold red", justify="center")
        subtitle = Text(justify="center")
        subtitle.append("  Adversarial Intelligence Engine for CI/CD  ", style="bold white on red")
        self.console.print(banner_text)
        self.console.print(subtitle)
        self.console.print()

        meta = Table.grid(padding=(0, 2))
        meta.add_column(style="dim")
        meta.add_column(style="bold white")
        meta.add_row("Target:", target)
        meta.add_row("Trace ID:", f"[cyan]{trace_id}[/]")
        meta.add_row("Started:", time.strftime("%Y-%m-%d %H:%M:%S"))
        self.console.print(Panel(meta, border_style="red", box=box.ROUNDED, title="[bold red]🔥 Attack Initiated[/]"))
        self.console.print()

    # ── Agent lifecycle ───────────────────────────────────────────────────────

    def print_agent_deployed(self, agent_id: str, attack_type: str, description: str):
        self._agent_stats[agent_id] = {
            "type": attack_type,
            "mutations": 0,
            "triggered": 0,
            "fitness": 100.0,
        }
        self.console.print(
            f"  [bold yellow]⚡ DEPLOYING[/]  [cyan]{attack_type}[/] agent  "
            f"[dim]{agent_id}[/]"
        )
        self.console.print(f"     [dim italic]{description}[/]")

    def print_attack_complete(
        self,
        agent_id: str,
        attack_type: str,
        total: int,
        triggered: int,
        fitness: float,
        is_alive: bool,
        failures: List[str],
    ):
        if agent_id in self._agent_stats:
            self._agent_stats[agent_id].update(
                {"mutations": total, "triggered": triggered, "fitness": fitness}
            )

        status = "[bold green]ALIVE[/]" if is_alive else "[bold red]DEAD[/]"
        trig_style = "red bold" if triggered > 0 else "green"
        triggered_str = f"[{trig_style}]{triggered}[/]"

        self.console.print(
            f"  [dim]└─[/] Mutations: [white]{total}[/]  │  "
            f"Failures triggered: {triggered_str}  │  "
            f"Fitness: [white]{fitness:.0f}[/]  │  {status}"
        )

        for f in failures[:2]:
            self.console.print(f"       [red]⚠[/] [dim]{f}[/]")

        self.console.print()

    def print_agent_obituary(
        self,
        agent_id: str,
        attack_type: str,
        fitness: float,
        mutations: int,
        triggered: int,
    ):
        """The death announcement — designed to be screenshot-worthy."""
        content = Text(justify="center")
        content.append("\n")
        content.append("  Species: ", style="bold dim")
        content.append(attack_type.upper(), style="bold yellow")
        content.append("   Agent: ", style="bold dim")
        content.append(agent_id, style="dim")
        content.append("\n\n")
        content.append("  Mutations attempted:  ", style="bold")
        content.append(str(mutations), style="white")
        content.append("\n  Failures triggered:   ", style="bold")
        content.append(str(triggered), style="white")
        content.append("\n  Final fitness:        ", style="bold")
        content.append(f"{fitness:.1f} / 100", style="bold red")
        content.append("\n\n  Cause: ", style="bold")
        content.append("FITNESS COLLAPSE", style="bold red")
        content.append(f"\n  The pipeline survived every {attack_type} attack.", style="dim italic")
        content.append("\n  This species line ends here.\n", style="dim italic")

        self.console.print(
            Panel(
                content,
                title="[bold red]💀  AGENT OBITUARY  💀[/]",
                border_style="red",
                box=box.HEAVY,
            )
        )

    # ── Kill screen (critical vulnerability found) ────────────────────────────

    def print_kill_screen(
        self,
        agent_id: str,
        attack_type: str,
        failure_description: str,
        trace_id: str,
    ):
        """Printed when a critical vulnerability is discovered. Screenshot bait."""
        hit_art = Text(justify="center")
        hit_art.append("  H I T  ", style="bold white on red")

        content = Text()
        content.append("\n")
        content.append("  CRITICAL VULNERABILITY FOUND\n", style="bold red")
        content.append("  ─────────────────────────────────────\n\n", style="dim")
        content.append("  Agent:   ", style="bold")
        content.append(f"{agent_id}\n", style="cyan")
        content.append("  Attack:  ", style="bold")
        content.append(f"{attack_type}\n", style="yellow")
        content.append("  Kill:    ", style="bold")
        content.append(f"{failure_description}\n\n", style="red")
        content.append("  Replay this exact attack:\n", style="dim")
        content.append(f"  crucible replay --trace {trace_id}", style="bold cyan")
        content.append("\n")

        self.console.print(
            Panel(
                content,
                title="[bold red on white]  ██ CRUCIBLE KILL ██  [/]",
                border_style="bright_red",
                box=box.DOUBLE_EDGE,
            )
        )

    # ── Scoring & report ──────────────────────────────────────────────────────

    def print_score_update(self, score: float, grade: str):
        bar_filled = int(score / 5)
        bar_empty = 20 - bar_filled
        color = GRADE_COLORS.get(grade, "white")
        bar = f"[{color}]{'█' * bar_filled}[/][dim]{'░' * bar_empty}[/]"
        self.console.print(f"\n  Resilience:  {bar}  [{color}]{score:.0f}/100 ({grade})[/]\n")

    def print_final_report(
        self,
        result: Dict,
        engine_status: Dict,
        darwin_report: Optional[Dict] = None,
    ):
        score = result.get("resilience_score", 0)
        grade = result.get("grade", "?")
        color = GRADE_COLORS.get(grade, "white")

        # Score bar
        bar_filled = int(score / 5)
        bar_empty = 20 - bar_filled
        score_bar = f"[{color}]{'█' * bar_filled}[/][dim]{'░' * bar_empty}[/]"

        elapsed = time.time() - self._start_time

        # Component table
        comp_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
        comp_table.add_column("Component")
        comp_table.add_column("Score", justify="right")
        comp_table.add_column("Weight", justify="right", style="dim")
        weights = {
            "survival_rate": "40%",
            "blast_containment": "25%",
            "recovery_speed": "20%",
            "coverage_breadth": "15%",
        }
        for comp, val in result.get("components", {}).items():
            c = "green" if val >= 70 else "yellow" if val >= 40 else "red"
            comp_table.add_row(
                comp.replace("_", " ").title(),
                f"[{c}]{val:.1f}[/]",
                weights.get(comp, ""),
            )

        # Agent survival table
        agent_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
        agent_table.add_column("Agent")
        agent_table.add_column("Type")
        agent_table.add_column("Mutations", justify="right")
        agent_table.add_column("Kills", justify="right")
        agent_table.add_column("Fitness", justify="right")
        agent_table.add_column("Status")
        for agent_id, stats in self._agent_stats.items():
            alive = stats["fitness"] >= 20
            status = "[green]SURVIVOR[/]" if alive else "[red]EXTINCT[/]"
            kill_style = "red" if stats["triggered"] > 0 else "dim"
            agent_table.add_row(
                f"[dim]{agent_id[:18]}[/]",
                stats["type"],
                str(stats["mutations"]),
                f"[{kill_style}]{stats['triggered']}[/]",
                f"{stats['fitness']:.0f}",
                status,
            )

        # Vuln list
        vuln_text = Text()
        for v in result.get("top_vulnerabilities", []):
            vuln_text.append(f"  ⚠  {v}\n", style="yellow")

        # Blast radius
        blast = result.get("blast_radius", [])
        blast_str = ", ".join(blast) if blast else "contained"

        # Build report
        report_content = Text()
        report_content.append(f"\n  {score_bar}  ", style="")
        report_content.append(f"{score:.0f}/100  ({grade})", style=f"bold {color}")
        report_content.append(f"     {elapsed:.1f}s\n\n", style="dim")

        self.console.print(Rule("[bold red]🔥 CRUCIBLE REPORT CARD[/]", style="red"))
        self.console.print()
        self.console.print(report_content)
        self.console.print(comp_table)
        self.console.print()

        if result.get("top_vulnerabilities"):
            self.console.print(Panel(
                vuln_text,
                title="[bold yellow]⚠  Top Vulnerabilities[/]",
                border_style="yellow",
                box=box.ROUNDED,
            ))

        self.console.print()
        self.console.print(Panel(
            agent_table,
            title="[bold]Agent Survival Log[/]",
            border_style="dim",
            box=box.ROUNDED,
        ))

        # Cemetery
        dead = [
            aid for aid, s in self._agent_stats.items() if s["fitness"] < 20
        ]
        if dead:
            self.console.print()
            cemetery = Text()
            for d in dead:
                s = self._agent_stats[d]
                cemetery.append(f"  RIP  {d}  —  {s['type']}  —  fitness: {s['fitness']:.0f}\n", style="dim")
            self.console.print(Panel(
                cemetery,
                title="[bold red]💀 Failure Cemetery[/]",
                border_style="red dim",
                box=box.ROUNDED,
            ))

        # Darwin report
        if darwin_report:
            self._print_darwin_section(darwin_report)

        # Blast radius & trace
        self.console.print()
        self.console.print(f"  [dim]Blast radius:[/]  {blast_str}")
        self.console.print(f"  [dim]Trace saved:[/]  [cyan]{result.get('replay_command', '')}[/]")
        self.console.print()
        self.console.print(Rule(style="dim"))

    def _print_darwin_section(self, darwin_report: Dict):
        self.console.print()
        darwin_table = Table(
            box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1),
            title="[bold]🧬 Evolutionary Pressure[/]"
        )
        darwin_table.add_column("Species")
        darwin_table.add_column("Runs", justify="right")
        darwin_table.add_column("Lifetime Fitness", justify="right")
        darwin_table.add_column("Generation", justify="right")
        darwin_table.add_column("Status")

        for species, data in darwin_report.items():
            fitness = data.get("fitness", 0)
            c = "green" if data.get("is_dominant") else "red" if data.get("is_extinct") else "yellow"
            status = (
                "[green]DOMINANT[/]" if data.get("is_dominant")
                else "[red]EXTINCT[/]" if data.get("is_extinct")
                else "[yellow]EVOLVING[/]"
            )
            darwin_table.add_row(
                species,
                str(data.get("runs", 0)),
                f"[{c}]{fitness:.1f}[/]",
                str(data.get("generation", 1)),
                status,
            )
        self.console.print(Panel(darwin_table, border_style="blue", box=box.ROUNDED))

    # ── Shadow promotion event ────────────────────────────────────────────────

    def print_shadow_promotion(self, attack_type: str, shadow_rate: float, prod_rate: float):
        content = Text()
        content.append(f"\n  Species:  {attack_type}\n", style="bold")
        content.append(f"  Shadow trigger rate:      {shadow_rate:.1%}\n", style="green")
        content.append(f"  Production trigger rate:  {prod_rate:.1%}\n", style="yellow")
        content.append("\n  Shadow agent staged for promotion.\n", style="bold green")
        self.console.print(Panel(
            content,
            title="[bold green]🧬 SHADOW PROMOTED[/]",
            border_style="green",
            box=box.ROUNDED,
        ))

    # ── Misc helpers ──────────────────────────────────────────────────────────

    def print_section(self, msg: str):
        self.console.print(f"\n  [bold dim]{msg}[/]")

    def print_info(self, msg: str):
        self.console.print(f"  [dim]{msg}[/]")
