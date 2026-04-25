"""End-to-end integration test for the world state layer."""

from __future__ import annotations

import yaml

from umwelt.registry.taxa import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.world import load_world, materialize, render_yaml, validate_world
from umwelt.world.model import DetailLevel


def test_full_pipeline(tmp_path):
    """Parse world file with shorthands, validate, materialize at all levels."""
    p = tmp_path / "delegate.world.yml"
    p.write_text(
        "tools: [Read, Edit, Bash]\n"
        "modes: [implement]\n"
        "principal: Teague\n"
        "resources:\n"
        "  memory: 1GB\n"
        "  wall-time: 10m\n"
        "entities:\n"
        "  - type: tool\n"
        "    id: Bash\n"
        "    classes: [dangerous]\n"
        "    attributes:\n"
        '      description: "Execute shell commands"\n'
        "projections:\n"
        "  - type: dir\n"
        "    id: node_modules\n"
        "    attributes:\n"
        '      path: "node_modules/"\n'
    )
    with registry_scope():
        register_sandbox_vocabulary()
        world = load_world(p)
        world = validate_world(world)

        # Bash should appear once (explicit wins over shorthand)
        bash_entities = [e for e in world.entities if e.id == "Bash"]
        assert len(bash_entities) == 1
        assert bash_entities[0].classes == ("dangerous",)

        # Resource block should be one entity with attributes
        resource_entities = [e for e in world.entities if e.type == "resource"]
        assert len(resource_entities) == 1
        assert resource_entities[0].attributes["memory"] == "1GB"
        assert resource_entities[0].attributes["wall-time"] == "10m"

        # Full materialization
        mw = materialize(world, DetailLevel.FULL)
        assert mw.meta.entity_count == 6  # 3 tools + 1 mode + 1 principal + 1 resource
        assert len(mw.projections) == 1
        assert mw.meta.detail_level == "full"

        # Outline strips attributes
        mw_outline = materialize(world, DetailLevel.OUTLINE)
        assert len(mw_outline.entities) == 6
        for e in mw_outline.entities:
            assert e.attributes == {}

        # Summary has counts only
        mw_summary = materialize(world, DetailLevel.SUMMARY)
        assert len(mw_summary.entities) == 0
        assert mw_summary.meta.entity_count == 6
        assert mw_summary.meta.type_counts["tool"] == 3

        # YAML round-trip
        text = render_yaml(mw)
        parsed = yaml.safe_load(text)
        assert parsed["meta"]["entity_count"] == 6
        assert len(parsed["entities"]) == 6
