"""Tests for the umwelt error hierarchy."""

import pytest

from umwelt.errors import (
    RegistryError,
    UmweltError,
    ViewError,
    ViewParseError,
    ViewValidationError,
)


def test_umwelt_error_is_exception():
    assert issubclass(UmweltError, Exception)


def test_view_error_is_umwelt_error():
    assert issubclass(ViewError, UmweltError)


def test_view_parse_error_is_view_error():
    assert issubclass(ViewParseError, ViewError)


def test_view_validation_error_is_view_error():
    assert issubclass(ViewValidationError, ViewError)


def test_registry_error_is_umwelt_error():
    assert issubclass(RegistryError, UmweltError)


def test_view_parse_error_captures_position():
    err = ViewParseError("unexpected token", line=5, col=12)
    assert err.line == 5
    assert err.col == 12
    assert "line 5" in str(err)
    assert "col 12" in str(err)


def test_view_parse_error_optional_source_path():
    from pathlib import Path

    err = ViewParseError(
        "unexpected token", line=5, col=12, source_path=Path("views/test.umw")
    )
    assert err.source_path == Path("views/test.umw")
    assert "views/test.umw" in str(err)


def test_view_parse_error_raises_cleanly():
    with pytest.raises(ViewParseError, match="unexpected token"):
        raise ViewParseError("unexpected token", line=1, col=1)
