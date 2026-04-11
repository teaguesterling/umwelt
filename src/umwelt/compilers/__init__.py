"""The compiler protocol and registry for enforcement targets.

Core umwelt ships zero concrete compilers. Consumers register theirs
via register() at import time.
"""

from umwelt.compilers.protocol import (
    Altitude,
    Compiler,
    available,
    clear_compilers,
    get,
    register,
)

__all__ = [
    "Altitude",
    "Compiler",
    "available",
    "clear_compilers",
    "get",
    "register",
]
