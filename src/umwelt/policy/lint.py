# src/umwelt/policy/lint.py
from __future__ import annotations

import json
import logging
import sqlite3
import warnings as warnings_mod
from dataclasses import dataclass, field
from typing import Any

from umwelt.errors import PolicyLintError
from umwelt.policy.engine import LintWarning

logger = logging.getLogger("umwelt.policy")


@dataclass(frozen=True)
class LintConfig:
    default: str
    overrides: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_lint_mode(cls, mode: str | dict[str, Any]) -> LintConfig:
        if isinstance(mode, str):
            return cls(default=mode, overrides={})
        default = mode.get("default", "warn")
        overrides: dict[str, str] = {}
        for level in ("error", "warn", "notice", "off"):
            for smell in mode.get(level, []):
                overrides[smell] = level
        return cls(default=default, overrides=overrides)

    def severity_for(self, smell: str) -> str:
        return self.overrides.get(smell, self.default)


def process_lint_results(
    lint_warnings: list[LintWarning], config: LintConfig,
) -> list[LintWarning]:
    errors: list[LintWarning] = []
    kept: list[LintWarning] = []
    for w in lint_warnings:
        effective = config.severity_for(w.smell)
        if effective == "off":
            continue
        elif effective == "notice":
            logger.info("lint [notice]: %s — %s", w.smell, w.description)
            kept.append(w)
        elif effective == "warn":
            warnings_mod.warn(
                f"umwelt lint: {w.smell} — {w.description}",
                UserWarning,
                stacklevel=2,
            )
            kept.append(w)
        elif effective == "error":
            errors.append(w)
            kept.append(w)
    if errors:
        raise PolicyLintError(errors)
    return kept


def run_lint(con: sqlite3.Connection) -> list[LintWarning]:
    results: list[LintWarning] = []
    results.extend(_detect_narrow_win(con))
    results.extend(_detect_shadowed_rule(con))
    results.extend(_detect_source_order_dependence(con))
    results.extend(_detect_uncovered_entity(con))
    results.extend(_detect_specificity_escalation(con))
    results.extend(_detect_fixed_override(con))
    results.extend(_detect_unrealizable_altitude(con))
    results.extend(_detect_cross_axis_dominance(con))
    results.extend(_detect_ceiling_ineffective(con))
    results.extend(_detect_specificity_tie(con))
    results.extend(_detect_cross_axis_tie(con))
    results.extend(_detect_ceiling_conflict(con))
    return results


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
        diff = sum(w - r for w, r in zip(winner_spec, runner_spec, strict=False))
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
    for src_file, src_line, prop_name, _entity_id in rows:
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


