"""Validator protocol and registration."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from umwelt.registry.taxa import _current_state, get_taxon, resolve_taxon


@runtime_checkable
class ValidatorProtocol(Protocol):
    """A validator inspects rules in its taxon and emits warnings or errors.

    `rules` is the full list of RuleBlocks whose target_taxon equals the
    validator's registered taxon. The validator mutates the shared `warnings`
    list for soft findings and raises ViewValidationError for hard failures.
    """

    def validate(self, rules: list[Any], warnings: list[Any]) -> None:
        ...


def register_validator(*, taxon: str, validator: ValidatorProtocol) -> None:
    get_taxon(taxon)
    canonical = resolve_taxon(taxon)
    state = _current_state()
    state.validators.setdefault(canonical, []).append(validator)


def get_validators(taxon: str) -> list[ValidatorProtocol]:
    state = _current_state()
    canonical = resolve_taxon(taxon)
    return list(state.validators.get(canonical, []))
