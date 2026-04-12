"""Tests for resolving hook commands via executable entities."""
from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.entities import ExecEntity


def test_resolve_command_with_named_exec():
    """When exec[name='pytest'] { path: '/usr/local/bin/pytest'; } exists,
    resolve_command('pytest') returns '/usr/local/bin/pytest'."""
    rv = ResolvedView()
    rv.add("world", ExecEntity(name="pytest", path="/usr/local/bin/pytest"), {"path": "/usr/local/bin/pytest"})
    from umwelt.sandbox.exec_resolve import resolve_command
    result = resolve_command("pytest", rv)
    assert result == "/usr/local/bin/pytest"


def test_resolve_command_falls_back_to_original():
    """When no named executable matches, return the original command name."""
    rv = ResolvedView()
    rv.add("world", ExecEntity(), {"search-path": "/bin:/usr/bin"})
    from umwelt.sandbox.exec_resolve import resolve_command
    # Without filesystem access, resolve_command returns the original name
    # (search-path resolution requires which-like lookup)
    result = resolve_command("unknown-cmd", rv)
    assert result == "unknown-cmd"


def test_resolve_command_prefers_named_exec():
    """Named executable takes priority over search-path lookup."""
    rv = ResolvedView()
    rv.add("world", ExecEntity(name="bash", path="/bin/bash"), {"path": "/bin/bash"})
    rv.add("world", ExecEntity(), {"search-path": "/usr/bin"})
    from umwelt.sandbox.exec_resolve import resolve_command
    result = resolve_command("bash", rv)
    assert result == "/bin/bash"
