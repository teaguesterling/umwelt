"""Compare two parsed views and report rule-level differences.

Comparison key: the serialized selector text. Rules with the same selector
text are considered "the same rule" — their declarations are compared to
detect changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from umwelt.ast import Declaration, RuleBlock, View
from umwelt.inspect_util import _selector_str


def _rule_key(rule: RuleBlock) -> str:
    """Stable string key for a rule: its selector(s) serialized."""
    return ", ".join(_selector_str(s) for s in rule.selectors)


def _decls_equal(a: tuple[Declaration, ...], b: tuple[Declaration, ...]) -> bool:
    """Compare two declaration tuples for semantic equality."""
    if len(a) != len(b):
        return False
    a_map = {d.property_name: d.values for d in a}
    b_map = {d.property_name: d.values for d in b}
    return a_map == b_map


@dataclass
class ViewDiff:
    """Result of comparing two parsed views."""

    added: list[RuleBlock]
    """Rules present in B but not A."""

    removed: list[RuleBlock]
    """Rules present in A but not B."""

    changed: list[tuple[RuleBlock, RuleBlock]]
    """Rules with the same selector text but different declarations: (old, new)."""

    unchanged: int
    """Count of rules identical in both views."""


def diff_views(view_a: View, view_b: View) -> ViewDiff:
    """Compare two views rule by rule and return a ViewDiff."""
    a_map: dict[str, RuleBlock] = {}
    for rule in view_a.rules:
        key = _rule_key(rule)
        a_map[key] = rule

    b_map: dict[str, RuleBlock] = {}
    for rule in view_b.rules:
        key = _rule_key(rule)
        b_map[key] = rule

    added: list[RuleBlock] = []
    removed: list[RuleBlock] = []
    changed: list[tuple[RuleBlock, RuleBlock]] = []
    unchanged = 0

    for key, rule_a in a_map.items():
        if key not in b_map:
            removed.append(rule_a)
        else:
            rule_b = b_map[key]
            if _decls_equal(rule_a.declarations, rule_b.declarations):
                unchanged += 1
            else:
                changed.append((rule_a, rule_b))

    for key, rule_b in b_map.items():
        if key not in a_map:
            added.append(rule_b)

    return ViewDiff(added=added, removed=removed, changed=changed, unchanged=unchanged)


def format_diff(diff: ViewDiff) -> str:
    """Format a ViewDiff as human-readable text."""
    lines: list[str] = []

    if not diff.added and not diff.removed and not diff.changed:
        lines.append(f"No differences. {diff.unchanged} rule(s) identical.")
        return "\n".join(lines)

    summary_parts = []
    if diff.added:
        summary_parts.append(f"+{len(diff.added)} added")
    if diff.removed:
        summary_parts.append(f"-{len(diff.removed)} removed")
    if diff.changed:
        summary_parts.append(f"~{len(diff.changed)} changed")
    if diff.unchanged:
        summary_parts.append(f"{diff.unchanged} unchanged")
    lines.append("  ".join(summary_parts))
    lines.append("")

    for rule in diff.removed:
        key = _rule_key(rule)
        lines.append(f"- {key}")
        for decl in rule.declarations:
            lines.append(f"    - {decl.property_name}: {', '.join(decl.values)}")

    for rule_a, rule_b in diff.changed:
        key = _rule_key(rule_a)
        lines.append(f"~ {key}")
        a_map = {d.property_name: d.values for d in rule_a.declarations}
        b_map = {d.property_name: d.values for d in rule_b.declarations}
        all_props = sorted(set(a_map) | set(b_map))
        for prop in all_props:
            a_val = a_map.get(prop)
            b_val = b_map.get(prop)
            if a_val != b_val:
                if a_val is not None:
                    lines.append(f"    - {prop}: {', '.join(a_val)}")
                if b_val is not None:
                    lines.append(f"    + {prop}: {', '.join(b_val)}")

    for rule in diff.added:
        key = _rule_key(rule)
        lines.append(f"+ {key}")
        for decl in rule.declarations:
            lines.append(f"    + {decl.property_name}: {', '.join(decl.values)}")

    return "\n".join(lines)
