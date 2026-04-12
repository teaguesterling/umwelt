"""Tests for the value parser utility."""

import pytest

from umwelt.sandbox.compilers._value_parser import (
    parse_memory_mb,
    parse_size_for_tmpfs,
    parse_time_seconds,
)


def test_memory_mb():
    assert parse_memory_mb("512MB") == 512
    assert parse_memory_mb("1GB") == 1024
    assert parse_memory_mb("256") == 256  # default MB
    assert parse_memory_mb("512mb") == 512  # case insensitive


def test_memory_mb_kilobytes():
    assert parse_memory_mb("2048KB") == 2
    assert parse_memory_mb("512KB") == max(1, 512 // 1024)


def test_memory_mb_terabytes():
    assert parse_memory_mb("1TB") == 1024 * 1024


def test_memory_mb_invalid():
    with pytest.raises(ValueError, match="cannot parse memory value"):
        parse_memory_mb("not-a-number")


def test_time_seconds():
    assert parse_time_seconds("60s") == 60
    assert parse_time_seconds("5m") == 300
    assert parse_time_seconds("1h") == 3600
    assert parse_time_seconds("60") == 60  # default seconds


def test_time_seconds_milliseconds():
    assert parse_time_seconds("2000ms") == 2
    assert parse_time_seconds("500ms") == max(1, 500 // 1000)


def test_time_seconds_invalid():
    with pytest.raises(ValueError, match="cannot parse time value"):
        parse_time_seconds("forever")


def test_tmpfs_size():
    assert parse_size_for_tmpfs("64MB") == "64M"
    assert parse_size_for_tmpfs("1GB") == "1G"


def test_tmpfs_size_kb():
    assert parse_size_for_tmpfs("512KB") == "512K"


def test_tmpfs_size_default_unit():
    assert parse_size_for_tmpfs("128") == "128M"  # default MB


def test_tmpfs_size_invalid():
    with pytest.raises(ValueError, match="cannot parse size value"):
        parse_size_for_tmpfs("huge")
