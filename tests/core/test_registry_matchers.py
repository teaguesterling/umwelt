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


def test_duplicate_matcher_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_matcher(taxon="world", matcher=NullMatcher())
        with pytest.raises(RegistryError, match="already registered"):
            register_matcher(taxon="world", matcher=NullMatcher())


def test_get_unknown_matcher_raises():
    with registry_scope():
        register_taxon(name="world", description="w")
        with pytest.raises(RegistryError, match="no matcher registered"):
            get_matcher("world")


def test_matcher_protocol_is_runtime_checkable():
    # A structural check: NullMatcher satisfies MatcherProtocol
    assert isinstance(NullMatcher(), MatcherProtocol)
