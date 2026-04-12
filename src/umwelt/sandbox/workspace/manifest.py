"""Workspace manifest: tracks virtual ↔ real path mappings with content hashes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManifestEntry:
    """One entry in the workspace manifest."""

    real_path: Path
    virtual_path: Path
    writable: bool
    content_hash_at_build: str
    strategy_name: str


@dataclass(frozen=True)
class WorkspaceManifest:
    """The full manifest for a built workspace."""

    entries: tuple[ManifestEntry, ...]
    base_dir: Path
    workspace_root: Path
