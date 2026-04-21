# tests/policy/test_integration.py
import pytest
import yaml

from umwelt.errors import PolicyDenied
from umwelt.policy import PolicyEngine


def test_full_pipeline(tmp_path):
    """End-to-end: from_files -> resolve -> trace -> lint -> save -> from_db -> resolve."""
    world_path = tmp_path / "delegate.world.yml"
    world_path.write_text("""
entities:
  - type: tool
    id: Read
  - type: tool
    id: Edit
    classes: [edit]
  - type: tool
    id: Bash
    classes: [dangerous, shell]
  - type: mode
    id: implement
""")
    style_path = tmp_path / "policy.umw"
    style_path.write_text("""
tool { allow: true; max-level: 5; }
tool.dangerous { max-level: 3; allow: false; }
tool#Bash { risk-note: Prefer structured tools; }
mode { allow: true; }
""")

    # Build from files
    engine = PolicyEngine.from_files(world=world_path, stylesheet=style_path)

    # Resolve
    assert engine.resolve(type="tool", id="Read", property="allow") == "true"
    assert engine.resolve(type="tool", id="Bash", property="allow") == "false"
    assert engine.resolve(type="tool", id="Bash", property="max-level") == "3"

    bash_props = engine.resolve(type="tool", id="Bash")
    assert isinstance(bash_props, dict)
    assert "risk-note" in bash_props

    # Resolve all
    tools = engine.resolve_all(type="tool")
    assert len(tools) == 3

    # Trace
    trace = engine.trace(type="tool", id="Bash", property="allow")
    assert trace.value == "false"
    assert len(trace.candidates) >= 2

    # Lint
    warnings = engine.lint()
    assert isinstance(warnings, list)

    # Check / require
    assert engine.check(type="tool", id="Read", allow="true") is True
    assert engine.check(type="tool", id="Bash", allow="true") is False

    with pytest.raises(PolicyDenied):
        engine.require(type="tool", id="Bash", allow="true")

    # Save and reload
    db_path = tmp_path / "policy.db"
    engine.save(str(db_path))
    assert db_path.exists()

    engine2 = PolicyEngine.from_db(str(db_path))
    assert engine2.resolve(type="tool", id="Read", property="allow") == "true"
    assert engine2.resolve(type="tool", id="Bash", property="allow") == "false"

    # Raw SQL
    rows = engine2.execute("SELECT COUNT(*) FROM entities")
    assert rows[0][0] >= 4


def test_extend_cow_semantics(tmp_path):
    """Extend produces a new engine; original is unchanged."""
    world_path = tmp_path / "w.world.yml"
    world_path.write_text("entities:\n  - type: tool\n    id: Read\n")
    style_path = tmp_path / "p.umw"
    style_path.write_text("tool { allow: true; }\n")

    engine1 = PolicyEngine.from_files(world=world_path, stylesheet=style_path)
    engine2 = engine1.extend(
        entities=[{"type": "tool", "id": "Bash", "classes": ["dangerous"]}],
        stylesheet="tool.dangerous { allow: false; }",
    )

    # Original unchanged
    tools1 = engine1.resolve_all(type="tool")
    assert len(tools1) == 1

    # Extended has both
    tools2 = engine2.resolve_all(type="tool")
    assert len(tools2) == 2
    assert engine2.resolve(type="tool", id="Bash", property="allow") == "false"


def test_programmatic_construction():
    """Build engine entirely in code."""
    engine = PolicyEngine()
    engine.add_entities([
        {"type": "tool", "id": "Read"},
        {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    ])
    engine.add_stylesheet("tool { allow: true; }\ntool.dangerous { allow: false; }")

    assert engine.resolve(type="tool", id="Read", property="allow") == "true"
    assert engine.resolve(type="tool", id="Bash", property="allow") == "false"


def test_to_files_roundtrip(tmp_path):
    """Export to files and verify they contain expected data."""
    engine = PolicyEngine()
    engine.add_entities([
        {"type": "tool", "id": "Read"},
        {"type": "tool", "id": "Bash", "classes": ["dangerous"]},
    ])
    engine.add_stylesheet("tool { allow: true; }")

    world_out = tmp_path / "out.world.yml"
    style_out = tmp_path / "out.umw"
    engine.to_files(world=world_out, stylesheet=style_out)

    assert world_out.exists()
    assert style_out.exists()

    world_data = yaml.safe_load(world_out.read_text())
    assert len(world_data["entities"]) >= 2
    ids = {e["id"] for e in world_data["entities"]}
    assert "Read" in ids
    assert "Bash" in ids
