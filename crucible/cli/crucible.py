#!/usr/bin/env python3
"""
Crucible CLI
Command-line interface for running adversarial attacks against CI/CD pipelines.

Usage (local mode — basic supply-chain check only, no signup required):
  crucible attack --target .github/workflows/ci.yml
  crucible audit .github/workflows/ci.yml
  crucible compare HEAD~1 HEAD
  crucible badge --target workflow.yml --output badge.svg
  crucible status

Usage (--engine cloud — full 6-agent engine, requires CRUCIBLE_CLOUD_URL +
CRUCIBLE_API_KEY):
  crucible attack --demo --engine cloud
  crucible attack --target workflow.yml --attacks timing,env,network --engine cloud --github-comment
  crucible validate threatmodel.json --engine cloud --demo

Not available in this release (moved to Cloud, no local or CLI-callable
Cloud equivalent yet — see CHANGELOG.md): trend, replay, patterns,
evolution, serve.
"""

import asyncio
import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile

from crucible.runner import CrucibleRunner, ALL_ATTACKS, CloudExecutionError
from crucible.integrations.github.commenter import generate_svg_badge
from crucible.scoring.basic_scorer import BasicScorer


def _engine_mode(args) -> str:
    return getattr(args, "engine", None) or os.environ.get("CRUCIBLE_ENGINE", "local")


def _cloud_only(feature: str):
    print(
        f"'{feature}' requires Crucible Cloud — pass --engine cloud "
        "(and set CRUCIBLE_CLOUD_URL / CRUCIBLE_API_KEY). Not available in local mode.",
        file=sys.stderr,
    )
    sys.exit(1)


# ── attack ────────────────────────────────────────────────────────────────────

def cmd_attack(args):
    try:
        runner = CrucibleRunner(
            verbose=not args.quiet and not args.json,
            mode=_engine_mode(args),
        )
    except NotImplementedError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    attacks = args.attacks.split(',') if args.attacks else None

    # Per-attack ingestion (--publish-cloud) is a separate, existing feature:
    # it streams each attack result to Crucible Cloud's ingest API regardless
    # of which engine ran it. It is unrelated to --engine cloud, which decides
    # WHERE the attack itself executes.
    on_attack_result = None
    publish_failures = []
    if getattr(args, 'publish_cloud', False):
        from crucible.sinks.crucible_cloud_sink import CrucibleCloudSink
        sink = CrucibleCloudSink.from_env()
        if sink is None:
            print(
                "--publish-cloud requires CRUCIBLE_CLOUD_URL and CRUCIBLE_API_KEY to be set.",
                file=sys.stderr,
            )
            sys.exit(1)

        def on_attack_result(trace_id, index, result):
            # The runner swallows exceptions from this callback so one bad
            # upload can't fail the whole attack run (see runner.py) — but
            # that means failures must be tracked here, not just logged, or
            # --publish-cloud can silently no-op on every attack. Re-raise so
            # the runner's existing log line still fires.
            try:
                sink.publish(trace_id, index, result)
            except Exception as e:
                publish_failures.append(str(e))
                raise

    try:
        result = asyncio.run(runner.run(
            target_path=args.target if not args.demo else None,
            attacks=attacks,
            tags=args.tags.split(',') if args.tags else [],
            demo_mode=args.demo or not args.target,
            seed=getattr(args, 'seed', None),
            on_attack_result=on_attack_result,
        ))
    except CloudExecutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, 'github_comment', False):
        # Posted by the CLI, not the engine: GitHubCommenter reads
        # GITHUB_TOKEN/GITHUB_REPOSITORY/PR_NUMBER from this process's env,
        # which is correct whether the run executed locally or on Cloud —
        # those vars belong to the calling CI job, not the Cloud server.
        from crucible.integrations.github.commenter import GitHubCommenter
        commenter = GitHubCommenter()
        if commenter.is_configured():
            ok = commenter.post_pr_comment(result)
            print("GitHub PR comment posted." if ok else "GitHub PR comment failed.")
        else:
            print("GitHub commenter not configured (set GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER).")

    if getattr(args, 'sarif', None):
        from crucible.integrations.github.sarif import write_sarif
        count = write_sarif(result.get('failure_points', []), args.sarif, target_path=args.target)
        print(f"SARIF: {count} finding(s) written to {args.sarif}")

    if args.json:
        out = {k: v for k, v in result.items() if k != 'shadow_summary'}
        print(json.dumps(out, indent=2))
    elif args.quiet:
        if result.get("format_supported", True):
            print(f"{result['resilience_score']:.0f}/100 ({result['grade']}) — {result['trace_id']}")
        else:
            reasons = "; ".join(result.get("unsupported_reasons", []))
            print(f"UNSUPPORTED ({result['grade']}) — {result['trace_id']} — {reasons}")
    else:
        print(f"Seed: {result['seed']}  (re-run: --seed {result['seed']})")

    if publish_failures:
        print(
            f"Error: --publish-cloud failed for {len(publish_failures)} attack result(s); "
            "results were NOT uploaded to Crucible Cloud. See the ERROR log lines above "
            f"for details (first: {publish_failures[0]}).",
            file=sys.stderr,
        )
        sys.exit(1)


