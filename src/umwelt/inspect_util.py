"""Structural summary of a parsed/resolved view for umwelt inspect."""

from __future__ import annotations

from collections import defaultdict

from umwelt.ast import ComplexSelector, RuleBlock, View


def format_inspection(view: View) -> str:
    """Return a human-readable structural summary of a view."""
    lines: list[str] = []
    total_rules = len(view.rules)
    rule_word = "rule" if total_rules == 1 else "rules"
    lines.append(f"{total_rules} {rule_word}, {len(view.warnings)} warnings")
    lines.append("")

    # Group rules by target taxon.
    by_taxon: dict[str, list[RuleBlock]] = defaultdict(list)
    for rule in view.rules:
        if rule.selectors:
            taxon = rule.selectors[0].target_taxon
            by_taxon[taxon].append(rule)

    for taxon in sorted(by_taxon.keys()):
        rules = by_taxon[taxon]
        lines.append(f"# {taxon} ({len(rules)} rule(s))")
        for rule in rules:
            sel_strs = [_selector_str(s) for s in rule.selectors]
            prop_names = sorted({d.property_name for d in rule.declarations})
            lines.append(f"  {', '.join(sel_strs)}")
            for name in prop_names:
                values = [
                    d.values for d in rule.declarations if d.property_name == name
                ]
                lines.append(f"      {name}: {values}")
        lines.append("")

    if view.warnings:
        lines.append("Warnings:")
        for w in view.warnings:
            lines.append(f"  line {w.span.line}: {w.message}")

    return "\n".join(lines)


def _selector_str(complex_sel: ComplexSelector) -> str:
    """A best-effort string rendering of a ComplexSelector."""
    parts: list[str] = []
    for i, part in enumerate(complex_sel.parts):
        simple = part.selector
        s = simple.type_name or "*"
        if simple.id_value:
            s += f"#{simple.id_value}"
        for cls in simple.classes:
            s += f".{cls}"
        for attr in simple.attributes:
            if attr.op is None:
                s += f"[{attr.name}]"
            else:
                s += f'[{attr.name}{attr.op}"{attr.value}"]'
        for pseudo in simple.pseudo_classes:
            if pseudo.argument:
                s += f":{pseudo.name}({pseudo.argument})"
            else:
                s += f":{pseudo.name}"
        if i == 0:
            parts.append(s)
        else:
            combinator_str = {
                "descendant": " ",
                "child": " > ",
                "sibling": " ~ ",
                "adjacent": " + ",
            }.get(part.combinator, " ")
            parts.append(f"{combinator_str}{s}")
    return "".join(parts)
