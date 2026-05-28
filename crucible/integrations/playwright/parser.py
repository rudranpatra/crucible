"""
Playwright Integration
Parses Playwright test suites as Crucible attack targets.
Playwright tests define real user flows — Crucible attacks the flows themselves.

Supports: TypeScript (.spec.ts), JavaScript (.spec.js), Python (.py)
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class PlaywrightParser:
    """
    Converts Playwright test files into Crucible attack targets.

    Extracts:
    - Page navigation sequences
    - Element interaction chains
    - Network request patterns (fetch/XHR/waitForResponse)
    - Assertion checkpoints (expect calls)

    Attack strategies enabled:
    - timing: attack page load waits (waitForSelector, waitForNavigation)
    - network: chaos on fetch/XHR/API calls
    - reorder: shuffle navigation sequences
    """

    # TS/JS patterns
    _GOTO = re.compile(r"page\.goto\(['\"]([^'\"]+)['\"]")
    _CLICK = re.compile(r"(?:page|locator)\.\w*click\w*\(['\"]?([^'\")\n,]+)['\"]?")
    _FILL = re.compile(r"(?:page|locator)\.fill\(['\"]([^'\"]+)['\"]")
    _WAIT_SELECTOR = re.compile(r"page\.waitForSelector\(['\"]([^'\"]+)['\"]")
    _WAIT_NAV = re.compile(r"page\.waitForNavigation\(")
    _WAIT_RESP = re.compile(r"page\.waitForResponse\(['\"]([^'\"]+)['\"]")
    _EXPECT = re.compile(r"expect\(([^)]+)\)")
    _FETCH = re.compile(r"(?:fetch|page\.request\.(?:get|post|put|delete))\(['\"]([^'\"]+)['\"]")
    _TEST_BLOCK = re.compile(r"test\(['\"]([^'\"]+)['\"]", re.MULTILINE)
    _DESCRIBE = re.compile(r"describe\(['\"]([^'\"]+)['\"]")
    _ENV_VAR = re.compile(r"process\.env\.([A-Z_][A-Z0-9_]*)")

    # Python patterns (playwright-python)
    _PY_GOTO = re.compile(r'page\.goto\(["\']([^"\']+)["\']')
    _PY_CLICK = re.compile(r'page\.(?:click|locator)\(["\']([^"\']+)["\']')
    _PY_FILL = re.compile(r'page\.fill\(["\']([^"\']+)["\']')
    _PY_WAIT = re.compile(r'page\.wait_for_(?:selector|navigation|response)\(["\']?([^"\')\n,]+)["\']?')
    _PY_EXPECT = re.compile(r'expect\(([^)]+)\)')
    _PY_ENV = re.compile(r'os\.environ\.get\(["\']([A-Z_][A-Z0-9_]*)["\']')

    def parse_file(self, path: str) -> Dict:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Playwright test file not found: {path}")

        content = p.read_text(encoding="utf-8")
        is_python = p.suffix == ".py"

        if is_python:
            return self._parse_python(content, str(p))
        return self._parse_js_ts(content, str(p))

    def parse_content(self, content: str, source: str = "inline", is_python: bool = False) -> Dict:
        if is_python:
            return self._parse_python(content, source)
        return self._parse_js_ts(content, source)

    # ── JS/TS parsing ─────────────────────────────────────────────────────────

    def _parse_js_ts(self, content: str, source: str) -> Dict:
        test_names = self._TEST_BLOCK.findall(content)
        describe_blocks = self._DESCRIBE.findall(content)

        navigations = self._GOTO.findall(content)
        waits = self._WAIT_SELECTOR.findall(content)
        has_wait_nav = bool(self._WAIT_NAV.search(content))
        wait_responses = self._WAIT_RESP.findall(content)
        fetches = self._FETCH.findall(content)
        assertions = self._EXPECT.findall(content)
        env_vars = list(set(self._ENV_VAR.findall(content)))

        steps = self._build_steps_js(content)
        network_calls = self._build_network_calls(navigations, fetches, wait_responses)

        return self._build_target(
            name=describe_blocks[0] if describe_blocks else Path(source).stem,
            source_file=source,
            test_names=test_names,
            steps=steps,
            navigations=navigations,
            waits=waits,
            has_wait_nav=has_wait_nav,
            assertions=assertions,
            network_calls=network_calls,
            env_vars=env_vars,
        )

    def _build_steps_js(self, content: str) -> List[Dict]:
        """Extract ordered interaction steps from JS/TS content."""
        steps = []
        lines = content.splitlines()

        patterns = [
            (self._GOTO, "navigate", True),
            (re.compile(r"page\.(?:click|locator\([^)]+\)\.click)\("), "interact", True),
            (re.compile(r"page\.fill\("), "fill", False),
            (re.compile(r"page\.waitFor"), "wait", False),
            (re.compile(r"expect\("), "assert", False),
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()
            for pattern, step_type, is_critical in patterns:
                if pattern.search(stripped):
                    steps.append({
                        "name": f"{step_type}_line_{i + 1}",
                        "index": len(steps),
                        "type": step_type,
                        "source_line": stripped[:80],
                        "is_critical": is_critical,
                        "env_vars": [],
                        "network_calls": [],
                        "dependencies": [],
                        "has_retry": "retry" in stripped.lower(),
                    })
                    break

        return steps

    # ── Python parsing ────────────────────────────────────────────────────────

    def _parse_python(self, content: str, source: str) -> Dict:
        test_names = re.findall(r"def (test_\w+)\(", content)
        navigations = self._PY_GOTO.findall(content)
        waits = self._PY_WAIT.findall(content)
        assertions = self._PY_EXPECT.findall(content) + re.findall(r"assert\b", content)[:5]
        env_vars = self._PY_ENV.findall(content)

        steps = self._build_steps_python(content)
        network_calls = self._build_network_calls(navigations, [], [])

        return self._build_target(
            name=Path(source).stem,
            source_file=source,
            test_names=test_names,
            steps=steps,
            navigations=navigations,
            waits=waits,
            has_wait_nav="wait_for_navigation" in content,
            assertions=assertions,
            network_calls=network_calls,
            env_vars=list(set(env_vars)),
        )

    def _build_steps_python(self, content: str) -> List[Dict]:
        steps = []
        lines = content.splitlines()
        patterns = [
            (re.compile(r"page\.goto\("), "navigate", True),
            (re.compile(r"page\.(?:click|locator)\("), "interact", True),
            (re.compile(r"page\.fill\("), "fill", False),
            (re.compile(r"page\.wait_for"), "wait", False),
            (re.compile(r"expect\(|assert "), "assert", False),
        ]
        for i, line in enumerate(lines):
            stripped = line.strip()
            for pattern, step_type, is_critical in patterns:
                if pattern.search(stripped):
                    steps.append({
                        "name": f"{step_type}_line_{i + 1}",
                        "index": len(steps),
                        "type": step_type,
                        "source_line": stripped[:80],
                        "is_critical": is_critical,
                        "env_vars": [],
                        "network_calls": [],
                        "dependencies": [],
                        "has_retry": False,
                    })
                    break
        return steps

    # ── Target assembly ───────────────────────────────────────────────────────

    def _build_network_calls(
        self,
        navigations: List[str],
        fetches: List[str],
        wait_responses: List[str],
    ) -> List[str]:
        calls = []
        for url in navigations:
            calls.append(f"page_load:{self._domain(url)}")
        for url in fetches:
            calls.append(f"api_fetch:{self._domain(url)}")
        for url in wait_responses:
            calls.append(f"wait_response:{self._domain(url)}")
        if not calls:
            calls = ["page_load", "xhr_request"]
        return list(dict.fromkeys(calls))  # deduplicate, preserve order

    def _build_target(
        self,
        name: str,
        source_file: str,
        test_names: List[str],
        steps: List[Dict],
        navigations: List[str],
        waits: List[str],
        has_wait_nav: bool,
        assertions: List[str],
        network_calls: List[str],
        env_vars: List[str],
    ) -> Dict:
        critical_order = [s["name"] for s in steps if s.get("is_critical")]
        downstream = [s["name"] for s in steps if s.get("type") == "assert"]

        env_dicts = [{"name": v, "pinned": None, "is_secret": "token" in v.lower() or "key" in v.lower()} for v in env_vars]

        timeout_ms = 30000 if waits else 60000

        return {
            "name": name,
            "source_file": source_file,
            "source_type": "playwright",
            "triggers": ["test_run"],
            "test_count": len(test_names),
            "test_names": test_names[:10],
            "jobs": [{"name": "playwright_tests", "runs_on": "browser"}],
            "steps": steps,
            "env_vars": env_dicts,
            "network_calls": network_calls,
            "dependencies": [
                {"name": "@playwright/test", "pinned": None},
                {"name": "playwright", "pinned": None},
            ],
            "navigations": navigations,
            "assertion_count": len(assertions),
            "has_page_waits": bool(waits),
            "has_wait_navigation": has_wait_nav,
            "timeout_ms": timeout_ms,
            "has_retry_logic": False,
            "has_timeout": True,
            "critical_order_steps": critical_order,
            "downstream_steps": downstream,
        }

    @staticmethod
    def _domain(url: str) -> str:
        try:
            parts = url.split("/")
            return parts[2] if len(parts) > 2 else url[:30]
        except Exception:
            return url[:30]


def create_demo_playwright_target() -> Dict:
    """Demo Playwright target for testing without a real test file."""
    return {
        "name": "checkout_flow_tests",
        "source_file": "tests/checkout.spec.ts",
        "source_type": "playwright",
        "triggers": ["test_run"],
        "test_count": 4,
        "test_names": [
            "user can add item to cart",
            "checkout form validates required fields",
            "payment succeeds with valid card",
            "order confirmation page loads",
        ],
        "jobs": [{"name": "playwright_tests", "runs_on": "browser"}],
        "steps": [
            {"name": "navigate_home", "index": 0, "type": "navigate", "is_critical": True, "env_vars": [], "network_calls": ["page_load:example.com"], "dependencies": [], "has_retry": False, "source_line": "await page.goto('https://example.com')"},
            {"name": "interact_add_to_cart", "index": 1, "type": "interact", "is_critical": True, "env_vars": [], "network_calls": [], "dependencies": [], "has_retry": False, "source_line": "await page.click('[data-testid=add-to-cart]')"},
            {"name": "wait_cart_update", "index": 2, "type": "wait", "is_critical": False, "env_vars": [], "network_calls": [], "dependencies": [], "has_retry": False, "source_line": "await page.waitForSelector('.cart-count')"},
            {"name": "navigate_checkout", "index": 3, "type": "navigate", "is_critical": True, "env_vars": [], "network_calls": ["page_load:example.com"], "dependencies": [], "has_retry": False, "source_line": "await page.goto('/checkout')"},
            {"name": "assert_checkout_form", "index": 4, "type": "assert", "is_critical": False, "env_vars": [], "network_calls": [], "dependencies": [], "has_retry": False, "source_line": "await expect(page.locator('#checkout-form')).toBeVisible()"},
        ],
        "env_vars": [
            {"name": "BASE_URL", "pinned": None, "is_secret": False},
            {"name": "STRIPE_TEST_KEY", "pinned": None, "is_secret": True},
        ],
        "network_calls": ["page_load:example.com", "api_fetch:api.stripe.com", "xhr_request"],
        "dependencies": [
            {"name": "@playwright/test", "pinned": None},
        ],
        "navigations": ["https://example.com", "https://example.com/checkout"],
        "assertion_count": 6,
        "has_page_waits": True,
        "has_wait_navigation": True,
        "timeout_ms": 30000,
        "has_retry_logic": False,
        "has_timeout": True,
        "critical_order_steps": ["navigate_home", "interact_add_to_cart", "navigate_checkout"],
        "downstream_steps": ["assert_checkout_form"],
    }
