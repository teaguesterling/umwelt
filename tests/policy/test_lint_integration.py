from __future__ import annotations

import os
import warnings as warnings_mod

import pytest

from umwelt.errors import PolicyLintError
from umwelt.policy import PolicyEngine


# This CSS triggers source_order_dependence: two rules at the same specificity
# set different values for the same property on the same entity.
LINT_TRIGGERING_CSS = "tool { allow: true; }\ntool { allow: false; }"


@pytest.fixture
def engine_with_lint_smell():
    """Engine whose CSS triggers source_order_dependence warnings."""
    engine = PolicyEngine()
    engine.add_entities([
        {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    ])
    engine.add_stylesheet(LINT_TRIGGERING_CSS)
    return engine


class TestLintModeOff:
    def test_default_is_off(self, engine_with_lint_smell):
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine_with_lint_smell.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) == 0

    def test_explicit_off(self):
        engine = PolicyEngine(lint_mode="off")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) == 0


class TestLintModeWarn:
    def test_warn_emits_on_compile(self):
        engine = PolicyEngine(lint_mode="warn")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1


class TestLintModeError:
    def test_error_raises_on_compile(self):
        engine = PolicyEngine(lint_mode="error")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        with pytest.raises(PolicyLintError):
            engine.resolve(type="tool", id="Bash", property="allow")


class TestLintModeNotice:
    def test_notice_does_not_raise(self):
        engine = PolicyEngine(lint_mode="notice")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        val = engine.resolve(type="tool", id="Bash", property="allow")
        assert val == "false"


class TestLintModeDict:
    def test_custom_config(self):
        engine = PolicyEngine(lint_mode={
            "error": ["source_order_dependence"],
            "default": "off",
        })
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        with pytest.raises(PolicyLintError) as exc_info:
            engine.resolve(type="tool", id="Bash", property="allow")
        assert exc_info.value.warnings[0].smell == "source_order_dependence"


class TestFromFilesLintMode:
    def test_from_files_with_lint(self, tmp_path):
        world = tmp_path / "test.world.yml"
        world.write_text("entities:\n  - type: tool\n    id: Bash\n    classes: [dangerous]\n")
        style = tmp_path / "test.umw"
        style.write_text(LINT_TRIGGERING_CSS + "\n")
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine = PolicyEngine.from_files(world=world, stylesheet=style, lint_mode="warn")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1


class TestFromDbLintMode:
    def test_from_db_with_lint(self, tmp_path):
        engine = PolicyEngine()
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        db_path = tmp_path / "test.db"
        engine.save(str(db_path))
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            PolicyEngine.from_db(str(db_path), lint_mode="warn")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1


class TestExtendInheritance:
    def test_extend_inherits_lint_mode(self):
        engine = PolicyEngine(lint_mode="error")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        with pytest.raises(PolicyLintError):
            engine.extend(
                entities=[{"type": "tool", "id": "Read", "classes": ["safe"]}],
            )

    def test_extend_overrides_lint_mode(self):
        # Parent uses clean CSS so it compiles without lint errors.
        # The lint-triggering CSS is added via extend's stylesheet.
        engine = PolicyEngine(lint_mode="error")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet("tool { allow: true; }")
        # Extending with lint_mode="off" should not raise even though parent is "error"
        extended = engine.extend(
            entities=[{"type": "tool", "id": "Read", "classes": ["safe"]}],
            stylesheet=LINT_TRIGGERING_CSS,
            lint_mode="off",
        )
        assert extended.resolve(type="tool", id="Read", property="allow") == "false"


class TestEnvVar:
    def test_env_var_sets_default(self, monkeypatch):
        monkeypatch.setenv("UMWELT_LINT", "warn")
        engine = PolicyEngine()
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        with warnings_mod.catch_warnings(record=True) as caught:
            warnings_mod.simplefilter("always")
            engine.resolve(type="tool", id="Bash", property="allow")
        lint_warnings = [w for w in caught if "umwelt lint" in str(w.message)]
        assert len(lint_warnings) >= 1

    def test_explicit_overrides_env(self, monkeypatch):
        monkeypatch.setenv("UMWELT_LINT", "error")
        engine = PolicyEngine(lint_mode="off")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        val = engine.resolve(type="tool", id="Bash", property="allow")
        assert val == "false"


class TestExplicitLintUnchanged:
    def test_lint_returns_all_regardless_of_mode(self):
        engine = PolicyEngine(lint_mode="off")
        engine.add_entities([{"type": "tool", "id": "Bash", "classes": ["dangerous"]}])
        engine.add_stylesheet(LINT_TRIGGERING_CSS)
        engine.resolve(type="tool", id="Bash", property="allow")
        results = engine.lint()
        assert len(results) >= 1
