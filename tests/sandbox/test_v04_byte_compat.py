"""Snapshot tests that compiler output remains byte-identical across v0.5.

Guards claims B1-continuity (compiler output stable across the VSM
restructure), C3-continuity (proof-tree stability proxy), H1 (all three
compilers still work after taxa restructure), A6 (compilers continue
reading world-axis as before — the action-axis was additive only), and
I1 (diff completeness indirect). See
docs/vision/evaluation-framework.md.

The test runs every fixture through every compiler, captures output, and
compares to stored golden files under tests/sandbox/golden/v05/. To
regenerate goldens after an intentional output change, set the
UMWELT_UPDATE_GOLDENS environment variable to "1".
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from umwelt.cascade.resolver import resolve
from umwelt.parser import parse
from umwelt.registry import register_matcher, registry_scope
from umwelt.sandbox.actor_matcher import ActorMatcher
from umwelt.sandbox.capability_matcher import CapabilityMatcher
from umwelt.sandbox.compilers.bwrap import BwrapCompiler
from umwelt.sandbox.compilers.lackpy_namespace import LackpyNamespaceCompiler
from umwelt.sandbox.compilers.nsjail import NsjailCompiler
from umwelt.sandbox.state_matcher import StateMatcher
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
from umwelt.sandbox.world_matcher import WorldMatcher

FIXTURE_DIR = Path(__file__).parent.parent.parent / "src" / "umwelt" / "_fixtures"
GOLDEN_DIR = Path(__file__).parent / "golden" / "v05"


def _serialize(output) -> str:
    """Serialize compiler output to a stable string for snapshot comparison."""
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "\n".join(str(x) for x in output)
    if isinstance(output, dict):
        return json.dumps(output, indent=2, sort_keys=True, default=str)
    return repr(output)


COMPILERS: list[tuple[str, object]] = [
    ("nsjail", NsjailCompiler()),
    ("bwrap", BwrapCompiler()),
    ("lackpy-namespace", LackpyNamespaceCompiler()),
]


def _collect_fixtures() -> list[Path]:
    return sorted(FIXTURE_DIR.glob("*.umw"))


@pytest.fixture
def vocab_with_matchers():
    """Register vocabulary + matchers with base_dir pointing at the fixture dir.

    We use the real fixture directory so WorldMatcher can resolve paths.
    """
    with registry_scope():
        register_sandbox_vocabulary()
        register_matcher(taxon="world", matcher=WorldMatcher(base_dir=FIXTURE_DIR))
        register_matcher(taxon="capability", matcher=CapabilityMatcher())
        register_matcher(taxon="state", matcher=StateMatcher())
        register_matcher(taxon="actor", matcher=ActorMatcher())
        yield


@pytest.mark.parametrize(
    ("fixture", "target"),
    [(f, t) for f in _collect_fixtures() for t, _ in COMPILERS],
    ids=lambda v: v.name if isinstance(v, Path) else str(v),
)
def test_compiler_output_byte_identical(vocab_with_matchers, fixture, target):
    compiler = next(c for t, c in COMPILERS if t == target)
    view = parse(fixture)
    rv = resolve(view)
    output = compiler.compile(rv)
    serialized = _serialize(output)
    golden = GOLDEN_DIR / f"{fixture.stem}.{target}.golden"

    if os.environ.get("UMWELT_UPDATE_GOLDENS") == "1":
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(serialized)
        return

    if not golden.exists():
        pytest.skip(
            f"no golden for {fixture.name} / {target} yet — run with UMWELT_UPDATE_GOLDENS=1"
        )

    expected = golden.read_text()
    assert serialized == expected, (
        f"output drift for {fixture.name} compiled by {target}. "
        f"If intended, run: UMWELT_UPDATE_GOLDENS=1 python3 -m pytest "
        f"tests/sandbox/test_v04_byte_compat.py"
    )
