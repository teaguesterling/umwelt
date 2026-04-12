"""Shared fixtures for sandbox consumer tests."""

from __future__ import annotations

import pytest

from umwelt.registry import registry_scope
from umwelt.sandbox.vocabulary import register_sandbox_vocabulary


def _register_sandbox() -> None:
    """Register sandbox vocabulary in the current registry scope."""
    register_sandbox_vocabulary()


@pytest.fixture
def sandbox_scope():
    """Enter a fresh registry scope with the sandbox vocabulary registered."""
    with registry_scope() as scope:
        register_sandbox_vocabulary()
        yield scope
