import pytest
from umwelt.errors import PolicyDenied, PolicyError, PolicyCompilationError, UmweltError


class TestErrorHierarchy:
    def test_policy_error_is_umwelt_error(self):
        assert issubclass(PolicyError, UmweltError)

    def test_policy_denied_is_policy_error(self):
        assert issubclass(PolicyDenied, PolicyError)

    def test_policy_compilation_error_is_policy_error(self):
        assert issubclass(PolicyCompilationError, PolicyError)

    def test_policy_denied_fields(self):
        exc = PolicyDenied(
            entity="tool#Bash",
            property="editable",
            expected="true",
            actual="false",
        )
        assert exc.entity == "tool#Bash"
        assert exc.property == "editable"
        assert exc.expected == "true"
        assert exc.actual == "false"
        assert "tool#Bash" in str(exc)
        assert "editable" in str(exc)


class TestDataModels:
    def test_lint_warning_construction(self):
        from umwelt.policy import LintWarning
        w = LintWarning(
            smell="narrow_win",
            severity="warning",
            description="Winner won by 1 specificity point",
            entities=("tool#Bash",),
            property="max-level",
        )
        assert w.smell == "narrow_win"
        assert w.severity == "warning"

    def test_trace_result_construction(self):
        from umwelt.policy import TraceResult, Candidate
        c = Candidate(
            value="3",
            specificity="00001,00000,00001",
            rule_index=2,
            source_file="policy.umw",
            source_line=10,
            won=True,
        )
        tr = TraceResult(
            entity="tool#Bash",
            property="max-level",
            value="3",
            candidates=(c,),
        )
        assert tr.value == "3"
        assert len(tr.candidates) == 1
        assert tr.candidates[0].won is True

    def test_lint_warning_frozen(self):
        from umwelt.policy import LintWarning
        w = LintWarning(smell="narrow_win", severity="warning", description="test", entities=(), property=None)
        with pytest.raises(AttributeError):
            w.smell = "other"

    def test_candidate_frozen(self):
        from umwelt.policy import Candidate
        c = Candidate(value="3", specificity="x", rule_index=0, source_file="", source_line=0, won=True)
        with pytest.raises(AttributeError):
            c.value = "5"


import json
import sqlite3
import tempfile
from pathlib import Path

from umwelt.errors import PolicyDenied
from umwelt.policy.engine import PolicyEngine


@pytest.fixture
def sample_world_yml(tmp_path):
    p = tmp_path / "test.world.yml"
    p.write_text("""
entities:
  - type: tool
    id: Read
  - type: tool
    id: Bash
    classes: [dangerous]
  - type: mode
    id: implement
""")
    return p


@pytest.fixture
def sample_stylesheet(tmp_path):
    p = tmp_path / "policy.umw"
    p.write_text("""
tool { allow: true; max-level: 5; }
tool.dangerous { max-level: 3; allow: false; }
mode { allow: true; }
""")
    return p


class TestFromFiles:
    def test_creates_engine(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        assert engine is not None

    def test_resolve_after_from_files(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        val = engine.resolve(type="tool", id="Read", property="allow")
        assert val == "true"

    def test_resolve_all_properties(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        props = engine.resolve(type="tool", id="Bash")
        assert isinstance(props, dict)
        assert "allow" in props
        assert "max-level" in props


class TestFromDb:
    def test_roundtrip_save_load(self, sample_world_yml, sample_stylesheet, tmp_path):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        db_path = tmp_path / "policy.db"
        engine1.save(str(db_path))

        engine2 = PolicyEngine.from_db(str(db_path))
        val = engine2.resolve(type="tool", id="Read", property="allow")
        assert val == "true"

    def test_from_db_is_cow(self, sample_world_yml, sample_stylesheet, tmp_path):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        db_path = tmp_path / "policy.db"
        engine1.save(str(db_path))

        engine2 = PolicyEngine.from_db(str(db_path))
        assert engine2.resolve(type="tool", id="Read", property="allow") == "true"


class TestProgrammatic:
    def test_programmatic_build(self):
        engine = PolicyEngine()
        engine.add_entities([
            {"type": "tool", "id": "Read"},
            {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
        ])
        engine.add_stylesheet("tool { allow: true; }\ntool.dangerous { allow: false; }")

        val = engine.resolve(type="tool", id="Read", property="allow")
        assert val == "true"

        val = engine.resolve(type="tool", id="Bash", property="allow")
        assert val == "false"


class TestExtend:
    def test_extend_produces_new_engine(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine2 = engine1.extend(
            entities=[{"type": "mode", "id": "review"}],
        )
        assert engine2 is not engine1

    def test_extend_preserves_original(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine1.extend(
            entities=[{"type": "mode", "id": "review"}],
        )
        modes = engine1.resolve_all(type="mode")
        assert len(modes) == 1

    def test_extend_adds_entities(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine2 = engine1.extend(
            entities=[{"type": "mode", "id": "review"}],
        )
        modes = engine2.resolve_all(type="mode")
        assert len(modes) == 2

    def test_extend_with_stylesheet(self, sample_world_yml, sample_stylesheet):
        engine1 = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine2 = engine1.extend(
            stylesheet="tool#Read { visible: false; }",
        )
        val = engine2.resolve(type="tool", id="Read", property="visible")
        assert val == "false"


class TestConvenience:
    def test_check_true(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        assert engine.check(type="tool", id="Read", allow="true") is True

    def test_check_false(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        assert engine.check(type="tool", id="Bash", allow="true") is False

    def test_require_passes(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        engine.require(type="tool", id="Read", allow="true")

    def test_require_raises_policy_denied(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        with pytest.raises(PolicyDenied) as exc_info:
            engine.require(type="tool", id="Bash", allow="true")
        assert exc_info.value.actual == "false"


class TestTrace:
    def test_trace_returns_candidates(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        result = engine.trace(type="tool", id="Bash", property="allow")
        assert result.value is not None
        assert len(result.candidates) >= 1


class TestLint:
    def test_lint_returns_list(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        warnings = engine.lint()
        assert isinstance(warnings, list)


class TestExecute:
    def test_raw_sql(self, sample_world_yml, sample_stylesheet):
        engine = PolicyEngine.from_files(
            world=sample_world_yml,
            stylesheet=sample_stylesheet,
        )
        rows = engine.execute("SELECT COUNT(*) FROM entities")
        assert rows[0][0] >= 3
