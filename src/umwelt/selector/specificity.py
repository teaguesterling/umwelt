"""CSS3 specificity computation for umwelt selectors.

Per CSS3, specificity is a tuple (ids, classes+attrs+pseudos, types):

- Count of IDs in the selector.
- Count of classes + attribute selectors + pseudo-classes.
- Count of type selectors (the universal selector * contributes 0).

For a compound selector, each simple selector's tuple is summed
component-wise.
"""

from __future__ import annotations

from umwelt.ast import ComplexSelector, SimpleSelector


def simple_specificity(selector: SimpleSelector) -> tuple[int, int, int]:
    ids = 1 if selector.id_value is not None else 0
    classes_attrs_pseudos = (
        len(selector.classes)
        + len(selector.attributes)
        + len(selector.pseudo_classes)
    )
    types = 1 if (selector.type_name is not None and selector.type_name != "*") else 0
    return (ids, classes_attrs_pseudos, types)


def compound_specificity(compound: ComplexSelector) -> tuple[int, int, int]:
    total_ids = 0
    total_cap = 0
    total_types = 0
    for part in compound.parts:
        ids, cap, types = simple_specificity(part.selector)
        total_ids += ids
        total_cap += cap
        total_types += types
    return (total_ids, total_cap, total_types)
