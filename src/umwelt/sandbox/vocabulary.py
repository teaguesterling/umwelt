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
    register_taxon_alias,
    register_validator,
)


def register_sandbox_vocabulary() -> None:
    """Register all sandbox taxa, entities, and properties, and sugar transformers."""
    _register_world()
    _register_capability()
    _register_state()
    _register_actor()
    _register_vsm_aliases()
    _register_use()               # NEW
    _register_principal()         # Task 9: S5 identity axis
    _register_audit()             # Task 10: S3* cross-cut observer
    _register_validators()
    _register_sugar()
    _register_world_shorthands()


def _register_vsm_aliases() -> None:
    """Register VSM taxon names as aliases of legacy taxa.

    v0.5: operation/coordination/control/intelligence point at the same
    underlying taxa as capability/state/actor. The spec's logical split of
    `state` into `coordination` and `control` is virtual in v0.5 — both
    names resolve to the same bucket. The physical split happens in v0.6+
    when the legacy-shim is retired.

    `principal` and `audit` are genuinely new taxa and are registered
    directly (Task 9 and Task 10), not as aliases.
    """
    register_taxon_alias(alias="operation", canonical="capability")
    register_taxon_alias(alias="coordination", canonical="state")
    register_taxon_alias(alias="control", canonical="state")
    register_taxon_alias(alias="intelligence", canonical="actor")


def _register_sugar() -> None:
    from umwelt.sandbox.desugar import register_sandbox_sugar

    register_sandbox_sugar()


def _register_use() -> None:
    """Register the `use` entity — permissioned projection of world resources."""
    register_entity(
        taxon="operation",
        name="use",
        attributes={
            "of": AttrSchema(
                type=str,
                description="Selector pointing at the world entity (e.g. 'file#/src/auth.py').",
            ),
            "of-kind": AttrSchema(
                type=str,
                description="Match all uses whose target is of a given kind (e.g. 'file', 'network').",
            ),
            "of-like": AttrSchema(
                type=str,
                description="Prefix-like match against target paths (e.g. 'file#/src').",
            ),
        },
        description=(
            "A permissioned projection of a world entity into the action axis. "
            "Permissions (editable, visible, allow, deny) live on uses, not on "
            "world entities themselves."
        ),
        category="access",
    )

    register_property(taxon="operation", entity="use", name="editable", value_type=bool,
                      restrictive_direction="false",
                      description="Whether this use grants edit access.")
    register_property(taxon="operation", entity="use", name="visible", value_type=bool,
                      restrictive_direction="false",
                      description="Whether this use grants visibility.")
    register_property(taxon="operation", entity="use", name="show", value_type=str,
                      description="Projection kind: body, outline, signature.")
    register_property(taxon="operation", entity="use", name="allow", value_type=bool,
                      restrictive_direction="false",
                      description="Whether this use is permitted.")
    register_property(taxon="operation", entity="use", name="deny", value_type=str,
                      restrictive_direction="superset",
                      description="Deny pattern ('*' for blanket deny).")
    register_property(taxon="operation", entity="use", name="allow-pattern", value_type=list,
                      comparison="pattern-in",
                      description="Glob patterns for allowed invocations of this use.")
    register_property(taxon="operation", entity="use", name="deny-pattern", value_type=list,
                      comparison="pattern-in",
                      description="Glob patterns for denied invocations of this use.")


def _register_principal() -> None:
    """Register the `principal` taxon — S5 identity axis."""
    register_taxon(
        name="principal",
        description="S5: commissioning identity. Who set the bounds for the delegate.",
        ma_concept="principal_axis",
    )
    register_entity(
        taxon="principal",
        name="principal",
        attributes={
            "name": AttrSchema(type=str, description="Principal identifier (used as #id)."),
        },
        description="The commissioning principal.",
        category="identity",
    )
    register_property(taxon="principal", entity="principal", name="intent", value_type=str,
                      description="Free-form description of why this delegate was commissioned.")
    register_property(taxon="principal", entity="principal", name="grade", value_type=int,
                      description="Ma-grade label (0-4). Consumed by audit; other compilers ignore.")


