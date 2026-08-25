from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jetlinks_ai_api.services.chatbi.demo_db import ensure_demo_db

TABLE_NAMES = {
    "fire_alarm_record",
    "fire_personnel",
    "fire_equipment",
    "fire_inspection",
}

EXPECTED_ROW_COUNTS = {
    "fire_alarm_record": 240,
    "fire_personnel": 80,
    "fire_equipment": 120,
    "fire_inspection": 120,
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    return {row[0] for row in rows}


def _table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: _table_count(conn, table) for table in TABLE_NAMES}


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


@pytest.fixture()
def demo_db_path(tmp_path: Path) -> Path:
    return tmp_path / "chatbi" / "demo.sqlite3"


def test_ensure_demo_db_creates_database_and_returns_none(
    demo_db_path: Path,
) -> None:
    result = ensure_demo_db(str(demo_db_path))

    assert result is None
    assert demo_db_path.is_file()


def test_ensure_demo_db_creates_exact_table_set(demo_db_path: Path) -> None:
    ensure_demo_db(str(demo_db_path))

    with _connect(demo_db_path) as connection:
        assert _table_names(connection) == TABLE_NAMES


@pytest.mark.parametrize(("table", "expected_count"), EXPECTED_ROW_COUNTS.items())
def test_ensure_demo_db_seeds_fixed_row_counts(
    table: str,
    expected_count: int,
    demo_db_path: Path,
) -> None:
    ensure_demo_db(str(demo_db_path))

    with _connect(demo_db_path) as connection:
        assert _table_count(connection, table) == expected_count


def test_ensure_demo_db_is_idempotent(demo_db_path: Path) -> None:
    ensure_demo_db(str(demo_db_path))
    ensure_demo_db(str(demo_db_path))

    with _connect(demo_db_path) as connection:
        assert _counts(connection) == EXPECTED_ROW_COUNTS


def test_ensure_demo_db_creates_missing_parent_directories(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "chatbi" / "level-1" / "level-2" / "demo.sqlite3"

    result = ensure_demo_db(str(database_path))

    assert result is None
    assert database_path.parent.is_dir()
    assert database_path.is_file()
