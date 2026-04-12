"""Entity wrapper dataclasses for the sandbox vocabulary.

Each entity type the sandbox consumer registers gets a simple frozen
dataclass to carry its attributes. Core umwelt treats these as opaque
handles; the sandbox matchers know how to construct and introspect them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileEntity:
    """A file in the filesystem."""

    path: str
    abs_path: Path
    name: str
    language: str | None = None


@dataclass(frozen=True)
class DirEntity:
    """A directory in the filesystem."""

    path: str
    abs_path: Path
    name: str


@dataclass(frozen=True)
class ResourceEntity:
    """A runtime resource (memory, cpu-time, wall-time, etc.)."""

    kind: str


@dataclass(frozen=True)
class NetworkEntity:
    """A network endpoint."""

    host: str | None = None
    port: int | None = None


@dataclass(frozen=True)
class EnvEntity:
    """An environment variable."""

    name: str


@dataclass(frozen=True)
class MountEntity:
    """A bind mount in the workspace."""

    src: str
    dst: str
    type: str = "bind"
    writable: bool = False


@dataclass(frozen=True)
class ToolEntity:
    """A tool the actor can call."""

    name: str
    kit: str | None = None
    altitude: str | None = None
    level: int = 0


@dataclass(frozen=True)
class KitEntity:
    """A named group of tools."""

    name: str
    version: str | None = None


@dataclass(frozen=True)
class HookEntity:
    """A lifecycle hook."""

    event: str
    phase: str | None = None


@dataclass(frozen=True)
class BudgetEntity:
    """A runtime budget."""

    kind: str


@dataclass(frozen=True)
class JobEntity:
    """An execution run."""

    id: str
    state: str = "pending"
    delegate: bool = False
