"""Tests for altitude filtering: PropertySchema.altitude, pre-filtering, linting."""
from __future__ import annotations

import pytest

from umwelt.compilers.protocol import Altitude, _ALTITUDE_RANK, _filter_by_altitude
from umwelt.registry import register_entity, register_property, register_taxon, registry_scope
from umwelt.registry.entities import AttrSchema
from umwelt.registry.properties import PropertySchema


def test_property_schema_has_altitude():
    schema = PropertySchema(
        name="editable", taxon="world", entity="file",
        value_type=bool, altitude="os",
    )
    assert schema.altitude == "os"


def test_property_schema_altitude_defaults_to_none():
    schema = PropertySchema(
        name="editable", taxon="world", entity="file",
        value_type=bool,
    )
    assert schema.altitude is None


def test_altitude_ranking():
    assert _ALTITUDE_RANK["os"] < _ALTITUDE_RANK["language"]
    assert _ALTITUDE_RANK["language"] < _ALTITUDE_RANK["semantic"]
    assert _ALTITUDE_RANK["semantic"] < _ALTITUDE_RANK["conversational"]


def test_register_property_with_altitude():
    with registry_scope():
        register_taxon(name="world", description="w")
        register_entity(taxon="world", name="file",
                       attributes={"path": AttrSchema(type=str)}, description="f")
        register_property(
            taxon="world", entity="file", name="editable",
            value_type=bool, description="can edit",
            altitude="os",
        )
        from umwelt.registry import get_property
        prop = get_property("world", "file", "editable")
        assert prop.altitude == "os"
