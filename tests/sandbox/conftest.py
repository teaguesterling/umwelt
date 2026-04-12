"""Shared fixtures for sandbox consumer tests."""

from __future__ import annotations

import sys

import pytest

from umwelt.registry import registry_scope


def _register_sandbox_in_scope() -> None:
    """Register sandbox vocabulary in the current registry scope.

    On first call (before any sandbox module is cached), imports umwelt.sandbox
    so that __init__.py fires into the active scope. On subsequent calls (module
    already cached), calls register_sandbox_vocabulary() directly.
    """
    if "umwelt.sandbox" not in sys.modules:
        import umwelt.sandbox  # noqa: F401  # fires __init__ into current scope
    else:
        from umwelt.sandbox.vocabulary import register_sandbox_vocabulary
        register_sandbox_vocabulary()


@pytest.fixture
def sandbox_scope():
    """Enter a fresh registry scope with the sandbox vocabulary registered."""
    with registry_scope() as scope:
        _register_sandbox_in_scope()
        yield scope
