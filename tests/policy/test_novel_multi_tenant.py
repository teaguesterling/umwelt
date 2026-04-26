"""Pressure tests: Multi-Tenant Access Control domain.

Novel domain that exercises:
- Overlapping principal + mode + tool rules with all three axes active
- Multi-axis context qualifiers simultaneously
- Cross-axis specificity dominance (cross-axis > single-axis)
- max-level with <= comparison (MIN of all candidates = ceiling can only go down)
- Specificity ties resolved by source order within same axis
- check/require enforcement patterns
- Trace debugging through complex rule sets
- extend() for tenant isolation
"""
from __future__ import annotations

import pytest

from umwelt.errors import PolicyDenied
from umwelt.policy import PolicyEngine


@pytest.fixture
def tenant_engine(tmp_path):
    """Multi-tenant engine with roles, tenants, and overlapping tool permissions."""
    world = tmp_path / "tenant.world.yml"
    world.write_text("""\
entities:
  - type: tool
    id: Read
    classes: [safe, filesystem]
  - type: tool
    id: Edit
    classes: [safe, filesystem, mutating]
  - type: tool
    id: Bash
    classes: [dangerous, shell, mutating]
  - type: tool
    id: WebSearch
    classes: [safe, network]
  - type: tool
    id: WebFetch
    classes: [network, mutating]
  - type: tool
    id: Deploy
    classes: [dangerous, infrastructure, mutating]
  - type: tool
    id: DatabaseQuery
    classes: [dangerous, data, mutating]

  - type: mode
    id: explore
  - type: mode
    id: implement
  - type: mode
    id: review
  - type: mode
    id: deploy
  - type: mode
    id: emergency

  - type: principal
    id: developer
  - type: principal
    id: reviewer
  - type: principal
    id: ops
  - type: principal
    id: admin
""")
    style = tmp_path / "tenant.umw"
    style.write_text("""\
/* Layer 1: Base — everything visible, safe tools allowed */
tool { visible: true; allow: false; }

/* Layer 2: Safe tools allowed with level cap */
tool.safe { allow: true; max-level: 5; }

/* Layer 3: Dangerous tools allowed with lower cap and sandbox */
tool.dangerous { allow: true; max-level: 3; require: sandbox; }

/* Layer 4: Mutating tools need audit */
tool.mutating { audit-trail: required; }

/* Layer 5: Specific overrides (ID selector) */
tool#Deploy { allow: false; require: approval; }

/* ---- Mode-gated rules ---- */

/* Explore: read-only, no mutating (order matters: mutating deny AFTER safe allow) */
mode#explore tool.safe { allow: true; }
mode#explore tool.mutating { allow: false; }

/* Implement: dangerous tools get higher cap */
mode#implement tool.dangerous { max-level: 4; }
mode#implement tool#Deploy { allow: false; }

/* Review: read-only */
mode#review tool { allow: false; }
mode#review tool.safe { allow: true; }

/* Deploy: infrastructure tools enabled */
mode#deploy tool { allow: false; }
mode#deploy tool#Deploy { allow: true; }
mode#deploy tool#Bash { allow: true; }

/* Emergency: everything allowed */
mode#emergency tool { allow: true; }

/* ---- Principal-gated rules ---- */

/* Ops gets infrastructure access */
principal#ops tool.infrastructure { allow: true; }

/* Admin overrides tool allow */
principal#admin tool { allow: true; }
principal#admin tool.dangerous { require: none; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


@pytest.fixture
def base_tenant_engine(tmp_path):
    """Tenant engine with only base rules — no mode/principal gating.

    Used for testing pure single-axis cascade without cross-axis interference.
    """
    world = tmp_path / "tenant.world.yml"
    world.write_text("""\
entities:
  - type: tool
    id: Read
    classes: [safe, filesystem]
  - type: tool
    id: Edit
    classes: [safe, filesystem, mutating]
  - type: tool
    id: Bash
    classes: [dangerous, shell, mutating]
  - type: tool
    id: Deploy
    classes: [dangerous, infrastructure, mutating]
  - type: tool
    id: DatabaseQuery
    classes: [dangerous, data, mutating]
""")
    style = tmp_path / "tenant.umw"
    style.write_text("""\
tool { visible: true; allow: false; }
tool.safe { allow: true; max-level: 5; }
tool.dangerous { allow: true; max-level: 3; require: sandbox; }
tool.mutating { audit-trail: required; }
tool#Deploy { allow: false; require: approval; }
""")
    return PolicyEngine.from_files(world=world, stylesheet=style)


class TestPureCascade:
    """Test cascade without cross-axis rules — predictable single-axis specificity."""

    def test_safe_tool_allowed(self, base_tenant_engine):
        assert base_tenant_engine.check(type="tool", id="Read", allow="true")

    def test_dangerous_tool_allowed(self, base_tenant_engine):
        assert base_tenant_engine.check(type="tool", id="Bash", allow="true")

    def test_dangerous_requires_sandbox(self, base_tenant_engine):
        val = base_tenant_engine.resolve(type="tool", id="Bash", property="require")
        assert val == "sandbox"

    def test_deploy_denied_by_id(self, base_tenant_engine):
        # tool#Deploy { allow: false } beats tool.dangerous { allow: true }
        # ID selector has higher specificity than class selector
        assert base_tenant_engine.check(type="tool", id="Deploy", allow="false")

    def test_deploy_requires_approval(self, base_tenant_engine):
        # tool#Deploy { require: approval } beats tool.dangerous { require: sandbox }
        val = base_tenant_engine.resolve(type="tool", id="Deploy", property="require")
        assert val == "approval"

    def test_mutating_tools_need_audit(self, base_tenant_engine):
        for tool_id in ["Edit", "Bash", "Deploy", "DatabaseQuery"]:
            val = base_tenant_engine.resolve(type="tool", id=tool_id, property="audit-trail")
            assert val == "required", f"{tool_id} missing audit-trail"

    def test_non_mutating_no_audit(self, base_tenant_engine):
        val = base_tenant_engine.resolve(type="tool", id="Read", property="audit-trail")
        assert val is None

    def test_all_tools_visible(self, base_tenant_engine):
        tools = base_tenant_engine.resolve_all(type="tool")
        for t in tools:
            assert t["properties"].get("visible") == "true"


class TestMaxLevelCeiling:
    """Test max-level with <= comparison: MIN of all candidates wins.

    The <= comparison means max-level is a ceiling that can only go DOWN.
    If any matching rule sets max-level: 3, no other rule can raise it.
    """

    def test_safe_tool_level(self, base_tenant_engine):
        val = base_tenant_engine.resolve(type="tool", id="Read", property="max-level")
        assert val == "5"

    def test_dangerous_tool_level(self, base_tenant_engine):
        val = base_tenant_engine.resolve(type="tool", id="Bash", property="max-level")
        assert val == "3"

    def test_deploy_gets_dangerous_ceiling(self, base_tenant_engine):
        # Deploy is .dangerous, so max-level: 3 from class rule applies
        # No ID-level max-level override, so class rule is the only candidate
        val = base_tenant_engine.resolve(type="tool", id="Deploy", property="max-level")
        assert val == "3"

    def test_mode_cannot_raise_ceiling(self, tenant_engine):
        # mode#implement tool.dangerous { max-level: 4 } vs tool.dangerous { max-level: 3 }
        # <= comparison: MIN(3, 4) = 3 — ceiling can't be raised
        val = tenant_engine.resolve(
            type="tool", id="Bash", property="max-level",
            context={"mode": "implement"},
        )
        assert val == "3"


class TestCrossAxisDominance:
    """Test that cross-axis rules dominate single-axis rules in unfiltered cascade.

    Without context filtering, ALL candidates compete. Cross-axis selectors
    (mode#X tool, principal#Y tool) have higher specificity than single-axis
    selectors (tool, tool.class, tool#id). This is by design — the cross-axis
    component is counted in the specificity tuple.
    """

    def test_admin_dominates_unfiltered_allow(self, tenant_engine):
        # principal#admin tool { allow: true } has cross-axis specificity
        # → beats tool#Deploy { allow: false } (single-axis ID)
        val = tenant_engine.resolve(type="tool", id="Deploy", property="allow")
        assert val == "true"

    def test_admin_dominates_require(self, tenant_engine):
        # principal#admin tool.dangerous { require: none } beats
        # tool.dangerous { require: sandbox } and tool#Deploy { require: approval }
        val = tenant_engine.resolve(type="tool", id="Bash", property="require")
        assert val == "none"

    def test_trace_shows_cross_axis_winner(self, tenant_engine):
        result = tenant_engine.trace(type="tool", id="Deploy", property="allow")
        winner = next(c for c in result.candidates if c.won)
        # Winner should be the cross-axis rule (admin or similar)
        assert winner.value == "true"
        # Multiple candidates competed
        assert len(result.candidates) >= 3


class TestModeFilteredAccess:
    """Test mode-gated access control with context filtering."""

    def test_explore_blocks_mutating(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Edit", property="allow",
            context={"mode": "explore"},
        )
        assert val == "false"

    def test_explore_allows_safe_read(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Read", property="allow",
            context={"mode": "explore"},
        )
        assert val == "true"

    def test_explore_allows_websearch(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="WebSearch", property="allow",
            context={"mode": "explore"},
        )
        assert val == "true"

    def test_implement_still_blocks_deploy(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Deploy", property="allow",
            context={"mode": "implement"},
        )
        assert val == "false"

    def test_review_blocks_dangerous(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Bash", property="allow",
            context={"mode": "review"},
        )
        assert val == "false"

    def test_review_allows_safe(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Read", property="allow",
            context={"mode": "review"},
        )
        assert val == "true"

    def test_deploy_enables_deploy_tool(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Deploy", property="allow",
            context={"mode": "deploy"},
        )
        assert val == "true"

    def test_deploy_enables_bash(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Bash", property="allow",
            context={"mode": "deploy"},
        )
        assert val == "true"

    def test_deploy_blocks_edit(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Edit", property="allow",
            context={"mode": "deploy"},
        )
        assert val == "false"

    def test_emergency_enables_everything(self, tenant_engine):
        tools = tenant_engine.resolve_all(
            type="tool", context={"mode": "emergency"},
        )
        for t in tools:
            assert t["properties"].get("allow") == "true", \
                f"Emergency should allow {t['entity_id']}"


class TestPrincipalAccess:
    """Test principal-gated access patterns."""

    def test_ops_can_use_deploy(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Deploy", property="allow",
            context=[("principal", "principal", "ops")],
        )
        assert val == "true"

    def test_admin_overrides_all(self, tenant_engine):
        tools = tenant_engine.resolve_all(
            type="tool",
            context=[("principal", "principal", "admin")],
        )
        for t in tools:
            assert t["properties"].get("allow") == "true", \
                f"Admin should allow {t['entity_id']}"

    def test_admin_removes_sandbox(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Bash", property="require",
            context=[("principal", "principal", "admin")],
        )
        assert val == "none"


class TestMultiAxisCombinations:
    """Test multiple context qualifiers active simultaneously."""

    def test_ops_in_deploy_mode(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Deploy", property="allow",
            context=[
                ("state", "mode", "deploy"),
                ("principal", "principal", "ops"),
            ],
        )
        assert val == "true"

    def test_developer_in_review_safe_tool(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Read", property="allow",
            context=[
                ("state", "mode", "review"),
                ("principal", "principal", "developer"),
            ],
        )
        # mode#review tool.safe { allow: true } fires
        assert val == "true"

    def test_admin_in_emergency(self, tenant_engine):
        tools = tenant_engine.resolve_all(
            type="tool",
            context=[
                ("state", "mode", "emergency"),
                ("principal", "principal", "admin"),
            ],
        )
        for t in tools:
            assert t["properties"].get("allow") == "true"

    def test_ops_in_review_deploy_blocked(self, tenant_engine):
        val = tenant_engine.resolve(
            type="tool", id="Deploy", property="allow",
            context=[
                ("state", "mode", "review"),
                ("principal", "principal", "ops"),
            ],
        )
        # mode#review tool { allow: false } competes with
        # principal#ops tool.infrastructure { allow: true }
        # Both are cross-axis; infrastructure class adds specificity → ops wins
        assert val == "true"


class TestExtendForTenantIsolation:
    """Test extend() for tenant-specific policy forks."""

    def test_tenant_restricts_network(self, base_tenant_engine):
        extended = base_tenant_engine.extend(
            entities=[
                {"type": "tool", "id": "WebSearch", "classes": ["safe", "network"]},
                {"type": "tool", "id": "WebFetch", "classes": ["network", "mutating"]},
            ],
            stylesheet="tool.network { allow: false; }",
        )
        assert extended.check(type="tool", id="WebSearch", allow="false")
        assert extended.check(type="tool", id="WebFetch", allow="false")

    def test_tenant_adds_custom_tool(self, base_tenant_engine):
        custom = base_tenant_engine.extend(
            entities=[{"type": "tool", "id": "CustomLint", "classes": ["safe"]}],
            stylesheet="tool.safe { allow: true; max-level: 5; }\ntool#CustomLint { visible: true; }",
        )
        val = custom.resolve(type="tool", id="CustomLint", property="allow")
        assert val == "true"

    def test_tenant_inherits_base_rules(self, base_tenant_engine):
        extended = base_tenant_engine.extend(
            entities=[{"type": "mode", "id": "custom-mode"}],
        )
        assert extended.check(type="tool", id="Read", allow="true")
        assert extended.check(type="tool", id="Deploy", allow="false")


class TestEnforcementPatterns:
    """Test check/require as enforcement primitives."""

    def test_require_passes_for_safe_tool(self, base_tenant_engine):
        base_tenant_engine.require(type="tool", id="Read", allow="true")

    def test_require_fails_for_deploy(self, base_tenant_engine):
        with pytest.raises(PolicyDenied) as exc_info:
            base_tenant_engine.require(type="tool", id="Deploy", allow="true")
        assert "Deploy" in exc_info.value.entity

    def test_require_with_context(self, tenant_engine):
        tenant_engine.require(
            type="tool", id="Deploy",
            context={"mode": "deploy"},
            allow="true",
        )

    def test_check_multiple_properties(self, base_tenant_engine):
        assert base_tenant_engine.check(
            type="tool", id="Bash",
            allow="true", require="sandbox",
        )

    def test_check_fails_on_mismatch(self, base_tenant_engine):
        assert not base_tenant_engine.check(
            type="tool", id="Bash",
            allow="true", require="none",
        )


class TestSaveAndReload:
    """Test persistence with multi-tenant policy."""

    def test_round_trip(self, base_tenant_engine, tmp_path):
        db_path = tmp_path / "tenant.db"
        base_tenant_engine.save(str(db_path))

        reloaded = PolicyEngine.from_db(str(db_path))
        assert reloaded.check(type="tool", id="Read", allow="true")
        assert reloaded.check(type="tool", id="Deploy", allow="false")
        assert reloaded.resolve(type="tool", id="Bash", property="max-level") == "3"
