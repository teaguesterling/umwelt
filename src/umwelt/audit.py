"""Security-aware audit: per-entity resolved policy with source attribution.

The audit engine walks the parsed view and for each (rule group, property)
reports:
- The winning value (from cascade resolution when matchers are available,
  or the last-declared value from raw rules as a fallback)
- The source rule (line number, specificity)
- Any widening warnings
- Enforcement coverage per compiler

Design note: Unlike dry-run (which requires live matchers to resolve
entities), the audit engine works in two modes:
  1. If live matchers are registered for a taxon, entities are resolved
     via the cascade resolver and we get real entity instances.
  2. If no matcher is registered (e.g. in tests or offline contexts),
     the engine falls back to raw rule scanning and reports synthetic
     entity summaries keyed by (taxon, type_name, rule_index).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from umwelt.ast import View
from umwelt.compilers import available, get
from umwelt.registry.properties import PropertySchema, RestrictiveDirection

# Legacy fallback for properties registered before restrictive_direction existed.
_WIDENING_TRANSITIONS: dict[str, list[tuple[str, str]]] = {
    "editable": [("false", "true")],
    "allow": [("false", "true")],
    "visible": [("false", "true")],
    "deny": [("*", "")],  # removing deny = widening
}


def is_widening(
    old_value: str,
    new_value: str,
    *,
    prop_schema: PropertySchema | None = None,
    prop_name: str = "",
) -> bool:
    """Determine if a value transition is widening (more permissive).

    Uses restrictive_direction from PropertySchema when available,
    falls back to the legacy _WIDENING_TRANSITIONS table.
    """
    direction = prop_schema.restrictive_direction if prop_schema else None
    if direction is not None:
        return _is_widening_by_direction(old_value, new_value, direction)
    name = prop_schema.name if prop_schema else prop_name
    if name in _WIDENING_TRANSITIONS:
        return any(
            old_value == r and new_value == p
            for r, p in _WIDENING_TRANSITIONS[name]
        )
    return False


def _is_widening_by_direction(
    old_value: str, new_value: str, direction: RestrictiveDirection
) -> bool:
    if direction == "false":
        return old_value == "false" and new_value == "true"
    if direction == "true":
        return old_value == "true" and new_value == "false"
    if direction == "min":
        try:
            return float(new_value) > float(old_value)
        except ValueError:
            return False
    if direction == "max":
        try:
            return float(new_value) < float(old_value)
        except ValueError:
            return False
    if direction == "subset":
        return not set(new_value.split()) <= set(old_value.split())
    if direction == "superset":
        return set(new_value.split()) < set(old_value.split())
    return False


@dataclass
class PropertyAttribution:
    """A resolved property value with its source."""

    property_name: str
    value: str
    source_line: int
    specificity: tuple[int, ...]
    is_widening: bool = False
    widened_from_line: int | None = None


@dataclass
class EntityAudit:
    """Audit result for a single entity (or rule group in fallback mode)."""

    entity: Any
    taxon: str
    properties: list[PropertyAttribution] = field(default_factory=list)


@dataclass
class AuditReport:
    """Full audit report."""

    entities: list[EntityAudit] = field(default_factory=list)
    enforcement_coverage: dict[str, list[str]] = field(default_factory=dict)
    widening_count: int = 0


def audit_view(view: View, world: str | None = None) -> AuditReport:
    """Produce an audit report for a parsed view.

    Attempts live resolution via the cascade resolver. If no matchers are
    registered for a taxon (e.g. in offline/test contexts), falls back to
    raw rule scanning and reports synthetic entity summaries.
    """
    report = AuditReport()

    # Try live resolution first; fall back to raw rule scan on RegistryError.
    try:
        from umwelt.cascade.resolver import resolve

        resolved = resolve(view, world=world)
        for taxon in resolved.taxa():
            for entity, props in resolved.entries(taxon):
                ea = EntityAudit(entity=entity, taxon=taxon)
                for prop_name, value in props.items():
                    attr = PropertyAttribution(
                        property_name=prop_name,
                        value=value,
                        source_line=_find_source_line(view, taxon, prop_name),
                        specificity=(0, 0, 0),
                    )
                    ea.properties.append(attr)
                report.entities.append(ea)
    except Exception:
        # Fall back: scan raw rules and synthesize entity summaries.
        _collect_from_raw_rules(view, world, report)

    # Detect widenings across raw rules (always, regardless of resolution mode).
    widenings = _detect_widening(view)

    # Annotate property attributions with widening flags.
    for ea in report.entities:
        for attr in ea.properties:
            if attr.property_name in widenings:
                for prev_line, later_line, _ in widenings[attr.property_name]:
                    if attr.source_line == later_line:
                        attr.is_widening = True
                        attr.widened_from_line = prev_line
                        report.widening_count += 1

    # If no entities were resolved but widenings exist, still count them.
    if not report.entities and widenings:
        for _prop, transitions in widenings.items():
            report.widening_count += len(transitions)

    # Enforcement coverage.
    compilers = available()
    for name in compilers:
        compiler = get(name)
        report.enforcement_coverage[name] = [compiler.altitude]

    return report


def _collect_from_raw_rules(
    view: View, world: str | None, report: AuditReport
) -> None:
    """Fallback: build entity summaries from raw rule declarations.

    Groups rules by (taxon, type_name) and collects declared properties.
    Last-write wins per property (document order).
    """
    # Per (taxon, type_name): dict of prop -> (value, line)
    groups: dict[tuple[str, str], dict[str, tuple[str, int]]] = {}

    for rule in view.rules:
        for sel in rule.selectors:
            taxon = sel.target_taxon
            # Determine a display type name from the first structural part.
            type_name = "*"
            for part in sel.parts:
                if part.selector.type_name:
                    type_name = part.selector.type_name
                    break
            key = (taxon, type_name)
            props = groups.setdefault(key, {})
            for decl in rule.declarations:
                value = decl.values[0] if decl.values else ""
                props[decl.property_name] = (value, decl.span.line)

    for (taxon, type_name), props in groups.items():
        # Synthetic entity: a plain dict for display purposes.
        entity = {"taxon": taxon, "type": type_name}
        ea = EntityAudit(entity=entity, taxon=taxon)
        for prop_name, (value, line) in props.items():
            attr = PropertyAttribution(
                property_name=prop_name,
                value=value,
                source_line=line,
                specificity=(0, 0, 0),
            )
            ea.properties.append(attr)
        report.entities.append(ea)


def _find_source_line(view: View, taxon: str, prop_name: str) -> int:
    """Find the line number of the rule that declares this property.

    Walks rules in reverse document order (last declaration wins in
    equal-specificity cascade).
    """
    for rule in reversed(view.rules):
        for decl in rule.declarations:
            if decl.property_name == prop_name:
                return decl.span.line
    return 0


def _detect_widening(view: View) -> dict[str, list[tuple[int, int, str]]]:
    """Walk rules in document order and detect widening transitions.

    Uses restrictive_direction from PropertySchema when available,
    falls back to the legacy _WIDENING_TRANSITIONS table.

    Returns a dict keyed by property name, with lists of
    (earlier_line, later_line, property_name) tuples.
    """
    last_seen: dict[str, tuple[str, int]] = {}  # prop_name -> (value, line)
    widenings: dict[str, list[tuple[int, int, str]]] = {}
    schema_cache: dict[str, PropertySchema | None] = {}

    for rule in view.rules:
        for decl in rule.declarations:
            prop = decl.property_name
            value = decl.values[0] if decl.values else ""
            line = decl.span.line

            if prop in last_seen:
                prev_value, prev_line = last_seen[prop]
                if prop not in schema_cache:
                    schema_cache[prop] = _lookup_property_schema(prop)
                if is_widening(
                    prev_value, value,
                    prop_schema=schema_cache[prop],
                    prop_name=prop,
                ):
                    widenings.setdefault(prop, []).append(
                        (prev_line, line, prop)
                    )

            last_seen[prop] = (value, line)

    return widenings


def _lookup_property_schema(prop_name: str) -> PropertySchema | None:
    """Best-effort lookup of a property schema across all registered entities."""
    try:
        from umwelt.registry.taxa import _current_state
        state = _current_state()
        for (_taxon, _entity, name), schema in state.properties.items():
            if name == prop_name:
                return schema
    except Exception:
        pass
    return None


def format_audit(view: View, world: str | None = None) -> str:
    """Format an audit report as human-readable text."""
    report = audit_view(view, world=world)
    lines: list[str] = []

    lines.append("=== umwelt audit ===")
    lines.append("")

    if not report.entities:
        lines.append("No entities resolved.")
        return "\n".join(lines)

    for ea in report.entities:
        entity_desc = _describe_entity(ea.entity)
        lines.append(f"  {entity_desc} ({ea.taxon})")
        for attr in ea.properties:
            prefix = "  !! WIDENS" if attr.is_widening else "     "
            source = f"line {attr.source_line}" if attr.source_line else "default"
            lines.append(f"{prefix} {attr.property_name}: {attr.value}  <- {source}")
        lines.append("")

    # Enforcement coverage
    if report.enforcement_coverage:
        lines.append("Enforcement coverage:")
        for name, altitudes in report.enforcement_coverage.items():
            lines.append(f"  {name}: {', '.join(altitudes)}")
        lines.append("")

    if report.widening_count > 0:
        lines.append(f"!! {report.widening_count} widening warning(s) detected")

    return "\n".join(lines)


def _describe_entity(entity: Any) -> str:
    """Human-readable description of an entity."""
    if isinstance(entity, dict):
        return f"{entity.get('type', '?')}:{entity.get('taxon', '?')}"
    etype = type(entity).__name__
    name = getattr(entity, "name", None)
    path = getattr(entity, "path", None)
    kind = getattr(entity, "kind", None)
    if name:
        return f"{etype}[name={name!r}]"
    if path:
        return f"{etype}[path={path!r}]"
    if kind:
        return f"{etype}[kind={kind!r}]"
    return etype
