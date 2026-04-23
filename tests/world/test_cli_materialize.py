
import pytest
import yaml

from umwelt.cli import build_parser, main
from umwelt.registry.taxa import registry_scope


@pytest.fixture(autouse=True)
def fresh_registry():
    """Isolate each test in its own registry scope so vocabulary can be re-registered."""
    with registry_scope():
        yield


def test_materialize_subcommand_exists():
    parser = build_parser()
    args = parser.parse_args(["materialize", "test.world.yml"])
    assert args.command == "materialize"

def test_materialize_default_level():
    parser = build_parser()
    args = parser.parse_args(["materialize", "test.world.yml"])
    assert args.level == "full"

def test_materialize_accepts_level_flag():
    parser = build_parser()
    args = parser.parse_args(["materialize", "test.world.yml", "--level", "summary"])
    assert args.level == "summary"

def test_materialize_to_stdout(tmp_path, capsys):
    p = tmp_path / "test.world.yml"
    p.write_text("entities:\n  - type: tool\n    id: Read\n")
    rc = main(["materialize", str(p)])
    assert rc == 0
    out = capsys.readouterr().out
    parsed = yaml.safe_load(out)
    assert parsed["meta"]["entity_count"] == 1

def test_materialize_to_file(tmp_path):
    p = tmp_path / "test.world.yml"
    p.write_text("entities:\n  - type: tool\n    id: Read\n")
    out = tmp_path / "out.yml"
    rc = main(["materialize", str(p), "-o", str(out)])
    assert rc == 0
    assert out.exists()
    parsed = yaml.safe_load(out.read_text())
    assert parsed["meta"]["entity_count"] == 1

def test_materialize_file_not_found(capsys):
    rc = main(["materialize", "/nonexistent.world.yml"])
    assert rc == 2
