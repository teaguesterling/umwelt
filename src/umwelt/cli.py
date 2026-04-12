"""Command-line interface for umwelt."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from pprint import pformat

from umwelt.check_util import format_check
from umwelt.dry_run import format_dry_run
from umwelt.errors import ViewError
from umwelt.inspect_util import format_inspection
from umwelt.parser import parse


def _preload_toy_taxonomy_if_requested() -> None:
    """For tests: if UMWELT_PRELOAD_TOY=1, install the toy taxonomy.

    The CLI is otherwise vocabulary-agnostic — it parses whatever taxa
    are currently registered, which in production is whatever the
    consumer imported. This hook is solely for test runs.
    """
    if os.environ.get("UMWELT_PRELOAD_TOY") != "1":
        return
    try:
        # We can't import from tests/ at runtime in production; guard.
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from tests.core.helpers.toy_taxonomy import (
            ToyShapesMatcher,
            ToyThing,
            install_toy_taxonomy,
        )

        things_env = os.environ.get("UMWELT_PRELOAD_TOY_THINGS", "")
        things: list[ToyThing] = []
        for entry in filter(None, things_env.split(",")):
            if ":" not in entry:
                continue
            ident, color = entry.split(":", 1)
            things.append(
                ToyThing(type_name="thing", id=ident.strip(), color=color.strip())
            )
        shapes = ToyShapesMatcher(things=things)
        install_toy_taxonomy(shapes_matcher=shapes)
    except Exception:
        pass


def _cmd_parse(args: argparse.Namespace) -> int:
    _preload_toy_taxonomy_if_requested()
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
    _preload_toy_taxonomy_if_requested()
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
    _preload_toy_taxonomy_if_requested()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_dry_run(view))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    _preload_toy_taxonomy_if_requested()
    try:
        view = parse(Path(args.file))
    except FileNotFoundError as exc:
        print(f"error: No such file: {exc.filename}", file=sys.stderr)
        return 2
    except ViewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_check(view))
    return 0


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
    p_dry.set_defaults(func=_cmd_dry_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
