#!/usr/bin/env python3
"""
Crucible CLI
Command-line interface for running adversarial attacks against CI/CD pipelines.

Usage:
  crucible attack --target .github/workflows/ci.yml
  crucible attack --demo --rich
  crucible attack --target workflow.yml --attacks timing,env,network --github-comment
  crucible attack --demo --shadow
  crucible compare HEAD~1 HEAD
  crucible trend
  crucible replay --trace trc_abc123
  crucible patterns
  crucible evolution
  crucible badge --target workflow.yml --output badge.svg
  crucible serve
  crucible status
"""

import asyncio
import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import CrucibleRunner, ALL_ATTACKS
from integrations.github.commenter import generate_svg_badge


# ── attack ────────────────────────────────────────────────────────────────────

def cmd_attack(args):
    runner = CrucibleRunner(
        verbose=not args.quiet,
        use_dashboard=getattr(args, 'rich', False),
        use_shadow=getattr(args, 'shadow', False),
    )
    attacks = args.attacks.split(',') if args.attacks else None

    result = asyncio.run(runner.run(
        target_path=args.target if not args.demo else None,
        attacks=attacks,
        tags=args.tags.split(',') if args.tags else [],
        demo_mode=args.demo or not args.target,
        github_comment=getattr(args, 'github_comment', False),
        seed=getattr(args, 'seed', None),
    ))

    if args.json:
        out = {k: v for k, v in result.items() if k != 'shadow_summary'}
        print(json.dumps(out, indent=2))
    elif args.quiet:
        print(f"{result['resilience_score']:.0f}/100 ({result['grade']}) — {result['trace_id']}")
    elif not getattr(args, 'rich', False):
        print(f"Seed: {result['seed']}  (re-run: --seed {result['seed']})")


# ── replay ────────────────────────────────────────────────────────────────────

def cmd_replay(args):
    runner = CrucibleRunner(verbose=False)
    result = runner.replay(args.trace)
    if 'error' in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print(f"\nTrace:      {result['trace_id']}")
    print(f"Target:     {result['target']}")
    print(f"Score:      {result['resilience_score']}/100")
    print(f"Failures:   {result['failure_count']}")
    print(f"Blast:      {', '.join(result['blast_radius']) if result['blast_radius'] else 'contained'}")
    if result.get('seed') is not None:
        print(f"Seed:       {result['seed']}")
    if result.get('failure_points'):
        print("\nFailure points:")
        for fp in result['failure_points'][:5]:
            print(f"  ⚠  {fp}")
    print(f"\n{result['replay_command']}")
    if result.get('seed') is not None:
        attacks_str = ','.join(result.get('attack_types', []))
        hint = f"crucible attack --seed {result['seed']}"
        if attacks_str:
            hint += f" --attacks {attacks_str}"
        print(f"Reproduce:  {hint}")


# ── patterns ──────────────────────────────────────────────────────────────────

def cmd_patterns(args):
    runner = CrucibleRunner(verbose=False)
    patterns = runner.patterns()

    if args.json:
        print(json.dumps(patterns, indent=2))
        return

    if not patterns:
        print("No traces found. Run 'crucible attack' first.")
        return

    print("\nFailure Pattern Analysis")
    print(f"Total traces:     {patterns['total_traces']}")
    print(f"Avg score:        {patterns['average_resilience_score']}/100")
    print(f"Trend:            {patterns['score_trend']}")
    print()

    print("Attack failure rates:")
    for attack, rate in patterns.get('attack_failure_rates', {}).items():
        bar = "█" * int(rate * 20)
        print(f"  {attack:<12} {bar:<20} {rate:.1%}")

    print()
    print("Most vulnerable steps:")
    for item in patterns.get('most_vulnerable_steps', []):
        print(f"  {item['step']}: failed {item['failure_count']} time(s)")


# ── evolution ─────────────────────────────────────────────────────────────────

