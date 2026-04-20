from pathlib import Path

import pytest

from umwelt.errors import WorldParseError
from umwelt.world.model import Provenance
from umwelt.world.parser import load_world


class TestExplicitEntities:
    def test_parse_basic(self, minimal_world_yml):
        wf = load_world(minimal_world_yml)
        assert len(wf.entities) == 1
        assert wf.entities[0].type == "tool"
        assert wf.entities[0].id == "Read"

    def test_parse_with_classes(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("entities:\n  - type: tool\n    id: Bash\n    classes: [dangerous, shell]\n")
        wf = load_world(p)
        assert wf.entities[0].classes == ("dangerous", "shell")

    def test_parse_with_attributes(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text('entities:\n  - type: tool\n    id: Read\n    attributes:\n      description: "read files"\n')
        wf = load_world(p)
        assert wf.entities[0].attributes["description"] == "read files"

    def test_parse_with_parent(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("entities:\n  - type: file\n    id: auth.py\n    parent: src\n")
        wf = load_world(p)
        assert wf.entities[0].parent == "src"

    def test_provenance_is_explicit(self, minimal_world_yml):
        wf = load_world(minimal_world_yml)
        assert wf.entities[0].provenance == Provenance.EXPLICIT

    def test_source_path_stored(self, minimal_world_yml):
        wf = load_world(minimal_world_yml)
        assert wf.source_path == str(minimal_world_yml)

    def test_missing_type_raises(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("entities:\n  - id: Read\n")
        with pytest.raises(WorldParseError, match="type"):
            load_world(p)

    def test_missing_id_raises(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("entities:\n  - type: tool\n")
        with pytest.raises(WorldParseError, match="id"):
            load_world(p)

    def test_id_coerced_to_string(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("entities:\n  - type: resource\n    id: 42\n")
        wf = load_world(p)
        assert wf.entities[0].id == "42"


class TestProjections:
    def test_parse_projections(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("projections:\n  - type: dir\n    id: node_modules\n    attributes:\n      path: node_modules/\n")
        wf = load_world(p)
        assert len(wf.projections) == 1
        assert wf.projections[0].id == "node_modules"


class TestShorthandExpansion:
    def test_tools_shorthand(self, tmp_path, toy_world_vocab):
        p = tmp_path / "t.world.yml"
        p.write_text("tools: [Read, Edit]\n")
        wf = load_world(p)
        assert len(wf.entities) == 2
        assert wf.entities[0].type == "tool"
        assert {e.id for e in wf.entities} == {"Read", "Edit"}

    def test_modes_shorthand(self, tmp_path, toy_world_vocab):
        p = tmp_path / "t.world.yml"
        p.write_text("modes: [implement, review]\n")
        wf = load_world(p)
        assert len(wf.entities) == 2
        assert all(e.type == "mode" for e in wf.entities)

    def test_scalar_shorthand(self, tmp_path, toy_world_vocab):
        p = tmp_path / "t.world.yml"
        p.write_text("principal: Teague\n")
        wf = load_world(p)
        assert len(wf.entities) == 1
        assert wf.entities[0].type == "principal"
        assert wf.entities[0].id == "Teague"

    def test_map_shorthand(self, tmp_path, toy_world_vocab):
        p = tmp_path / "t.world.yml"
        p.write_text("resources:\n  memory: 512MB\n  wall-time: 5m\n")
        wf = load_world(p)
        assert len(wf.entities) == 2
        mem = next(e for e in wf.entities if e.id == "memory")
        assert mem.attributes["limit"] == "512MB"

    def test_explicit_overrides_shorthand(self, tmp_path, toy_world_vocab):
        p = tmp_path / "t.world.yml"
        p.write_text("tools: [Read]\nentities:\n  - type: tool\n    id: Read\n    classes: [safe]\n")
        wf = load_world(p)
        reads = [e for e in wf.entities if e.id == "Read"]
        assert len(reads) == 1
        assert reads[0].classes == ("safe",)


class TestWarnings:
    def test_discover_warning(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("discover:\n  - matcher: filesystem\n    root: src/\n")
        wf = load_world(p)
        assert any("not yet implemented" in w.message.lower() for w in wf.warnings)

    def test_reserved_key_warning(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("vars:\n  root: /workspace\n")
        wf = load_world(p)
        assert any("reserved" in w.message.lower() for w in wf.warnings)

    def test_unknown_key_warning(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("frobnicate: true\n")
        wf = load_world(p)
        assert any("unknown" in w.message.lower() for w in wf.warnings)


class TestEdgeCases:
    def test_empty_file(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("")
        wf = load_world(p)
        assert len(wf.entities) == 0

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_world(Path("/nonexistent/test.world.yml"))

    def test_malformed_yaml_raises(self, tmp_path):
        p = tmp_path / "t.world.yml"
        p.write_text("[invalid: yaml: {broken")
        with pytest.raises(WorldParseError, match="invalid YAML"):
            load_world(p)
