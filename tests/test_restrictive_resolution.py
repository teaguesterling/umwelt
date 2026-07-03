"""Regression tests for the authorization-soundness hardening (GHSA-8fg4-2x93-4q77).

Scope of the accompanying fix:

* Network egress is **deny-by-default** at the OS altitude (nsjail): the jail is
  network-isolated unless a policy carries an explicit positive ``allow: true``.
  A ``deny`` value can never *open* the network, which closes the
  isolation-bypass where a broad ``network { deny: "*" }`` base was loosened by a
  more-specific ``network { deny: "none" }`` (or an equal-specificity later
  rule): absent an explicit allow the jail stays isolated regardless of how
  ``deny`` resolves.
* A file the policy marks ``visible: false`` is not mounted into the jail at all.

Deliberately OUT of scope (see the module docstring in ``test_boolean_escalation``
and the PR body): the boolean permission-escalation via specificity for
``editable``/``allow`` is an *unresolved threat-model conflict*, because the
escalation shape is structurally identical to the intended, security-conscious
"deny-all-except-X in mode Y" exception idiom. The two cannot be distinguished by
restrictiveness alone. That invariant pair is asserted below (one side xfail) so
the tension is visible and guarded against a regression that over-denies.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler
from umwelt.sandbox.entities import FileEntity, NetworkEntity


# ---------------------------------------------------------------------------
# Network egress: deny-by-default (CRITICAL — isolation bypass, GHSA item 1)
# ---------------------------------------------------------------------------


class TestNsjailNetworkDenyByDefault:
    def test_no_network_rule_is_isolated(self):
        rv = ResolvedView()
        rv.add(
            "world",
            FileEntity(path="a.py", abs_path=Path("/w/a.py"), name="a.py"),
            {"editable": "false"},
        )
        assert "clone_newnet: true" in NsjailCompiler().compile(rv)

    def test_deny_all_stays_isolated(self):
        rv = ResolvedView()
        rv.add("world", NetworkEntity(), {"deny": "*"})
        assert "clone_newnet: true" in NsjailCompiler().compile(rv)

    def test_resolved_deny_none_does_not_open_network(self):
        # This is the isolation-bypass shape: whatever loosened `deny` to "none",
        # the jail must stay isolated because there is no explicit allow.
        rv = ResolvedView()
        rv.add("world", NetworkEntity(), {"deny": "none"})
        assert "clone_newnet: true" in NsjailCompiler().compile(rv)

    def test_explicit_allow_true_opens_network(self):
        rv = ResolvedView()
        rv.add("world", NetworkEntity(), {"allow": "true"})
        assert "clone_newnet" not in NsjailCompiler().compile(rv)


# ---------------------------------------------------------------------------
# Visibility dropped at OS altitude (GHSA item 5)
# ---------------------------------------------------------------------------


class TestNsjailVisibility:
    def test_invisible_file_not_mounted(self):
        rv = ResolvedView()
        rv.add(
            "world",
            FileEntity(path="secret.py", abs_path=Path("/w/secret.py"), name="secret.py"),
            {"editable": "false", "visible": "false"},
        )
        assert "secret.py" not in NsjailCompiler().compile(rv)

    def test_visible_file_still_mounted(self):
        rv = ResolvedView()
        rv.add(
            "world",
            FileEntity(path="app.py", abs_path=Path("/w/app.py"), name="app.py"),
            {"editable": "false", "visible": "true"},
        )
        assert "app.py" in NsjailCompiler().compile(rv)


# ---------------------------------------------------------------------------
# The unresolved core: permission escalation vs the exception idiom.
# ---------------------------------------------------------------------------


def _tree(tmp_path):
    (tmp_path / "src" / "secrets").mkdir(parents=True)
    (tmp_path / "src" / "secrets" / "key.py").write_text("# key")
    (tmp_path / "src" / "app.py").write_text("# app")
    return tmp_path


def _resolve_editable(view_text, tmp_path):
    from umwelt.cascade.resolver import resolve
    from umwelt.parser import parse
    from umwelt.registry import register_matcher, registry_scope
    from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
    from umwelt.sandbox.world_matcher import WorldMatcher

    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=_tree(tmp_path)))
        resolved = resolve(parse(view_text, validate=False))
        return {
            e.path: props.get("editable")
            for e, props in resolved.entries("world")
            if hasattr(e, "path")
        }


class TestBooleanEscalationInvariant:
    """The fix must eventually satisfy BOTH of these simultaneously.

    They are structurally identical (broad deny + narrower allow), so any model
    that denies the escalation with plain restrictive-meet also denies the
    legitimate exception. Distinguishing them needs a trust/layer boundary
    (e.g. the fixed-constraint clamp — GHSA item 4), not restrictiveness. Until
    that lands, ``test_escalation_is_denied`` is a known fail-open (xfail) and
    ``test_exception_idiom_still_grants`` guards against a regression that would
    "fix" escalation by breaking the idiom.
    """

    def test_exception_idiom_still_grants(self, tmp_path):
        # "deny all .py, allow the secrets subtree" — the exception must grant.
        editable = _resolve_editable(
            'file[path$=".py"] { editable: false; }\n'
            'file[path^="src/secrets"] { editable: true; }',
            tmp_path,
        )
        # The intended cascade semantics: the more-specific allow wins.
        assert editable["src/secrets/key.py"] == "true"

    @pytest.mark.xfail(
        reason="Unresolved: escalation shape is identical to the exception "
        "idiom; needs the fixed-constraint clamp (GHSA-8fg4-2x93-4q77 item 4), "
        "not restrictive-meet. Tracked in the PR / advisory.",
        strict=True,
    )
    def test_escalation_is_denied(self, tmp_path):
        editable = _resolve_editable(
            'file[path$=".py"] { editable: false; }\n'
            'file[path^="src/secrets"] { editable: true; }',
            tmp_path,
        )
        assert editable["src/secrets/key.py"] == "false"
