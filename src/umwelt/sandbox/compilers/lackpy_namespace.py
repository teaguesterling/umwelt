"""Compile a resolved view into a lackpy namespace restriction config.

Language-altitude compiler. Reads capability-taxon entries (tool allow/deny,
kit allow, max-level, patterns) and emits a Python dict that lackpy's
namespace validator can consume directly.

See docs/vision/compilers/index.md for the compiler taxonomy.

World-taxon entries (files, mounts, network, resources) are silently ignored
— those are OS-altitude concerns handled by nsjail/bwrap.
"""
from __future__ import annotations

import contextlib
from typing import Any

from umwelt.cascade.resolver import ResolvedView
from umwelt.compilers.protocol import Altitude


class LackpyNamespaceCompiler:
    target_name: str = "lackpy-namespace"
    target_format: str = "dict"
    altitude: Altitude = "language"

    def compile(self, view: ResolvedView, **kwargs: Any) -> dict[str, Any]:
        config: dict[str, Any] = {
            "allowed_tools": [],
            "denied_tools": [],
            "kits": [],
            "max_level": None,
            "allow_patterns": {},
            "deny_patterns": {},
        }

        for entity, props in view.entries("capability"):
            entity_type = type(entity).__name__
            if entity_type == "ToolEntity":
                self._process_tool(config, entity, props)
            elif entity_type == "KitEntity":
                self._process_kit(config, entity, props)

        return config

    def _process_tool(
        self, config: dict[str, Any], entity: Any, props: dict[str, str]
    ) -> None:
        name = getattr(entity, "name", "")
        if not name:
            # Bare tool rule (no name) — check for max-level
            max_level = props.get("max-level")
            if max_level is not None:
                with contextlib.suppress(ValueError):
                    config["max_level"] = int(max_level)
            return

        allow = props.get("allow", "").lower()
        if allow == "true" and name not in config["allowed_tools"]:
            config["allowed_tools"].append(name)
        elif allow == "false" and name not in config["denied_tools"]:
            config["denied_tools"].append(name)

        # Tool-specific max-level
        max_level = props.get("max-level")
        if max_level is not None:
            config.setdefault("tool_levels", {})[name] = int(max_level)

        # Patterns
        allow_pattern = props.get("allow-pattern", "")
        if allow_pattern:
            config["allow_patterns"][name] = [p.strip() for p in allow_pattern.split(",")]
        deny_pattern = props.get("deny-pattern", "")
        if deny_pattern:
            config["deny_patterns"][name] = [p.strip() for p in deny_pattern.split(",")]

    def _process_kit(
        self, config: dict[str, Any], entity: Any, props: dict[str, str]
    ) -> None:
        name = getattr(entity, "name", "")
        allow = props.get("allow", "").lower()
        if allow == "true" and name and name not in config["kits"]:
            config["kits"].append(name)
