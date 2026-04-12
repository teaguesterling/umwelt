"""Tests for --world CLI flag."""
from umwelt.cli import build_parser


def test_compile_accepts_world_flag():
    parser = build_parser()
    args = parser.parse_args(["compile", "--target", "nsjail", "--world", "dev", "view.umw"])
    assert args.world == "dev"


def test_dry_run_accepts_world_flag():
    parser = build_parser()
    args = parser.parse_args(["dry-run", "--world", "dev", "view.umw"])
    assert args.world == "dev"


def test_world_defaults_to_none():
    parser = build_parser()
    args = parser.parse_args(["compile", "--target", "nsjail", "view.umw"])
    assert args.world is None
