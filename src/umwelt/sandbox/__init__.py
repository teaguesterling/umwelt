"""The first-party sandbox consumer of umwelt.

Importing this package registers the world, capability, and state taxa
with the active registry scope. In production, that's the global scope.
In tests, use registry_scope() to isolate vocabulary registration.
"""

from umwelt.sandbox.vocabulary import register_sandbox_vocabulary

register_sandbox_vocabulary()
