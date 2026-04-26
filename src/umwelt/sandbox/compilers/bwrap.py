"""Compile a resolved umwelt view into bwrap argv list.

The compiler reads OS-altitude constructs from the resolved view and emits
a flat list of bwrap command-line flags. Budget enforcement that bwrap
can't express natively (memory, cpu-time, max-fds) goes into a separate
wrapper command list (prlimit/timeout).

Ordering per bwrap spec:
  clearenv -> setenv -> binds/tmpfs -> unshare-net

See docs/vision/compilers/bwrap.md for the full mapping table.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from umwelt.cascade.resolver import ResolvedView
from umwelt.compilers.protocol import Altitude
from umwelt.sandbox.compilers._value_parser import (
    parse_memory_mb,
    parse_size_for_tmpfs,
    parse_time_seconds,
)

_SYSTEM_BIND_PATHS = ["/bin", "/usr", "/lib", "/lib64", "/sbin"]


@dataclass
class BwrapCompilation:
    """Two-piece output: bwrap argv flags + wrapper commands for budget."""

    argv: list[str] = field(default_factory=list)
    wrapper: list[str] = field(default_factory=list)


class BwrapCompiler:
    """Compiler protocol implementation for bwrap (bubblewrap)."""

    target_name: str = "bwrap"
    target_format: str = "argv"
    altitude: Altitude = "os"

    def compile(
        self,
        view: ResolvedView,
        workspace_root: str = "/workspace",
        include_system_mounts: bool = True,
    ) -> dict[str, Any]:
        """Compile to a dict with 'argv' and 'wrapper' keys.

        Satisfies the Compiler protocol (returns dict).
        """
        result = self.compile_full(view, workspace_root, include_system_mounts)
        return {"argv": result.argv, "wrapper": result.wrapper}

    def compile_full(
        self,
        view: ResolvedView,
        workspace_root: str = "/workspace",
        include_system_mounts: bool = True,
    ) -> BwrapCompilation:
        """Compile to a BwrapCompilation with typed access."""
        result = BwrapCompilation()

        # Accumulators for ordered emission
        env_setenvs: list[tuple[str, str]] = []  # (name, value)
        binds: list[tuple[str, str, str]] = []    # (flag, src, dst)
        tmpfs_flags: list[tuple[str, ...]] = []
        unshare_flags: list[str] = []

        for entity, props in view.entries("world"):
            entity_type = type(entity).__name__
            if entity_type == "FileEntity":
                self._collect_file(binds, entity, props, workspace_root)
            elif entity_type == "MountEntity":
                self._collect_mount(binds, tmpfs_flags, entity, props)
            elif entity_type == "ResourceEntity":
                self._collect_resource(result, tmpfs_flags, entity, props)
            elif entity_type == "NetworkEntity":
                self._collect_network(unshare_flags, entity, props)
            elif entity_type == "EnvEntity":
                self._collect_env(env_setenvs, entity, props)
            elif entity_type == "ExecEntity":
                self._collect_exec(env_setenvs, entity, props)
            # All other entity types (ToolEntity, HookEntity, etc.) are silently dropped.

        # Emit in spec ordering: clearenv -> setenv -> binds -> tmpfs -> unshare
        result.argv.append("--clearenv")

        for name, value in env_setenvs:
            result.argv.extend(["--setenv", name, value])

        if include_system_mounts:
            for path in _SYSTEM_BIND_PATHS:
                result.argv.extend(["--ro-bind", path, path])

        for flag, src, dst in binds:
            result.argv.extend([flag, src, dst])

        for parts in tmpfs_flags:
            result.argv.extend(parts)

        result.argv.extend(unshare_flags)

        return result

    def _collect_file(
        self,
        binds: list[tuple[str, str, str]],
        entity: Any,
        props: dict[str, str],
        root: str,
    ) -> None:
        path = getattr(entity, "path", "")
        editable = props.get("editable", "false").lower() == "true"
        dst = path if path.startswith("/") else f"{root}/{path}"
        src = str(getattr(entity, "abs_path", path))
        flag = "--bind" if editable else "--ro-bind"
        binds.append((flag, src, dst))

    def _collect_mount(
        self,
        binds: list[tuple[str, str, str]],
        tmpfs_flags: list[tuple[str, ...]],
        entity: Any,
        props: dict[str, str],
    ) -> None:
        path = getattr(entity, "path", "")
        source = props.get("source", path)
        readonly = props.get("readonly", "false").lower() == "true"
        mount_type = props.get("type", "bind")
        if mount_type == "tmpfs":
            size = props.get("size", "64MB")
            tmpfs_flags.append(("--tmpfs", path, f"--size={parse_size_for_tmpfs(size)}"))
        else:
            flag = "--ro-bind" if readonly else "--bind"
            binds.append((flag, source, path))

    def _collect_resource(
        self,
        result: BwrapCompilation,
        tmpfs_flags: list[tuple[str, ...]],
        entity: Any,
        props: dict[str, str],
    ) -> None:
        if props.get("memory"):
            bytes_val = parse_memory_mb(props["memory"]) * 1024 * 1024
            result.wrapper.extend(["prlimit", f"--as={bytes_val}"])
        if props.get("wall-time"):
            secs = parse_time_seconds(props["wall-time"])
            result.wrapper.extend(["timeout", str(secs)])
        if props.get("cpu-time"):
            secs = parse_time_seconds(props["cpu-time"])
            result.wrapper.extend(["prlimit", f"--cpu={secs}"])
        if props.get("max-fds"):
            result.wrapper.extend(["prlimit", f"--nofile={int(props['max-fds'])}"])
        if props.get("tmpfs"):
            tmpfs_flags.append(("--tmpfs", "/tmp", f"--size={parse_size_for_tmpfs(props['tmpfs'])}"))

    def _collect_network(
        self,
        unshare_flags: list[str],
        entity: Any,
        props: dict[str, str],
    ) -> None:
        if props.get("deny", "") == "*":
            unshare_flags.append("--unshare-net")

    def _collect_env(
        self,
        env_setenvs: list[tuple[str, str]],
        entity: Any,
        props: dict[str, str],
    ) -> None:
        if props.get("allow", "false").lower() == "true":
            name = getattr(entity, "name", "")
            if name:
                value = os.environ.get(name, "")
                env_setenvs.append((name, value))

    def _collect_exec(
        self,
        env_setenvs: list[tuple[str, str]],
        entity: Any,
        props: dict[str, str],
    ) -> None:
        search_path = props.get("search-path", "")
        if search_path:
            # Insert PATH at the beginning of setenvs
            env_setenvs.insert(0, ("PATH", search_path))
