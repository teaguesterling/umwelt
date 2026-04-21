from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    value: str
    specificity: str
    rule_index: int
    source_file: str
    source_line: int
    won: bool


@dataclass(frozen=True)
class TraceResult:
    entity: str
    property: str
    value: str | None
    candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class LintWarning:
    smell: str
    severity: str
    description: str
    entities: tuple[str, ...]
    property: str | None
