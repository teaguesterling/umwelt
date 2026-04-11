"""Tests for the public import surface."""


def test_top_level_imports():
    from umwelt import (  # noqa: F401
        ParseWarning,
        RegistryError,
        SourceSpan,
        UmweltError,
        View,
        ViewError,
        ViewParseError,
        ViewValidationError,
        __version__,
    )


def test_version_format():
    from umwelt import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0
