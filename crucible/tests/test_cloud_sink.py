"""CrucibleCloudSink — per-attack POSTs to Crucible Cloud over stdlib urllib."""

import json
import sys
import urllib.error
import urllib.request


from crucible.sinks.crucible_cloud_sink import CrucibleCloudSink


class FakeAttackResult:
    """Same attribute surface as agents.base_agent.AttackResult."""

    def __init__(self):
        self.success = True
        self.mutation_applied = {"unset": "DATABASE_URL"}
        self.failure_triggered = True
        self.failure_description = "build step crashed"
        self.affected_steps = ["run_tests"]
        self.recovery_time_ms = 1200.5
        self.raw_output = "SECRET_TOKEN=abc123 leaked into stderr"
        self.attack_type = "env"


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b'{"stored": true}'


def _capture(monkeypatch):
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent["url"] = req.full_url
        sent["method"] = req.get_method()
        sent["headers"] = {k.lower(): v for k, v in req.header_items()}
        sent["body"] = json.loads(req.data.decode())
        sent["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return sent


def test_from_env_returns_none_without_both_vars(monkeypatch):
    monkeypatch.delenv("CRUCIBLE_CLOUD_URL", raising=False)
    monkeypatch.delenv("CRUCIBLE_API_KEY", raising=False)
    assert CrucibleCloudSink.from_env() is None

    monkeypatch.setenv("CRUCIBLE_CLOUD_URL", "https://cloud.example")
    assert CrucibleCloudSink.from_env() is None

    monkeypatch.setenv("CRUCIBLE_API_KEY", "cru_testkey")
    sink = CrucibleCloudSink.from_env()
    assert isinstance(sink, CrucibleCloudSink)
    assert sink.url == "https://cloud.example"


def test_publish_posts_one_attack_to_the_nested_route(monkeypatch):
    sent = _capture(monkeypatch)
    sink = CrucibleCloudSink("https://cloud.example/", "cru_testkey")

    sink.publish("trc_abc123", 7, FakeAttackResult())

    assert sent["url"] == "https://cloud.example/results/trc_abc123/attacks"
    assert sent["method"] == "POST"
    assert sent["headers"]["X-api-key".lower()] == "cru_testkey"
    assert sent["headers"]["Content-type".lower()] == "application/json"
    assert sent["body"] == {
        "attack_id": "atk_0007",
        "attack_type": "env",
        "success": True,
        "failure_triggered": True,
        "failure_description": "build step crashed",
        "affected_steps": ["run_tests"],
        "recovery_time_ms": 1200.5,
        "mutation_applied": {"unset": "DATABASE_URL"},
    }


def test_publish_never_transmits_raw_output(monkeypatch):
    sent = _capture(monkeypatch)
    CrucibleCloudSink("https://cloud.example", "cru_testkey").publish("trc_x", 0, FakeAttackResult())

    assert "raw_output" not in sent["body"]
    assert "SECRET_TOKEN" not in json.dumps(sent["body"])


def test_publish_raises_on_http_error_for_the_runner_to_swallow(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", boom)

    try:
        CrucibleCloudSink("https://cloud.example", "cru_testkey").publish("trc_x", 0, FakeAttackResult())
    except urllib.error.HTTPError:
        return
    raise AssertionError("expected the HTTPError to propagate to the runner's guard")


import asyncio  # noqa: E402

from crucible.runner import CrucibleRunner  # noqa: E402


def _unpinned_action_workflow(tmp_path):
    wf = tmp_path / "ci.yml"
    wf.write_text(
        "name: ci\n"
        "on: push\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - name: checkout\n"
        "        uses: actions/checkout@v4\n"
    )
    return str(wf)


def test_runner_invokes_callback_once_per_attack_result(tmp_path):
    collected = []
    runner = CrucibleRunner(traces_dir=str(tmp_path), verbose=False)

    result = asyncio.run(
        runner.run(
            target_path=_unpinned_action_workflow(tmp_path),
            attacks=["supply_chain"],
            seed=1234,
            on_attack_result=lambda trace_id, index, attack: collected.append((trace_id, index, attack)),
        )
    )

    assert collected, "expected at least one AttackResult to be published"
    assert all(trace_id == result["trace_id"] for trace_id, _, _ in collected)
    assert [index for _, index, _ in collected] == list(range(len(collected)))
    assert all(hasattr(attack, "failure_triggered") for _, _, attack in collected)


def test_runner_survives_a_failing_sink(tmp_path):
    def explode(trace_id, index, attack):
        raise RuntimeError("cloud is down")

    runner = CrucibleRunner(traces_dir=str(tmp_path), verbose=False)
    result = asyncio.run(
        runner.run(
            target_path=_unpinned_action_workflow(tmp_path),
            attacks=["supply_chain"], seed=1234, on_attack_result=explode,
        )
    )

    # the run still completes and still returns the full aggregate report
    assert "resilience_score" in result
    assert "grade" in result
    assert result["trace_id"]


def test_run_without_a_callback_is_unchanged(tmp_path):
    runner = CrucibleRunner(traces_dir=str(tmp_path), verbose=False)
    result = asyncio.run(runner.run(demo_mode=True, attacks=["env"], seed=1234))

    assert set(result) >= {
        "trace_id",
        "crucible_version",
        "target",
        "resilience_score",
        "grade",
        "components",
        "failure_count",
        "blast_radius",
        "top_vulnerabilities",
        "replay_command",
        "engine_status",
        "agent_reflections",
        "shadow_summary",
        "seed",
        "failure_points",
    }


import argparse  # noqa: E402

import pytest  # noqa: E402

import crucible.cli.crucible as cli  # noqa: E402


def _attack_args(**overrides):
    defaults = dict(
        target=None, demo=True, attacks="env", tags=None, rich=False, shadow=False,
        github_comment=False, sarif=None, seed=1234, quiet=True, json=False, publish_cloud=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_attack_parser_accepts_cloud_flag(monkeypatch):
    """argparse must accept --cloud (exit 2 would mean 'unrecognised argument'),
    and cmd_attack must then own the missing-credentials failure (exit 1)."""
    monkeypatch.delenv("CRUCIBLE_CLOUD_URL", raising=False)
    monkeypatch.delenv("CRUCIBLE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["crucible", "attack", "--demo", "--quiet", "--cloud"])

    with pytest.raises(SystemExit) as excinfo:
        cli.main()
    assert excinfo.value.code == 1, "exit 2 means argparse rejected --cloud"


def test_cmd_attack_exits_when_cloud_env_missing(monkeypatch):
    monkeypatch.delenv("CRUCIBLE_CLOUD_URL", raising=False)
    monkeypatch.delenv("CRUCIBLE_API_KEY", raising=False)

    with pytest.raises(SystemExit) as excinfo:
        cli.cmd_attack(_attack_args(publish_cloud=True))
    assert excinfo.value.code == 1


def test_cmd_attack_passes_sink_publish_when_cloud_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("CRUCIBLE_CLOUD_URL", "https://cloud.example")
    monkeypatch.setenv("CRUCIBLE_API_KEY", "cru_testkey")
    monkeypatch.chdir(tmp_path)

    published = []

    def fake_publish(self, trace_id, index, result):
        published.append((trace_id, index))

    monkeypatch.setattr(CrucibleCloudSink, "publish", fake_publish)

    wf_path = _unpinned_action_workflow(tmp_path)
    cli.cmd_attack(_attack_args(publish_cloud=True, demo=False, target=wf_path, attacks="supply_chain"))

    assert published, "expected --publish-cloud to publish at least one attack"
    assert [index for _, index in published] == list(range(len(published)))


def test_cmd_attack_publishes_nothing_without_cloud_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("CRUCIBLE_CLOUD_URL", "https://cloud.example")
    monkeypatch.setenv("CRUCIBLE_API_KEY", "cru_testkey")
    monkeypatch.chdir(tmp_path)

    published = []
    monkeypatch.setattr(
        CrucibleCloudSink, "publish",
        lambda self, trace_id, index, result: published.append(index),
    )

    cli.cmd_attack(_attack_args(publish_cloud=False))

    assert published == [], "env vars alone must not trigger per-attack ingestion"
