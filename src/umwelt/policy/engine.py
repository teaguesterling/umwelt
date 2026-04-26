from __future__ import annotations

import logging
import sqlite3
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from umwelt.errors import PolicyDenied

logger = logging.getLogger("umwelt.policy")


@dataclass(frozen=True)
class Candidate:
    value: str
    specificity: str
    rule_index: int
    source_file: str
    source_line: int
    won: bool


@dataclass(frozen=True)
class TraceResult:
    entity: str
    property: str
    value: str | None
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class LintWarning:
    smell: str
    severity: str
    description: str
    entities: tuple[str, ...]
    property: str | None


class PolicyEngine:
    """Consumer-facing API for querying resolved world knowledge."""

    def __init__(self) -> None:
        self._con: sqlite3.Connection | None = None
        self._pending_entities: list[dict[str, Any]] = []
        self._pending_stylesheets: list[str] = []
        self._compiled = False

    @classmethod
    def from_files(
        cls,
        *,
        world: str | Path,
        stylesheet: str | Path,
    ) -> PolicyEngine:
        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.dialects import SQLiteDialect
        from umwelt.compilers.sql.populate import populate_from_world
        from umwelt.compilers.sql.schema import create_schema
        from umwelt.parser import parse
        from umwelt.policy.projections import create_compilation_meta, create_projection_views
        from umwelt.world.parser import load_world

        world_path = Path(world)
        stylesheet_path = Path(stylesheet)

        try:
            _load_default_vocabulary()
        except Exception:
            logger.debug("vocabulary registration skipped", exc_info=True)

        world_file = load_world(world_path)
        view = parse(stylesheet_path)

        dialect = SQLiteDialect()
        con = sqlite3.connect(":memory:")
        con.executescript(create_schema(dialect))
        populate_from_world(con, world_file)
        compile_view(con, view, dialect, source_file=str(stylesheet_path))

        try:
            create_projection_views(con)
        except Exception:
            logger.debug("projection views skipped", exc_info=True)
        try:
            create_compilation_meta(
                con,
                source_world=str(world_path),
                source_stylesheet=str(stylesheet_path),
            )
        except Exception:
            logger.debug("compilation meta skipped", exc_info=True)

        engine = cls.__new__(cls)
        engine._con = con
        engine._pending_entities = []
        engine._pending_stylesheets = []
        engine._compiled = True

        logger.info(
            "compile",
            extra={
                "source_files": [str(world_path), str(stylesheet_path)],
                "entity_count": con.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
            },
        )
        return engine

    @classmethod
    def from_db(cls, path: str | Path) -> PolicyEngine:
        source = sqlite3.connect(str(path))
        con = sqlite3.connect(":memory:")
        source.backup(con)
        source.close()

        engine = cls.__new__(cls)
        engine._con = con
        engine._pending_entities = []
        engine._pending_stylesheets = []
        engine._compiled = True
        return engine

    def add_entities(self, entities: list[dict[str, Any]]) -> None:
        self._pending_entities.extend(entities)
        self._compiled = False

    def add_stylesheet(self, css: str) -> None:
        self._pending_stylesheets.append(css)
        self._compiled = False

    def register_vocabulary(self, registrar: Any) -> None:
        registrar()

    def _ensure_compiled(self) -> sqlite3.Connection:
        if self._con is not None and self._compiled:
            return self._con

        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.dialects import SQLiteDialect
        from umwelt.compilers.sql.populate import populate_from_world
        from umwelt.compilers.sql.schema import create_schema
        from umwelt.parser import parse as parse_css
        from umwelt.policy.projections import create_projection_views
        from umwelt.world.model import DeclaredEntity, WorldFile

        try:
            _load_default_vocabulary()
        except Exception:
            logger.debug("vocabulary registration skipped", exc_info=True)

        dialect = SQLiteDialect()
        con = self._con or sqlite3.connect(":memory:")
        if not self._compiled:
            con.executescript(create_schema(dialect))

        if self._pending_entities:
            declared = []
            for e in self._pending_entities:
                classes = tuple(e.get("classes", ()))
                declared.append(DeclaredEntity(
                    type=e["type"],
                    id=e["id"],
                    classes=classes,
                    attributes=e.get("attributes", {}),
                    parent=e.get("parent"),
                ))
            wf = WorldFile(entities=tuple(declared), projections=(), warnings=())
            populate_from_world(con, wf)
            self._pending_entities = []

        for css_text in self._pending_stylesheets:
            view = parse_css(css_text, validate=False)
            compile_view(con, view, dialect)
        self._pending_stylesheets = []

        try:
            create_projection_views(con)
        except Exception:
            logger.debug("projection views skipped", exc_info=True)

        self._con = con
        self._compiled = True
        return con

    @staticmethod
    def _resolve_mode_to_context(
        mode: str | None, context: list | dict | None
    ) -> list | dict | None:
        if mode is not None and context is not None:
            raise ValueError("Cannot specify both mode= and context=")
        if mode is not None:
            warnings.warn(
                "mode= is deprecated, use context={'mode': value} instead",
                DeprecationWarning,
                stacklevel=3,
            )
            return {"mode": mode}
        return context

    def resolve(
        self,
        *,
        type: str,
        id: str,
        property: str | None = None,
        mode: str | None = None,
        context: list | dict | None = None,
    ) -> str | dict[str, str] | None:
        context = self._resolve_mode_to_context(mode, context)
        from umwelt.policy.queries import resolve_entity

        con = self._ensure_compiled()
        result = resolve_entity(con, type=type, id=id, property=property, context=context)
        logger.info(
            "resolve",
            extra={"entity": f"{type}#{id}", "property": property, "context": context, "value": result},
        )
        return result

    def resolve_all(self, *, type: str, mode: str | None = None, context: list | dict | None = None) -> list[dict]:
        context = self._resolve_mode_to_context(mode, context)
        from umwelt.policy.queries import resolve_all_entities

        con = self._ensure_compiled()
        results = resolve_all_entities(con, type=type, context=context)
        logger.info(
            "resolve_all",
            extra={"type": type, "context": context, "result_count": len(results)},
        )
        return results

    def trace(
        self,
        *,
        type: str,
        id: str,
        property: str,
        mode: str | None = None,
        context: list | dict | None = None,
    ) -> TraceResult:
        context = self._resolve_mode_to_context(mode, context)
        from umwelt.policy.queries import trace_entity

        con = self._ensure_compiled()
        result = trace_entity(con, type=type, id=id, property=property, context=context)
        logger.debug(
            "trace",
            extra={
                "entity": f"{type}#{id}",
                "property": property,
                "context": context,
                "candidates": len(result.candidates),
            },
        )
        return result

    def lint(self) -> list[LintWarning]:
        from umwelt.policy.lint import run_lint

        con = self._ensure_compiled()
        return run_lint(con)

    def check(self, *, type: str, id: str, mode: str | None = None, context: list | dict | None = None, **expected: str) -> bool:
        context = self._resolve_mode_to_context(mode, context)
        for prop_name, expected_val in expected.items():
            actual = self.resolve(type=type, id=id, property=prop_name, context=context)
            if actual != expected_val:
                return False
        return True

    def require(self, *, type: str, id: str, mode: str | None = None, context: list | dict | None = None, **expected: str) -> None:
        context = self._resolve_mode_to_context(mode, context)
        for prop_name, expected_val in expected.items():
            actual = self.resolve(type=type, id=id, property=prop_name, context=context)
            if actual != expected_val:
                logger.warning(
                    "require_denied",
                    extra={
                        "entity": f"{type}#{id}",
                        "property": prop_name,
                        "expected": expected_val,
                        "actual": actual,
                    },
                )
                raise PolicyDenied(
                    entity=f"{type}#{id}",
                    property=prop_name,
                    expected=expected_val,
                    actual=actual or "(none)",
                )

    def extend(
        self,
        *,
        entities: list[dict[str, Any]] | None = None,
        stylesheet: str | None = None,
    ) -> PolicyEngine:
        con = self._ensure_compiled()

        new_con = sqlite3.connect(":memory:")
        con.backup(new_con)

        new_engine = PolicyEngine.__new__(PolicyEngine)
        new_engine._con = new_con
        new_engine._pending_entities = list(entities) if entities else []
        new_engine._pending_stylesheets = [stylesheet] if stylesheet else []
        new_engine._compiled = False

        if new_engine._pending_entities or new_engine._pending_stylesheets:
            new_engine._recompile_incremental()

        logger.info(
            "extend",
            extra={
                "entities_added": len(entities) if entities else 0,
                "stylesheet_added": bool(stylesheet),
            },
        )
        return new_engine

    def _recompile_incremental(self) -> None:
        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.dialects import SQLiteDialect
        from umwelt.compilers.sql.populate import populate_from_world
        from umwelt.compilers.sql.resolution import create_resolution_views
        from umwelt.parser import parse as parse_css
        from umwelt.policy.projections import create_projection_views
        from umwelt.world.model import DeclaredEntity, WorldFile

        try:
            _load_default_vocabulary()
        except Exception:
            logger.debug("vocabulary registration skipped", exc_info=True)

        con = self._con
        dialect = SQLiteDialect()

        if self._pending_entities:
            declared = []
            for e in self._pending_entities:
                classes = tuple(e.get("classes", ()))
                declared.append(DeclaredEntity(
                    type=e["type"],
                    id=e["id"],
                    classes=classes,
                    attributes=e.get("attributes", {}),
                    parent=e.get("parent"),
                ))
            wf = WorldFile(entities=tuple(declared), projections=(), warnings=())
            populate_from_world(con, wf)
            self._pending_entities = []

        _resolution_views = (
            "resolved_properties", "_resolved_exact",
            "_resolved_cap", "_resolved_pattern",
        )
        for view_name in _resolution_views:
            con.execute(f'DROP VIEW IF EXISTS "{view_name}"')

        had_stylesheets = bool(self._pending_stylesheets)
        for css_text in self._pending_stylesheets:
            view = parse_css(css_text, validate=False)
            compile_view(con, view, dialect)
        self._pending_stylesheets = []

        if not had_stylesheets:
            try:
                con.execute("SELECT 1 FROM resolved_properties LIMIT 1")
            except sqlite3.OperationalError:
                create_resolution_views(con, dialect)

        for view_name in ("resolved_entities",):
            con.execute(f'DROP VIEW IF EXISTS "{view_name}"')
        existing_views = con.execute(
            "SELECT name FROM sqlite_master WHERE type='view' AND name NOT LIKE '_%'"
        ).fetchall()
        for (vname,) in existing_views:
            if vname != "resolved_properties":
                con.execute(f'DROP VIEW IF EXISTS "{vname}"')
        try:
            create_projection_views(con)
        except Exception:
            logger.debug("projection views skipped", exc_info=True)

        self._compiled = True

    def save(self, path: str | Path) -> None:
        con = self._ensure_compiled()
        target = sqlite3.connect(str(path))
        con.backup(target)
        target.close()

    def to_files(
        self,
        *,
        world: str | Path,
        stylesheet: str | Path,
    ) -> None:
        import json

        import yaml

        con = self._ensure_compiled()

        # Export entities to world YAML
        rows = con.execute(
            "SELECT entity_id, type_name, classes, attributes "
            "FROM entities ORDER BY type_name, entity_id"
        ).fetchall()
        entities_out = []
        for entity_id, type_name, classes_json, attrs_json in rows:
            entry: dict[str, Any] = {"type": type_name, "id": entity_id}
            classes = json.loads(classes_json) if classes_json else []
            if classes:
                entry["classes"] = classes
            attrs = json.loads(attrs_json) if attrs_json else {}
            if attrs:
                entry["attributes"] = attrs
            entities_out.append(entry)

        world_path = Path(world)
        world_data = {"entities": entities_out}
        world_path.write_text(
            yaml.dump(world_data, default_flow_style=False, sort_keys=False)
        )

        # Export stylesheet: copy original if tracked, otherwise emit a comment
        stylesheet_path = Path(stylesheet)
        source_stylesheet: str | None = None
        try:
            row = con.execute(
                "SELECT value FROM compilation_meta WHERE key = 'source_stylesheet'"
            ).fetchone()
            if row:
                source_stylesheet = row[0]
        except Exception:
            pass

        if source_stylesheet and Path(source_stylesheet).exists():
            stylesheet_path.write_bytes(Path(source_stylesheet).read_bytes())
        else:
            # Best-effort: emit each distinct (property_name, property_value) combination
            # grouped by source_file and rule_index as a comment block.
            rule_rows = con.execute(
                "SELECT property_name, property_value, source_file, rule_index "
                "FROM cascade_candidates ORDER BY source_file, rule_index, property_name"
            ).fetchall()
            by_rule: dict[tuple[str, int], list[tuple[str, str]]] = {}
            for prop_name, prop_value, src_file, rule_idx in rule_rows:
                key = (src_file or "", rule_idx)
                by_rule.setdefault(key, []).append((prop_name, prop_value))

            lines = ["/* exported from compiled policy */"]
            for (src_file, rule_idx), props in by_rule.items():
                if src_file:
                    lines.append(f"/* rule {rule_idx} from {src_file} */")
                lines.append("* {")
                for name, value in props:
                    lines.append(f"  {name}: {value};")
                lines.append("}")
                lines.append("")
            stylesheet_path.write_text("\n".join(lines))

    def execute(self, sql: str, params: tuple = ()) -> list[tuple]:
        con = self._ensure_compiled()
        return con.execute(sql, params).fetchall()


def _load_default_vocabulary() -> None:
    from umwelt.registry.plugins import discover_plugins
    loaded = discover_plugins()
    # Fallback: if sandbox wasn't loaded via entry point, import directly.
    if "sandbox" not in loaded:
        try:
            from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
            register_sandbox_vocabulary()
        except ImportError:
            pass
