"""
db.py — Initialises the Jarvis SQLite database schema.
Run this once to create the required tables.
"""

import sqlite3
from backend.config import DB_PATH


def init_db() -> None:
    """Create all required tables if they don't already exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sys_command (
            id   INTEGER PRIMARY KEY,
            name VARCHAR(100),
            path VARCHAR(1000)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_command (
            id   INTEGER PRIMARY KEY,
            name VARCHAR(100),
            url  VARCHAR(1000)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id    INTEGER PRIMARY KEY,
            name  VARCHAR(200),
            Phone VARCHAR(255),
            email VARCHAR(255) NULL
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialised successfully.")


if __name__ == "__main__":
    init_db()
