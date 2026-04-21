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
