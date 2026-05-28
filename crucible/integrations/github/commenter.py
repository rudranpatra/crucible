"""
GitHub PR Commenter
Posts Crucible resilience scores as PR comments on every run.
This is the Codecov play: every PR gets a score, scores become culture.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, Optional


BADGE_COLORS = {
    "bright_green": "#4c1",
    "green": "#97ca00",
    "yellow": "#dfb317",
    "orange": "#fe7d37",
    "red": "#e05d44",
}

GITHUB_API = "https://api.github.com"


class GitHubCommenter:
    """
    Posts a formatted Crucible report as a GitHub PR comment.

    Reads from env vars by default:
      GITHUB_TOKEN        — personal access token or Actions token
      GITHUB_REPOSITORY   — e.g. "org/repo"
      PR_NUMBER           — pull request number (also checks GITHUB_PR_NUMBER)
    """

    MARKER = "<!-- crucible-report -->"

    def __init__(
        self,
        token: Optional[str] = None,
        repo: Optional[str] = None,
        pr_number: Optional[int] = None,
    ):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.repo = repo or os.environ.get("GITHUB_REPOSITORY", "")
        raw_pr = pr_number or os.environ.get("PR_NUMBER") or os.environ.get("GITHUB_PR_NUMBER", "")
        try:
            self.pr_number = int(raw_pr) if raw_pr else 0
        except ValueError:
            self.pr_number = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def is_configured(self) -> bool:
        return bool(self.token and self.repo and self.pr_number)

    def post_pr_comment(self, result: Dict) -> bool:
        """
        Post (or update) a Crucible report comment on the PR.
        Returns True on success.
        """
        if not self.is_configured():
            return False

        body = self._format_comment(result)

        existing_id = self._find_existing_comment()
        if existing_id:
            return self._update_comment(existing_id, body)
        return self._create_comment(body)

    # ── Comment formatting ────────────────────────────────────────────────────

    def _format_comment(self, result: Dict) -> str:
        score = result.get("resilience_score", 0)
        grade = result.get("grade", "?")
        trace_id = result.get("trace_id", "unknown")
        replay = result.get("replay_command", "crucible replay --trace ...")
        blast = result.get("blast_radius", [])
        vulns = result.get("top_vulnerabilities", [])
        failure_count = result.get("failure_count", 0)

        if score >= 75:
            badge = "🟢"
            label = "Resilient"
        elif score >= 50:
            badge = "🟡"
            label = "Moderate risk"
        else:
            badge = "🔴"
            label = "Vulnerable"

        lines = [
            self.MARKER,
            "## 🔥 Crucible Resilience Report",
            "",
            f"{badge} **{score:.0f}/100** &nbsp;({grade}) &nbsp;— {label}",
            "",
        ]

        if vulns:
            lines.append("**Vulnerabilities detected:**")
            for v in vulns[:4]:
                lines.append(f"- ⚠️ `{v}`")
            lines.append("")

        if blast:
            lines.append(f"**Blast radius:** `{', '.join(blast)}`")
        else:
            lines.append("**Blast radius:** contained ✅")

        lines += [
            f"**Failures triggered:** {failure_count}",
            "",
            "**Replay this run:**",
            "```bash",
            replay,
            "```",
            "",
            f"<sup>Trace `{trace_id}` · "
            f"[Crucible](https://github.com/crucible-ci/crucible) "
            f"— Adversarial CI/CD Engine</sup>",
        ]
        return "\n".join(lines)

    # ── GitHub API calls ──────────────────────────────────────────────────────

    def _find_existing_comment(self) -> Optional[int]:
        url = f"{GITHUB_API}/repos/{self.repo}/issues/{self.pr_number}/comments"
        try:
            data = self._get(url)
            for comment in data:
                if self.MARKER in comment.get("body", ""):
                    return comment["id"]
        except Exception:
            pass
        return None

    def _create_comment(self, body: str) -> bool:
        url = f"{GITHUB_API}/repos/{self.repo}/issues/{self.pr_number}/comments"
        try:
            self._post(url, {"body": body})
            return True
        except Exception:
            return False

    def _update_comment(self, comment_id: int, body: str) -> bool:
        url = f"{GITHUB_API}/repos/{self.repo}/issues/comments/{comment_id}"
        try:
            self._patch(url, {"body": body})
            return True
        except Exception:
            return False

    def _get(self, url: str):
        req = urllib.request.Request(url)
        self._add_headers(req)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def _post(self, url: str, payload: Dict):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        self._add_headers(req)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def _patch(self, url: str, payload: Dict):
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data, method="PATCH")
        self._add_headers(req)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    def _add_headers(self, req: urllib.request.Request):
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")


# ── Badge generation (standalone) ─────────────────────────────────────────────

def generate_svg_badge(score: float, grade: str) -> str:
    """Generate a Shields.io-style SVG badge for README embedding."""
    if score >= 75:
        color = "#4c1"
    elif score >= 60:
        color = "#97ca00"
    elif score >= 40:
        color = "#dfb317"
    else:
        color = "#e05d44"

    label = "crucible"
    value = f"{score:.0f}/100 {grade}"
    label_w = 72
    value_w = len(value) * 7 + 10
    total_w = label_w + value_w

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{total_w}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_w}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="110">
    <text aria-hidden="true" x="{label_w * 5}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(label_w - 10) * 10}" lengthAdjust="spacing">{label}</text>
    <text x="{label_w * 5}" y="140" transform="scale(.1)" textLength="{(label_w - 10) * 10}" lengthAdjust="spacing">{label}</text>
    <text aria-hidden="true" x="{label_w * 10 + value_w * 5}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)" textLength="{(value_w - 10) * 10}" lengthAdjust="spacing">{value}</text>
    <text x="{label_w * 10 + value_w * 5}" y="140" transform="scale(.1)" textLength="{(value_w - 10) * 10}" lengthAdjust="spacing">{value}</text>
  </g>
</svg>"""
