"""Tests for sandbox per-taxon validators."""

from __future__ import annotations

import pytest

from umwelt.errors import ViewValidationError
from umwelt.registry import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

# ---------------------------------------------------------------------------
# WorldValidator
# ---------------------------------------------------------------------------


def test_path_traversal_raises():
    """A path attribute containing '..' must raise ViewValidationError."""
    with registry_scope():
        register_sandbox_vocabulary()
        from umwelt.parser import parse

        with pytest.raises(ViewValidationError, match="path traversal"):
            parse('file[path="../etc/passwd"] { editable: true; }', validate=True)


def test_clean_path_passes():
    """A normal path attribute must not raise."""
    with registry_scope():
        register_sandbox_vocabulary()
        from umwelt.parser import parse

        # Should not raise.
        view = parse('file[path^="src/auth/"] { editable: true; }', validate=True)
        assert view is not None


def test_path_without_traversal_passes():
    """A path containing 'dots' in a filename is fine — only '..' is forbidden."""
    with registry_scope():
        register_sandbox_vocabulary()
        from umwelt.parser import parse

        view = parse('file[name="setup.py"] { editable: true; }', validate=True)
        assert view is not None


# ---------------------------------------------------------------------------
# CapabilityValidator
# ---------------------------------------------------------------------------


def test_allow_deny_overlap_produces_warning():
    """allow: true and allow: false on the same rule block produce a warning."""
    with registry_scope():
        register_sandbox_vocabulary()
        from umwelt.parser import parse

        # We need to write a view with duplicate allow declarations.
        # The parser collects both values in the Declaration.values tuple
        # because it keeps duplicate keys.
        # Use the @capability scope so selectors resolve against that taxon.
        view = parse(
            "@capability { tool[name=\"Bash\"] { allow: true; allow: false; } }",
            validate=True,
        )
        messages = [w.message for w in view.warnings]
        assert any("allow and deny" in m for m in messages), (
            f"Expected allow/deny warning, got: {messages}"
        )


def test_no_overlap_produces_no_allow_deny_warning():
    """A rule with only allow: true should not produce a conflict warning."""
    with registry_scope():
        register_sandbox_vocabulary()
        from umwelt.parser import parse

        view = parse(
            '@capability { tool[name="Bash"] { allow: true; } }',
            validate=True,
        )
        conflict_warnings = [
            w for w in view.warnings if "allow and deny" in w.message
        ]
        assert conflict_warnings == []


# ---------------------------------------------------------------------------
# Validator integration via parse(validate=True)
# ---------------------------------------------------------------------------


def test_validators_run_as_part_of_parse():
    """parse(validate=True) triggers registered validators end-to-end."""
    with registry_scope():
        register_sandbox_vocabulary()
        from umwelt.parser import parse

        # The world validator should reject path traversal when validate=True.
        with pytest.raises(ViewValidationError):
            parse('file[path="../../secret"] { editable: true; }', validate=True)


def test_validators_skipped_when_validate_false():
    """parse(validate=False) skips validators — no error for path traversal."""
    with registry_scope():
        register_sandbox_vocabulary()
        from umwelt.parser import parse

        # Should not raise even though path contains "..".
        view = parse('file[path="../../secret"] { editable: true; }', validate=False)
        assert view is not None
