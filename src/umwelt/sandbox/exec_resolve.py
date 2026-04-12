"""Resolve command names to absolute paths via executable entities in a ResolvedView."""

from __future__ import annotations

from umwelt.cascade.resolver import ResolvedView


def resolve_command(command: str, view: ResolvedView) -> str:
    """Resolve a command name to an absolute path using executable entities.

    Resolution order:
    1. Named executable entity with matching name -> use its path property
    2. Fall back to the original command name (let the jail's PATH handle it)

    The search-path property on the bare executable entity is consumed by the
    compiler (emitted as PATH envar), not resolved here. The jail's own
    PATH lookup handles resolution at runtime.
    """
    for entity, props in view.entries("world"):
        if type(entity).__name__ != "ExecEntity":
            continue
        name = getattr(entity, "name", None)
        if name and name == command:
            path = props.get("path") or getattr(entity, "path", None)
            if path:
                return path
    return command
