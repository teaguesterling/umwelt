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
    """A resource block declaring runtime limits (memory, wall-time, cpu, etc.)."""


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
class WorldEntity:
    """A named environment (root of the world hierarchy)."""

    name: str


@dataclass(frozen=True)
class MountEntity:
    """A bind mount or tmpfs in the workspace."""

    path: str
    source: str | None = None
    type: str = "bind"
    readonly: bool = False


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
class ModeEntity:
    """A regulation mode (S3).

    Modes are named instances authored via ID selectors: `mode#review`,
    `mode#implement`. Classes remain for categories: `mode#review.read-only`.

    In v0.5, modes are always "active" as cross-axis context qualifiers —
    runtime mode-filtering (only fire rules whose mode ID matches the
    current mode) is a v0.6+ concern coordinated with kibitzer's
    `ChangeToolMode`.
    """

    id: str | None = None
    name: str | None = None
    classes: tuple[str, ...] = ()


@dataclass(frozen=True)
class JobEntity:
    """An execution run."""

    id: str
    state: str = "pending"
    delegate: bool = False


@dataclass(frozen=True)
class InferencerEntity:
    """A language model / inferencer."""

    model: str | None = None
    kit: str | None = None
    temperature: float | None = None


@dataclass(frozen=True)
class ExecutorEntity:
    """An executor (tool runner)."""

    tool_name: str | None = None
    altitude: str | None = None


@dataclass(frozen=True)
class ExecEntity:
    """An executable binary available inside the jail."""

    name: str | None = None
    path: str | None = None
    search_path: str | None = None


@dataclass(frozen=True)
class UseEntity:
    """A permissioned projection of a world entity into the action axis.

    `of` is the target world entity selector, stored as the raw string
    (e.g. 'file#/src/auth.py'). `of_kind` and `of_like` are kind/prefix
    forms captured from of-kind= / of-like= attributes.

    Permissions (editable, visible, allow, deny, show) land on use
    entities during cascade resolution, not on the world entities
    themselves. See docs/vision/evaluation-framework.md claim A5.
    """

    of: str | None = None
    of_kind: str | None = None
    of_like: str | None = None


@dataclass(frozen=True)
class PrincipalEntity:
    """The commissioning principal (S5 — identity axis).

    Carries name (id-like), intent (why), grade (optional Ma-grade 0-4).
    Principals appear as the outermost qualifier in selectors:
        principal#Teague use[of="file#X"] { editable: true; }
    """
    name: str | None = None


@dataclass(frozen=True)
class ObservationEntity:
    """An observation entry emitted by a Layer-2 observer (blq, ratchet-detect).

    Lives in the audit taxon (S3*) — outside the world the delegate occupies.
    """
    name: str | None = None


@dataclass(frozen=True)
class ManifestEntity:
    """A workspace manifest reference in the audit taxon."""
    name: str | None = None
