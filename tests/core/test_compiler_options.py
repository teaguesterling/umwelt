"""Tests for compiler protocol with **options support."""
from __future__ import annotations

from typing import Any

from umwelt.cascade.resolver import ResolvedView
from umwelt.compilers.protocol import Compiler


class OptionsCapturingCompiler:
    target_name = "test"
    target_format = "json"
    altitude = "semantic"

    def __init__(self):
        self.last_options: dict = {}

    def compile(self, view: ResolvedView, **options: Any) -> dict[str, Any]:
        self.last_options = options
        return {"options": options}


def test_compiler_with_options_satisfies_protocol():
    c = OptionsCapturingCompiler()
    assert isinstance(c, Compiler)


def test_compiler_receives_options():
    c = OptionsCapturingCompiler()
    c.compile(ResolvedView(), workspace_root="/workspace", mode="implement")
    assert c.last_options == {"workspace_root": "/workspace", "mode": "implement"}


def test_compiler_works_without_options():
    c = OptionsCapturingCompiler()
    c.compile(ResolvedView())
    assert c.last_options == {}
