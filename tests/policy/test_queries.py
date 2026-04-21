# tests/policy/test_queries.py

from umwelt.policy.queries import resolve_entity, resolve_all_entities, trace_entity, select_entities


class TestResolveEntity:
    def test_resolve_single_property(self, policy_db):
        val = resolve_entity(policy_db, type="tool", id="Read", property="allow")
        assert val == "true"

    def test_resolve_all_properties(self, policy_db):
        props = resolve_entity(policy_db, type="tool", id="Bash")
        assert props["risk-note"] == "Prefer structured"
        assert props["allow"] == "false"  # rule 4 wins (higher specificity class selector)

    def test_resolve_cap_comparison(self, policy_db):
        props = resolve_entity(policy_db, type="tool", id="Bash")
        assert props["max-level"] == "3"  # cap: MIN wins

    def test_resolve_nonexistent_entity(self, policy_db):
        val = resolve_entity(policy_db, type="tool", id="NonExistent", property="allow")
        assert val is None

    def test_resolve_nonexistent_property(self, policy_db):
        val = resolve_entity(policy_db, type="tool", id="Read", property="nonexistent")
        assert val is None

    def test_resolve_mode_entity(self, policy_db):
        val = resolve_entity(policy_db, type="mode", id="implement", property="allow")
        assert val == "true"


class TestResolveAll:
    def test_resolve_all_tools(self, policy_db):
        results = resolve_all_entities(policy_db, type="tool")
        assert len(results) == 3
        ids = {r["entity_id"] for r in results}
        assert ids == {"Read", "Edit", "Bash"}

    def test_resolve_all_includes_properties(self, policy_db):
        results = resolve_all_entities(policy_db, type="tool")
        bash = next(r for r in results if r["entity_id"] == "Bash")
        assert bash["properties"]["allow"] == "false"
        assert bash["properties"]["max-level"] == "3"

    def test_resolve_all_modes(self, policy_db):
        results = resolve_all_entities(policy_db, type="mode")
        assert len(results) == 2

    def test_resolve_all_unknown_type(self, policy_db):
        results = resolve_all_entities(policy_db, type="nonexistent")
        assert results == []


class TestTraceEntity:
    def test_trace_returns_all_candidates(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="allow")
        assert len(result.candidates) >= 2  # rule 0 and rule 4

    def test_trace_marks_winner(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="allow")
        winners = [c for c in result.candidates if c.won]
        assert len(winners) == 1
        assert winners[0].value == "false"

    def test_trace_value_matches_resolve(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="allow")
        resolved = resolve_entity(policy_db, type="tool", id="Bash", property="allow")
        assert result.value == resolved

    def test_trace_nonexistent(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="NonExistent", property="allow")
        assert result.value is None
        assert result.candidates == ()

    def test_trace_candidates_ordered_by_specificity(self, policy_db):
        result = trace_entity(policy_db, type="tool", id="Bash", property="max-level")
        specs = [c.specificity for c in result.candidates]
        assert specs == sorted(specs, reverse=True)


class TestSelectEntities:
    def test_select_by_type(self, policy_db):
        entities = select_entities(policy_db, type="tool")
        assert len(entities) == 3

    def test_select_by_type_and_id(self, policy_db):
        entities = select_entities(policy_db, type="tool", id="Bash")
        assert len(entities) == 1
        assert entities[0]["entity_id"] == "Bash"

    def test_select_by_classes(self, policy_db):
        entities = select_entities(policy_db, type="tool", classes=["dangerous"])
        assert len(entities) == 1
        assert entities[0]["entity_id"] == "Bash"

    def test_select_returns_entity_fields(self, policy_db):
        entities = select_entities(policy_db, type="tool", id="Read")
        e = entities[0]
        assert "entity_id" in e
        assert "type_name" in e
        assert "classes" in e
        assert "attributes" in e
