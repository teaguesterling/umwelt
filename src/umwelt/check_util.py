"""Pipeline check: parse + validate + run every registered compiler."""

from __future__ import annotations

from umwelt.ast import View
from umwelt.cascade.resolver import resolve
from umwelt.compilers import available, get


def format_check(view: View) -> str:
    """Return a human-readable check report for a parsed view."""
    lines: list[str] = []
    total_rules = len(view.rules)
    rule_word = "rule" if total_rules == 1 else "rules"
    lines.append(f"Parsed: {total_rules} {rule_word}, {len(view.warnings)} warnings")

    if view.warnings:
        for w in view.warnings:
            lines.append(f"  warning (line {w.span.line}): {w.message}")

    compilers = available()
    if not compilers:
        lines.append("Compilers: 0 compilers registered (core-only)")
        return "\n".join(lines)

    lines.append(f"Compilers: {len(compilers)} registered")
    resolved = resolve(view)
    for name in compilers:
        compiler = get(name)
        try:
            output = compiler.compile(resolved)
            lines.append(f"  {name} ({compiler.altitude}): OK")
            if isinstance(output, str):
                lines.append(f"    {len(output)} bytes emitted")
            elif isinstance(output, list):
                lines.append(f"    {len(output)} items emitted")
            elif isinstance(output, dict):
                lines.append(f"    {len(output)} keys emitted")
        except Exception as exc:
            lines.append(f"  {name} ({compiler.altitude}): FAILED — {exc}")

    return "\n".join(lines)
