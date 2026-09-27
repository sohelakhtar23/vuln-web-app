import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "vulnerable_app.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email    TEXT,
            password TEXT
        )"""
    )
    conn.commit()
    conn.close()