def cmd_evolution(args):
    runner = CrucibleRunner(verbose=False)
    evo = runner.evolution()

    if args.json:
        print(json.dumps(evo, indent=2))
        return

    species = evo.get('species', {})
    if not species:
        print("No evolutionary data yet. Run multiple attacks to build species history.")
        return

    print("\n🧬 Evolutionary Pressure Report")
    print("-" * 50)

    dominant = evo.get('dominant', [])
    extinct = evo.get('extinct', [])

    if dominant:
        print(f"\nDominant species: {', '.join(dominant)}")
    if extinct:
        print(f"Extinct species:  {', '.join(extinct)}")

    print("\nSpecies fitness:")
    for name, data in species.items():
        status = "DOMINANT" if data['is_dominant'] else "EXTINCT" if data['is_extinct'] else "EVOLVING"
        print(
            f"  {name:<12}  fitness: {data['fitness']:.1f}  "
            f"runs: {data['runs']}  gen: {data['generation']}  [{status}]"
        )

    promotions = evo.get('promotions', [])
    if promotions:
        print(f"\nEvolutionary events: {len(promotions)} promotions recorded")
        for p in promotions[-3:]:
            print(f"  ↑ {p['agent_type']} promoted — shadow {p['shadow_rate']:.1%} vs prod {p['production_rate']:.1%}")


# ── audit ─────────────────────────────────────────────────────────────────────

def cmd_audit(args):
    """
    Focused supply-chain + dependency audit against a real workflow file.
    Designed to be the first command a security engineer runs.
    """
    target = args.target or '.'
    from pathlib import Path
    import glob as _glob

    # Expand '.' to workflow files
    if target == '.' or Path(target).is_dir():
        patterns = [
            str(Path(target) / '.github' / 'workflows' / '*.yml'),
            str(Path(target) / '.github' / 'workflows' / '*.yaml'),
        ]
        files = []
        for p in patterns:
            files.extend(_glob.glob(p))
        if not files:
            print("No workflow files found. Pass a path: crucible audit .github/workflows/ci.yml")
            return
    else:
        files = [target]

    for wf_path in files:
        print(f"\nAuditing: {wf_path}")
        print("-" * 60)
        runner = CrucibleRunner(verbose=False)
        result = asyncio.run(runner.run(
            target_path=wf_path,
            attacks=['supply_chain', 'dependency', 'env'],
        ))

        score = result['resilience_score']
        grade = result['grade']
        grade_color = {'A': '✅', 'B': '✅', 'C': '⚠️', 'D': '❌', 'F': '❌'}.get(grade, '❌')
        print(f"Resilience: {score:.0f}/100  [{grade}] {grade_color}")

        vulns = result.get('top_vulnerabilities', [])
        if vulns:
            print("\nFindings:")
            for v in vulns:
                prefix = '[CRITICAL]' if 'CRITICAL' in v else '[HIGH]' if 'Supply chain' in v or 'Dependency' in v else '[MEDIUM]'
                print(f"  {prefix} {v}")
        else:
            print("  No findings.")

        print(f"\nTrace: {result['trace_id']}  (replay: crucible replay --trace {result['trace_id']})")

    if args.json:
        print(json.dumps(result, indent=2))


# ── badge ─────────────────────────────────────────────────────────────────────

def cmd_badge(args):
    if args.target and not args.demo:
        runner = CrucibleRunner(verbose=False)
        result = asyncio.run(runner.run(
            target_path=args.target,
            demo_mode=False,
        ))
    elif args.score is not None:
        result = {
            'resilience_score': args.score,
            'grade': _score_to_grade(args.score),
        }
    else:
        print("Provide --target <workflow.yml> or --score <0-100>", file=sys.stderr)
        sys.exit(1)

    score = result['resilience_score']
    grade = result['grade']
    svg = generate_svg_badge(score, grade)

    output = getattr(args, 'output', None)
    if output:
        with open(output, 'w') as f:
            f.write(svg)
        print(f"Badge saved to {output}")
        print(f"Add to README: ![Crucible Resilience]({output})")
    else:
        print(svg)


# ── compare ───────────────────────────────────────────────────────────────────

