"""Parse view declaration values into nsjail-native units."""

import re

_SIZE_PATTERN = re.compile(r'^(\d+)\s*(KB|MB|GB|TB)?$', re.IGNORECASE)
_TIME_PATTERN = re.compile(r'^(\d+)\s*(ms|s|m|h)?$', re.IGNORECASE)


def parse_memory_mb(value: str) -> int:
    """Parse a memory value like '512MB' into megabytes (nsjail's rlimit_as unit)."""
    m = _SIZE_PATTERN.match(value.strip())
    if not m:
        raise ValueError(f"cannot parse memory value: {value!r}")
    num = int(m.group(1))
    unit = (m.group(2) or "MB").upper()
    if unit == "KB":
        return max(1, num // 1024)
    if unit == "MB":
        return num
    if unit == "GB":
        return num * 1024
    if unit == "TB":
        return num * 1024 * 1024
    return num


def parse_time_seconds(value: str) -> int:
    """Parse a time value like '60s' or '5m' into seconds."""
    m = _TIME_PATTERN.match(value.strip())
    if not m:
        raise ValueError(f"cannot parse time value: {value!r}")
    num = int(m.group(1))
    unit = (m.group(2) or "s").lower()
    if unit == "ms":
        return max(1, num // 1000)
    if unit == "s":
        return num
    if unit == "m":
        return num * 60
    if unit == "h":
        return num * 3600
    return num


def parse_size_for_tmpfs(value: str) -> str:
    """Parse a size value into the format nsjail's tmpfs options expect (e.g. '64M')."""
    m = _SIZE_PATTERN.match(value.strip())
    if not m:
        raise ValueError(f"cannot parse size value: {value!r}")
    num = int(m.group(1))
    unit = (m.group(2) or "MB").upper()
    if unit == "KB":
        return f"{num}K"
    if unit == "MB":
        return f"{num}M"
    if unit == "GB":
        return f"{num}G"
    return f"{num}M"
