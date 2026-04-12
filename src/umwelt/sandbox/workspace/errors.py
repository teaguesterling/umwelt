"""Workspace-specific errors."""

from umwelt.errors import UmweltError


class WorkspaceError(UmweltError):
    """Raised on workspace build or materialization failures."""


class ViewViolation(UmweltError):
    """Raised when writeback detects a rejected or conflicting change."""
