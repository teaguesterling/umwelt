"""Filesystem matcher for the world taxon.

Walks a base directory and returns FileEntity / DirEntity instances that
the core selector engine can evaluate attribute selectors against.
Also provides singleton entities for resource, network, and env types.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from umwelt.sandbox.entities import (
    DirEntity,
    EnvEntity,
    FileEntity,
    NetworkEntity,
    ResourceEntity,
    WorldEntity,
)

RESOURCE_KINDS = ("memory", "cpu-time", "wall-time", "max-fds", "tmpfs")


class WorldMatcher:
    """MatcherProtocol implementation for the world taxon."""

    def __init__(
        self,
        base_dir: Path,
        env_vars: list[str] | None = None,
        world_name: str = "default",
    ) -> None:
        self._base_dir = base_dir.resolve()
        self._env_vars = env_vars or []
        self._world_name = world_name
        self._files: list[FileEntity] | None = None
        self._dirs: list[DirEntity] | None = None

    def _scan(self) -> None:
        """Lazily scan the filesystem under base_dir."""
        if self._files is not None:
            return
        files: list[FileEntity] = []
        dirs: list[DirEntity] = []
        for p in sorted(self._base_dir.rglob("*")):
            rel = str(p.relative_to(self._base_dir))
            if p.is_file():
                lang = _guess_language(p.suffix)
                files.append(FileEntity(path=rel, abs_path=p, name=p.name, language=lang))
            elif p.is_dir():
                dirs.append(DirEntity(path=rel, abs_path=p, name=p.name))
        self._files = files
        self._dirs = dirs

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        self._scan()
        if type_name == "world":
            return [WorldEntity(name=self._world_name)]
        if type_name == "file":
            return list(self._files or [])
        if type_name == "dir":
            return list(self._dirs or [])
        if type_name == "resource":
            return [ResourceEntity(kind=k) for k in RESOURCE_KINDS]
        if type_name == "network":
            return [NetworkEntity()]
        if type_name == "env":
            return [EnvEntity(name=n) for n in self._env_vars]
        if type_name == "*":
            result: list[Any] = []
            result.append(WorldEntity(name=self._world_name))
            result.extend(self._files or [])
            result.extend(self._dirs or [])
            result.extend(ResourceEntity(kind=k) for k in RESOURCE_KINDS)
            result.append(NetworkEntity())
            result.extend(EnvEntity(name=n) for n in self._env_vars)
            return result
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        """Return child entities of a parent (dir → file, dir → dir).

        'children' here means all descendants, not just direct children.
        A file under src/auth/ is a descendant of the src dir.
        """
        self._scan()
        if not isinstance(parent, DirEntity):
            return []
        parent_path = parent.abs_path
        if child_type == "file":
            return [
                f
                for f in (self._files or [])
                if str(f.abs_path).startswith(str(parent_path) + "/")
            ]
        if child_type == "dir":
            return [
                d
                for d in (self._dirs or [])
                if str(d.abs_path).startswith(str(parent_path) + "/")
                and d.abs_path != parent_path
            ]
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        # World entities are never used as context qualifiers; world is
        # always the target taxon for sandbox rules.
        return False

    def get_attribute(self, entity: Any, name: str) -> Any:
        return getattr(entity, name, None)

    def get_id(self, entity: Any) -> str | None:
        name = getattr(entity, "name", None)
        if name is not None:
            return str(name)
        kind = getattr(entity, "kind", None)
        if kind is not None:
            return str(kind)
        return None


def _guess_language(suffix: str) -> str | None:
    """Guess the programming language from a file suffix."""
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".rb": "ruby",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".md": "markdown",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
    }
    return mapping.get(suffix)