def _detect_source_order_dependence(con: sqlite3.Connection) -> list[LintWarning]:
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
    for entity_id, prop_name, val1, val2, _spec in rows:
        key = (entity_id, prop_name)
        if key in seen:
            continue
        seen.add(key)
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="source_order_dependence",
            severity="warning",
            description=(
                f"{entity_name} '{prop_name}': '{val1}' vs '{val2}'"
                " at same specificity — resolved by source order (later rule wins)"
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


def _detect_fixed_override(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when a fixed constraint overrides a cascade-resolved value."""
    warnings: list[LintWarning] = []

    try:
        rows = con.execute("""
            SELECT fc.entity_id, fc.property_name, fc.property_value, fc.selector,
                   rp.property_value AS cascade_value
            FROM fixed_constraints fc
            JOIN resolved_properties rp
                ON fc.entity_id = rp.entity_id
                AND fc.property_name = rp.property_name
            WHERE fc.property_value != rp.property_value
        """).fetchall()
    except sqlite3.OperationalError:
        return warnings

    for entity_id, prop_name, fixed_val, selector, cascade_val in rows:
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="fixed_override",
            severity="info",
            description=(
                f"{entity_name} '{prop_name}': fixed constraint ({selector}) "
                f"overrides cascade value '{cascade_val}' with '{fixed_val}'"
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


def _detect_unrealizable_altitude(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when a resolved property is at an altitude no compiler handles."""
    warnings: list[LintWarning] = []
    try:
        from umwelt.compilers.protocol import _ALTITUDE_RANK, available
        from umwelt.registry.properties import get_property

        registered = available()
        if not registered:
            return warnings

        from umwelt.compilers.protocol import get as get_compiler
        compiler_altitudes = set()
        for name in registered:
            try:
                c = get_compiler(name)
                compiler_altitudes.add(c.altitude)
            except Exception:
                continue

        if not compiler_altitudes:
            return warnings

        max_rank = max(_ALTITUDE_RANK.get(a, 0) for a in compiler_altitudes)

        rows = con.execute(
            "SELECT DISTINCT property_name FROM resolved_properties"
        ).fetchall()

        for (prop_name,) in rows:
            try:
                state_rows = con.execute(
                    "SELECT DISTINCT e.type_name FROM entities e "
                    "JOIN resolved_properties rp ON e.id = rp.entity_id "
                    "WHERE rp.property_name = ? LIMIT 1",
                    (prop_name,),
                ).fetchall()
                if not state_rows:
                    continue
                type_name = state_rows[0][0]
                taxon_row = con.execute(
                    "SELECT DISTINCT e.taxon FROM entities e "
                    "JOIN resolved_properties rp ON e.id = rp.entity_id "
                    "WHERE rp.property_name = ? AND e.type_name = ? LIMIT 1",
                    (prop_name, type_name),
                ).fetchall()
                if not taxon_row:
                    continue
                taxon = taxon_row[0][0]
                schema = get_property(taxon, type_name, prop_name)
                if schema.altitude and _ALTITUDE_RANK.get(schema.altitude, 0) > max_rank:
                    warnings.append(LintWarning(
                        smell="unrealizable_altitude",
                        severity="warning",
                        description=(
                            f"Property '{prop_name}' ({schema.altitude}) has no compiler "
                            f"at that altitude"
                        ),
                        entities=(),
                        property=prop_name,
                    ))
            except Exception:
                continue
    except ImportError:
        pass
    return warnings


def _detect_cross_axis_dominance(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when a cross-axis rule dominates a single-axis selector."""
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
        winner_cross = winner_spec[0]
        runner_cross = runner_spec[0]
        if winner_cross > 0 and runner_cross == 0 and candidates[0][2] != candidates[1][2]:
            entity_name = _entity_name(con, entity_id)
            warnings.append(LintWarning(
                smell="cross_axis_dominance",
                severity="warning",
                description=(
                    f"{entity_name} '{prop_name}': cross-axis rule dominates"
                    f" single-axis selector — value '{candidates[0][2]}'"
                    f" overrides '{candidates[1][2]}'"
                ),
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _detect_ceiling_ineffective(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when a higher-specificity ceiling is looser than a lower one."""
    warnings: list[LintWarning] = []
    rows = con.execute("""
        SELECT entity_id, property_name, property_value, specificity
        FROM cascade_candidates
        WHERE comparison = '<='
        ORDER BY entity_id, property_name, specificity ASC
    """).fetchall()

    groups: dict[tuple[int, str], list[tuple[str, str]]] = {}
    for entity_id, prop_name, prop_value, spec in rows:
        key = (entity_id, prop_name)
        groups.setdefault(key, []).append((prop_value, spec))

    for (entity_id, prop_name), entries in groups.items():
        if len(entries) < 2:
            continue
        # entries are ordered by specificity ASC — track tightest ceiling seen so far
        tightest = int(entries[0][0])
        for value, _spec in entries[1:]:
            int_val = int(value)
            if int_val > tightest:
                # Higher-specificity rule has a looser ceiling — it's ineffective
                entity_name = _entity_name(con, entity_id)
                warnings.append(LintWarning(
                    smell="ceiling_ineffective",
                    severity="notice",
                    description=(
                        f"{entity_name} '{prop_name}': value '{value}'"
                        f" at higher specificity is ineffective"
                        f" — ceiling clamped to '{tightest}'"
                        f" by lower-specificity rule"
                    ),
                    entities=(entity_name,),
                    property=prop_name,
                ))
                break
            tightest = min(tightest, int_val)
    return warnings


def _detect_specificity_tie(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when two rules with same specificity AND same rule_index compete."""
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
            AND c1.rule_index = c2.rule_index
            AND c1.rowid < c2.rowid
        WHERE c1.property_value != c2.property_value
          AND c1.comparison = 'exact'
          AND c2.comparison = 'exact'
    """).fetchall()

    seen: set[tuple[int, str]] = set()
    for entity_id, prop_name, val1, val2, _spec in rows:
        key = (entity_id, prop_name)
        if key in seen:
            continue
        seen.add(key)
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="specificity_tie",
            severity="warning",
            description=(
                f"{entity_name} '{prop_name}': specificity tie"
                f" between '{val1}' and '{val2}'"
                f" — resolution order is nondeterministic"
            ),
            entities=(entity_name,),
            property=prop_name,
        ))
    return warnings


def _detect_cross_axis_tie(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when competing rules come from different cross-axes."""
    warnings: list[LintWarning] = []
    rows = con.execute("""
        SELECT c1.entity_id, c1.property_name,
               c1.property_value, c2.property_value,
               c1.rowid AS r1, c2.rowid AS r2
        FROM cascade_candidates c1
        JOIN cascade_candidates c2
            ON c1.entity_id = c2.entity_id
            AND c1.property_name = c2.property_name
            AND c1.rowid < c2.rowid
        WHERE c1.property_value != c2.property_value
          AND c1.comparison = 'exact'
          AND c2.comparison = 'exact'
    """).fetchall()

    for entity_id, prop_name, val1, val2, r1, r2 in rows:
        quals1 = con.execute(
            "SELECT taxon, type_name FROM cascade_context_qualifiers WHERE candidate_rowid = ?",
            (r1,),
        ).fetchall()
        quals2 = con.execute(
            "SELECT taxon, type_name FROM cascade_context_qualifiers WHERE candidate_rowid = ?",
            (r2,),
        ).fetchall()
        if not quals1 or not quals2:
            continue
        axes1 = {(t, tn) for t, tn in quals1}
        axes2 = {(t, tn) for t, tn in quals2}
        if axes1 != axes2 and not axes1.issubset(axes2) and not axes2.issubset(axes1):
            entity_name = _entity_name(con, entity_id)
            axis1_str = ", ".join(f"{tn}" for _, tn in sorted(axes1))
            axis2_str = ", ".join(f"{tn}" for _, tn in sorted(axes2))
            warnings.append(LintWarning(
                smell="cross_axis_tie",
                severity="warning",
                description=(
                    f"{entity_name} '{prop_name}': cross-axis rules"
                    f" from different axes compete"
                    f" — {axis1_str} ({val1}) vs {axis2_str} ({val2})"
                ),
                entities=(entity_name,),
                property=prop_name,
            ))
    return warnings


def _detect_ceiling_conflict(con: sqlite3.Connection) -> list[LintWarning]:
    """Warn when competing ceiling values exist at the same specificity."""
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
          AND c1.comparison = '<='
          AND c2.comparison = '<='
    """).fetchall()

    seen: set[tuple[int, str]] = set()
    for entity_id, prop_name, val1, val2, _spec in rows:
        key = (entity_id, prop_name)
        if key in seen:
            continue
        seen.add(key)
        min_val = min(val1, val2, key=lambda v: int(v))
        entity_name = _entity_name(con, entity_id)
        warnings.append(LintWarning(
            smell="ceiling_conflict",
            severity="notice",
            description=(
                f"{entity_name} '{prop_name}': competing ceiling values"
                f" '{val1}' and '{val2}' at same specificity"
                f" — MIN ('{min_val}') wins regardless of order"
            ),
            entities=(entity_name,),
            property=prop_name,
        ))
    return warnings
