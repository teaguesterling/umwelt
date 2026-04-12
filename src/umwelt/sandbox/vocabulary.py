"""Register the sandbox vocabulary (world, capability, state) with core umwelt.

Called at import time by sandbox/__init__.py. Each register_* call talks to
the active registry scope (which is the global scope in production and a
fresh scope in tests via registry_scope()).
"""

from __future__ import annotations

from umwelt.registry import (
    AttrSchema,
    register_entity,
    register_property,
    register_taxon,
    register_validator,
)


def register_sandbox_vocabulary() -> None:
    """Register all sandbox taxa, entities, and properties, and sugar transformers."""
    _register_world()
    _register_capability()
    _register_state()
    _register_validators()
    _register_sugar()


def _register_sugar() -> None:
    from umwelt.sandbox.desugar import register_sandbox_sugar

    register_sandbox_sugar()


def _register_validators() -> None:
    from umwelt.sandbox.validators import CapabilityValidator, WorldValidator

    register_validator(taxon="world", validator=WorldValidator())
    register_validator(taxon="capability", validator=CapabilityValidator())


def _register_world() -> None:
    register_taxon(
        name="world",
        description="Entities the actor can couple to: filesystem, network, environment, resources.",
        ma_concept="world_coupling_axis",
    )

    register_entity(
        taxon="world",
        name="dir",
        attributes={
            "path": AttrSchema(type=str, required=True, description="Directory path relative to base_dir"),
            "name": AttrSchema(type=str, required=True, description="Directory name"),
        },
        description="A directory in the filesystem.",
        category="filesystem",
    )

    register_entity(
        taxon="world",
        name="file",
        parent="dir",
        attributes={
            "path": AttrSchema(type=str, required=True, description="File path relative to base_dir"),
            "name": AttrSchema(type=str, required=True, description="File name"),
            "language": AttrSchema(type=str, description="Programming language (from extension)"),
        },
        description="A file in the filesystem. Descendant of a dir.",
        category="filesystem",
    )

    register_entity(
        taxon="world",
        name="resource",
        attributes={
            "kind": AttrSchema(type=str, required=True, description="Resource kind: memory, cpu-time, wall-time, max-fds, tmpfs"),
        },
        description="A runtime resource with a limit.",
        category="budget",
    )

    register_entity(
        taxon="world",
        name="network",
        attributes={
            "host": AttrSchema(type=str, description="Hostname"),
            "port": AttrSchema(type=int, description="Port number"),
        },
        description="A network endpoint.",
        category="network",
    )

    register_entity(
        taxon="world",
        name="env",
        attributes={
            "name": AttrSchema(type=str, required=True, description="Environment variable name"),
        },
        description="An environment variable.",
        category="environment",
    )

    register_entity(
        taxon="world",
        name="mount",
        attributes={
            "src": AttrSchema(type=str, required=True),
            "dst": AttrSchema(type=str, required=True),
            "type": AttrSchema(type=str),
        },
        description="A bind mount in the workspace.",
        category="workspace",
    )

    # Properties on world entities
    register_property(taxon="world", entity="file", name="editable", value_type=bool, description="Whether the actor may modify this file.")
    register_property(taxon="world", entity="file", name="visible", value_type=bool, description="Whether the actor can see this file.")
    register_property(taxon="world", entity="file", name="show", value_type=str, description="What to show: body, outline, signature.")
    register_property(taxon="world", entity="dir", name="editable", value_type=bool, description="Whether the actor may modify files in this dir.")
    register_property(taxon="world", entity="dir", name="visible", value_type=bool, description="Whether the actor can see this dir.")
    register_property(taxon="world", entity="resource", name="limit", value_type=str, description="Resource limit value with unit (e.g. 512MB, 60s).")
    register_property(taxon="world", entity="network", name="deny", value_type=str, description="Deny pattern ('*' for all).")
    register_property(taxon="world", entity="network", name="allow", value_type=bool, description="Whether this endpoint is allowed.")
    register_property(taxon="world", entity="env", name="allow", value_type=bool, description="Whether this env var is passed through.")
    register_property(taxon="world", entity="mount", name="size", value_type=str, description="Mount size limit.")


def _register_capability() -> None:
    register_taxon(
        name="capability",
        description="What the actor can do: tools, kits, effects, computation levels.",
        ma_concept="decision_surface_axis",
    )

    register_entity(
        taxon="capability",
        name="tool",
        attributes={
            "name": AttrSchema(type=str, required=True, description="Tool name"),
            "kit": AttrSchema(type=str, description="Kit this tool belongs to"),
            "altitude": AttrSchema(type=str, description="Enforcement altitude: os, language, semantic, conversational"),
            "level": AttrSchema(type=int, description="Computation level 0-8"),
        },
        description="A tool the actor can call.",
        category="tools",
    )

    register_entity(
        taxon="capability",
        name="kit",
        attributes={
            "name": AttrSchema(type=str, required=True, description="Kit name"),
            "version": AttrSchema(type=str, description="Kit version"),
        },
        description="A named group of tools.",
        category="tools",
    )

    register_property(taxon="capability", entity="tool", name="allow", value_type=bool, description="Whether the tool is permitted.")
    register_property(taxon="capability", entity="tool", name="max-level", value_type=int, comparison="<=", value_attribute="level", value_range=(0, 8), description="Maximum computation level permitted.", category="effects_ceiling")
    register_property(taxon="capability", entity="tool", name="require", value_type=str, description="Requirement for using this tool (e.g. 'sandbox').")
    register_property(taxon="capability", entity="tool", name="allow-pattern", value_type=list, comparison="pattern-in", description="Glob patterns for allowed invocations.")
    register_property(taxon="capability", entity="tool", name="deny-pattern", value_type=list, comparison="pattern-in", description="Glob patterns for denied invocations.")
    register_property(taxon="capability", entity="kit", name="allow", value_type=bool, description="Whether the kit is permitted.")


def _register_state() -> None:
    register_taxon(
        name="state",
        description="What the Harness tracks: jobs, hooks, budgets, observations.",
        ma_concept="observation_layer",
    )

    register_entity(
        taxon="state",
        name="hook",
        attributes={
            "event": AttrSchema(type=str, required=True, description="Lifecycle event: before-call, after-change, on-failure, on-timeout"),
            "phase": AttrSchema(type=str, description="Sub-categorization of the event"),
        },
        description="A lifecycle hook.",
        category="hooks",
    )

    register_entity(
        taxon="state",
        name="job",
        attributes={
            "id": AttrSchema(type=str, required=True),
            "state": AttrSchema(type=str),
            "delegate": AttrSchema(type=bool),
        },
        description="An execution run.",
        category="jobs",
    )

    register_entity(
        taxon="state",
        name="budget",
        attributes={
            "kind": AttrSchema(type=str, required=True),
        },
        description="A runtime budget.",
        category="budgets",
    )

    register_property(taxon="state", entity="hook", name="run", value_type=str, description="Shell command to execute for this hook.")
    register_property(taxon="state", entity="hook", name="timeout", value_type=str, description="Timeout for hook execution.")
    register_property(taxon="state", entity="job", name="inherit-budget", value_type=float, description="Fraction of parent budget to inherit.")
    register_property(taxon="state", entity="budget", name="limit", value_type=str, description="Budget limit value.")