# replay / patterns / evolution — removed for 0.5.0. Their backing store
# (memory.trace_memory, scoring.darwin_scorer) moved to Cloud, and Cloud has
# no callable equivalent endpoint yet. See CHANGELOG.md.


# ── audit ─────────────────────────────────────────────────────────────────────

def cmd_audit(args):
    """
    Focused supply-chain audit against a real workflow file (local mode).
    With --engine cloud, also runs dependency + env checks. Designed to be
    the first command a security engineer runs.
    """
    engine_mode = _engine_mode(args)
    audit_attacks = ['supply_chain', 'dependency', 'env'] if engine_mode == "cloud" else ['supply_chain']
    target = args.target or '.'
    from pathlib import Path
    import glob as _glob

    # Expand '.' to workflow files (GitHub Actions + GitLab CI)
    if target == '.' or Path(target).is_dir():
        patterns = [
            str(Path(target) / '.github' / 'workflows' / '*.yml'),
            str(Path(target) / '.github' / 'workflows' / '*.yaml'),
            str(Path(target) / '.gitlab-ci.yml'),
            str(Path(target) / '.gitlab-ci.yaml'),
        ]
        files = []
        for p in patterns:
            files.extend(_glob.glob(p))
        if not files:
            print("No workflow files found. Pass a path: crucible audit .github/workflows/ci.yml")
            return
    else:
        files = [target]

    result = None
    for wf_path in files:
        print(f"\nAuditing: {wf_path}")
        print("-" * 60)
        runner = CrucibleRunner(verbose=False, mode=engine_mode)
        result = asyncio.run(runner.run(
            target_path=wf_path,
            attacks=audit_attacks,
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

        replay_hint = result['replay_command'] or "not available (requires --engine cloud, replay not shipped yet)"
        print(f"\nTrace: {result['trace_id']}  (replay: {replay_hint})")

        if getattr(args, 'sarif', None):
            from crucible.integrations.github.sarif import write_sarif
            count = write_sarif(result.get('failure_points', []), args.sarif, target_path=wf_path)
            print(f"SARIF: {count} finding(s) written to {args.sarif}")

    if args.json and result:
        print(json.dumps(result, indent=2))


# ── badge ─────────────────────────────────────────────────────────────────────

def cmd_badge(args):
    if args.target and not args.demo:
        runner = CrucibleRunner(verbose=False, mode=_engine_mode(args))
        result = asyncio.run(runner.run(
            target_path=args.target,
            demo_mode=False,
        ))
    elif args.score is not None:
        result = {
            'resilience_score': args.score,
            'grade': BasicScorer().grade(args.score),
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
            runner = CrucibleRunner(verbose=False, agent_timeout=180.0, mode=_engine_mode(args))
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
    added = new_fps - old_fps
    fixed = old_fps - new_fps

    if delta < -5:
        print("\n⚠  Regression detected")
        if added:
            print("New vulnerabilities:")
            for fp in sorted(added):
                print(f"  - {fp}")
    elif delta > 5:
        print("\n✓  Improvement detected")
        if fixed:
            print("Resolved:")
            for fp in sorted(fixed):
                print(f"  + {fp}")
    else:
        print("\nNo significant change")

    if args.json:
        print(json.dumps({ref1: r1, ref2: r2, 'delta': delta, 'regression': delta < -5}, indent=2))

    if getattr(args, 'github_comment', False):
        from crucible.integrations.github.commenter import GitHubCommenter
        commenter = GitHubCommenter()
        commenter.post_compare_comment({
            'score_before': s1,
            'score_after': s2,
            'grade_before': r1['grade'],
            'grade_after': r2['grade'],
            'delta': delta,
            'added': sorted(added),
            'fixed': sorted(fixed),
            'trace_id': r2.get('trace_id', 'unknown'),
            'replay_command': r2.get('replay_command') or 'not available in local mode — requires --engine cloud',
        })


# trend / serve — removed for 0.5.0, same reason as replay/patterns/evolution.


# ── validate ──────────────────────────────────────────────────────────────────

def cmd_validate(args):
    """Import a threat model and validate it against Cloud's real attack
    engine. Cloud-only (see runner.CrucibleRunner.validate) — restored now
    that /v1/validate exists; still requires --engine cloud explicitly,
    same as every other cloud-only feature, never a silent fallback."""
    if _engine_mode(args) != "cloud":
        _cloud_only("validate")

    from crucible.threats.importer import ThreatDragonImporter

    threats = ThreatDragonImporter().import_file(
        args.threat_model, include_mitigated=args.include_mitigated,
    )
    threat_dicts = [t.to_dict() for t in threats]

    runner = CrucibleRunner(verbose=not args.json, mode="cloud")
    try:
        report = runner.validate(
            threat_dicts,
            target_path=args.target if not args.demo else None,
            demo_mode=args.demo or not args.target,
            seed=getattr(args, "seed", None),
        )
    except CloudExecutionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"\nThreat Validation: {report['target']}")
    print("-" * 60)
    print(f"Coverage: {report['coverage']:.0f}%  "
          f"(pass={report['passed']} fail={report['failed']} untested={report['untested']})")
    for t in report["threats"]:
        icon = {"pass": "✅", "fail": "❌", "untested": "⚠️"}.get(t["status"], "?")
        print(f"  {icon} [{t['status'].upper()}] {t['title']} ({t['plan_rationale'] or 'no plan'})")
    print(f"\nTrace: {report['trace_id']}  (replay: {report['replay_command'] or 'not available'})")

# ── status ────────────────────────────────────────────────────────────────────

def cmd_status(args):
    print("\nCrucible Status")
    print("-" * 40)
    print(f"Engine mode:       {_engine_mode(args)}")
    print(f"Attack types:      {', '.join(ALL_ATTACKS)} (local); full set requires --engine cloud")
    print("Trace history, patterns, and evolution require --engine cloud.")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog='crucible',
        description='Crucible — Adversarial Intelligence Engine for CI/CD Pipelines',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples (local mode — basic supply-chain check, no signup):
  crucible audit .                       # supply-chain audit (start here)
  crucible audit .github/workflows/ci.yml
  crucible attack --target ci.yml
  crucible compare HEAD~1 HEAD           # did this change make CI more or less resilient?
  crucible badge --score 73 -o badge.svg # generate README badge

examples (--engine cloud — full 6-agent engine, requires
CRUCIBLE_CLOUD_URL + CRUCIBLE_API_KEY):
  crucible attack --demo --engine cloud
  crucible compare HEAD~1 HEAD --engine cloud
  crucible validate threatmodel.json --engine cloud --demo

Not in this release (see CHANGELOG.md): trend, replay, patterns,
evolution, serve, --rich, --shadow.
        """,
    )
    subparsers = parser.add_subparsers(dest='command')

    # audit
    aup = subparsers.add_parser('audit', help='Supply-chain audit (adds dependency + env with --engine cloud)')
    aup.add_argument('target', nargs='?', default='.', help='Workflow file or repo root (default: .)')
    aup.add_argument('--sarif', metavar='FILE', help='Write findings as SARIF (for GitHub Security tab)')
    aup.add_argument('--json', '-j', action='store_true')
    aup.add_argument('--engine', choices=['local', 'cloud'], help='Execution engine (default: local, or $CRUCIBLE_ENGINE)')

    # attack
    ap = subparsers.add_parser('attack', help='Run adversarial attacks against a pipeline')
    ap.add_argument('--target', '-t', help='Path to workflow file (.yml, .gitlab-ci.yml, .spec.ts)')
    ap.add_argument('--demo', action='store_true', help='Run with synthetic demo target')
    ap.add_argument('--attacks', '-a', help=f'Comma-separated: {",".join(ALL_ATTACKS)}')
    ap.add_argument('--tags', help='Comma-separated tags for this run')
    # --rich / --shadow removed for 0.5.0: both raised NotImplementedError in
    # every mode (rich dashboard assumed live per-agent progress from the old
    # in-process engine; shadow mode's backing code moved to Cloud with no
    # wired endpoint). See CHANGELOG.md.
    ap.add_argument('--github-comment', action='store_true', dest='github_comment',
                    help='Post resilience score as GitHub PR comment')
    ap.add_argument('--sarif', metavar='FILE', help='Write findings as SARIF (for GitHub Security tab)')
    ap.add_argument('--seed', type=int, help='Fixed random seed for deterministic replay')
    ap.add_argument('--quiet', '-q', action='store_true', help='Suppress output (just print score)')
    ap.add_argument('--json', '-j', action='store_true', help='Output full result as JSON')
    ap.add_argument('--engine', choices=['local', 'cloud'], help='Execution engine (default: local, or $CRUCIBLE_ENGINE)')
    ap.add_argument('--publish-cloud', '--cloud', action='store_true', dest='publish_cloud',
                    help='Stream each attack result to Crucible Cloud for historical tracking, '
                         'regardless of --engine (requires CRUCIBLE_CLOUD_URL and CRUCIBLE_API_KEY). '
                         '"--cloud" is a deprecated alias — it decides WHETHER results are '
                         'published, not WHERE the attack runs; use --engine cloud for that.')

    # compare
    cp = subparsers.add_parser('compare', help='Compare resilience between two git refs')
    cp.add_argument('ref1', help='Base git ref (e.g. HEAD~1, main)')
    cp.add_argument('ref2', help='Target git ref (e.g. HEAD, feature-branch)')
    cp.add_argument('--target', '-t', help='Workflow file path (default: .github/workflows/ci.yml)')
    cp.add_argument('--attacks', '-a', help=f'Comma-separated: {",".join(ALL_ATTACKS)}')
    cp.add_argument('--seed', type=int, help='Fixed seed for reproducible comparison')
    cp.add_argument('--github-comment', action='store_true', dest='github_comment',
                     help='Post regression result as a PR comment (requires GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER)')
    cp.add_argument('--json', '-j', action='store_true')
    cp.add_argument('--engine', choices=['local', 'cloud'], help='Execution engine (default: local, or $CRUCIBLE_ENGINE)')

    # trend / replay / patterns / evolution — removed for 0.5.0 (see CHANGELOG.md)

    # badge
    bp = subparsers.add_parser('badge', help='Generate SVG resilience badge for README')
    bp.add_argument('--target', '-t', help='Workflow file to attack first')
    bp.add_argument('--demo', action='store_true', help='Use demo target')
    bp.add_argument('--score', type=float, help='Use a fixed score (skip running)')
    bp.add_argument('--output', '-o', help='Output file (default: stdout)')
    bp.add_argument('--engine', choices=['local', 'cloud'], help='Execution engine (default: local, or $CRUCIBLE_ENGINE)')

    # serve — removed for 0.5.0 (see CHANGELOG.md)

    # status
    subparsers.add_parser('status', help='Show Crucible status and stored trace summary')

    # validate — Cloud-only (requires --engine cloud); restored now that
    # /v1/validate exists (see CODEX_OSS_CLOUD_SPLIT.md open questions).
    vp = subparsers.add_parser('validate', help='Validate a threat model against Cloud\'s real attack engine (requires --engine cloud)')
    vp.add_argument('threat_model', help='Path to a Threat Dragon JSON export')
    vp.add_argument('--include-mitigated', action='store_true', dest='include_mitigated',
                     help='Also validate threats marked Mitigated/NotApplicable (default: skip them)')
    vp.add_argument('--target', '-t', help='Path to workflow file (.yml, .gitlab-ci.yml, .spec.ts)')
    vp.add_argument('--demo', action='store_true', help='Run with synthetic demo target')
    vp.add_argument('--seed', type=int, help='Fixed random seed for deterministic replay')
    vp.add_argument('--json', '-j', action='store_true', help='Output full report as JSON')
    vp.add_argument('--engine', choices=['local', 'cloud'], help='Execution engine (validate requires cloud)')

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
        'badge': cmd_badge,
        'status': cmd_status,
        'validate': cmd_validate,
    }
    dispatch[args.command](args)


if __name__ == '__main__':
    main()
