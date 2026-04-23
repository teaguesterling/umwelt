"""Command-line interface for umwelt."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from pprint import pformat

from umwelt.check_util import format_check
from umwelt.dry_run import format_dry_run
from umwelt.errors import ViewError
from umwelt.inspect_util import format_inspection
from umwelt.parser import parse


def _load_default_vocabulary() -> None:
    """Auto-load the sandbox vocabulary and compilers if available."""
    try:
        from umwelt.sandbox.compilers import register_sandbox_compilers
        from umwelt.sandbox.desugar import register_sandbox_sugar
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()
        register_sandbox_sugar()
        register_sandbox_compilers()
    except ImportError:
        pass


def _register_matchers(view_file: Path) -> None:
    """Register filesystem/capability/state matchers using the view file's directory.

    Called before resolve() to give the selector engine entity sources.
    Silently skips if matchers are already registered (e.g. in tests that
    pre-register their own matchers).
    """
    import contextlib

    try:
        from umwelt.errors import RegistryError
        from umwelt.registry import register_matcher
        from umwelt.sandbox.actor_matcher import ActorMatcher
        from umwelt.sandbox.capability_matcher import CapabilityMatcher
        from umwelt.sandbox.principal_matcher import PrincipalMatcher
        from umwelt.sandbox.state_matcher import StateMatcher
        from umwelt.sandbox.world_matcher import WorldMatcher

        base_dir = view_file.resolve().parent
        with contextlib.suppress(RegistryError):
            register_matcher(taxon="world", matcher=WorldMatcher(base_dir=base_dir))
        with contextlib.suppress(RegistryError):
            register_matcher(taxon="capability", matcher=CapabilityMatcher())
        with contextlib.suppress(RegistryError):
            register_matcher(taxon="state", matcher=StateMatcher())
        with contextlib.suppress(RegistryError):
            register_matcher(taxon="actor", matcher=ActorMatcher())
        with contextlib.suppress(RegistryError):
            register_matcher(taxon="principal", matcher=PrincipalMatcher())
        from umwelt.sandbox.audit_matcher import AuditMatcher
        with contextlib.suppress(RegistryError):
            register_matcher(taxon="audit", matcher=AuditMatcher())
    except ImportError:
        pass


def _cmd_parse(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(pformat(view, width=100))
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_inspection(view))
    return 0


def _cmd_dry_run(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _register_matchers(Path(args.file))
    print(format_dry_run(view, world=getattr(args, "world", None)))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _register_matchers(Path(args.file))
    print(format_check(view))
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    SQL_TARGETS = {"sqlite", "duckdb"}
    if args.target in SQL_TARGETS:
        return _cmd_compile_sql(args, view)

    _register_matchers(Path(args.file))

    from umwelt import compilers as compiler_registry
    from umwelt.cascade.resolver import resolve
    from umwelt.errors import RegistryError

    try:
        compiler = compiler_registry.get(args.target)
    except RegistryError:
        available = compiler_registry.available()
        names = ", ".join(available) if available else "(none)"
        print(
            f"error: no compiler registered for target {args.target!r}. "
            f"Available: {names}, sqlite, duckdb",
            file=sys.stderr,
        )
        return 1

    resolved = resolve(view, world=getattr(args, "world", None))
    output = compiler.compile(resolved)
    if isinstance(output, str):
        print(output, end="")
    elif isinstance(output, list):
        for item in output:
            print(item)
    elif isinstance(output, dict):
        import json
        print(json.dumps(output, indent=2))
    return 0


def _cmd_compile_sql(args: argparse.Namespace, view) -> int:
    """Compile a view to SQL text or a database."""
    try:
        from umwelt.compilers.sql.dialects import get_dialect
        from umwelt.compilers.sql.schema import create_schema
        from umwelt.compilers.sql.compiler import compile_view
        from umwelt.compilers.sql.populate import populate_entities
        from umwelt.compilers.sql.resolution import create_resolution_views, resolution_ddl
    except ImportError:
        print(
            "error: SQL compilation requires the 'sql' extras. "
            "Install with: pip install umwelt[sql]",
            file=sys.stderr,
        )
        return 1

    dialect = get_dialect(args.target)
    view_path = Path(args.file)
    _register_matchers(view_path)

    db_path = getattr(args, "db", None)
    output_path = getattr(args, "output", None)

    # Generate SQL text
    sql_text = create_schema(dialect)

    if db_path:
        if args.target == "sqlite":
            import sqlite3
            con = sqlite3.connect(db_path)
            con.executescript(sql_text)
            populate_entities(con, view_path.resolve().parent)
            compile_view(con, view, dialect, source_file=str(view_path))
            entity_n = con.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
            resolved_n = con.execute("SELECT COUNT(*) FROM resolved_properties").fetchone()[0]
            con.commit()
            con.close()
            print(f"Compiled {db_path}: {entity_n} entities, {resolved_n} resolved properties")
        elif args.target == "duckdb":
            try:
                import duckdb
            except ImportError:
                print("error: --db with duckdb target requires: pip install umwelt[duckdb]", file=sys.stderr)
                return 1
            print("error: DuckDB --db execution not yet implemented", file=sys.stderr)
            return 1

    if output_path:
        sql_with_resolution = sql_text + "\n\n" + resolution_ddl(dialect)
        Path(output_path).write_text(sql_with_resolution)
        if not db_path:
            print(f"SQL written to {output_path}")

    if not db_path and not output_path:
        sql_with_resolution = sql_text + "\n\n" + resolution_ddl(dialect)
        print(sql_with_resolution, end="")

    return 0


def _cmd_materialize(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    from umwelt.errors import WorldParseError
    from umwelt.world.materialize import materialize, render_yaml
    from umwelt.world.model import DetailLevel
    from umwelt.world.parser import load_world
    from umwelt.world.validate import validate_world

    try:
        world = load_world(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except WorldParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    world = validate_world(world)
    level = DetailLevel(args.level)
    result = materialize(world, level=level)
    output = render_yaml(result)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Materialized to {args.output}")
    else:
        print(output, end="")
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view_a = parse(Path(args.file_a))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        view_b = parse(Path(args.file_b))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    from umwelt.diff_util import diff_views, format_diff

    diff = diff_views(view_a, view_b)
    print(format_diff(diff))
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _register_matchers(Path(args.file))
    from umwelt.audit import format_audit
    print(format_audit(view, world=getattr(args, "world", None)))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    _load_default_vocabulary()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _register_matchers(Path(args.file))

    import shutil

    from umwelt.cascade.resolver import resolve

    resolved = resolve(view)
    command = args.command
    workspace_root = getattr(args, "workspace_root", "/workspace")
    target = getattr(args, "target", "nsjail")

    if target == "bwrap":
        if shutil.which("bwrap") is None:
            print("error: bwrap binary not found on PATH", file=sys.stderr)
            return 1
        from umwelt.sandbox.runners.bwrap import run_in_bwrap
        bwrap_result = run_in_bwrap(resolved, command, workspace_root=workspace_root)
        if bwrap_result.stdout:
            print(bwrap_result.stdout, end="")
        if bwrap_result.stderr:
            print(bwrap_result.stderr, end="", file=sys.stderr)
        return bwrap_result.returncode
    else:
        if shutil.which("nsjail") is None:
            print("error: nsjail binary not found on PATH", file=sys.stderr)
            return 1
        from umwelt.sandbox.runners.nsjail import run_in_nsjail
        nsjail_result = run_in_nsjail(resolved, command, workspace_root=workspace_root)
        if nsjail_result.stdout:
            print(nsjail_result.stdout, end="")
        if nsjail_result.stderr:
            print(nsjail_result.stderr, end="", file=sys.stderr)
        return nsjail_result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="umwelt",
        description="umwelt — the common language of the specified band",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_parse = subparsers.add_parser("parse", help="parse a view and print the AST")
    p_parse.add_argument("file", help="path to a .umw view file")
    p_parse.set_defaults(func=_cmd_parse)

    p_inspect = subparsers.add_parser(
        "inspect", help="print a structural summary of a view"
    )
    p_inspect.add_argument("file", help="path to a .umw view file")
    p_inspect.set_defaults(func=_cmd_inspect)

    p_check = subparsers.add_parser(
        "check", help="parse, validate, and run every registered compiler"
    )
    p_check.add_argument("file", help="path to a .umw view file")
    p_check.set_defaults(func=_cmd_check)

    p_dry = subparsers.add_parser(
        "dry-run", help="resolve a view and print per-entity cascaded properties"
    )
    p_dry.add_argument("file", help="path to a .umw view file")
    p_dry.add_argument(
        "--world", default=None,
        help="named world environment to resolve against (e.g. dev, ci)",
    )
    p_dry.set_defaults(func=_cmd_dry_run)

    p_audit = subparsers.add_parser(
        "audit", help="security-aware policy audit with widening detection"
    )
    p_audit.add_argument("file", help="path to a .umw view file")
    p_audit.add_argument(
        "--world", default=None,
        help="named world environment to audit",
    )
    p_audit.set_defaults(func=_cmd_audit)

    p_compile = subparsers.add_parser(
        "compile", help="compile a view to a target's native config format"
    )
    p_compile.add_argument("file", help="path to a .umw view file")
    p_compile.add_argument(
        "--target", required=True, help="compiler target name (e.g. nsjail)"
    )
    p_compile.add_argument(
        "--world", default=None,
        help="named world environment to resolve against (e.g. dev, ci)",
    )
    p_compile.add_argument(
        "-o", "--output", default=None,
        help="output file path for SQL text",
    )
    p_compile.add_argument(
        "-d", "--db", default=None,
        help="database connection string or file path (executes SQL)",
    )
    p_compile.set_defaults(func=_cmd_compile)

    p_mat = subparsers.add_parser("materialize", help="materialize a .world.yml file")
    p_mat.add_argument("file", help="path to a .world.yml file")
    p_mat.add_argument("--level", choices=["summary", "outline", "full"], default="full",
                       help="detail level (default: full)")
    p_mat.add_argument("-o", "--output", default=None, help="output file path")
    p_mat.set_defaults(func=_cmd_materialize)

    p_diff = subparsers.add_parser(
        "diff", help="compare two view files and show rule-level differences"
    )
    p_diff.add_argument("file_a", help="path to first .umw view file")
    p_diff.add_argument("file_b", help="path to second .umw view file")
    p_diff.set_defaults(func=_cmd_diff)

    p_run = subparsers.add_parser(
        "run", help="compile a view and run a command inside the sandbox"
    )
    p_run.add_argument("file", help="path to a .umw view file")
    p_run.add_argument(
        "--target", default="nsjail", help="compiler/runner target (default: nsjail)"
    )
    p_run.add_argument(
        "--workspace-root", default="/workspace", dest="workspace_root",
        help="workspace root inside the sandbox (default: /workspace)",
    )
    p_run.add_argument(
        "command", nargs=argparse.REMAINDER, help="command to run inside the sandbox"
    )
    p_run.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
