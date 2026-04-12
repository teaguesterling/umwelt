"""The first-party sandbox consumer of umwelt.

Importing this package does NOT automatically register the sandbox
vocabulary. Call ``register_sandbox_vocabulary()`` explicitly to register
the world, capability, and state taxa into the active registry scope.

In production code, call it once at startup::

    from umwelt.sandbox import register_sandbox_vocabulary
    register_sandbox_vocabulary()

In tests, call it inside a ``registry_scope()`` context so that the
vocabulary does not pollute the global scope::

    with registry_scope():
        register_sandbox_vocabulary()
        # ... test code ...

Rationale for no auto-registration: Python module imports are cached, so
``import umwelt.sandbox`` only fires the module body once. Auto-registering
at import time would contaminate the global registry scope as a side effect
of module collection, breaking core registry isolation tests. Explicit
registration is predictable and testable.
"""

from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

__all__ = ["register_sandbox_vocabulary"]
