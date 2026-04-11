"""Selector matching against a matcher's world.

`match_simple(simple, matcher, candidates)` returns the subset of
`candidates` that satisfy a simple selector's predicates (id, classes,
attribute filters, pseudo-classes).

`match_complex(complex_sel, registry, eval_context)` walks a compound
selector using the combinator mode classification: structural parts
navigate parent/child relationships via `matcher.children`, context
parts gate the rule via `matcher.condition_met`.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from umwelt.ast import AttrFilter, ComplexSelector, PseudoClass, SimpleSelector
from umwelt.registry.matchers import MatcherProtocol


def match_simple(
    simple: SimpleSelector,
    matcher: MatcherProtocol,
    candidates: list[Any],
) -> list[Any]:
    """Return candidates satisfying the simple selector's predicates."""
    return [c for c in candidates if _matches_simple(simple, matcher, c)]


def _matches_simple(
    simple: SimpleSelector, matcher: MatcherProtocol, entity: Any
) -> bool:
    # Type check (for non-universal selectors, the caller is responsible
    # for ensuring candidates are of the right type).
    if simple.id_value is not None and matcher.get_id(entity) != simple.id_value:
        return False
    for attr in simple.attributes:
        if not _matches_attribute(attr, matcher, entity):
            return False
    return all(_matches_pseudo(pseudo, matcher, entity) for pseudo in simple.pseudo_classes)


def _matches_attribute(
    attr: AttrFilter, matcher: MatcherProtocol, entity: Any
) -> bool:
    value = matcher.get_attribute(entity, attr.name)
    if value is None:
        return False
    if attr.op is None:
        return True  # [attr] — existence check
    expected = attr.value or ""
    str_value = str(value)
    if attr.op == "=":
        return str_value == expected
    if attr.op == "^=":
        return str_value.startswith(expected)
    if attr.op == "$=":
        return str_value.endswith(expected)
    if attr.op == "*=":
        return expected in str_value
    if attr.op == "~=":
        return expected in str_value.split()
    if attr.op == "|=":
        return str_value == expected or str_value.startswith(expected + "-")
    return False


def _matches_pseudo(
    pseudo: PseudoClass, matcher: MatcherProtocol, entity: Any
) -> bool:
    if pseudo.name == "glob":
        # :glob("pattern") — match the entity's path/name against fnmatch.
        # The matcher's "name" or "path" attribute is the subject.
        pattern = (pseudo.argument or "").strip().strip('"').strip("'")
        # Prefer a "path" attribute; fall back to "name" if absent.
        value = matcher.get_attribute(entity, "path") or matcher.get_attribute(
            entity, "name"
        )
        if value is None:
            return False
        return fnmatch.fnmatchcase(str(value), pattern)
    if pseudo.name == "not":
        # :not(inner) — Task 19 extends this with full sub-selector evaluation.
        # For now, Task 18 only handles simple :not with an attribute filter
        # inside — the argument is the serialized inner selector text.
        # v0.1-core keeps :not as a declarative-only stub.
        return True
    return True  # Unknown pseudo-classes are treated as always-match in v0.1.


class _RegistryAdapter:
    """Thin adapter around the plugin registry for selector matching."""

    def get_matcher(self, taxon: str) -> MatcherProtocol:
        from umwelt.registry import get_matcher

        return get_matcher(taxon)


def match_complex(
    complex_sel: ComplexSelector,
    registry: Any | None = None,
    eval_context: Any = None,
) -> list[Any]:
    """Walk a compound selector and return the final matched entity set.

    `registry` is any object with a `get_matcher(taxon) -> MatcherProtocol`
    method. If None, the global registry is used directly.
    `eval_context` is passed to cross-taxon context qualifiers.
    """
    registry = registry or _RegistryAdapter()
    current: list[Any] | None = None
    for part in complex_sel.parts:
        if part.mode == "context":
            qualifier_matcher = registry.get_matcher(part.selector.taxon)
            if not qualifier_matcher.condition_met(part.selector, eval_context):
                return []
            continue

        matcher = registry.get_matcher(part.selector.taxon)
        if current is None:
            # First structural/root part: start the navigation.
            type_name = part.selector.type_name or "*"
            if type_name == "*":
                # Universal — the matcher doesn't know about * natively; use
                # a best-effort approach: match every type the matcher owns.
                candidates: list[Any] = matcher.match_type("*")
            else:
                candidates = matcher.match_type(type_name)
        else:
            # Subsequent structural part: navigate from the previous frontier.
            type_name = part.selector.type_name or "*"
            candidates = []
            for parent in current:
                candidates.extend(matcher.children(parent, type_name))

        current = [c for c in candidates if _matches_simple(part.selector, matcher, c)]
        if not current:
            return []

    return current or []