def cmd_compare(args):
    """
    Compare resilience between two git refs.
    Uses git show to extract the workflow at each ref — no working-tree mutation.
    """
    ref1, ref2 = args.ref1, args.ref2
    wf = args.target or '.github/workflows/ci.yml'
    attacks = args.attacks.split(',') if args.attacks else None

    results = {}
    for ref in (ref1, ref2):
        proc = subprocess.run(['git', 'show', f'{ref}:{wf}'], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"Error: cannot read {ref}:{wf}\n{proc.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        with tempfile.NamedTemporaryFile(suffix='.yml', mode='w', delete=False) as f:
            f.write(proc.stdout)
            tmp = f.name
        try:
            runner = CrucibleRunner(verbose=False, agent_timeout=180.0)
            results[ref] = asyncio.run(runner.run(
                target_path=tmp, attacks=attacks, seed=getattr(args, 'seed', None)
            ))
        finally:
            os.unlink(tmp)

    r1, r2 = results[ref1], results[ref2]
    s1, s2 = r1['resilience_score'], r2['resilience_score']
    delta = s2 - s1
    direction = "↑" if delta >= 0 else "↓"

    print(f"\nResilience: {s1:.0f} → {s2:.0f}  ({direction}{abs(delta):.0f})")
    print(f"Grade:      {r1['grade']} → {r2['grade']}")

    old_fps = set(r1.get('failure_points', []))
    new_fps = set(r2.get('failure_points', []))

    if delta < -5:
        print("\n⚠  Regression detected")
        added = new_fps - old_fps
        if added:
            print("New vulnerabilities:")
            for fp in sorted(added):
                print(f"  - {fp}")
    elif delta > 5:
        print("\n✓  Improvement detected")
        fixed = old_fps - new_fps
        if fixed:
            print("Resolved:")
            for fp in sorted(fixed):
                print(f"  + {fp}")
    else:
        print("\nNo significant change")

    if args.json:
        print(json.dumps({ref1: r1, ref2: r2, 'delta': delta, 'regression': delta < -5}, indent=2))


# ── trend ──────────────────────────────────────────────────────────────────────

def cmd_trend(args):
    """Show resilience score history from stored traces."""
    import time
    from memory.trace_memory import TraceMemory

    tm = TraceMemory()
    patterns = tm.get_failure_patterns()
    history = patterns.get('score_history', [])

    if not history:
        print("No traces found. Run 'crucible attack' first.")
        return

    if args.json:
        print(json.dumps(history, indent=2))
        return

    print(f"\nResilience Trend  ({len(history)} runs)")
    print("-" * 50)
    for entry in history:
        score = entry['score']
        bar = "█" * int(score / 5)
        ts = time.strftime('%Y-%m-%d', time.localtime(entry['created_at']))
        print(f"  {ts}  {score:5.0f}/100 ({_score_to_grade(score)})  {bar}")

    if len(history) > 1:
        delta = history[-1]['score'] - history[0]['score']
        direction = "↑" if delta >= 0 else "↓"
        print(f"\nOverall: {direction}{abs(delta):.0f} pts  ({patterns['score_trend']})")


# ── serve ─────────────────────────────────────────────────────────────────────

def cmd_serve(args):
    try:
        from dashboard.server import serve
        serve(
            traces_dir=getattr(args, 'traces_dir', 'traces'),
            host=getattr(args, 'host', '127.0.0.1'),
            port=getattr(args, 'port', 7331),
        )
    except ImportError:
        print("Error: fastapi and uvicorn are required for the web dashboard.")
        print("Install with: pip install fastapi uvicorn")
        sys.exit(1)


# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(args):
    runner = CrucibleRunner(verbose=False)
    patterns = runner.patterns()
    evo = runner.evolution()

    print("\nCrucible Status")
    print("-" * 40)
    print(f"Traces stored:     {patterns.get('total_traces', 0)}")
    print(f"Avg resilience:    {patterns.get('average_resilience_score', 'N/A')}/100")
    print(f"Score trend:       {patterns.get('score_trend', 'N/A')}")
    print(f"Attack types:      {', '.join(ALL_ATTACKS)}")
    print("Traces dir:        ./traces/")
    dominant = evo.get('dominant', [])
    extinct = evo.get('extinct', [])
    if dominant:
        print(f"Dominant species:  {', '.join(dominant)}")
    if extinct:
        print(f"Extinct species:   {', '.join(extinct)}")


# ── helpers ───────────────────────────────────────────────────────────────────

def _score_to_grade(score: float) -> str:
    if score >= 90:
        return 'A'
    if score >= 75:
        return 'B'
    if score >= 60:
        return 'C'
    if score >= 40:
        return 'D'
    return 'F'


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='crucible',
        description='Crucible — Adversarial Intelligence Engine for CI/CD Pipelines',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  crucible audit .                       # supply-chain + dependency audit (start here)
  crucible audit .github/workflows/ci.yml
  crucible attack --target ci.yml        # all 6 agents against a real workflow
  crucible attack --demo --rich          # rich terminal UI demo
  crucible attack --demo --shadow        # evolutionary shadow agents
  crucible compare HEAD~1 HEAD           # did this change make CI more or less resilient?
  crucible trend                         # score history across all runs
  crucible badge --score 73 -o badge.svg # generate README badge
  crucible replay --trace trc_abc123     # replay any stored trace
  crucible evolution                     # show species fitness over time
  crucible serve                         # start local web dashboard
        """,
    )
    subparsers = parser.add_subparsers(dest='command')

    # audit
    aup = subparsers.add_parser('audit', help='Supply-chain + dependency audit against a workflow (recommended first run)')
    aup.add_argument('target', nargs='?', default='.', help='Workflow file or repo root (default: .)')
    aup.add_argument('--json', '-j', action='store_true')

    # attack
    ap = subparsers.add_parser('attack', help='Run adversarial attacks against a pipeline')
    ap.add_argument('--target', '-t', help='Path to GitHub Actions workflow file')
    ap.add_argument('--demo', action='store_true', help='Run with synthetic demo target')
    ap.add_argument('--attacks', '-a', help=f'Comma-separated: {",".join(ALL_ATTACKS)}')
    ap.add_argument('--tags', help='Comma-separated tags for this run')
    ap.add_argument('--rich', action='store_true', help='Rich terminal dashboard (screenshot-worthy)')
    ap.add_argument('--shadow', action='store_true', help='Enable shadow agent evolutionary tracking')
    ap.add_argument('--github-comment', action='store_true', dest='github_comment',
                    help='Post resilience score as GitHub PR comment')
    ap.add_argument('--seed', type=int, help='Fixed random seed for deterministic replay')
    ap.add_argument('--quiet', '-q', action='store_true', help='Suppress output (just print score)')
    ap.add_argument('--json', '-j', action='store_true', help='Output full result as JSON')

    # compare
    cp = subparsers.add_parser('compare', help='Compare resilience between two git refs')
    cp.add_argument('ref1', help='Base git ref (e.g. HEAD~1, main)')
    cp.add_argument('ref2', help='Target git ref (e.g. HEAD, feature-branch)')
    cp.add_argument('--target', '-t', help='Workflow file path (default: .github/workflows/ci.yml)')
    cp.add_argument('--attacks', '-a', help=f'Comma-separated: {",".join(ALL_ATTACKS)}')
    cp.add_argument('--seed', type=int, help='Fixed seed for reproducible comparison')
    cp.add_argument('--json', '-j', action='store_true')

    # trend
    tp = subparsers.add_parser('trend', help='Show resilience score history from stored traces')
    tp.add_argument('--json', '-j', action='store_true')

    # replay
    rp = subparsers.add_parser('replay', help='Replay a stored attack trace')
    rp.add_argument('--trace', required=True, help='Trace ID or path to .crucible file')
    rp.add_argument('--json', '-j', action='store_true')

    # patterns
    pp = subparsers.add_parser('patterns', help='Show failure patterns across all traces')
    pp.add_argument('--json', '-j', action='store_true')

    # evolution
    ep = subparsers.add_parser('evolution', help='Show species evolutionary pressure over time')
    ep.add_argument('--json', '-j', action='store_true')

    # badge
    bp = subparsers.add_parser('badge', help='Generate SVG resilience badge for README')
    bp.add_argument('--target', '-t', help='Workflow file to attack first')
    bp.add_argument('--demo', action='store_true', help='Use demo target')
    bp.add_argument('--score', type=float, help='Use a fixed score (skip running)')
    bp.add_argument('--output', '-o', help='Output file (default: stdout)')

    # serve
    sp = subparsers.add_parser('serve', help='Start local web dashboard (requires fastapi)')
    sp.add_argument('--host', default='127.0.0.1')
    sp.add_argument('--port', type=int, default=7331)
    sp.add_argument('--traces-dir', default='traces', dest='traces_dir')

    # status
    subparsers.add_parser('status', help='Show Crucible status and stored trace summary')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    log_level = logging.WARNING if getattr(args, "quiet", False) else logging.INFO
    logging.basicConfig(format="%(levelname)s %(name)s %(message)s", level=log_level)

    dispatch = {
        'audit': cmd_audit,
        'attack': cmd_attack,
        'compare': cmd_compare,
        'trend': cmd_trend,
        'replay': cmd_replay,
        'patterns': cmd_patterns,
        'evolution': cmd_evolution,
        'badge': cmd_badge,
        'serve': cmd_serve,
        'status': cmd_status,
    }
    dispatch[args.command](args)


if __name__ == '__main__':
    main()
