from __future__ import annotations

import sqlite3
from pathlib import Path

# Single source of truth for default DB path
DB_PATH = Path("access_codes.db")


def create_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create a sqlite3 connection with row access by name."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn
