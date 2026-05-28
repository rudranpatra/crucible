"""Tests for GitHub commenter, badge generator, and Playwright parser."""

import os
import sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrations.github.commenter import GitHubCommenter, generate_svg_badge
from integrations.playwright.parser import PlaywrightParser, create_demo_playwright_target


# ── GitHubCommenter ───────────────────────────────────────────────────────────

class TestGitHubCommenter:
    def test_instantiation_no_env(self):
        c = GitHubCommenter(token="", repo="", pr_number=0)
        assert not c.is_configured()

    def test_is_configured_with_all_fields(self):
        c = GitHubCommenter(token="tok", repo="org/repo", pr_number=42)
        assert c.is_configured()

    def test_is_not_configured_missing_token(self):
        c = GitHubCommenter(token="", repo="org/repo", pr_number=42)
        assert not c.is_configured()

    def test_is_not_configured_missing_repo(self):
        c = GitHubCommenter(token="tok", repo="", pr_number=42)
        assert not c.is_configured()

    def test_is_not_configured_missing_pr(self):
        c = GitHubCommenter(token="tok", repo="org/repo", pr_number=0)
        assert not c.is_configured()

    def test_post_pr_comment_not_configured_returns_false(self):
        c = GitHubCommenter(token="", repo="", pr_number=0)
        result = c.post_pr_comment({"resilience_score": 75.0, "grade": "B"})
        assert result is False

    def test_format_comment_contains_score(self):
        c = GitHubCommenter(token="tok", repo="org/repo", pr_number=1)
        comment = c._format_comment({
            "resilience_score": 73.0,
            "grade": "C",
            "trace_id": "trc_abc",
            "replay_command": "crucible replay --trace trc_abc",
            "blast_radius": ["deploy_staging"],
            "top_vulnerabilities": ["timing vuln"],
            "failure_count": 3,
        })
        assert "73" in comment
        assert "trc_abc" in comment
        assert "Crucible" in comment

    def test_format_comment_green_when_high_score(self):
        c = GitHubCommenter(token="tok", repo="org/repo", pr_number=1)
        comment = c._format_comment({
            "resilience_score": 90.0,
            "grade": "A",
            "trace_id": "trc_123",
            "replay_command": "...",
            "blast_radius": [],
            "top_vulnerabilities": [],
            "failure_count": 0,
        })
        assert "🟢" in comment

    def test_format_comment_red_when_low_score(self):
        c = GitHubCommenter(token="tok", repo="org/repo", pr_number=1)
        comment = c._format_comment({
            "resilience_score": 30.0,
            "grade": "F",
            "trace_id": "trc_abc",
            "replay_command": "...",
            "blast_radius": ["step_a", "step_b"],
            "top_vulnerabilities": ["critical vuln"],
            "failure_count": 5,
        })
        assert "🔴" in comment

    def test_marker_in_comment(self):
        c = GitHubCommenter(token="tok", repo="org/repo", pr_number=1)
        comment = c._format_comment({
            "resilience_score": 60.0, "grade": "C",
            "trace_id": "t", "replay_command": "...",
            "blast_radius": [], "top_vulnerabilities": [], "failure_count": 0,
        })
        assert GitHubCommenter.MARKER in comment

    def test_env_vars_read(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "env_token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
        monkeypatch.setenv("PR_NUMBER", "99")
        c = GitHubCommenter()
        assert c.token == "env_token"
        assert c.repo == "org/repo"
        assert c.pr_number == 99


# ── Badge generator ───────────────────────────────────────────────────────────

class TestBadgeGenerator:
    def test_returns_svg_string(self):
        svg = generate_svg_badge(73.0, "C")
        assert isinstance(svg, str)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_contains_score(self):
        svg = generate_svg_badge(85.0, "B")
        assert "85" in svg

    def test_contains_grade(self):
        svg = generate_svg_badge(92.0, "A")
        assert "A" in svg

    def test_contains_label(self):
        svg = generate_svg_badge(50.0, "D")
        assert "crucible" in svg

    def test_green_for_high_score(self):
        svg = generate_svg_badge(80.0, "B")
        assert "#4c1" in svg or "#97ca00" in svg

    def test_red_for_low_score(self):
        svg = generate_svg_badge(25.0, "F")
        assert "#e05d44" in svg

    def test_different_scores_produce_different_svgs(self):
        svg1 = generate_svg_badge(90.0, "A")
        svg2 = generate_svg_badge(30.0, "F")
        assert svg1 != svg2


# ── PlaywrightParser ──────────────────────────────────────────────────────────

class TestPlaywrightParser:
    @pytest.fixture
    def parser(self):
        return PlaywrightParser()

    @pytest.fixture
    def sample_ts(self):
        return """
import { test, expect } from '@playwright/test';

describe('Checkout Flow', () => {
  test('user can add to cart', async ({ page }) => {
    await page.goto('https://example.com/shop');
    await page.click('[data-testid=add-to-cart]');
    await page.waitForSelector('.cart-count');
    expect(page.locator('.cart-count')).toBeTruthy();
  });

  test('checkout validates email', async ({ page }) => {
    await page.goto('https://example.com/checkout');
    await page.fill('#email', 'invalid');
    await page.waitForNavigation();
    const response = await page.waitForResponse('https://api.example.com/validate');
    expect(page.locator('.error')).toBeVisible();
  });
});
"""

    @pytest.fixture
    def sample_py(self):
        return """
import os
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get('BASE_URL', 'http://localhost:3000')
API_KEY = os.environ.get('API_KEY', '')

def test_login(page: Page):
    page.goto(f'{BASE_URL}/login')
    page.fill('#username', 'user@example.com')
    page.click('#submit')
    page.wait_for_selector('.dashboard')
    expect(page.locator('.dashboard')).to_be_visible()
"""

    def test_parse_js_returns_target(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "checkout.spec.ts")
        assert 'name' in target
        assert 'steps' in target
        assert 'network_calls' in target
        assert target['source_type'] == 'playwright'

    def test_extracts_navigations(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "test.spec.ts")
        assert len(target['navigations']) >= 1
        assert any("example.com" in n for n in target['navigations'])

    def test_extracts_test_names(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "test.spec.ts")
        assert target['test_count'] >= 2

    def test_extracts_network_calls(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "test.spec.ts")
        assert len(target['network_calls']) > 0

    def test_has_page_waits(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "test.spec.ts")
        assert target['has_page_waits'] is True

    def test_has_wait_navigation(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "test.spec.ts")
        assert target['has_wait_navigation'] is True

    def test_parse_python(self, parser, sample_py):
        target = parser.parse_content(sample_py, "test_login.py", is_python=True)
        assert target['source_type'] == 'playwright'
        assert len(target['env_vars']) >= 1

    def test_python_extracts_env_vars(self, parser, sample_py):
        target = parser.parse_content(sample_py, "test.py", is_python=True)
        env_names = [e['name'] for e in target['env_vars']]
        assert 'BASE_URL' in env_names or 'API_KEY' in env_names

    def test_steps_have_required_fields(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "test.spec.ts")
        for step in target['steps']:
            assert 'name' in step
            assert 'index' in step
            assert 'type' in step
            assert 'is_critical' in step

    def test_navigate_steps_are_critical(self, parser, sample_ts):
        target = parser.parse_content(sample_ts, "test.spec.ts")
        nav_steps = [s for s in target['steps'] if s['type'] == 'navigate']
        assert all(s['is_critical'] for s in nav_steps)

    def test_file_not_found_raises(self, parser):
        with pytest.raises(FileNotFoundError):
            parser.parse_file("/nonexistent/path/test.spec.ts")

    def test_parse_file_js(self, parser, tmp_path, sample_ts):
        f = tmp_path / "test.spec.ts"
        f.write_text(sample_ts)
        target = parser.parse_file(str(f))
        assert target['source_type'] == 'playwright'

    def test_parse_file_python(self, parser, tmp_path, sample_py):
        f = tmp_path / "test_login.py"
        f.write_text(sample_py)
        target = parser.parse_file(str(f))
        assert target['source_type'] == 'playwright'

    def test_demo_playwright_target(self):
        target = create_demo_playwright_target()
        assert target['source_type'] == 'playwright'
        assert len(target['steps']) >= 3
        assert len(target['test_names']) >= 2

    def test_target_compatible_with_agents(self, parser, sample_ts):
        """Target from Playwright parser should work with Crucible attack agents."""
        target = parser.parse_content(sample_ts, "test.spec.ts")
        # Verify all required fields for agents exist
        required = ['steps', 'env_vars', 'network_calls', 'dependencies',
                    'timeout_ms', 'has_retry_logic', 'has_timeout',
                    'critical_order_steps', 'downstream_steps']
        for field in required:
            assert field in target, f"Missing required field: {field}"
