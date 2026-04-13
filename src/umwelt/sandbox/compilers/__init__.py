"""Sandbox enforcement compilers.

Importing this module registers available compilers with the core registry.
"""

from umwelt.compilers import register as register_compiler
from umwelt.sandbox.compilers.bwrap import BwrapCompiler
from umwelt.sandbox.compilers.lackpy_namespace import LackpyNamespaceCompiler
from umwelt.sandbox.compilers.nsjail import NsjailCompiler


def register_sandbox_compilers() -> None:
    """Register all sandbox compilers with the core compiler registry."""
    register_compiler("nsjail", NsjailCompiler())
    register_compiler("bwrap", BwrapCompiler())
    register_compiler("lackpy-namespace", LackpyNamespaceCompiler())
