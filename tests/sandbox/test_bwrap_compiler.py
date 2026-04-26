"""Tests for the bwrap compiler."""
from pathlib import Path

from umwelt.cascade.resolver import ResolvedView
from umwelt.sandbox.compilers.bwrap import BwrapCompiler
from umwelt.sandbox.entities import (
    EnvEntity,
    ExecEntity,
    MountEntity,
    NetworkEntity,
    ResourceEntity,
)


class TestBwrapMounts:
    def test_bind_mount_from_mount_entity(self):
        rv = ResolvedView()
        rv.add("world", MountEntity(path="/workspace/src"), {"source": "./src", "readonly": "false"})
        result = BwrapCompiler().compile_full(rv)
        assert "--bind" in result.argv
        idx = result.argv.index("--bind")
        assert result.argv[idx + 1] == "./src"
        assert result.argv[idx + 2] == "/workspace/src"

    def test_readonly_mount(self):
        rv = ResolvedView()
        rv.add("world", MountEntity(path="/workspace/tests"), {"source": "./tests", "readonly": "true"})
        result = BwrapCompiler().compile_full(rv)
        assert "--ro-bind" in result.argv

    def test_file_editable_true(self):
        from umwelt.sandbox.entities import FileEntity
        rv = ResolvedView()
        rv.add("world", FileEntity(
            path="src/auth/login.py",
            abs_path=Path("/project/src/auth/login.py"),
            name="login.py",
        ), {"editable": "true"})
        result = BwrapCompiler().compile_full(rv)
        assert "--bind" in result.argv
        idx = result.argv.index("--bind")
        assert result.argv[idx + 1] == "/project/src/auth/login.py"
        assert result.argv[idx + 2] == "/workspace/src/auth/login.py"

    def test_file_editable_false(self):
        from umwelt.sandbox.entities import FileEntity
        rv = ResolvedView()
        rv.add("world", FileEntity(
            path="src/common/util.py",
            abs_path=Path("/project/src/common/util.py"),
            name="util.py",
        ), {"editable": "false"})
        result = BwrapCompiler().compile_full(rv)
        assert "--ro-bind" in result.argv

    def test_absolute_path_mirrors(self):
        rv = ResolvedView()
        rv.add("world", MountEntity(path="/tmp/work"), {"source": "/tmp/work", "readonly": "false"})
        result = BwrapCompiler().compile_full(rv)
        idx = result.argv.index("--bind")
        assert result.argv[idx + 1] == "/tmp/work"
        assert result.argv[idx + 2] == "/tmp/work"


