"""The umwelt plugin registry.

Consumers register taxa, entities, properties, matchers, validators, and
compilers at import time. Core umwelt reads the registry during parsing,
selector evaluation, and cascade resolution.
"""

from umwelt.registry.taxa import (
    RegistryState,
    TaxonSchema,
    get_taxon,
    list_taxa,
    register_taxon,
    registry_scope,
)

__all__ = [
    "RegistryState",
    "TaxonSchema",
    "get_taxon",
    "list_taxa",
    "register_taxon",
    "registry_scope",
]
