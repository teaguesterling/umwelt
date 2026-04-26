"""Plugin autodiscovery via entry points."""
from __future__ import annotations

import logging
from importlib.metadata import entry_points

logger = logging.getLogger("umwelt.registry")

ENTRY_POINT_GROUP = "umwelt.plugins"


def discover_plugins() -> list[str]:
    """Load all registered umwelt plugins. Returns names of loaded plugins."""
    loaded: list[str] = []
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            register_fn = ep.load()
            register_fn()
            loaded.append(ep.name)
        except Exception:
            logger.debug("plugin %s failed to load", ep.name, exc_info=True)
    return loaded
