from umwelt.world.model import DeclaredEntity, WorldFile, WorldWarning
from umwelt.world.validate import validate_world


class TestValidation:
    def test_known_type_no_warning(self, toy_world_vocab):
        wf = WorldFile(
            entities=(DeclaredEntity(type="tool", id="Read"),),
            projections=(), warnings=(),
        )
        result = validate_world(wf)
        type_warnings = [w for w in result.warnings if "unknown" in w.message.lower() and "type" in w.message.lower()]
        assert len(type_warnings) == 0

    def test_unknown_type_produces_warning(self, toy_world_vocab):
        wf = WorldFile(
            entities=(DeclaredEntity(type="frobnitz", id="X"),),
            projections=(), warnings=(),
        )
        result = validate_world(wf)
        assert any("frobnitz" in w.message for w in result.warnings)

    def test_preserves_existing_warnings(self, toy_world_vocab):
        existing = WorldWarning(message="prior warning")
        wf = WorldFile(entities=(), projections=(), warnings=(existing,))
        result = validate_world(wf)
        assert existing in result.warnings

    def test_empty_registry_warns_all(self):
        from umwelt.registry.taxa import registry_scope
        with registry_scope():
            wf = WorldFile(
                entities=(DeclaredEntity(type="tool", id="Read"),),
                projections=(), warnings=(),
            )
            result = validate_world(wf)
            assert any("tool" in w.message for w in result.warnings)

    def test_multiple_entities_validated(self, toy_world_vocab):
        wf = WorldFile(
            entities=(
                DeclaredEntity(type="tool", id="Read"),
                DeclaredEntity(type="unknown_thing", id="X"),
            ),
            projections=(), warnings=(),
        )
        result = validate_world(wf)
        assert any("unknown_thing" in w.message for w in result.warnings)