class TestBwrapEnv:
    def test_clearenv_when_no_explicit_allows(self):
        rv = ResolvedView()
        # No env entities means deny-all default
        result = BwrapCompiler().compile_full(rv)
        assert "--clearenv" in result.argv

    def test_setenv_for_allowed_vars(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        rv = ResolvedView()
        rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
        result = BwrapCompiler().compile_full(rv)
        assert "--setenv" in result.argv
        idx = result.argv.index("--setenv")
        assert result.argv[idx + 1] == "CI"
        assert result.argv[idx + 2] == "true"

    def test_clearenv_before_setenv(self, monkeypatch):
        """--clearenv must come before --setenv in the argv."""
        monkeypatch.setenv("CI", "true")
        rv = ResolvedView()
        rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
        result = BwrapCompiler().compile_full(rv)
        clearenv_idx = result.argv.index("--clearenv")
        setenv_idx = result.argv.index("--setenv")
        assert clearenv_idx < setenv_idx

    def test_path_from_exec_entity(self):
        rv = ResolvedView()
        rv.add("world", ExecEntity(), {"search-path": "/bin:/usr/bin"})
        result = BwrapCompiler().compile_full(rv)
        # PATH is emitted as --setenv PATH ...
        idx = [i for i, v in enumerate(result.argv) if v == "--setenv" and result.argv[i + 1] == "PATH"]
        assert len(idx) == 1
        assert result.argv[idx[0] + 2] == "/bin:/usr/bin"


class TestBwrapOrdering:
    """Verify the ordering spec: clearenv -> setenv -> binds -> unshare."""

    def test_ordering_clearenv_before_setenv_before_bind_before_unshare(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        rv = ResolvedView()
        rv.add("world", EnvEntity(name="CI"), {"allow": "true"})
        rv.add("world", MountEntity(path="/workspace/src"), {"source": "./src"})
        rv.add("world", NetworkEntity(), {"deny": "*"})
        result = BwrapCompiler().compile_full(rv)

        clearenv_idx = result.argv.index("--clearenv")
        setenv_idx = result.argv.index("--setenv")
        bind_idx = result.argv.index("--ro-bind")
        unshare_idx = result.argv.index("--unshare-net")

        assert clearenv_idx < setenv_idx < bind_idx < unshare_idx


class TestBwrapResourceLimits:
    def test_memory_limit_emits_prlimit(self):
        rv = ResolvedView()
        rv.add("world", ResourceEntity(), {"memory": "512MB"})
        result = BwrapCompiler().compile_full(rv)
        assert "prlimit" in result.wrapper
        assert "--as=536870912" in result.wrapper  # 512 * 1024 * 1024

    def test_wall_time_emits_timeout(self):
        rv = ResolvedView()
        rv.add("world", ResourceEntity(), {"wall-time": "60s"})
        result = BwrapCompiler().compile_full(rv)
        assert "timeout" in result.wrapper
        assert "60" in result.wrapper

    def test_cpu_time_emits_prlimit_cpu(self):
        rv = ResolvedView()
        rv.add("world", ResourceEntity(), {"cpu-time": "30s"})
        result = BwrapCompiler().compile_full(rv)
        assert "prlimit" in result.wrapper
        assert "--cpu=30" in result.wrapper

    def test_max_fds_emits_prlimit_nofile(self):
        rv = ResolvedView()
        rv.add("world", ResourceEntity(), {"max-fds": "128"})
        result = BwrapCompiler().compile_full(rv)
        assert "--nofile=128" in result.wrapper

    def test_tmpfs_resource_emits_bwrap_flag(self):
        rv = ResolvedView()
        rv.add("world", ResourceEntity(), {"tmpfs": "64MB"})
        result = BwrapCompiler().compile_full(rv)
        assert "--tmpfs" in result.argv
        assert "/tmp" in result.argv

    def test_network_deny_all_emits_unshare_net(self):
        rv = ResolvedView()
        rv.add("world", NetworkEntity(), {"deny": "*"})
        result = BwrapCompiler().compile_full(rv)
        assert "--unshare-net" in result.argv

    def test_tools_silently_dropped(self):
        from umwelt.sandbox.entities import ToolEntity
        rv = ResolvedView()
        rv.add("capability", ToolEntity(name="Bash"), {"allow": "false"})
        result = BwrapCompiler().compile_full(rv, include_system_mounts=False)
        assert result.argv == ["--clearenv"]  # only the default clearenv
        assert result.wrapper == []

    def test_full_worked_example(self, monkeypatch):
        """The worked example from docs/vision/compilers/bwrap.md."""
        monkeypatch.setenv("CI", "true")
        rv = ResolvedView()
        rv.add("world", MountEntity(path="/workspace/src/auth"), {"source": "src/auth", "readonly": "false"})
        rv.add("world", MountEntity(path="/workspace/src/common"), {"source": "src/common", "readonly": "true"})
        rv.add("world", MountEntity(path="/tmp/work"), {"source": "/tmp/work", "readonly": "false"})
        rv.add("world", NetworkEntity(), {"deny": "*"})
        rv.add("world", ResourceEntity(), {"memory": "512MB", "wall-time": "60s", "tmpfs": "64MB"})
        rv.add("world", EnvEntity(name="CI"), {"allow": "true"})

        result = BwrapCompiler().compile_full(rv)

        # Verify binds
        assert "--bind" in result.argv
        assert "--ro-bind" in result.argv
        # Verify network
        assert "--unshare-net" in result.argv
        # Verify env
        assert "--clearenv" in result.argv
        assert "--setenv" in result.argv
        # Verify tmpfs
        assert "--tmpfs" in result.argv
        # Verify wrapper
        assert "timeout" in result.wrapper
        assert "prlimit" in result.wrapper
