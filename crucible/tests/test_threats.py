"""Tests for the threat schema, Threat Dragon importer, planner, validator, and CLI."""

import argparse
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.base_agent import AttackResult, BaseAdversarialAgent
from threats.schema import Evidence, Threat, ThreatStatus, ThreatValidationReport
from threats.importer import ThreatDragonImporter
from threats.planner import ThreatPlanner
from threats.validator import ThreatValidator
import threats.validator as validator_module

FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples", "threat-model.json"
)


# ── Test doubles: deterministic agents, no subprocess/network involved ───────

class _AlwaysPassAgent(BaseAdversarialAgent):
    attack_type = "fake_pass"
    description = "test double: never triggers a failure"

    async def generate_mutations(self, target):
        return [{"noop": True}]

    async def apply_mutation(self, target, mutation):
        return AttackResult(
            success=True, mutation_applied=mutation, failure_triggered=False,
            failure_description=None, affected_steps=[], recovery_time_ms=None,
        )


class _AlwaysFailAgent(BaseAdversarialAgent):
    attack_type = "fake_fail"
    description = "test double: always triggers a failure"

    async def generate_mutations(self, target):
        return [{"noop": True}]

    async def apply_mutation(self, target, mutation):
        return AttackResult(
            success=True, mutation_applied=mutation, failure_triggered=True,
            failure_description="fake failure for testing", affected_steps=["fake_step"],
            recovery_time_ms=100.0,
        )


FAKE_REGISTRY = {"fake_pass": _AlwaysPassAgent, "fake_fail": _AlwaysFailAgent}


@pytest.fixture
def fake_registry(monkeypatch):
    monkeypatch.setattr(validator_module, "ATTACK_REGISTRY", FAKE_REGISTRY)
    return FAKE_REGISTRY


def make_threat(id_, attack_plan, title="t", technique="Spoofing"):
    return Threat(id=id_, title=title, technique=technique, attack_plan=list(attack_plan))


# ── Schema ─────────────────────────────────────────────────────────────────────

class TestSchema:
    def test_threat_to_dict_serializes_status_as_string(self):
        t = Threat(id="1", title="x", status=ThreatStatus.FAIL)
        d = t.to_dict()
        assert d["status"] == "fail"

    def test_evidence_to_dict(self):
        e = Evidence(attack_type="env", trace_id="trc_1", failure_triggered=True, description="boom")
        d = e.to_dict()
        assert d["attack_type"] == "env"
        assert d["failure_triggered"] is True

    def test_report_coverage_excludes_untested(self):
        threats = [
            make_threat("1", [], title="a"),
            make_threat("2", ["env"], title="b"),
        ]
        threats[0].status = ThreatStatus.UNTESTED
        threats[1].status = ThreatStatus.PASS
        report = ThreatValidationReport(trace_id="trc_x", target="t", threats=threats, replay_command="...")
        assert report.coverage == 50.0
        assert report.passed == 1
        assert report.untested == 1

    def test_report_failure_points_only_from_fail_threats(self):
        passed = make_threat("1", ["env"], title="passed")
        passed.status = ThreatStatus.PASS
        passed.evidence = [Evidence(attack_type="env", trace_id="t", failure_triggered=False, description=None)]

        failed = make_threat("2", ["env"], title="failed")
        failed.status = ThreatStatus.FAIL
        failed.evidence = [Evidence(attack_type="env", trace_id="t", failure_triggered=True, description="bad env")]

        report = ThreatValidationReport(trace_id="trc_x", target="t", threats=[passed, failed], replay_command="...")
        assert report.failure_points() == ["bad env"]

    def test_report_coverage_empty_threats_is_zero(self):
        report = ThreatValidationReport(trace_id="trc_x", target="t", threats=[], replay_command="...")
        assert report.coverage == 0.0


# ── Threat Dragon importer ────────────────────────────────────────────────────

