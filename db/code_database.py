from __future__ import annotations

import sqlite3
from datetime import datetime
from access_codes import AccessCode
from access_codes import DATETIME_FORMAT


def create_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS access_codes (
            id TEXT PRIMARY KEY,
            secret TEXT NOT NULL,
            datetime TEXT NOT NULL,
            sheet_id INTEGER NOT NULL,
            valid INTEGER NOT NULL CHECK (valid IN (0, 1))
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_access_codes_valid
        ON access_codes(valid)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_access_codes_sheet_id
        ON access_codes(sheet_id)
        """
    )


def upsert_code(conn: sqlite3.Connection, code: AccessCode) -> None:
    conn.execute(
        """
        INSERT INTO access_codes (id, secret, datetime, sheet_id, valid)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            secret = excluded.secret,
            datetime = excluded.datetime,
            sheet_id = excluded.sheet_id,
            valid = excluded.valid
        """,
        (
            code.id,
            code.secret,
            code.datetime.strftime(DATETIME_FORMAT),
            code.sheet_id,
            int(code.valid),
        ),
    )


def _row_to_access_code(row: sqlite3.Row) -> AccessCode:
    return AccessCode(
        id=row["id"],
        secret=row["secret"],
        datetime=datetime.strptime(row["datetime"], DATETIME_FORMAT),
        sheet_id=row["sheet_id"],
        valid=bool(row["valid"]),
    )


def get_code_by_id(conn: sqlite3.Connection, code_id: str) -> AccessCode | None:
    row = conn.execute(
        """
        SELECT id, secret, datetime, sheet_id, valid
        FROM access_codes
        WHERE id = ?
        """,
        (code_id,),
    ).fetchone()

    if row is None:
        return None

    return _row_to_access_code(row)


def get_all_codes(conn: sqlite3.Connection) -> list[AccessCode]:
    rows = conn.execute(
        """
        SELECT id, secret, datetime, sheet_id, valid
        FROM access_codes
        ORDER BY datetime
        """
    ).fetchall()

    return [_row_to_access_code(row) for row in rows]


def invalidate_code(conn: sqlite3.Connection, code_id: str) -> bool:
    cursor = conn.execute(
        """
        UPDATE access_codes
        SET valid = 0
        WHERE id = ? AND valid = 1
        """,
        (code_id,),
    )
    return cursor.rowcount > 0


def get_next_sheet_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT MAX(sheet_id) as max_id
        FROM access_codes
        """
    ).fetchone()

    max_id = row["max_id"] if row["max_id"] is not None else 0
    return max_id + 1


def last_datetime_for_sheet(conn: sqlite3.Connection, sheet_id: int) -> datetime | None:
    row = conn.execute(
        """
        SELECT datetime
        FROM access_codes
        WHERE sheet_id = ?
        ORDER BY datetime DESC
        LIMIT 1
        """,
        (sheet_id,),
    ).fetchone()

    if row is None:
        return None

    return datetime.strptime(row["datetime"], DATETIME_FORMAT)
