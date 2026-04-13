"""Tests for umwelt audit."""
from umwelt.audit import format_audit, AuditReport, audit_view
from umwelt.ast import (
    View, RuleBlock, ComplexSelector, CompoundPart, SimpleSelector,
    Declaration, SourceSpan,
)


def _span(line=1):
    return SourceSpan(line=line, col=1)


def _simple(type_name, taxon):
    return SimpleSelector(
        type_name=type_name, taxon=taxon, id_value=None,
        classes=(), attributes=(), pseudo_classes=(), span=_span(),
    )


def _part(selector, combinator="root", mode="root"):
    return CompoundPart(selector=selector, combinator=combinator, mode=mode)


def _complex(parts, target_taxon, specificity=(0, 0, 1)):
    return ComplexSelector(parts=tuple(parts), target_taxon=target_taxon, specificity=specificity)


def _decl(name, *values, line=1):
    return Declaration(property_name=name, values=tuple(values), span=_span(line))


def _rule(selectors, declarations, line=1):
    return RuleBlock(
        selectors=tuple(selectors), declarations=tuple(declarations),
        nested_blocks=(), span=_span(line),
    )


def _view(*rules):
    return View(
        rules=tuple(rules), unknown_at_rules=(), warnings=(),
        source_text="", source_path=None,
    )


class TestAuditReport:
    def test_empty_view_produces_empty_report(self):
        view = _view()
        report = audit_view(view)
        assert report.entities == []

    def test_single_rule_shows_attribution(self):
        sel = _complex([_part(_simple("file", "world"))], "world")
        rule = _rule([sel], [_decl("editable", "true", line=5)], line=5)
        view = _view(rule)
        report = audit_view(view)
        assert len(report.entities) >= 1


class TestAuditOutput:
    def test_format_includes_entity_and_property(self):
        sel = _complex([_part(_simple("file", "world"))], "world")
        rule = _rule([sel], [_decl("editable", "true", line=5)], line=5)
        view = _view(rule)
        output = format_audit(view)
        assert "editable" in output


class TestWideningDetection:
    def test_editable_false_then_true_is_widening(self):
        """editable: false then editable: true in a later rule = widening."""
        file_sel = _complex([_part(_simple("file", "world"))], "world", specificity=(0, 0, 1))

        r1 = _rule([file_sel], [_decl("editable", "false", line=3)], line=3)
        r2 = _rule([file_sel], [_decl("editable", "true", line=5)], line=5)
        view = _view(r1, r2)
        report = audit_view(view)

        # Find widening warnings
        widenings = [
            attr
            for ea in report.entities
            for attr in ea.properties
            if attr.is_widening
        ]
        assert len(widenings) >= 1
        assert widenings[0].property_name == "editable"
        assert report.widening_count >= 1

    def test_editable_true_then_false_is_not_widening(self):
        """Tightening (true then false) is normal cascade, not a warning."""
        file_sel = _complex([_part(_simple("file", "world"))], "world")
        r1 = _rule([file_sel], [_decl("editable", "true", line=3)], line=3)
        r2 = _rule([file_sel], [_decl("editable", "false", line=5)], line=5)
        view = _view(r1, r2)
        report = audit_view(view)
        widenings = [
            attr for ea in report.entities for attr in ea.properties if attr.is_widening
        ]
        assert len(widenings) == 0

    def test_allow_false_to_true_is_widening(self):
        """allow: false then allow: true = widening."""
        tool_sel = _complex([_part(_simple("tool", "capability"))], "capability")
        r1 = _rule([tool_sel], [_decl("allow", "false", line=2)], line=2)
        r2 = _rule([tool_sel], [_decl("allow", "true", line=4)], line=4)
        view = _view(r1, r2)
        report = audit_view(view)
        assert report.widening_count >= 1

    def test_deny_removed_is_widening(self):
        """deny: '*' in rule 1, deny: '' in rule 2 = widening (deny removed)."""
        net_sel = _complex([_part(_simple("network", "world"))], "world")
        r1 = _rule([net_sel], [_decl("deny", "*", line=1)], line=1)
        r2 = _rule([net_sel], [_decl("deny", "", line=3)], line=3)
        view = _view(r1, r2)
        report = audit_view(view)
        assert report.widening_count >= 1
