"""Database connection and initialization for the Vulnerable Web Application.

VULN-1 (SQL Injection) lives in the callers of get_db() — auth_service and
the /search route build SQL by string concatenation. This module is
deliberately minimal: a connection helper, a row factory, and a CREATE
TABLE IF NOT EXISTS on boot.
"""

import sqlite3
from pathlib import Path

# backend/app/db/session.py -> project root (4 parents up)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = _PROJECT_ROOT / "vulnerable_app.db"


def get_db() -> sqlite3.Connection:
    """Open a SQLite connection to vulnerable_app.db at the project root.

    check_same_thread=False simplifies FastAPI's threadpool use.
    Row factory is set so callers can read columns by name.
    """
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the users table on startup if it does not already exist.

    Idempotent: safe to call on every boot. The DB file itself is created
    automatically by sqlite3.connect() if it does not exist.
    """
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email    TEXT,
                password TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
