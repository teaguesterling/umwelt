"""Per-taxon cascade resolver.

Walks every rule in a parsed View, evaluates selectors via match_complex,
groups results by the rule's target_taxon, and for each
(entity, property) picks the winning rule via CSS specificity with
document order as the tiebreaker.

The output is a ResolvedView, keyed by taxon. Each taxon's contents is
a list of (entity, {property: value}) pairs — a list rather than a dict
because entity handles are opaque and not necessarily hashable.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from umwelt.ast import ComplexSelector, RuleBlock, View
from umwelt.selector.match import match_complex


def _has_world_qualifier(selector: ComplexSelector) -> tuple[bool, str | None]:
    """Check if a complex selector has a world-type entity with an id.

    Returns (has_world_id, world_name).
    - (True, "dev") means the selector contains world#dev
    - (False, None) means no world qualifier found
    """
    for part in selector.parts:
        if (
            part.selector.type_name == "world"
            and part.selector.taxon == "world"
            and part.selector.id_value is not None
        ):
            return True, part.selector.id_value
    return False, None


def _filter_rules_by_world_indexed(
    rules: tuple[RuleBlock, ...],
    world: str | None,
) -> list[tuple[int, RuleBlock]]:
    """Pre-filter rules by world qualifier, preserving original document-order indices.

    Rules where ALL selectors target a different world are excluded.
    Rules where ANY selector is unscoped or matches the target world
    are included.
    """
    if world is None:
        return list(enumerate(rules))

    result: list[tuple[int, RuleBlock]] = []
    for idx, rule in enumerate(rules):
        dominated_by_wrong_world = True
        for sel in rule.selectors:
            has_world, world_name = _has_world_qualifier(sel)
            if not has_world:
                # Unscoped selector - always include
                dominated_by_wrong_world = False
                break
            elif world_name == world:
                # Matches target world
                dominated_by_wrong_world = False
                break
        if not dominated_by_wrong_world:
            result.append((idx, rule))
    return result


@dataclass(frozen=True)
class _RuleApplication:
    rule_index: int
    selector_index: int
    specificity: tuple[int, int, int]
    rule: RuleBlock
    selector: ComplexSelector


@dataclass
class ResolvedView:
    """Cascade-resolved view: per-taxon, per-entity, per-property values."""

    _by_taxon: dict[str, list[tuple[Any, dict[str, str]]]] = field(default_factory=dict)

    def entries(self, taxon: str) -> Iterator[tuple[Any, dict[str, str]]]:
        """Iterate (entity, {property: value}) pairs for a taxon."""
        yield from self._by_taxon.get(taxon, [])

    def add(self, taxon: str, entity: Any, properties: dict[str, str]) -> None:
        self._by_taxon.setdefault(taxon, []).append((entity, properties))

    def taxa(self) -> list[str]:
        return list(self._by_taxon.keys())


def resolve(view: View, eval_context: Any = None, world: str | None = None) -> ResolvedView:
    """Resolve a parsed view through per-taxon CSS cascade.

    If world is specified, pre-filter rules to include only those matching
    the named world (or unscoped global rules).
    """
    indexed_rules = _filter_rules_by_world_indexed(view.rules, world)

    # 1. Expand the view's rules into one application per (rule, selector),
    # tagged with document order and specificity.
    apps: list[_RuleApplication] = []
    for r_idx, rule in indexed_rules:
        for s_idx, sel in enumerate(rule.selectors):
            apps.append(
                _RuleApplication(
                    rule_index=r_idx,
                    selector_index=s_idx,
                    specificity=sel.specificity,
                    rule=rule,
                    selector=sel,
                )
            )

    # 2. For each application, evaluate the selector and collect matched
    # entities grouped by the rule's target taxon.
    # Per-taxon accumulator: list of (entity_key, entity, matching_applications)
    per_taxon: dict[str, list[tuple[int, Any, list[_RuleApplication]]]] = {}
    for app in apps:
        matched = match_complex(app.selector, eval_context=eval_context)
        for entity in matched:
            key = id(entity)  # entities are not generally hashable
            bucket = per_taxon.setdefault(app.selector.target_taxon, [])
            # Find or create the slot for this entity.
            slot: list[_RuleApplication] | None = None
            for k, _e, lst in bucket:
                if k == key:
                    slot = lst
                    break
            if slot is None:
                slot = []
                bucket.append((key, entity, slot))
            slot.append(app)

    # 3. For each (taxon, entity), run the property-level cascade.
    resolved = ResolvedView()
    for taxon, bucket in per_taxon.items():
        for _key, entity, applications in bucket:
            properties: dict[str, str] = {}
            # Determine the winner per property.
            winners: dict[str, _RuleApplication] = {}
            for app in applications:
                for decl in app.rule.declarations:
                    current = winners.get(decl.property_name)
                    if current is None:
                        winners[decl.property_name] = app
                        continue
                    # Compare specificity; ties go to later document order.
                    if app.specificity > current.specificity or (
                        app.specificity == current.specificity
                        and (app.rule_index, app.selector_index)
                        > (current.rule_index, current.selector_index)
                    ):
                        winners[decl.property_name] = app
            # Collect the winning declaration values.
            for prop_name, app in winners.items():
                # Find the declaration with this property name in the winning rule.
                for decl in app.rule.declarations:
                    if decl.property_name == prop_name:
                        # For multi-value lists, join with commas; for
                        # single-value, use the value directly.
                        if len(decl.values) == 1:
                            properties[prop_name] = decl.values[0]
                        else:
                            properties[prop_name] = ", ".join(decl.values)
                        break
            resolved.add(taxon, entity, properties)

    return resolved
