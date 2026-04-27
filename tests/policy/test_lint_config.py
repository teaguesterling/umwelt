from __future__ import annotations

import logging
import warnings as warnings_mod

import pytest

from umwelt.errors import PolicyLintError
from umwelt.policy.engine import LintWarning
from umwelt.policy.lint import LintConfig, process_lint_results


class TestLintConfigFromString:
    def test_off(self):
        cfg = LintConfig.from_lint_mode("off")
        assert cfg.default == "off"
        assert cfg.overrides == {}

    def test_warn(self):
        cfg = LintConfig.from_lint_mode("warn")
        assert cfg.default == "warn"

    def test_error(self):
        cfg = LintConfig.from_lint_mode("error")
        assert cfg.default == "error"

    def test_notice(self):
        cfg = LintConfig.from_lint_mode("notice")
        assert cfg.default == "notice"


class TestLintConfigFromDict:
    def test_dict_with_default(self):
        cfg = LintConfig.from_lint_mode({
            "error": ["cross_axis_dominance"],
            "warn": ["narrow_win"],
            "notice": ["uncovered_entity"],
            "off": ["shadowed_rule"],
            "default": "notice",
        })
        assert cfg.default == "notice"
        assert cfg.severity_for("cross_axis_dominance") == "error"
        assert cfg.severity_for("narrow_win") == "warn"
        assert cfg.severity_for("uncovered_entity") == "notice"
        assert cfg.severity_for("shadowed_rule") == "off"

    def test_dict_default_fallback(self):
        cfg = LintConfig.from_lint_mode({"default": "warn"})
        assert cfg.severity_for("anything") == "warn"

    def test_dict_missing_default_uses_warn(self):
        cfg = LintConfig.from_lint_mode({"error": ["narrow_win"]})
        assert cfg.default == "warn"
        assert cfg.severity_for("narrow_win") == "error"
        assert cfg.severity_for("other") == "warn"

    def test_empty_dict(self):
        cfg = LintConfig.from_lint_mode({})
        assert cfg.default == "warn"


class TestSeverityFor:
    def test_override_wins(self):
        cfg = LintConfig(default="warn", overrides={"narrow_win": "error"})
        assert cfg.severity_for("narrow_win") == "error"

    def test_default_when_no_override(self):
        cfg = LintConfig(default="notice", overrides={})
        assert cfg.severity_for("narrow_win") == "notice"


def _make_warning(smell: str = "narrow_win", desc: str = "test") -> LintWarning:
    return LintWarning(smell=smell, severity="warning", description=desc, entities=(), property=None)


class TestProcessLintResults:
    def test_off_suppresses(self):
        cfg = LintConfig.from_lint_mode("off")
        result = process_lint_results([_make_warning()], cfg)
        assert result == []

    def test_notice_logs(self, caplog):
        cfg = LintConfig.from_lint_mode("notice")
        with caplog.at_level(logging.INFO, logger="umwelt.policy"):
            result = process_lint_results([_make_warning()], cfg)
        assert len(result) == 1
        assert "narrow_win" in caplog.text

    def test_warn_emits_warning(self):
        cfg = LintConfig.from_lint_mode("warn")
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            result = process_lint_results([_make_warning()], cfg)
        assert len(result) == 1
        assert len(caught) == 1
        assert "narrow_win" in str(caught[0].message)

    def test_error_raises(self):
        cfg = LintConfig.from_lint_mode("error")
        with pytest.raises(PolicyLintError) as exc_info:
            process_lint_results([_make_warning()], cfg)
        assert len(exc_info.value.warnings) == 1

    def test_mixed_severities(self):
        cfg = LintConfig.from_lint_mode({
            "error": ["narrow_win"],
            "off": ["shadowed_rule"],
            "default": "notice",
        })
        ws = [
            _make_warning("narrow_win", "bad"),
            _make_warning("shadowed_rule", "ok"),
            _make_warning("other_smell", "meh"),
        ]
        with pytest.raises(PolicyLintError) as exc_info:
            process_lint_results(ws, cfg)
        assert len(exc_info.value.warnings) == 1
        assert exc_info.value.warnings[0].smell == "narrow_win"

    def test_no_warnings_returns_empty(self):
        cfg = LintConfig.from_lint_mode("error")
        result = process_lint_results([], cfg)
        assert result == []
