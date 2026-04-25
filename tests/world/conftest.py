import pytest

from umwelt.registry import AttrSchema, register_entity, register_taxon
from umwelt.registry.taxa import registry_scope
from umwelt.world.shorthands import register_shorthand


@pytest.fixture
def minimal_world_yml(tmp_path):
    p = tmp_path / "test.world.yml"
    p.write_text("entities:\n  - type: tool\n    id: Read\n")
    return p


@pytest.fixture
def toy_world_vocab():
    with registry_scope():
        register_taxon(name="capability", description="test cap taxon")
        register_entity(taxon="capability", name="tool",
            attributes={"description": AttrSchema(type=str)}, description="a tool")
        register_taxon(name="state", description="test state taxon")
        register_entity(taxon="state", name="mode",
            attributes={}, description="a mode")
        register_taxon(name="principal", description="test principal")
        register_entity(taxon="principal", name="principal",
            attributes={}, description="a principal")
        register_taxon(name="actor", description="test actor")
        register_entity(taxon="actor", name="inferencer",
            attributes={}, description="an inferencer")
        register_taxon(name="world", description="test world")
        register_entity(taxon="world", name="resource",
            attributes={"name": AttrSchema(type=str)}, description="a resource block")
        register_shorthand(key="tools", entity_type="tool", form="list")
        register_shorthand(key="modes", entity_type="mode", form="list")
        register_shorthand(key="principal", entity_type="principal", form="scalar")
        register_shorthand(key="inferencer", entity_type="inferencer", form="scalar")
        register_shorthand(key="resources", entity_type="resource", form="block")
        yield
