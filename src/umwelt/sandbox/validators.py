"""Per-taxon validators for the sandbox vocabulary.

WorldValidator — checks for path-traversal sequences in file/dir selectors.
CapabilityValidator — warns when allow and deny appear on the same selector.
"""

from __future__ import annotations

from umwelt.ast import ParseWarning, RuleBlock


class WorldValidator:
    """Validates world-taxon rules."""

    def validate(self, rules: list[RuleBlock], warnings: list[ParseWarning]) -> None:
        for rule in rules:
            for sel in rule.selectors:
                for part in sel.parts:
                    for attr in part.selector.attributes:
                        if attr.name == "path" and attr.value and ".." in attr.value:
                            from umwelt.errors import ViewValidationError

                            raise ViewValidationError(
                                f"path traversal detected: {attr.value!r}"
                            )


class CapabilityValidator:
    """Validates capability-taxon rules."""

    def validate(self, rules: list[RuleBlock], warnings: list[ParseWarning]) -> None:
        # Check for allow/deny overlap: if the same rule block has both
        # allow: true and allow: false (deny), emit a warning.
        for rule in rules:
            allow_vals: set[str] = set()
            for decl in rule.declarations:
                if decl.property_name == "allow":
                    allow_vals.update(decl.values)
            if "true" in allow_vals and "false" in allow_vals:
                warnings.append(
                    ParseWarning(
                        message="allow and deny on the same selector may conflict",
                        span=rule.span,
                    )
                )
