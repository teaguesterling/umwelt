"""Dry-run resolver: print per-entity resolved properties."""

from __future__ import annotations

from umwelt.ast import View
from umwelt.cascade.resolver import resolve


def format_dry_run(view: View) -> str:
    lines: list[str] = []
    resolved = resolve(view)
    taxa = resolved.taxa()
    if not taxa:
        lines.append("(no matches)")
        return "\n".join(lines)
    for taxon in sorted(taxa):
        entries = list(resolved.entries(taxon))
        lines.append(f"# {taxon} ({len(entries)} entities)")
        for entity, properties in entries:
            ident = getattr(entity, "id", None) or getattr(entity, "name", None) or repr(entity)
            lines.append(f"  {ident}")
            for prop_name in sorted(properties):
                lines.append(f"    {prop_name}: {properties[prop_name]}")
        lines.append("")
    return "\n".join(lines)
