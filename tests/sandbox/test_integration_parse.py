"""Integration tests: every fixture parses without errors."""

from pathlib import Path
import pytest
from umwelt.parser import parse
from umwelt.registry import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.desugar import register_sandbox_sugar

FIXTURES = Path(__file__).resolve().parents[2] / "src" / "umwelt" / "_fixtures"


def _parse_fixture(name: str):
    with registry_scope():
        register_sandbox_vocabulary()
        register_sandbox_sugar()
        return parse(FIXTURES / name)


def test_minimal_parses():
    view = _parse_fixture("minimal.umw")
    assert len(view.rules) >= 1
    assert view.warnings == () or all("duplicate" not in w.message for w in view.warnings)


def test_readonly_exploration_parses():
    view = _parse_fixture("readonly-exploration.umw")
    assert len(view.rules) >= 5


def test_auth_fix_parses():
    view = _parse_fixture("auth-fix.umw")
    assert len(view.rules) >= 10


def test_actor_conditioned_parses():
    view = _parse_fixture("actor-conditioned.umw")
    assert len(view.rules) >= 2
    # The compound selector should be detected
    compound = view.rules[1].selectors[0]
    assert len(compound.parts) >= 2
