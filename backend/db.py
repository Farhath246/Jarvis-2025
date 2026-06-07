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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      VARCHAR(100) UNIQUE NOT NULL,
            email         VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Memory System Tables (Phase 1) ────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_msg    TEXT NOT NULL,
            jarvis_msg  TEXT NOT NULL,
            topic       VARCHAR(200),
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            key         VARCHAR(100) PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_facts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fact        TEXT NOT NULL,
            source      VARCHAR(100) DEFAULT 'conversation',
            confidence  REAL DEFAULT 1.0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Monitoring Tables (Phase 3) ─────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            service     VARCHAR(50)  NOT NULL,
            model       VARCHAR(100),
            latency_ms  INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            success     BOOLEAN DEFAULT 1,
            error_msg   TEXT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS error_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            source      VARCHAR(100) NOT NULL,
            error_msg   TEXT NOT NULL,
            severity    VARCHAR(20) DEFAULT 'error',
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── AutoML Tables (Phase 4) ──────────────────────────────────────────

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trained_models (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        VARCHAR(100) UNIQUE NOT NULL,
            task_type   VARCHAR(20) NOT NULL,
            target_col  VARCHAR(100) NOT NULL,
            metrics     TEXT,
            model_path  VARCHAR(500) NOT NULL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Database initialised successfully.")


if __name__ == "__main__":
    init_db()
