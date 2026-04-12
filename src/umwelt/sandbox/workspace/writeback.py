"""Workspace writeback: splice delegate edits back to real files.

Walks the manifest after the delegate finishes and classifies each
entry's state into one of four outcomes: NoOp, Applied, Rejected,
Conflict. Applied changes are written to the real path AFTER all
reconciliation decisions are made (no partial updates on failure).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from umwelt.sandbox.workspace.errors import ViewViolation
from umwelt.sandbox.workspace.manifest import ManifestEntry, WorkspaceManifest


@dataclass(frozen=True)
class NoOp:
    entry: ManifestEntry


@dataclass(frozen=True)
class Applied:
    entry: ManifestEntry
    new_content: bytes


@dataclass(frozen=True)
class Rejected:
    entry: ManifestEntry
    reason: str


@dataclass(frozen=True)
class Conflict:
    entry: ManifestEntry
    reason: str


ReconcileResult = NoOp | Applied | Rejected | Conflict


@dataclass
class WriteBackResult:
    applied: list[Applied] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    noops: list[NoOp] = field(default_factory=list)


class WriteBack:
    def __init__(self, strict: bool = False) -> None:
        self._strict = strict

    def apply_entry(self, entry: ManifestEntry, workspace_root: Path) -> ReconcileResult:
        """Reconcile a single manifest entry."""
        virtual_path = workspace_root / entry.virtual_path
        real_hash_now = _hash_file(entry.real_path)
        real_changed = real_hash_now != entry.content_hash_at_build

        if not entry.writable:
            if real_changed:
                return Rejected(entry, "read-only file was modified during delegate execution")
            return NoOp(entry)

        virtual_hash_now = _hash_file(virtual_path)
        virtual_changed = virtual_hash_now != entry.content_hash_at_build

        if not virtual_changed and not real_changed:
            return NoOp(entry)
        if virtual_changed and not real_changed:
            return Applied(entry, virtual_path.read_bytes())
        if not virtual_changed and real_changed:
            return Conflict(entry, "real file modified externally")
        return Conflict(entry, "both virtual and real modified")

    def apply(self, manifest: WorkspaceManifest) -> WriteBackResult:
        """Reconcile all entries and apply changes atomically."""
        result = WriteBackResult()
        pending_writes: list[tuple[Path, bytes]] = []

        for entry in manifest.entries:
            outcome = self.apply_entry(entry, manifest.workspace_root)
            if isinstance(outcome, NoOp):
                result.noops.append(outcome)
            elif isinstance(outcome, Applied):
                result.applied.append(outcome)
                pending_writes.append((entry.real_path, outcome.new_content))
            elif isinstance(outcome, Rejected):
                result.rejected.append(outcome)
            elif isinstance(outcome, Conflict):
                result.conflicts.append(outcome)

        if self._strict and (result.rejected or result.conflicts):
            reasons = [r.reason for r in result.rejected] + [c.reason for c in result.conflicts]
            raise ViewViolation(f"writeback violations: {'; '.join(reasons)}")

        for real_path, content in pending_writes:
            real_path.write_bytes(content)

        return result


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
