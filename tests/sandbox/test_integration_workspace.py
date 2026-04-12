"""End-to-end integration: parse → build workspace → edit → writeback."""

from __future__ import annotations

from pathlib import Path

from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.entities import ToolEntity
from umwelt.sandbox.state_matcher import StateMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher
from umwelt.sandbox.workspace.builder import WorkspaceBuilder
from umwelt.sandbox.workspace.writeback import Applied, WriteBack

FIXTURES = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(base: Path) -> None:
    """Create a minimal project tree for integration tests."""
    (base / "src" / "auth").mkdir(parents=True)
    (base / "src" / "common").mkdir(parents=True)
    (base / "src" / "auth" / "login.py").write_text("# original login")
    (base / "src" / "common" / "util.py").write_text("# original util")


_TOOLS = [
    ToolEntity(name="Read"),
    ToolEntity(name="Edit"),
    ToolEntity(name="Grep"),
    ToolEntity(name="Glob"),
    ToolEntity(name="Bash"),
    ToolEntity(name="Write"),
]


def _setup_registry(base: Path) -> None:
    """Register sandbox vocabulary + all matchers in the active scope."""
    register_sandbox_vocabulary()
    register_matcher(taxon="world", matcher=WorldMatcher(base_dir=base))
    register_matcher(taxon="capability", matcher=CapabilityMatcher(tools=list(_TOOLS)))
    register_matcher(taxon="state", matcher=StateMatcher())


# ---------------------------------------------------------------------------
# Task 16 Test 1: full workspace lifecycle from auth-fix fixture
# ---------------------------------------------------------------------------


def test_auth_fix_lifecycle(tmp_path):
    """Parse auth-fix.umw → build workspace → edit → writeback → verify."""
    _make_project(tmp_path)
    login_real = tmp_path / "src" / "auth" / "login.py"
    util_real = tmp_path / "src" / "common" / "util.py"

    with registry_scope():
        _setup_registry(tmp_path)
        view = parse(FIXTURES / "auth-fix.umw")

        with WorkspaceBuilder().build(view, tmp_path) as ws:
            # Step 5: verify file strategies
            manifest_by_rel = {
                str(e.real_path.relative_to(tmp_path)): e
                for e in ws.manifest.entries
            }

            # src/auth/login.py → editable: true → copy, not symlink
            auth_entry = manifest_by_rel.get("src/auth/login.py")
            assert auth_entry is not None, "src/auth/login.py must be in manifest"
            assert auth_entry.writable is True
            assert auth_entry.virtual_path.exists()
            assert not auth_entry.virtual_path.is_symlink(), "editable file should be a copy"

            # src/common/util.py → editable: false → symlink
            common_entry = manifest_by_rel.get("src/common/util.py")
            assert common_entry is not None, "src/common/util.py must be in manifest"
            assert common_entry.writable is False
            assert common_entry.virtual_path.is_symlink(), "read-only file should be a symlink"

            # Step 6: modify the writable copy
            auth_entry.virtual_path.write_text("# edited by delegate")

            # Step 7: run writeback
            wb_result = WriteBack().apply(ws.manifest)

        # Step 8: change applied to real src/auth/login.py
        assert login_real.read_text() == "# edited by delegate"
        assert len(wb_result.applied) >= 1
        applied_paths = {a.entry.real_path for a in wb_result.applied}
        assert login_real in applied_paths

        # Step 9: src/common/util.py is unchanged
        assert util_real.read_text() == "# original util"


def test_auth_fix_readonly_file_unmodified(tmp_path):
    """Read-only files under src/common/ pass through writeback as NoOp."""
    _make_project(tmp_path)
    util_real = tmp_path / "src" / "common" / "util.py"

    with registry_scope():
        _setup_registry(tmp_path)
        view = parse(FIXTURES / "auth-fix.umw")

        with WorkspaceBuilder().build(view, tmp_path) as ws:
            # Do NOT modify the symlinked util.py — just writeback
            wb_result = WriteBack().apply(ws.manifest)

        # util.py was not modified, should be a NoOp
        noop_paths = {n.entry.real_path for n in wb_result.noops}
        assert util_real in noop_paths
        assert util_real.read_text() == "# original util"


def test_workspace_context_manager_cleanup(tmp_path):
    """Workspace root is removed after exiting the context manager."""
    _make_project(tmp_path)

    with registry_scope():
        _setup_registry(tmp_path)
        view = parse(FIXTURES / "auth-fix.umw")

        with WorkspaceBuilder().build(view, tmp_path) as ws:
            ws_root = ws.root
            assert ws_root.exists()

    assert not ws_root.exists()


def test_inline_view_lifecycle(tmp_path):
    """Inline view text (not from fixture file) produces correct workspace."""
    _make_project(tmp_path)
    login_real = tmp_path / "src" / "auth" / "login.py"

    view_text = (
        'file[path^="src/"] { editable: false; }\n'
        'file[path^="src/auth/"] { editable: true; }\n'
    )

    with registry_scope():
        _setup_registry(tmp_path)
        view = parse(view_text, validate=False)

        with WorkspaceBuilder().build(view, tmp_path) as ws:
            manifest_by_rel = {
                str(e.real_path.relative_to(tmp_path)): e
                for e in ws.manifest.entries
            }
            auth_entry = manifest_by_rel.get("src/auth/login.py")
            assert auth_entry is not None
            assert auth_entry.writable is True

            # Modify and writeback
            auth_entry.virtual_path.write_text("# inline test edit")
            wb_result = WriteBack().apply(ws.manifest)

    assert login_real.read_text() == "# inline test edit"
    assert isinstance(wb_result.applied[0], Applied)
