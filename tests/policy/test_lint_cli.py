from __future__ import annotations

import pytest

from umwelt.cli import build_parser


class TestCheckLintFlag:
    def test_check_parser_accepts_lint(self):
        parser = build_parser()
        args = parser.parse_args(["check", "test.umw", "--lint", "warn"])
        assert args.lint == "warn"

    def test_check_default_no_lint(self):
        parser = build_parser()
        args = parser.parse_args(["check", "test.umw"])
        assert args.lint is None


class TestCompileLintFlag:
    def test_compile_parser_accepts_lint(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "test.umw", "--target", "sqlite", "--lint", "error"])
        assert args.lint == "error"

    def test_compile_default_no_lint(self):
        parser = build_parser()
        args = parser.parse_args(["compile", "test.umw", "--target", "sqlite"])
        assert args.lint is None


class TestDryRunLintFlag:
    def test_dry_run_parser_accepts_lint(self):
        parser = build_parser()
        args = parser.parse_args(["dry-run", "test.umw", "--lint", "notice"])
        assert args.lint == "notice"

    def test_dry_run_default_no_lint(self):
        parser = build_parser()
        args = parser.parse_args(["dry-run", "test.umw"])
        assert args.lint is None
