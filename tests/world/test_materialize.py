import yaml

from umwelt.world.materialize import materialize, render_yaml
from umwelt.world.model import (
    DeclaredEntity,
    DetailLevel,
    Projection,
    Provenance,
    WorldFile,
)


def _sample_world():
    return WorldFile(
        entities=(
            DeclaredEntity(type="tool", id="Read", attributes={"description": "read files"}),
            DeclaredEntity(
                type="tool", id="Edit", classes=("edit",), attributes={"description": "edit files"}
            ),
            DeclaredEntity(type="mode", id="implement"),
        ),
        projections=(
            Projection(type="dir", id="node_modules", attributes={"path": "node_modules/"}),
        ),
        warnings=(),
        source_path="test.world.yml",
    )


class TestMaterialize:
    def test_full_includes_everything(self):
        mw = materialize(_sample_world(), DetailLevel.FULL)
        assert len(mw.entities) == 3
        assert mw.entities[0].attributes["description"] == "read files"

    def test_outline_strips_attributes(self):
        mw = materialize(_sample_world(), DetailLevel.OUTLINE)
        assert len(mw.entities) == 3
        assert mw.entities[0].attributes == {}
        assert mw.entities[1].classes == ("edit",)

    def test_summary_has_no_entities(self):
        mw = materialize(_sample_world(), DetailLevel.SUMMARY)
        assert len(mw.entities) == 0

    def test_summary_type_counts(self):
        mw = materialize(_sample_world(), DetailLevel.SUMMARY)
        assert mw.meta.type_counts == {"tool": 2, "mode": 1}

    def test_meta_fields(self):
        mw = materialize(_sample_world(), DetailLevel.FULL)
        assert mw.meta.source == "test.world.yml"
        assert mw.meta.entity_count == 3
        assert mw.meta.detail_level == "full"
        assert mw.meta.materialized_at  # non-empty ISO timestamp

    def test_projections_at_all_levels(self):
        for level in DetailLevel:
            mw = materialize(_sample_world(), level)
            assert len(mw.projections) == 1

    def test_provenance_preserved(self):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read", provenance=Provenance.EXPLICIT),),
            projections=(),
            warnings=(),
        )
        mw = materialize(wf, DetailLevel.FULL)
        assert mw.entities[0].provenance == Provenance.EXPLICIT


class TestRenderYaml:
    def test_roundtrip_valid_yaml(self):
        mw = materialize(_sample_world(), DetailLevel.FULL)
        text = render_yaml(mw)
        parsed = yaml.safe_load(text)
        assert "meta" in parsed
        assert "entities" in parsed

    def test_summary_format(self):
        mw = materialize(_sample_world(), DetailLevel.SUMMARY)
        text = render_yaml(mw)
        parsed = yaml.safe_load(text)
        assert parsed["meta"]["entity_count"] == 3
        assert parsed["meta"]["type_counts"]["tool"] == 2
        assert (
            "entities" not in parsed or parsed["entities"] is None or len(parsed["entities"]) == 0
        )

    def test_full_includes_attributes(self):
        mw = materialize(_sample_world(), DetailLevel.FULL)
        text = render_yaml(mw)
        parsed = yaml.safe_load(text)
        tool_read = next(e for e in parsed["entities"] if e["id"] == "Read")
        assert tool_read["attributes"]["description"] == "read files"
