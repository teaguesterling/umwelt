"""Tests for matcher registration."""

from typing import Any

import pytest

from umwelt.errors import RegistryError
from umwelt.registry import (
    MatcherProtocol,
    get_matcher,
    register_matcher,
    register_taxon,
    registry_scope,
)
from umwelt.registry.matchers import CompositeMatcher


class NullMatcher:
    """A matcher that never matches anything. For testing registration only."""

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        return []

    def children(self, parent: Any, child_type: str) -> list[Any]:
        return []

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        return False

    def get_attribute(self, entity: Any, name: str) -> Any:
        return None

    def get_id(self, entity: Any) -> str | None:
        return None


def test_register_and_lookup_matcher():
    with registry_scope():
        register_taxon(name="world", description="w")
        m = NullMatcher()
        register_matcher(taxon="world", matcher=m)
        assert get_matcher("world") is m


def test_matcher_for_unknown_taxon_raises():
    with registry_scope(), pytest.raises(RegistryError, match="taxon 'ghost' not registered"):
        register_matcher(taxon="ghost", matcher=NullMatcher())


def test_duplicate_matcher_auto_composes():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_matcher(taxon="world", matcher=NullMatcher())
        register_matcher(taxon="world", matcher=NullMatcher())
        result = get_matcher("world")
        assert isinstance(result, CompositeMatcher)


def test_get_unknown_matcher_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="no matcher registered"):
            get_matcher("world")


def test_matcher_protocol_is_runtime_checkable():
    # A structural check: NullMatcher satisfies MatcherProtocol
    assert isinstance(NullMatcher(), MatcherProtocol)


# --- CompositeMatcher tests ---


class _SimpleEntity:
    """A trivial entity with an id and attributes."""

    def __init__(self, eid: str, attrs: dict[str, Any] | None = None):
        self.eid = eid
        self.attrs = attrs or {}


class CountingMatcher:
    """A matcher that returns predictable, identifiable results."""

    def __init__(self, tag: str, entities: list[Any] | None = None):
        self.tag = tag
        self._entities = entities or []

    def match_type(self, type_name: str, context: Any = None) -> list[Any]:
        return [e for e in self._entities if True]

    def children(self, parent: Any, child_type: str) -> list[Any]:
        return [e for e in self._entities if True]

    def condition_met(self, selector: Any, context: Any = None) -> bool:
        return self.tag == "yes"

    def get_attribute(self, entity: Any, name: str) -> Any:
        if isinstance(entity, _SimpleEntity):
            return entity.attrs.get(name)
        return None

    def get_id(self, entity: Any) -> str | None:
        if isinstance(entity, _SimpleEntity):
            return entity.eid
        return None


def test_composite_match_type_unions():
    e1, e2 = _SimpleEntity("a"), _SimpleEntity("b")
    m1 = CountingMatcher("m1", [e1])
    m2 = CountingMatcher("m2", [e2])
    comp = CompositeMatcher(m1, m2)
    result = comp.match_type("any")
    assert result == [e1, e2]


def test_composite_children_unions():
    parent = _SimpleEntity("p")
    c1, c2 = _SimpleEntity("c1"), _SimpleEntity("c2")
    m1 = CountingMatcher("m1", [c1])
    m2 = CountingMatcher("m2", [c2])
    comp = CompositeMatcher(m1, m2)
    result = comp.children(parent, "child")
    assert result == [c1, c2]


def test_composite_condition_met_or_semantics():
    m_yes = CountingMatcher("yes")
    m_no = CountingMatcher("no")
    comp = CompositeMatcher(m_no, m_yes)
    assert comp.condition_met("anything") is True

    comp_all_no = CompositeMatcher(m_no, CountingMatcher("no"))
    assert comp_all_no.condition_met("anything") is False


def test_composite_get_id_first_non_none():
    e = _SimpleEntity("found")
    m_none = CountingMatcher("none", [])  # get_id returns None for non-_SimpleEntity
    m_found = CountingMatcher("found", [e])
    comp = CompositeMatcher(m_none, m_found)
    assert comp.get_id(e) == "found"
    # first delegate returns "found" too if given the entity
    comp2 = CompositeMatcher(m_found, m_none)
    assert comp2.get_id(e) == "found"


def test_composite_get_attribute_first_non_none():
    e = _SimpleEntity("x", {"color": "red"})
    m_none = CountingMatcher("none")
    m_attr = CountingMatcher("attr")
    comp = CompositeMatcher(m_none, m_attr)
    assert comp.get_attribute(e, "color") == "red"
    assert comp.get_attribute(e, "missing") is None


def test_composite_add():
    e1, e2 = _SimpleEntity("a"), _SimpleEntity("b")
    m1 = CountingMatcher("m1", [e1])
    m2 = CountingMatcher("m2", [e2])
    comp = CompositeMatcher(m1)
    assert comp.match_type("any") == [e1]
    comp.add(m2)
    assert comp.match_type("any") == [e1, e2]


def test_auto_composition_on_collision():
    with registry_scope():
        register_taxon(name="world", description="w")
        m1 = NullMatcher()
        m2 = NullMatcher()
        register_matcher(taxon="world", matcher=m1)
        register_matcher(taxon="world", matcher=m2)
        result = get_matcher("world")
        assert isinstance(result, CompositeMatcher)


def test_triple_composition():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_matcher(taxon="world", matcher=NullMatcher())
        register_matcher(taxon="world", matcher=NullMatcher())
        register_matcher(taxon="world", matcher=NullMatcher())
        result = get_matcher("world")
        assert isinstance(result, CompositeMatcher)
        assert len(result._delegates) == 3