def _register_audit() -> None:
    """Register the audit taxon (S3*) — cross-cut observer outside the world."""
    register_taxon(
        name="audit",
        description="S3* cross-cut observer. Outside the world it observes.",
        ma_concept="audit_axis",
    )
    register_entity(
        taxon="audit",
        name="observation",
        attributes={
            "name": AttrSchema(type=str, description="Observation identifier (used as #id)."),
        },
        description="A Layer-2 observation entry (blq, ratchet-detect output).",
        category="observation",
    )
    register_entity(
        taxon="audit",
        name="manifest",
        attributes={
            "name": AttrSchema(type=str, description="Manifest identifier."),
        },
        description="A workspace manifest reference.",
        category="manifest",
    )

    register_property(taxon="audit", entity="observation", name="source", value_type=str,
                     description="Observer source (e.g. 'kibitzer', 'ratchet-detect').")
    register_property(taxon="audit", entity="observation", name="enabled", value_type=bool,
                     restrictive_direction="true",
                     description="Whether this observation is enabled.")
    register_property(taxon="audit", entity="manifest", name="path", value_type=str,
                     description="Path to the manifest file.")

    register_property(taxon="audit", entity="observation", name="type",
                     value_type=str, description="event category: tool_call, build_run, failure, etc.")
    register_property(taxon="audit", entity="observation", name="timestamp",
                     value_type=str, description="ISO 8601 timestamp")
    register_property(taxon="audit", entity="observation", name="session_id",
                     value_type=str, description="Claude Code session ID")
    register_property(taxon="audit", entity="observation", name="severity",
                     value_type=str, description="info, warning, error, critical")
    register_property(taxon="audit", entity="observation", name="tags",
                     value_type=str, description="classification tags: repeated_pattern, permission_denial, etc.")
    register_property(taxon="audit", entity="observation", name="payload",
                     value_type=str, description="JSON blob with tool-specific structure")


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
        name="world",
        attributes={
            "name": AttrSchema(type=str, description="Environment name (used as #id in selectors)"),
        },
        description="A named environment — the root of the world hierarchy. world#dev, world#ci, etc.",
        category="environment",
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
            "name": AttrSchema(type=str, description="Resource block name"),
        },
        description="A resource block declaring runtime limits (memory, wall-time, cpu, etc.).",
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
        parent="world",
        attributes={
            "path": AttrSchema(type=str, required=True, description="Mount destination path inside the workspace"),
            "source": AttrSchema(type=str, description="Host path or URL this mount maps from"),
            "type": AttrSchema(type=str, description="Mount type: bind, tmpfs, overlay"),
        },
        description="A bind mount or tmpfs in the workspace.",
        category="workspace",
    )

    # Properties on world entities
    register_property(taxon="world", entity="file", name="editable", value_type=bool, restrictive_direction="false", description="Whether the actor may modify this file.")
    register_property(taxon="world", entity="file", name="visible", value_type=bool, restrictive_direction="false", description="Whether the actor can see this file.")
    register_property(taxon="world", entity="file", name="show", value_type=str, description="What to show: body, outline, signature.")
    register_property(taxon="world", entity="dir", name="editable", value_type=bool, restrictive_direction="false", description="Whether the actor may modify files in this dir.")
    register_property(taxon="world", entity="dir", name="visible", value_type=bool, restrictive_direction="false", description="Whether the actor can see this dir.")
    register_property(taxon="world", entity="resource", name="memory", value_type=str, restrictive_direction="min", description="Memory limit with unit (e.g. 512MB, 1GB).")
    register_property(taxon="world", entity="resource", name="wall-time", value_type=str, restrictive_direction="min", description="Wall-clock time limit (e.g. 10m, 1h).")
    register_property(taxon="world", entity="resource", name="cpu-time", value_type=str, restrictive_direction="min", description="CPU time limit (e.g. 30s, 5m).")
    register_property(taxon="world", entity="resource", name="max-fds", value_type=int, restrictive_direction="min", description="Maximum open file descriptors.")
    register_property(taxon="world", entity="resource", name="tmpfs", value_type=str, restrictive_direction="min", description="Tmpfs size for /tmp (e.g. 64MB).")
    register_property(taxon="world", entity="network", name="deny", value_type=str, restrictive_direction="superset", description="Deny pattern ('*' for all).")
    register_property(taxon="world", entity="network", name="allow", value_type=bool, restrictive_direction="false", description="Whether this endpoint is allowed.")
    register_property(taxon="world", entity="env", name="allow", value_type=bool, restrictive_direction="false", description="Whether this env var is passed through.")
    register_property(taxon="world", entity="mount", name="size", value_type=str, description="Mount size limit.")
    register_property(taxon="world", entity="mount", name="source", value_type=str, description="Host path or URL this mount maps from.")
    register_property(taxon="world", entity="mount", name="readonly", value_type=bool, restrictive_direction="true", description="Whether the mount is read-only.")
    register_property(taxon="world", entity="mount", name="type", value_type=str, description="Mount type: bind, tmpfs, overlay.")

    register_entity(
        taxon="world",
        name="exec",
        parent="world",
        attributes={
            "name": AttrSchema(type=str, description="Executable name (e.g. bash, python3)"),
            "path": AttrSchema(type=str, description="Absolute path to binary inside the jail"),
        },
        description="An executable binary available inside the jail environment.",
        category="executables",
    )

    register_property(
        taxon="world",
        entity="exec",
        name="path",
        value_type=str,
        description="Absolute path to the binary inside the jail.",
    )
    register_property(
        taxon="world",
        entity="exec",
        name="search-path",
        value_type=str,
        description="Colon-separated PATH directories for the jail. Default: /bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin",
    )


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
            "param-count": AttrSchema(type=int, description="Number of parameters (MCP-projected)"),
            "output-type": AttrSchema(type=str, description="Output format: structured, text, stream (MCP-projected)"),
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

    register_property(taxon="capability", entity="tool", name="allow", value_type=bool, restrictive_direction="false", description="Whether the tool is permitted.")
    register_property(taxon="capability", entity="tool", name="visible", value_type=bool, restrictive_direction="false", description="Whether the tool is displayed to the delegate. Default follows 'allow'.")
    register_property(taxon="capability", entity="tool", name="max-level", value_type=int, comparison="<=", restrictive_direction="min", value_attribute="level", value_range=(0, 8), description="Maximum computation level permitted.", category="effects_ceiling")
    register_property(taxon="capability", entity="tool", name="require", value_type=str, description="Requirement for using this tool (e.g. 'sandbox').")
    register_property(taxon="capability", entity="tool", name="allow-pattern", value_type=list, comparison="pattern-in", restrictive_direction="subset", description="Glob patterns for allowed invocations.")
    register_property(taxon="capability", entity="tool", name="deny-pattern", value_type=list, comparison="pattern-in", restrictive_direction="superset", description="Glob patterns for denied invocations.")
    register_property(taxon="capability", entity="kit", name="allow", value_type=bool, restrictive_direction="false", description="Whether the kit is permitted.")
    register_property(
        taxon="capability",
        entity="tool",
        name="exec",
        value_type=str,
        description="Name of the executable entity this tool delegates to (e.g. 'bash').",
    )


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

    register_entity(
        taxon="state",
        name="mode",
        attributes={
            "name": AttrSchema(type=str, description="Mode ID (used as #id in selectors)"),
        },
        description=(
            "A regulation mode (S3). Authored via ID selectors: `mode#review`, "
            "`mode#implement`. Modes are named instances, not categories — IDs, "
            "not classes. Classes remain for mode categories: `mode#review.read-only`, "
            "`mode#implement.destructive`. ID selectors ensure mode-qualified rules "
            "dominate in the axis-count-first specificity model."
        ),
        category="regulation",
    )

    register_property(taxon="state", entity="hook", name="run", value_type=str, description="Shell command to execute for this hook.")
    register_property(taxon="state", entity="hook", name="timeout", value_type=str, description="Timeout for hook execution.")
    register_property(taxon="state", entity="job", name="inherit-budget", value_type=float, description="Fraction of parent budget to inherit.")
    register_property(taxon="state", entity="budget", name="limit", value_type=str, description="Budget limit value.")


