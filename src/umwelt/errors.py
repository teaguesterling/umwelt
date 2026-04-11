"""Exception hierarchy for umwelt."""

from __future__ import annotations

from pathlib import Path


class UmweltError(Exception):
    """Base class for all umwelt errors."""


class ViewError(UmweltError):
    """Base class for errors raised while handling a view."""


class ViewParseError(ViewError):
    """Raised when a view file fails to parse."""

    def __init__(
        self,
        message: str,
        *,
        line: int,
        col: int,
        source_path: Path | None = None,
    ) -> None:
        self.message = message
        self.line = line
        self.col = col
        self.source_path = source_path
        location = f"line {line}, col {col}"
        if source_path is not None:
            location = f"{source_path} {location}"
        super().__init__(f"{message} ({location})")


class ViewValidationError(ViewError):
    """Raised when a parsed view fails semantic validation."""


class RegistryError(UmweltError):
    """Raised on plugin-registry collisions or lookup failures."""
