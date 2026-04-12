"""Tests for world-scoped resolver filtering."""
from umwelt.ast import (
    ComplexSelector,
    CompoundPart,
    Declaration,
    RuleBlock,
    SimpleSelector,
    SourceSpan,
)
from umwelt.cascade.resolver import _filter_rules_by_world_indexed


def _span():
    return SourceSpan(line=1, col=1)


def _simple(type_name, taxon, id_value=None, attrs=()):
    return SimpleSelector(
        type_name=type_name, taxon=taxon, id_value=id_value,
        classes=(), attributes=tuple(attrs), pseudo_classes=(), span=_span(),
    )


def _rule(selectors, declarations):
    return RuleBlock(
        selectors=tuple(selectors),
        declarations=tuple(declarations),
        nested_blocks=(),
        span=_span(),
    )


def _decl(name, *values):
    return Declaration(property_name=name, values=tuple(values), span=_span())


def _complex(parts, target_taxon, specificity=(0, 0, 1)):
    return ComplexSelector(
        parts=tuple(parts), target_taxon=target_taxon, specificity=specificity,
    )


def _part(selector, combinator="root", mode="root"):
    return CompoundPart(selector=selector, combinator=combinator, mode=mode)


class TestFilterRulesByWorld:
    """Test the pre-filtering of rules by world qualifier."""

    def test_unscoped_rule_always_included(self):
        """Rules with no world qualifier pass through for any world."""
        file_sel = _simple("file", "world")
        sel = _complex([_part(file_sel)], "world")
        rule = _rule([sel], [_decl("editable", "true")])
        result = _filter_rules_by_world_indexed(tuple([rule]), world="dev")
        assert len(result) == 1

    def test_matching_world_qualifier_included(self):
        """Rules with world#dev qualifier included when world='dev'."""
        world_sel = _simple("world", "world", id_value="dev")
        file_sel = _simple("file", "world")
        sel = _complex(
            [_part(world_sel), _part(file_sel, combinator="descendant", mode="structural")],
            "world",
        )
        rule = _rule([sel], [_decl("editable", "true")])
        result = _filter_rules_by_world_indexed(tuple([rule]), world="dev")
        assert len(result) == 1

    def test_non_matching_world_qualifier_excluded(self):
        """Rules with world#ci qualifier excluded when world='dev'."""
        world_sel = _simple("world", "world", id_value="ci")
        file_sel = _simple("file", "world")
        sel = _complex(
            [_part(world_sel), _part(file_sel, combinator="descendant", mode="structural")],
            "world",
        )
        rule = _rule([sel], [_decl("editable", "false")])
        result = _filter_rules_by_world_indexed(tuple([rule]), world="dev")
        assert len(result) == 0

    def test_no_world_filter_returns_all_rules(self):
        """When world=None, all rules are returned (no filtering)."""
        world_sel = _simple("world", "world", id_value="ci")
        file_sel = _simple("file", "world")
        sel = _complex(
            [_part(world_sel), _part(file_sel, combinator="descendant", mode="structural")],
            "world",
        )
        rule = _rule([sel], [_decl("editable", "false")])
        result = _filter_rules_by_world_indexed(tuple([rule]), world=None)
        assert len(result) == 1

    def test_mixed_rules_filtered_correctly(self):
        """Mix of world-scoped and unscoped rules filters correctly."""
        # Rule 1: unscoped (global default)
        r1 = _rule(
            [_complex([_part(_simple("file", "world"))], "world")],
            [_decl("editable", "false")],
        )
        # Rule 2: world#dev scoped
        world_dev = _simple("world", "world", id_value="dev")
        file_sel = _simple("file", "world")
        r2 = _rule(
            [_complex(
                [_part(world_dev), _part(file_sel, combinator="descendant", mode="structural")],
                "world",
            )],
            [_decl("editable", "true")],
        )
        # Rule 3: world#ci scoped
        world_ci = _simple("world", "world", id_value="ci")
        r3 = _rule(
            [_complex(
                [_part(world_ci), _part(file_sel, combinator="descendant", mode="structural")],
                "world",
            )],
            [_decl("editable", "false")],
        )
        result = _filter_rules_by_world_indexed(tuple([r1, r2, r3]), world="dev")
        assert len(result) == 2  # r1 (unscoped) + r2 (world#dev)

    def test_document_order_preserved(self):
        """Filtered rules preserve their original document-order indices."""
        r1 = _rule(
            [_complex([_part(_simple("file", "world"))], "world")],
            [_decl("editable", "false")],
        )
        world_ci = _simple("world", "world", id_value="ci")
        file_sel = _simple("file", "world")
        r2 = _rule(
            [_complex(
                [_part(world_ci), _part(file_sel, combinator="descendant", mode="structural")],
                "world",
            )],
            [_decl("editable", "false")],
        )
        world_dev = _simple("world", "world", id_value="dev")
        r3 = _rule(
            [_complex(
                [_part(world_dev), _part(file_sel, combinator="descendant", mode="structural")],
                "world",
            )],
            [_decl("editable", "true")],
        )
        result = _filter_rules_by_world_indexed(tuple([r1, r2, r3]), world="dev")
        # r1 is index 0, r3 is index 2 (r2 at index 1 is excluded)
        assert result[0][0] == 0  # original index of r1
        assert result[1][0] == 2  # original index of r3
