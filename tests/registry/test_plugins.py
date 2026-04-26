"""Tests for plugin autodiscovery and idempotent taxon registration."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from umwelt.errors import RegistryError
from umwelt.registry.plugins import discover_plugins
from umwelt.registry.taxa import register_taxon, registry_scope


class TestIdempotentRegisterTaxon:
    """register_taxon is a no-op when re-registering with the same description."""

    def test_same_description_is_noop(self):
        with registry_scope():
            register_taxon(name="t", description="desc")
            register_taxon(name="t", description="desc")  # should not raise

    def test_conflicting_description_raises(self):
        with registry_scope():
            register_taxon(name="t", description="desc A")
            with pytest.raises(RegistryError, match="conflicting"):
                register_taxon(name="t", description="desc B")


class TestDiscoverPlugins:
    """discover_plugins loads entry points from the umwelt.plugins group."""

    def test_returns_list(self):
        with registry_scope():
            result = discover_plugins()
            assert isinstance(result, list)

    def test_loads_fake_entry_point(self):
        called = []

        def fake_register():
            called.append(True)

        fake_ep = SimpleNamespace(name="fake", load=lambda: fake_register)

        with registry_scope():
            with patch(
                "umwelt.registry.plugins.entry_points", return_value=[fake_ep]
            ):
                loaded = discover_plugins()

        assert loaded == ["fake"]
        assert called == [True]

    def test_survives_broken_plugin(self):
        def bad_load():
            raise ImportError("boom")

        broken_ep = SimpleNamespace(name="broken", load=bad_load)

        with registry_scope():
            with patch(
                "umwelt.registry.plugins.entry_points", return_value=[broken_ep]
            ):
                loaded = discover_plugins()

        assert loaded == []
