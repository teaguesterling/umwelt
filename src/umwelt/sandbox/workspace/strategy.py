"""Materialization strategies for workspace construction.

The strategy determines HOW files enter the virtual workspace:
- Read-only: symlink (cheap, reflects external changes)
- Writable: copy (isolates delegate edits from real tree)

SHA-256 hashes are captured at build time for BOTH modes so writeback
can detect violations (read-only files modified) and conflicts (real
files modified externally during delegate execution).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Protocol

from umwelt.sandbox.workspace.manifest import ManifestEntry


class MaterializationStrategy(Protocol):
    """How files are materialized in the virtual workspace."""

    name: str

    def materialize(self, real: Path, virtual: Path, writable: bool) -> ManifestEntry:
        """Create the virtual entry and return a manifest entry with hash."""
        ...

    def reconcile(self, entry: ManifestEntry, workspace_root: Path) -> Any:
        """Compare virtual state to real state after delegate execution."""
        ...


class SymlinkReadonlyCopyWritable:
    """Default strategy: symlink read-only, copy writable, hash both."""

    name = "default"

    def materialize(self, real: Path, virtual: Path, writable: bool) -> ManifestEntry:
        virtual.parent.mkdir(parents=True, exist_ok=True)
        content_hash = _hash_file(real)
        if writable:
            shutil.copy2(real, virtual)
        else:
            virtual.symlink_to(real.resolve())
        return ManifestEntry(
            real_path=real,
            virtual_path=virtual,
            writable=writable,
            content_hash_at_build=content_hash,
            strategy_name=self.name,
        )

    def reconcile(self, entry: ManifestEntry, workspace_root: Path) -> Any:
        # Implemented in Task 11 (writeback).
        raise NotImplementedError("reconcile is implemented in writeback")


_STRATEGIES: dict[str, MaterializationStrategy] = {}


def register_strategy(strategy: MaterializationStrategy) -> None:
    _STRATEGIES[strategy.name] = strategy


def get_strategy(name: str) -> MaterializationStrategy:
    if name not in _STRATEGIES:
        if name == "default":
            default = SymlinkReadonlyCopyWritable()
            _STRATEGIES["default"] = default
            return default
        raise KeyError(f"strategy {name!r} not registered")
    return _STRATEGIES[name]


def _hash_file(path: Path) -> str:
    """SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
