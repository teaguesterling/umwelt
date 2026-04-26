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
    CompositeMatcher,
    MatcherProtocol,
    get_matcher,
    register_matcher,
)
from umwelt.registry.properties import (
    PropertySchema,
    RestrictiveDirection,
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
    register_taxon_alias,
    registry_scope,
    resolve_taxon,
)
from umwelt.registry.validators import (
    ValidatorProtocol,
    get_validators,
    register_validator,
)

__all__ = [
    "AttrSchema",
    "CompositeMatcher",
    "EntitySchema",
    "MatcherProtocol",
    "PropertySchema",
    "RegistryState",
    "TaxonSchema",
    "ValidatorProtocol",
    "get_entity",
    "get_matcher",
    "get_property",
    "get_taxon",
    "get_validators",
    "list_entities",
    "list_properties",
    "list_taxa",
    "register_entity",
    "register_matcher",
    "register_property",
    "register_taxon",
    "register_taxon_alias",
    "register_validator",
    "registry_scope",
    "resolve_entity_type",
    "resolve_taxon",
]