class TestImporter:
    def test_import_file_excludes_mitigated_by_default(self):
        threats = ThreatDragonImporter().import_file(FIXTURE_PATH)
        assert len(threats) == 5
        assert all(t.source.get("status") != "Mitigated" for t in threats)

    def test_import_file_include_mitigated(self):
        threats = ThreatDragonImporter().import_file(FIXTURE_PATH, include_mitigated=True)
        assert len(threats) == 6

    def test_normalizes_technique_and_severity(self):
        threats = ThreatDragonImporter().import_file(FIXTURE_PATH)
        replay = next(t for t in threats if "Replay" in t.title)
        assert replay.technique == "Spoofing"
        assert replay.severity == "high"
        assert replay.framework == "STRIDE"
        assert replay.component == "CI Runner"

    def test_stable_ids_from_source(self):
        threats = ThreatDragonImporter().import_file(FIXTURE_PATH)
        ids = {t.id for t in threats}
        assert "1" in ids and "2" in ids

    def test_flat_threats_shape(self):
        model = {"threats": [{"id": "x1", "title": "Flat threat", "type": "Tampering", "severity": "Low"}]}
        threats = ThreatDragonImporter().import_dict(model)
        assert len(threats) == 1
        assert threats[0].component == "unassigned"

    def test_skips_entries_without_title_or_description(self):
        model = {"threats": [{"id": "x1", "type": "Tampering"}]}
        threats = ThreatDragonImporter().import_dict(model)
        assert threats == []

    def test_duplicate_ids_get_suffixed(self):
        model = {"threats": [
            {"id": "dup", "title": "First", "type": "Spoofing"},
            {"id": "dup", "title": "Second", "type": "Tampering"},
        ]}
        threats = ThreatDragonImporter().import_dict(model)
        ids = [t.id for t in threats]
        assert len(set(ids)) == 2

    def test_unknown_severity_defaults_to_medium(self):
        model = {"threats": [{"id": "x1", "title": "Weird severity", "severity": "TBD"}]}
        threats = ThreatDragonImporter().import_dict(model)
        assert threats[0].severity == "medium"

    def test_import_file_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            ThreatDragonImporter().import_file("/nonexistent/path/threatmodel.json")

    def test_import_file_bad_json_raises_value_error(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        with pytest.raises(ValueError):
            ThreatDragonImporter().import_file(str(bad))


# ── Planner ────────────────────────────────────────────────────────────────────

class TestPlanner:
    def test_keyword_match_replay(self):
        t = Threat(id="1", title="OAuth Replay", technique="Spoofing")
        planned = ThreatPlanner().plan(t)
        assert set(planned.attack_plan) == {"network", "timing"}
        assert "keyword match" in planned.plan_rationale

    def test_stride_fallback_tampering(self):
        t = Threat(id="1", title="Config Change", description="alters build config", technique="Tampering")
        planned = ThreatPlanner().plan(t)
        assert set(planned.attack_plan) == {"supply_chain", "dependency"}
        assert "STRIDE fallback" in planned.plan_rationale

    def test_repudiation_has_no_coverage(self):
        t = Threat(id="1", title="No audit trail", description="cannot attribute action", technique="Repudiation")
        planned = ThreatPlanner().plan(t)
        assert planned.attack_plan == []

    def test_unrecognized_technique_untested(self):
        t = Threat(id="1", title="Something custom", description="n/a", technique="CustomFramework")
        planned = ThreatPlanner().plan(t)
        assert planned.attack_plan == []
        assert "unrecognized" in planned.plan_rationale

    def test_information_disclosure_fallback(self):
        t = Threat(id="1", title="Data exposure", description="leaks internal data", technique="Information Disclosure")
        planned = ThreatPlanner().plan(t)
        assert planned.attack_plan == ["env"]

    def test_plan_all(self):
        threats = [
            Threat(id="1", title="OAuth Replay", technique="Spoofing"),
            Threat(id="2", title="No audit trail", technique="Repudiation"),
        ]
        planned = ThreatPlanner().plan_all(threats)
        assert planned[0].attack_plan
        assert planned[1].attack_plan == []


# ── Validator ──────────────────────────────────────────────────────────────────

class TestValidator:
    @pytest.mark.asyncio
    async def test_validate_pass(self, tmp_path, fake_registry):
        threat = make_threat("1", ["fake_pass"])
        validator = ThreatValidator(traces_dir=str(tmp_path))
        report = await validator.validate([threat], {"name": "t"})
        assert threat.status == ThreatStatus.PASS
        assert threat.evidence and all(not e.failure_triggered for e in threat.evidence)
        assert report.passed == 1 and report.failed == 0 and report.untested == 0

    @pytest.mark.asyncio
    async def test_validate_fail(self, tmp_path, fake_registry):
        threat = make_threat("1", ["fake_fail"])
        validator = ThreatValidator(traces_dir=str(tmp_path))
        report = await validator.validate([threat], {"name": "t"})
        assert threat.status == ThreatStatus.FAIL
        assert "fake failure for testing" in report.failure_points()
        assert report.failed == 1

    @pytest.mark.asyncio
    async def test_validate_untested_when_no_attack_plan(self, tmp_path, fake_registry):
        threat = make_threat("1", [])
        validator = ThreatValidator(traces_dir=str(tmp_path))
        report = await validator.validate([threat], {"name": "t"})
        assert threat.status == ThreatStatus.UNTESTED
        assert threat.evidence == []
        assert report.untested == 1

    @pytest.mark.asyncio
    async def test_validate_deduplicates_agent_execution(self, tmp_path, fake_registry):
        threats = [make_threat("1", ["fake_fail"]), make_threat("2", ["fake_fail"])]
        validator = ThreatValidator(traces_dir=str(tmp_path))
        await validator.validate(threats, {"name": "t"})
        spawned = [a for a in validator.engine.agents.values() if a.agent_type == "fake_fail"]
        assert len(spawned) == 1

    @pytest.mark.asyncio
    async def test_validate_mixed_statuses_and_coverage(self, tmp_path, fake_registry):
        threats = [
            make_threat("1", ["fake_pass"]),
            make_threat("2", ["fake_fail"]),
            make_threat("3", []),
        ]
        validator = ThreatValidator(traces_dir=str(tmp_path))
        report = await validator.validate(threats, {"name": "t"})
        assert (report.passed, report.failed, report.untested) == (1, 1, 1)
        assert report.coverage == round(100 * 2 / 3, 1)

    @pytest.mark.asyncio
    async def test_validate_sets_evidence_replay_command(self, tmp_path, fake_registry):
        threat = make_threat("1", ["fake_fail"])
        validator = ThreatValidator(traces_dir=str(tmp_path))
        report = await validator.validate([threat], {"name": "t"})
        assert threat.evidence[0].replay_command == report.replay_command
        assert report.replay_command

    @pytest.mark.asyncio
    async def test_validate_stores_trace(self, tmp_path, fake_registry):
        threat = make_threat("1", ["fake_fail"])
        validator = ThreatValidator(traces_dir=str(tmp_path))
        report = await validator.validate([threat], {"name": "t"}, seed=42, tags=["nightly"])
        stored = validator.memory.load(report.trace_id)
        assert stored is not None
        assert "threat-validation" in stored.tags
        assert "nightly" in stored.tags
        assert stored.raw_trace["threats"][0]["status"] == "fail"

    @pytest.mark.asyncio
    async def test_validate_no_threats_no_agents_run(self, tmp_path, fake_registry):
        validator = ThreatValidator(traces_dir=str(tmp_path))
        report = await validator.validate([], {"name": "t"})
        assert report.threats == []
        assert validator.engine.agents == {}


# ── CLI ────────────────────────────────────────────────────────────────────────

class TestCLI:
    def test_cmd_validate_demo_json(self, tmp_path, capsys, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from cli.crucible import cmd_validate

        threat_model = {
            "threats": [
                {"id": "1", "title": "Unpinned action tampering", "type": "Tampering",
                 "severity": "High", "status": "Open", "description": "supply chain risk"},
                {"id": "2", "title": "Unattributable deploy", "type": "Repudiation",
                 "severity": "Medium", "status": "Open", "description": "no audit trail"},
                {"id": "3", "title": "Old finding", "type": "Tampering",
                 "severity": "Low", "status": "Mitigated", "description": "already fixed"},
            ]
        }
        model_path = tmp_path / "tm.json"
        model_path.write_text(json.dumps(threat_model))

        args = argparse.Namespace(
            threat_model=str(model_path), target=None, demo=True, include_mitigated=False,
            tags=None, github_comment=False, sarif=None, seed=42, json=True,
        )
        cmd_validate(args)

        out = capsys.readouterr().out
        report = json.loads(out)
        assert report["passed"] + report["failed"] + report["untested"] == 2
        by_id = {t["id"]: t for t in report["threats"]}
        assert by_id["2"]["status"] == "untested"
        assert by_id["1"]["status"] == "fail"

    def test_cmd_validate_no_open_threats_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from cli.crucible import cmd_validate

        model_path = tmp_path / "tm.json"
        model_path.write_text(json.dumps({"threats": [
            {"id": "1", "title": "Fixed", "status": "Mitigated"},
        ]}))

        args = argparse.Namespace(
            threat_model=str(model_path), target=None, demo=True, include_mitigated=False,
            tags=None, github_comment=False, sarif=None, seed=None, json=True,
        )
        with pytest.raises(SystemExit):
            cmd_validate(args)

    def test_validate_subcommand_registered(self):
        from cli.crucible import main
        import sys as _sys
        old_argv = _sys.argv
        try:
            _sys.argv = ["crucible", "validate", "--help"]
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        finally:
            _sys.argv = old_argv
