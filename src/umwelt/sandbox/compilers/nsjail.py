"""Compile a resolved umwelt view into nsjail protobuf textproto.

The compiler reads OS-altitude constructs from the resolved view:
- file entities → mount stanzas (bind mounts with rw based on editable)
- mount entities → mount stanzas (direct source/dest mapping)
- resource entities → rlimits and time_limit
- network entities → clone_newnet
- env entities → envar passthrough

Everything else (tools, hooks, actors, state) is silently dropped —
those are enforced at other altitudes.

See docs/vision/compilers/nsjail.md for the full mapping table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from umwelt.cascade.resolver import ResolvedView
from umwelt.compilers.protocol import Altitude
from umwelt.sandbox.compilers._value_parser import (
    parse_memory_mb,
    parse_size_for_tmpfs,
    parse_time_seconds,
)


@dataclass
class NsjailConfig:
    """In-memory representation of the nsjail textproto being built."""

    name: str = "umwelt-sandbox"
    hostname: str = "umwelt"
    time_limit: int | None = None
    clone_newnet: bool = False
    rlimit_as: int | None = None
    rlimit_cpu: int | None = None
    rlimit_nofile: int | None = None
    mounts: list[dict[str, Any]] = field(default_factory=list)
    envars: list[str] = field(default_factory=list)


class NsjailCompiler:
    """Compiler protocol implementation for nsjail."""

    target_name: str = "nsjail"
    target_format: str = "textproto"
    altitude: Altitude = "os"

    def compile(
        self,
        view: ResolvedView,
        workspace_root: str = "/workspace",
        include_system_mounts: bool = True,
    ) -> str:
        cfg = NsjailConfig()
        if include_system_mounts:
            _add_system_mounts(cfg)
        self._compile_world(cfg, view, workspace_root)
        return _emit_textproto(cfg)

    def _compile_world(self, cfg: NsjailConfig, view: ResolvedView, root: str) -> None:
        for entity, props in view.entries("world"):
            entity_type = type(entity).__name__
            if entity_type == "FileEntity":
                self._compile_file(cfg, entity, props, root)
            elif entity_type == "MountEntity":
                self._compile_mount(cfg, entity, props)
            elif entity_type == "ResourceEntity":
                self._compile_resource(cfg, entity, props)
            elif entity_type == "NetworkEntity":
                self._compile_network(cfg, entity, props)
            elif entity_type == "EnvEntity":
                self._compile_env(cfg, entity, props)
            elif entity_type == "ExecEntity":
                self._compile_exec(cfg, entity, props)
            # All other entity types (ToolEntity, HookEntity, etc.) are silently dropped.


    def _compile_file(
        self,
        cfg: NsjailConfig,
        entity: Any,
        props: dict[str, str],
        root: str,
    ) -> None:
        path = getattr(entity, "path", "")
        editable = props.get("editable", "false").lower() == "true"
        dst = path if path.startswith("/") else f"{root}/{path}"
        src = str(getattr(entity, "abs_path", path))
        cfg.mounts.append({
            "src": src,
            "dst": dst,
            "is_bind": True,
            "rw": editable,
        })

    def _compile_mount(
        self,
        cfg: NsjailConfig,
        entity: Any,
        props: dict[str, str],
    ) -> None:
        path = getattr(entity, "path", "")
        source = props.get("source", path)
        readonly = props.get("readonly", "false").lower() == "true"
        mount_type = props.get("type", "bind")
        if mount_type == "tmpfs":
            size = props.get("size", "64MB")
            cfg.mounts.append({
                "dst": path,
                "fstype": "tmpfs",
                "is_bind": False,
                "options": f"size={parse_size_for_tmpfs(size)}",
            })
        else:
            cfg.mounts.append({
                "src": source,
                "dst": path,
                "is_bind": True,
                "rw": not readonly,
            })

    def _compile_resource(
        self,
        cfg: NsjailConfig,
        entity: Any,
        props: dict[str, str],
    ) -> None:
        if props.get("memory"):
            cfg.rlimit_as = parse_memory_mb(props["memory"])
        if props.get("wall-time"):
            cfg.time_limit = parse_time_seconds(props["wall-time"])
        if props.get("cpu-time"):
            cfg.rlimit_cpu = parse_time_seconds(props["cpu-time"])
        if props.get("max-fds"):
            cfg.rlimit_nofile = int(props["max-fds"])
        if props.get("tmpfs"):
            cfg.mounts.append({
                "dst": "/tmp",
                "fstype": "tmpfs",
                "is_bind": False,
                "options": f"size={parse_size_for_tmpfs(props['tmpfs'])}",
            })

    def _compile_network(
        self,
        cfg: NsjailConfig,
        entity: Any,
        props: dict[str, str],
    ) -> None:
        if props.get("deny", "") == "*":
            cfg.clone_newnet = True

    def _compile_env(
        self,
        cfg: NsjailConfig,
        entity: Any,
        props: dict[str, str],
    ) -> None:
        if props.get("allow", "false").lower() == "true":
            name = getattr(entity, "name", "")
            if name:
                cfg.envars.append(name)

    def _compile_exec(
        self,
        cfg: NsjailConfig,
        entity: Any,
        props: dict[str, str],
    ) -> None:
        """Emit PATH envar when a bare (unnamed) exec entity declares search-path."""
        # Only emit PATH for the bare exec entity (no name set).
        # Named exec entities (exec[name='bash']) are used for command resolution,
        # not for PATH emission.
        name = getattr(entity, "name", None)
        if name:
            return
        search_path = props.get("search-path", "")
        if search_path:
            cfg.envars.insert(0, f"PATH={search_path}")


_SYSTEM_MOUNTS = [
    {"src": "/bin", "dst": "/bin", "is_bind": True, "rw": False},
    {"src": "/usr", "dst": "/usr", "is_bind": True, "rw": False},
    {"src": "/lib", "dst": "/lib", "is_bind": True, "rw": False},
    {"src": "/lib64", "dst": "/lib64", "is_bind": True, "rw": False},
    {"src": "/sbin", "dst": "/sbin", "is_bind": True, "rw": False},
    {"dst": "/proc", "fstype": "proc", "is_bind": False},
    {"dst": "/dev", "fstype": "tmpfs", "is_bind": False},
    {"dst": "/tmp", "fstype": "tmpfs", "is_bind": False},
]


def _add_system_mounts(cfg: NsjailConfig) -> None:
    """Add standard read-only system mounts so jailed processes can execute.

    Without these, the jail has no /bin, /usr, /lib — any command fails with
    "No such file or directory". These are always read-only bind mounts for
    system paths, plus proc and tmpfs for /dev and /tmp.
    """
    for mount in _SYSTEM_MOUNTS:
        cfg.mounts.append(dict(mount))


def _emit_textproto(cfg: NsjailConfig) -> str:
    """Hand-roll the textproto output."""
    lines: list[str] = []
    lines.append(f'name: "{cfg.name}"')
    lines.append(f'hostname: "{cfg.hostname}"')
    lines.append("")
    if cfg.time_limit is not None:
        lines.append(f"time_limit: {cfg.time_limit}")
        lines.append("")
    if cfg.clone_newnet:
        lines.append("clone_newnet: true")
        lines.append("")
    if cfg.rlimit_as is not None:
        lines.append(f"rlimit_as: {cfg.rlimit_as}")
        lines.append("rlimit_as_type: SOFT")
        lines.append("")
    if cfg.rlimit_cpu is not None:
        lines.append(f"rlimit_cpu: {cfg.rlimit_cpu}")
        lines.append("")
    if cfg.rlimit_nofile is not None:
        lines.append(f"rlimit_nofile: {cfg.rlimit_nofile}")
        lines.append("")
    for mount in cfg.mounts:
        lines.append("mount {")
        if "src" in mount:
            lines.append(f'  src: "{mount["src"]}"')
        lines.append(f'  dst: "{mount["dst"]}"')
        if "fstype" in mount:
            lines.append(f'  fstype: "{mount["fstype"]}"')
        lines.append(f'  is_bind: {"true" if mount.get("is_bind") else "false"}')
        if mount.get("rw") is not None:
            lines.append(f'  rw: {"true" if mount["rw"] else "false"}')
        if "options" in mount:
            lines.append(f'  options: "{mount["options"]}"')
        lines.append("}")
        lines.append("")
    for var in cfg.envars:
        lines.append(f'envar: "{var}"')
    return "\n".join(lines).strip() + "\n"
