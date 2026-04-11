"""The umwelt plugin registry.

Consumers register taxa, entities, properties, matchers, validators, and
compilers at import time. Core umwelt reads the registry during parsing,
selector evaluation, and cascade resolution.
"""

from umwelt.registry.entities import (
    AttrSchema,
    EntitySchema,
    get_entity,
    list_entities,
    register_entity,
    resolve_entity_type,
)
from umwelt.registry.taxa import (
    RegistryState,
    TaxonSchema,
    get_taxon,
    list_taxa,
    register_taxon,
    registry_scope,
)

__all__ = [
    "AttrSchema",
    "EntitySchema",
    "RegistryState",
    "TaxonSchema",
    "get_entity",
    "get_taxon",
    "list_entities",
    "list_taxa",
    "register_entity",
    "register_taxon",
    "registry_scope",
    "resolve_entity_type",
]
