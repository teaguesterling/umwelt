"""WorkspaceBuilder: builds a virtual workspace from a resolved view.

The caller is responsible for registering the sandbox vocabulary and a
WorldMatcher (configured with the correct base_dir) before calling
build(). The builder calls core's resolve() to evaluate selectors and
cascade properties, then materializes each matched FileEntity.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from umwelt.ast import View
from umwelt.cascade.resolver import resolve
from umwelt.sandbox.entities import FileEntity
from umwelt.sandbox.workspace.errors import WorkspaceError
from umwelt.sandbox.workspace.manifest import ManifestEntry, WorkspaceManifest
from umwelt.sandbox.workspace.strategy import get_strategy

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """A materialized virtual workspace.

    Use as a context manager to ensure cleanup on exit.
    """

    root: Path
    manifest: WorkspaceManifest
    view: Any  # View — typed as Any to avoid importing at runtime cost
    warnings: list[str] = field(default_factory=list)

    def cleanup(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)

    def __enter__(self) -> Workspace:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.cleanup()


class WorkspaceBuilder:
    """Build a virtual workspace from a parsed View.

    The caller must have registered the sandbox vocabulary and a
    WorldMatcher for the world taxon prior to calling build().
    """

    def __init__(self, strategy: str | None = None) -> None:
        self._strategy_name = strategy or "default"

    def build(self, view: View, base_dir: Path) -> Workspace:
        """Build a virtual workspace from a resolved view.

        Steps:
        1. Create a temp directory as workspace root.
        2. Call resolve(view) to get per-entity properties via cascade.
        3. For each FileEntity in the world taxon, check 'editable'.
        4. Guard against path traversal outside base_dir.
        5. Materialize each file via the configured strategy.
        6. Return a Workspace context manager.
        """
        base_dir = base_dir.resolve()
        ws_root = Path(tempfile.mkdtemp(prefix="umwelt-"))
        strategy = get_strategy(self._strategy_name)

        resolved = resolve(view)
        entries: list[ManifestEntry] = []
        warnings: list[str] = []

        for entity, props in resolved.entries("world"):
            if not isinstance(entity, FileEntity):
                continue

            real_path = entity.abs_path.resolve()

            # Path traversal guard.
            try:
                real_path.relative_to(base_dir)
            except ValueError:
                raise WorkspaceError(
                    f"Resolved path {real_path!r} is outside base_dir {base_dir!r}"
                ) from None

            writable = props.get("editable") == "true"
            rel = real_path.relative_to(base_dir)
            virtual_path = ws_root / rel

            entry = strategy.materialize(real_path, virtual_path, writable=writable)
            entries.append(entry)

        if not entries:
            msg = "No files matched any rule — workspace is empty"
            logger.warning(msg)
            warnings.append(msg)

        manifest = WorkspaceManifest(
            entries=tuple(entries),
            base_dir=base_dir,
            workspace_root=ws_root,
        )
        return Workspace(root=ws_root, manifest=manifest, view=view, warnings=warnings)
