"""Dispatch registered per-taxon validators over a parsed view."""

from __future__ import annotations

from umwelt.ast import ParseWarning, RuleBlock, View
from umwelt.registry import get_validators, list_taxa


def validate(view: View) -> View:
    """Run every registered validator over its taxon's rules.

    Returns a new `View` with any accumulated warnings attached. Hard
    failures raise ViewValidationError from the validator itself.
    """
    warnings_list: list[ParseWarning] = list(view.warnings)
    # Group rules by the rightmost selector's target_taxon.
    grouped: dict[str, list[RuleBlock]] = {}
    for rule in view.rules:
        for sel in rule.selectors:
            grouped.setdefault(sel.target_taxon, []).append(rule)
            break  # One rule -> one taxon group per rule; use first selector's taxon.
    for taxon in list_taxa():
        rules = grouped.get(taxon.name, [])
        for validator in get_validators(taxon.name):
            validator.validate(rules, warnings_list)
    return View(
        rules=view.rules,
        unknown_at_rules=view.unknown_at_rules,
        warnings=tuple(warnings_list),
        source_text=view.source_text,
        source_path=view.source_path,
    )
