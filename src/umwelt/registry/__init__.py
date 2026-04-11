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
from umwelt.registry.matchers import (
    MatcherProtocol,
    get_matcher,
    register_matcher,
)
from umwelt.registry.properties import (
    PropertySchema,
    get_property,
    list_properties,
    register_property,
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
    "MatcherProtocol",
    "PropertySchema",
    "RegistryState",
    "TaxonSchema",
    "get_entity",
    "get_matcher",
    "get_property",
    "get_taxon",
    "list_entities",
    "list_properties",
    "list_taxa",
    "register_entity",
    "register_matcher",
    "register_property",
    "register_taxon",
    "registry_scope",
    "resolve_entity_type",
]