def _register_actor() -> None:
    register_taxon(
        name="actor",
        description="The four Ma actors: principal, inferencer, executor, harness.",
        ma_concept="four_actor_taxonomy",
    )

    register_entity(
        taxon="actor",
        name="inferencer",
        attributes={
            "model": AttrSchema(type=str, description="Model identifier (e.g. claude-sonnet-4-6)"),
            "kit": AttrSchema(type=str, description="Kit this inferencer uses"),
            "temperature": AttrSchema(type=float, description="Sampling temperature"),
        },
        description="The language model / inferencer.",
        category="actors",
    )

    register_entity(
        taxon="actor",
        name="executor",
        attributes={
            "tool_name": AttrSchema(type=str, description="Tool this executor represents"),
            "altitude": AttrSchema(type=str, description="Enforcement altitude: os, language, semantic, conversational"),
        },
        description="An executor (tool runner).",
        category="actors",
    )

    register_property(taxon="actor", entity="inferencer", name="model", value_type=str, description="Model to use for this inferencer.")
    register_property(taxon="actor", entity="inferencer", name="temperature", value_type=float, description="Sampling temperature.")


def _register_world_shorthands() -> None:
    from umwelt.world.shorthands import register_shorthand

    register_shorthand(key="tools", entity_type="tool", form="list")
    register_shorthand(key="modes", entity_type="mode", form="list")
    register_shorthand(key="principal", entity_type="principal", form="scalar")
    register_shorthand(key="inferencer", entity_type="inferencer", form="scalar")
    register_shorthand(key="resources", entity_type="resource", form="block")
