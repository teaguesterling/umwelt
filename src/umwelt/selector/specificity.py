"""Cross-axis cascade specificity.

v0.5 extends CSS3 specificity with an axis_count-first tuple that captures
how many distinct taxon-axes a compound selector names. A rule joining more
axes is more specific than a rule naming fewer axes, regardless of within-
axis CSS3 counts. Matches the VSM-lattice view: a rule scoped to
(inferencer, tool, use) is more contextualized than a rule scoped to just
(use).

Tuple layout:
    (
        axis_count,
        principal_weight,
        world_weight,
        state_weight,        # coordination + control
        actor_weight,        # intelligence
        capability_weight,   # operation + use
        audit_weight,
    )

Each axis weight packs CSS3's (id, class+attr+pseudo, type) counts into a
single integer via id*10_000 + cap*100 + types. This lets axis_count
dominate the tuple's primary ordering while preserving exact within-axis
CSS3 behavior as the secondary ordering.

See docs/vision/evaluation-framework.md claims A2 and A3.
"""
from __future__ import annotations

from umwelt.ast import ComplexSelector, SimpleSelector

_AXES = ("principal", "world", "state", "actor", "capability", "audit")


def _simple_weight(selector: SimpleSelector) -> int:
    ids = 1 if selector.id_value is not None else 0
    cap = (
        len(selector.classes)
        + len(selector.attributes)
        + len(selector.pseudo_classes)
    )
    types = 1 if (selector.type_name is not None and selector.type_name != "*") else 0
    return ids * 10_000 + cap * 100 + types


def _canonical_axis(taxon: str) -> str:
    """Map alias taxa to canonical axis names for specificity accounting."""
    if taxon in ("coordination", "control"):
        return "state"
    if taxon == "intelligence":
        return "actor"
    if taxon == "operation":
        return "capability"
    return taxon


def compound_specificity(compound: ComplexSelector) -> tuple:
    weights = {axis: 0 for axis in _AXES}
    other_weight = 0
    axes_seen: set[str] = set()
    for part in compound.parts:
        axis = _canonical_axis(part.selector.taxon)
        w = _simple_weight(part.selector)
        if axis in weights:
            weights[axis] += w
        else:
            other_weight += w
        if part.selector.type_name is not None and part.selector.type_name != "*":
            axes_seen.add(axis)
    return (
        len(axes_seen),
        weights.get("principal", 0),
        weights.get("world", 0),
        weights.get("state", 0),
        weights.get("actor", 0),
        weights.get("capability", 0),
        weights.get("audit", 0),
        other_weight,
    )


# Back-compat: some callers still expect simple_specificity to return a
# 3-tuple. Preserve the CSS3-shape output for them.
def simple_specificity(selector: SimpleSelector) -> tuple[int, int, int]:
    ids = 1 if selector.id_value is not None else 0
    cap = (
        len(selector.classes)
        + len(selector.attributes)
        + len(selector.pseudo_classes)
    )
    types = 1 if (selector.type_name is not None and selector.type_name != "*") else 0
    return (ids, cap, types)
