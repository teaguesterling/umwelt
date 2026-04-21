# src/umwelt/policy/lint.py
from __future__ import annotations

import json
import logging
import sqlite3

from umwelt.policy.engine import LintWarning

logger = logging.getLogger("umwelt.policy")


def run_lint(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []
    warnings.extend(_detect_narrow_win(con))
    warnings.extend(_detect_shadowed_rule(con))
    warnings.extend(_detect_conflicting_intent(con))
    warnings.extend(_detect_uncovered_entity(con))
    warnings.extend(_detect_specificity_escalation(con))

    for w in warnings:
        logger.warning(
            "lint: %s — %s",
            w.smell,
            w.description,
            extra={"smell": w.smell, "entities": w.entities, "severity": w.severity},
        )
    return warnings


def _detect_narrow_win(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT cc.entity_id, cc.property_name, cc.property_value, cc.specificity, cc.rule_index
        FROM cascade_candidates cc
        WHERE cc.comparison = 'exact'
        ORDER BY cc.entity_id, cc.property_name, cc.specificity DESC, cc.rule_index DESC
    """).fetchall()

    groups: dict[tuple[int, str], list[tuple]] = {}
    for row in rows:
        key = (row[0], row[1])
        groups.setdefault(key, []).append(row)

    for (entity_id, prop_name), candidates in groups.items():
        if len(candidates) < 2:
            continue
        winner_spec = _parse_specificity(candidates[0][3])
        runner_spec = _parse_specificity(candidates[1][3])
        if winner_spec is None or runner_spec is None:
            continue
        diff = sum(w - r for w, r in zip(winner_spec, runner_spec))
        if 0 < diff <= 1:
            entity_name = _entity_name(con, entity_id)
            warnings.append(LintWarning(
                smell="narrow_win",
                severity="warning",
                description=f"{entity_name} '{prop_name}' won by specificity margin of {diff}",
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _detect_shadowed_rule(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT cc.source_file, cc.source_line, cc.property_name, cc.entity_id
        FROM cascade_candidates cc
        LEFT JOIN resolved_properties rp
            ON cc.entity_id = rp.entity_id
            AND cc.property_name = rp.property_name
            AND cc.property_value = rp.property_value
            AND cc.specificity = rp.specificity
            AND cc.rule_index = rp.rule_index
        WHERE rp.entity_id IS NULL
          AND cc.source_file IS NOT NULL
          AND cc.source_file != ''
    """).fetchall()

    shadowed_rules: dict[tuple[str, int], set[str]] = {}
    for src_file, src_line, prop_name, entity_id in rows:
        key = (src_file, src_line)
        shadowed_rules.setdefault(key, set()).add(prop_name)

    for (src_file, src_line), props in shadowed_rules.items():
        warnings.append(LintWarning(
            smell="shadowed_rule",
            severity="info",
            description=(
                f"Rule at {src_file}:{src_line} never wins"
                f" for properties: {', '.join(sorted(props))}"
            ),
            entities=(),
            property=None,
        ))
    return warnings


def _detect_conflicting_intent(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT c1.entity_id, c1.property_name,
               c1.property_value, c2.property_value,
               c1.specificity
        FROM cascade_candidates c1
        JOIN cascade_candidates c2
            ON c1.entity_id = c2.entity_id
            AND c1.property_name = c2.property_name
            AND c1.specificity = c2.specificity
            AND c1.rule_index < c2.rule_index
        WHERE c1.property_value != c2.property_value
          AND c1.comparison = 'exact'
          AND c2.comparison = 'exact'
    """).fetchall()

    seen: set[tuple[int, str]] = set()
    for entity_id, prop_name, val1, val2, spec in rows:
        key = (entity_id, prop_name)
        if key in seen:
            continue
        seen.add(key)
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="conflicting_intent",
            severity="warning",
            description=(
                f"{entity_name} '{prop_name}': '{val1}' vs '{val2}'"
                " at same specificity — winner decided by source order"
            ),
            entities=(entity_name,),
            property=prop_name,
        ))
    return warnings


def _detect_uncovered_entity(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT e.id, e.type_name, e.entity_id
        FROM entities e
        LEFT JOIN resolved_properties rp ON e.id = rp.entity_id
        WHERE rp.entity_id IS NULL
    """).fetchall()

    for eid, type_name, entity_id in rows:
        name = f"{type_name}#{entity_id}" if entity_id else f"{type_name}(id={eid})"
        warnings.append(LintWarning(
            smell="uncovered_entity",
            severity="info",
            description=f"{name} has no resolved properties",
            entities=(name,),
            property=None,
        ))
    return warnings


def _detect_specificity_escalation(con: sqlite3.Connection) -> list[LintWarning]:
    warnings: list[LintWarning] = []

    rows = con.execute("""
        SELECT entity_id, property_name, specificity
        FROM cascade_candidates
        ORDER BY entity_id, property_name, specificity ASC
    """).fetchall()

    groups: dict[tuple[int, str], list[str]] = {}
    for entity_id, prop_name, spec in rows:
        key = (entity_id, prop_name)
        groups.setdefault(key, []).append(spec)

    for (entity_id, prop_name), specs in groups.items():
        unique_specs = sorted(set(specs))
        if len(unique_specs) >= 3:
            entity_name = _entity_name(con, entity_id)
            warnings.append(LintWarning(
                smell="specificity_escalation",
                severity="warning",
                description=(
                    f"{entity_name} '{prop_name}' has"
                    f" {len(unique_specs)} specificity levels"
                    " — possible escalation war"
                ),
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _parse_specificity(spec_str: str) -> list[int] | None:
    try:
        parts = json.loads(spec_str)
        return [int(p) for p in parts]
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def _entity_name(con: sqlite3.Connection, entity_id: int) -> str:
    row = con.execute(
        "SELECT type_name, entity_id FROM entities WHERE id = ?",
        (entity_id,),
    ).fetchone()
    if row is None:
        return f"entity({entity_id})"
    type_name, eid = row
    return f"{type_name}#{eid}" if eid else f"{type_name}(id={entity_id})"
