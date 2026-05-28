#!/usr/bin/env python3
"""
Generates a static SVG screenshot of a Crucible demo run.
GitHub renders SVGs inline — no GIF tooling required.

Usage:
    cd crucible/
    python3 ../scripts/generate_demo_svg.py
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'crucible'))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.table import Table
from rich import box


def build_demo_svg(output_path: str):
    console = Console(record=True, width=100, highlight=False)

    # Banner
    console.print()
    console.print(Text("  🔥 CRUCIBLE — Adversarial CI/CD Engine", style="bold red"))
    console.print(Text("  Target: demo_ci_pipeline  |  Trace: trc_c003093279", style="dim"))
    console.print()

    # Agent 1: timing → extinct
    console.print("  [bold yellow]⚡ DEPLOYING[/]  [cyan]timing[/] agent  [dim]agent_timing_cef5f0e0[/]")
    console.print("     [dim italic]Injects timing delays and race conditions to expose timeout assumptions[/]")
    console.print("  [dim]└─[/] Mutations: [white]5[/]  │  Failures triggered: [green]0[/]  │  Fitness: [white]2[/]  │  [bold red]DEAD[/]")
    console.print()

    # Obituary
    obit = Text()
    obit.append("\n  Species: ", style="bold dim")
    obit.append("TIMING", style="bold yellow")
    obit.append("   Agent: ", style="bold dim")
    obit.append("agent_timing_cef5f0e0", style="dim")
    obit.append("\n\n  Mutations attempted:  ", style="bold")
    obit.append("5", style="white")
    obit.append("\n  Failures triggered:   ", style="bold")
    obit.append("0", style="white")
    obit.append("\n  Final fitness:        ", style="bold")
    obit.append("2.5 / 100", style="bold red")
    obit.append("\n\n  Cause: ", style="bold")
    obit.append("FITNESS COLLAPSE", style="bold red")
    obit.append("\n  The pipeline survived every timing attack.", style="dim italic")
    obit.append("\n  This species line ends here.\n", style="dim italic")
    console.print(Panel(obit, title="[bold red]💀  AGENT OBITUARY  💀[/]", border_style="red", box=box.HEAVY))
    console.print()

    # Agent 2: env
    console.print("  [bold yellow]⚡ DEPLOYING[/]  [cyan]env[/] agent  [dim]agent_env_a5629a5c[/]")
    console.print("     [dim italic]Corrupts environment variables to expose missing validation[/]")
    console.print()

    # Kill screen
    kill = Text()
    kill.append("\n  CRITICAL VULNERABILITY FOUND\n", style="bold red")
    kill.append("  ─────────────────────────────────────\n\n", style="dim")
    kill.append("  Agent:   ", style="bold")
    kill.append("agent_env_a5629a5c\n", style="cyan")
    kill.append("  Attack:  ", style="bold")
    kill.append("env\n", style="yellow")
    kill.append("  Kill:    ", style="bold")
    kill.append("DATABASE_URL → null_inject → cascade failure\n\n", style="red")
    kill.append("  crucible replay --trace trc_c003093279", style="bold cyan")
    kill.append("\n")
    console.print(Panel(kill, title="[bold red on white]  ██ CRUCIBLE KILL ██  [/]", border_style="bright_red", box=box.DOUBLE_EDGE))
    console.print("  [dim]└─[/] Mutations: [white]4[/]  │  Failures triggered: [red bold]2[/]  │  Fitness: [white]52[/]  │  [bold green]ALIVE[/]")
    console.print()

    # Agent 3: network
    console.print("  [bold yellow]⚡ DEPLOYING[/]  [cyan]network[/] agent  [dim]agent_network_5c6b0cfa[/]")
    console.print("     [dim italic]Simulates network chaos to expose missing retry and timeout logic[/]")
    console.print("  [dim]└─[/] Mutations: [white]4[/]  │  Failures triggered: [red bold]1[/]  │  Fitness: [white]27[/]  │  [bold green]ALIVE[/]")
    console.print("       [red]⚠[/] [dim]Network chaos: connection_reset on git_checkout — no retry logic detected[/]")
    console.print()

    # Agent 4: dependency
    console.print("  [bold yellow]⚡ DEPLOYING[/]  [cyan]dependency[/] agent  [dim]agent_dependency_99ad74e9[/]")
    console.print("     [dim italic]Injects dependency drift to expose version pinning and lockfile gaps[/]")
    console.print("  [dim]└─[/] Mutations: [white]3[/]  │  Failures triggered: [red bold]3[/]  │  Fitness: [white]100[/]  │  [bold green]ALIVE[/]")
    console.print("       [red]⚠[/] [dim]Dependency failure: numpy — yanked_version (unpinned package vulnerable)[/]")
    console.print()

    # Score bar
    score = 75
    bar_filled = int(score / 5)
    bar_empty = 20 - bar_filled
    score_text = Text()
    score_text.append(f"\n  ")
    score_text.append("█" * bar_filled, style="green")
    score_text.append("░" * bar_empty, style="dim")
    score_text.append(f"  {score}/100 (B)", style="bold green")
    score_text.append("\n")
    console.print(score_text)

    # Report rule
    console.print(Rule("[bold red]🔥 CRUCIBLE REPORT CARD[/]", style="red"))
    console.print()

    # Component table
    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
    table.add_column("Component")
    table.add_column("Score", justify="right")
    table.add_column("Weight", justify="right", style="dim")
    table.add_row("Survival Rate",    "[green]76.5[/]",  "40%")
    table.add_row("Blast Containment","[green]81.2[/]",  "25%")
    table.add_row("Recovery Speed",   "[yellow]50.0[/]", "20%")
    table.add_row("Coverage Breadth", "[green]100.0[/]", "15%")
    console.print(table)

    # Vulns
    vuln_text = Text()
    vuln_text.append("  ⚠  DATABASE_URL, API_KEY lack input validation\n", style="yellow")
    vuln_text.append("  ⚠  git_checkout has no retry/timeout logic\n", style="yellow")
    vuln_text.append("  ⚠  1 unpinned package vulnerable to yanked releases\n", style="yellow")
    console.print(Panel(vuln_text, title="[bold yellow]⚠  Top Vulnerabilities[/]", border_style="yellow", box=box.ROUNDED))

    # Blast radius
    console.print()
    console.print("  [dim]Blast radius:[/]  install, build, git_checkout, step_using_api_key")
    console.print("  [dim]Trace saved:[/]  [cyan]crucible replay --trace traces/trc_c003093279.crucible[/]")
    console.print()
    console.print(Rule(style="dim"))

    # Save SVG
    console.save_svg(output_path, title="Crucible — demo_ci_pipeline")
    print(f"SVG saved: {output_path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), '..', 'demo.svg'
    )
    build_demo_svg(os.path.abspath(out))
