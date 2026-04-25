"""Tests for the nsjail compiler."""

from __future__ import annotations

from pathlib import Path

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.nsjail import NsjailCompiler
from umwelt.sandbox.entities import (
    EnvEntity,
    FileEntity,
    HookEntity,
    NetworkEntity,
    ResourceEntity,
    ToolEntity,
)

# ---------------------------------------------------------------------------
# Task 0: mount emission from file entities
# ---------------------------------------------------------------------------


def test_file_editable_true_emits_rw_mount():
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="src/auth/login.py", abs_path=Path("/project/src/auth/login.py"), name="login.py"),
        {"editable": "true"},
    )
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert 'src: "/project/src/auth/login.py"' in output
    assert 'dst: "/workspace/src/auth/login.py"' in output
    assert "rw: true" in output


def test_file_editable_false_emits_ro_mount():
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="src/common/util.py", abs_path=Path("/project/src/common/util.py"), name="util.py"),
        {"editable": "false"},
    )
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert "rw: false" in output


def test_absolute_path_mirrors():
    rv = ResolvedView()
    rv.add(
        "world",
        FileEntity(path="/tmp/work/data.txt", abs_path=Path("/tmp/work/data.txt"), name="data.txt"),
        {"editable": "true"},
    )
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert 'dst: "/tmp/work/data.txt"' in output


def test_empty_view_emits_minimal_config():
    rv = ResolvedView()
    compiler = NsjailCompiler()
    output = compiler.compile(rv)
    assert 'name: "umwelt-sandbox"' in output
    assert 'hostname: "umwelt"' in output


# ---------------------------------------------------------------------------
# Task 1: network, resource limits, env passthrough, altitude filtering
# ---------------------------------------------------------------------------


def test_network_deny_all_emits_clone_newnet():
    rv = ResolvedView()
    rv.add("world", NetworkEntity(), {"deny": "*"})
    output = NsjailCompiler().compile(rv)
    assert "clone_newnet: true" in output


def test_network_no_deny_does_not_emit_clone_newnet():
    rv = ResolvedView()
    rv.add("world", NetworkEntity(), {"deny": "none"})
    output = NsjailCompiler().compile(rv)
    assert "clone_newnet" not in output


def test_memory_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(), {"memory": "512MB"})
    output = NsjailCompiler().compile(rv)
    assert "rlimit_as: 512" in output
    assert "rlimit_as_type: SOFT" in output


def test_wall_time_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(), {"wall-time": "60s"})
    output = NsjailCompiler().compile(rv)
    assert "time_limit: 60" in output


def test_wall_time_limit_minutes():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(), {"wall-time": "5m"})
    output = NsjailCompiler().compile(rv)
    assert "time_limit: 300" in output


def test_cpu_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(), {"cpu": "30s"})
    output = NsjailCompiler().compile(rv)
    assert "rlimit_cpu: 30" in output


def test_max_fds_limit():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(), {"max-fds": "128"})
    output = NsjailCompiler().compile(rv)
    assert "rlimit_nofile: 128" in output


def test_tmpfs_resource():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(), {"tmpfs": "64MB"})
    output = NsjailCompiler().compile(rv)
    assert 'fstype: "tmpfs"' in output
    assert 'options: "size=64M"' in output


def test_resource_without_limits_is_skipped():
    rv = ResolvedView()
    rv.add("world", ResourceEntity(), {})
    output = NsjailCompiler().compile(rv)
    assert "rlimit_as" not in output


def test_env_allow():
    rv = ResolvedView()
    rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
    rv.add("world", EnvEntity(name="PYTHONPATH"), {"allow": "true"})
    output = NsjailCompiler().compile(rv)
    assert 'envar: "CI"' in output
    assert 'envar: "PYTHONPATH"' in output


def test_env_deny_emits_nothing():
    rv = ResolvedView()
    rv.add("world", EnvEntity(name="SECRET"), {"allow": "false"})
    output = NsjailCompiler().compile(rv)
    assert "SECRET" not in output


def test_tools_silently_dropped():
    rv = ResolvedView()
    rv.add("capability", ToolEntity(name="Bash"), {"allow": "false"})
    output = NsjailCompiler().compile(rv)
    assert "Bash" not in output


def test_hooks_silently_dropped():
    rv = ResolvedView()
    rv.add("state", HookEntity(event="after-change"), {"run": "pytest"})
    output = NsjailCompiler().compile(rv)
    assert "pytest" not in output


def test_unknown_world_entities_silently_dropped():
    """Entities with unknown types in world taxon are ignored without error."""
    from umwelt.sandbox.entities import KitEntity

    rv = ResolvedView()
    rv.add("world", KitEntity(name="my-kit"), {"version": "1.0"})
    output = NsjailCompiler().compile(rv)
    assert "my-kit" not in output


# ---------------------------------------------------------------------------
# Task 2: Full textproto document — the worked example
# ---------------------------------------------------------------------------


def test_full_worked_example():
    """The worked example from docs/vision/compilers/nsjail.md."""
    rv = ResolvedView()
    rv.add("world", FileEntity(path="src/auth", abs_path=Path("src/auth"), name="auth"), {"editable": "true"})
    rv.add("world", FileEntity(path="src/common", abs_path=Path("src/common"), name="common"), {"editable": "false"})
    rv.add("world", FileEntity(path="/tmp/work", abs_path=Path("/tmp/work"), name="work"), {"editable": "true"})
    rv.add("world", NetworkEntity(), {"deny": "*"})
    rv.add("world", ResourceEntity(), {"memory": "512MB", "wall-time": "60s", "tmpfs": "64MB"})
    rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
    # These should be silently dropped:
    rv.add("capability", ToolEntity(name="Read"), {"allow": "true"})
    rv.add("state", HookEntity(event="after-change"), {"run": "pytest"})

    output = NsjailCompiler().compile(rv)

    # Verify key sections present
    assert 'name: "umwelt-sandbox"' in output
    assert "time_limit: 60" in output
    assert "clone_newnet: true" in output
    assert "rlimit_as: 512" in output
    # Three mounts: src/auth (rw), src/common (ro), /tmp/work (rw), plus tmpfs /tmp
    assert output.count("mount {") == 12  # 8 system + 3 files + 1 tmpfs
    assert 'envar: "CI"' in output
    # Tools and hooks NOT in output
    assert "Read" not in output
    assert "pytest" not in output
