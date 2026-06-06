"""
monitor.py — API & Performance Monitoring for Jarvis (Phase 3).

Tracks every API call, error, and performance metric. Provides
aggregated stats for the monitoring dashboard.

Usage:
    from backend.monitor import log_api_call, log_error, get_daily_stats

    # Log a Gemini API call
    log_api_call("gemini", "gemini-2.5-flash", latency_ms=320, tokens_used=150, success=True)

    # Log an error
    log_error("chatBot", "Connection timeout", severity="warning")

    # Get today's stats
    stats = get_daily_stats()
"""

import datetime
import logging
import sqlite3
import threading
import time
from functools import wraps

from backend.config import DB_PATH, MONITOR_ENABLED

logger = logging.getLogger(__name__)

_db_lock = threading.Lock()


# ── Database helpers ─────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    """Create monitoring tables if they don't exist."""
    conn = _get_conn()
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()


_ensure_tables()


# ─────────────────────────────────────────────────────────────────────────────
# API CALL LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def log_api_call(
    service: str,
    model: str = None,
    latency_ms: int = 0,
    tokens_used: int = 0,
    success: bool = True,
    error_msg: str = None,
) -> None:
    """
    Log an API call to the monitoring database.

    Args:
        service:     Service name (e.g., "gemini", "whisper", "google_search", "spotify")
        model:       Model name if applicable (e.g., "gemini-2.5-flash")
        latency_ms:  Response time in milliseconds
        tokens_used: Token count (for LLM calls)
        success:     Whether the call succeeded
        error_msg:   Error message if it failed
    """
    if not MONITOR_ENABLED:
        return
    try:
        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO api_logs (service, model, latency_ms, tokens_used, success, error_msg) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (service, model, latency_ms, tokens_used, 1 if success else 0, error_msg),
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.warning("log_api_call() error: %s", e)


def log_error(source: str, error_msg: str, severity: str = "error") -> None:
    """
    Log an error to the monitoring database.

    Args:
        source:    Where the error came from (e.g., "chatBot", "web_rag", "spotify")
        error_msg: The error message
        severity:  "info", "warning", "error", or "critical"
    """
    if not MONITOR_ENABLED:
        return
    try:
        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO error_logs (source, error_msg, severity) VALUES (?, ?, ?)",
                (source, str(error_msg)[:500], severity),
            )
            conn.commit()
            conn.close()
    except Exception as e:
        logger.warning("log_error() error: %s", e)



# ─────────────────────────────────────────────────────────────────────────────
# TIMER DECORATOR (for easy API call wrapping)
# ─────────────────────────────────────────────────────────────────────────────

def timed_api_call(service: str, model: str = None):
    """
    Decorator that automatically logs API call timing and success/failure.

    Usage:
        @timed_api_call("gemini", "gemini-2.5-flash")
        def call_gemini(prompt):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                elapsed_ms = int((time.time() - start) * 1000)
                log_api_call(service, model, latency_ms=elapsed_ms, success=True)
                return result
            except Exception as e:
                elapsed_ms = int((time.time() - start) * 1000)
                log_api_call(service, model, latency_ms=elapsed_ms, success=False, error_msg=str(e))
                raise
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# STATS & REPORTS
# ─────────────────────────────────────────────────────────────────────────────

def get_daily_stats() -> dict:
    """
    Get today's aggregated stats.

    Returns:
        {
            "date": "2024-06-06",
            "total_calls": 42,
            "successful_calls": 40,
            "failed_calls": 2,
            "avg_latency_ms": 285,
            "total_tokens": 5200,
            "total_errors": 3,
            "calls_by_service": {"gemini": 30, "google_search": 10, ...},
        }
    """
    today = datetime.date.today().isoformat()
    try:
        conn = _get_conn()
        cursor = conn.cursor()

        # Total calls today
        cursor.execute(
            "SELECT COUNT(*) as total, "
            "SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as ok, "
            "SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as fail, "
            "COALESCE(AVG(latency_ms), 0) as avg_lat, "
            "COALESCE(SUM(tokens_used), 0) as total_tokens "
            "FROM api_logs WHERE DATE(timestamp) = ?",
            (today,),
        )
        row = cursor.fetchone()

        # Calls by service
        cursor.execute(
            "SELECT service, COUNT(*) as cnt "
            "FROM api_logs WHERE DATE(timestamp) = ? "
            "GROUP BY service ORDER BY cnt DESC",
            (today,),
        )
        by_service = {r["service"]: r["cnt"] for r in cursor.fetchall()}

        # Errors today
        cursor.execute(
            "SELECT COUNT(*) FROM error_logs WHERE DATE(timestamp) = ?",
            (today,),
        )
        error_count = cursor.fetchone()[0]

        conn.close()

        return {
            "date": today,
            "total_calls": row["total"] or 0,
            "successful_calls": row["ok"] or 0,
            "failed_calls": row["fail"] or 0,
            "avg_latency_ms": round(row["avg_lat"] or 0),
            "total_tokens": row["total_tokens"] or 0,
            "total_errors": error_count,
            "calls_by_service": by_service,
        }
    except Exception as e:
        logger.error("get_daily_stats() error: %s", e)
        return {}


def get_usage_report(days: int = 7) -> list[dict]:
    """
    Get daily usage breakdown for the past N days.

    Returns:
        List of daily stats dicts, one per day, sorted newest first.
    """
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DATE(timestamp) as day, "
            "COUNT(*) as total_calls, "
            "SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as ok, "
            "SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as fail, "
            "COALESCE(AVG(latency_ms), 0) as avg_lat, "
            "COALESCE(SUM(tokens_used), 0) as tokens "
            "FROM api_logs "
            "WHERE timestamp >= DATE('now', ?) "
            "GROUP BY DATE(timestamp) "
            "ORDER BY day DESC",
            (f"-{days} days",),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "date": row["day"],
                "total_calls": row["total_calls"],
                "successful_calls": row["ok"] or 0,
                "failed_calls": row["fail"] or 0,
                "avg_latency_ms": round(row["avg_lat"] or 0),
                "total_tokens": row["tokens"] or 0,
            }
            for row in rows
        ]
    except Exception as e:
        logger.error("get_usage_report() error: %s", e)
        return []


def get_recent_errors(limit: int = 20) -> list[dict]:
    """Get the most recent error log entries."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, source, error_msg, severity, timestamp "
            "FROM error_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("get_recent_errors() error: %s", e)
        return []


def get_recent_api_calls(limit: int = 20) -> list[dict]:
    """Get the most recent API call log entries."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, service, model, latency_ms, tokens_used, success, error_msg, timestamp "
            "FROM api_logs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("get_recent_api_calls() error: %s", e)
        return []


def get_service_breakdown(days: int = 7) -> list[dict]:
    """Get call counts grouped by service for the past N days."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT service, COUNT(*) as calls, "
            "COALESCE(AVG(latency_ms), 0) as avg_lat, "
            "SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures "
            "FROM api_logs WHERE timestamp >= DATE('now', ?) "
            "GROUP BY service ORDER BY calls DESC",
            (f"-{days} days",),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "service": row["service"],
                "calls": row["calls"],
                "avg_latency_ms": round(row["avg_lat"]),
                "failures": row["failures"] or 0,
            }
            for row in rows
        ]
    except Exception as e:
        logger.error("get_service_breakdown() error: %s", e)
        return []


def get_hourly_distribution(date: str = None) -> list[dict]:
    """Get call counts by hour for a given date (defaults to today)."""
    if date is None:
        date = datetime.date.today().isoformat()
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT CAST(strftime('%H', timestamp) AS INTEGER) as hour, "
            "COUNT(*) as calls "
            "FROM api_logs WHERE DATE(timestamp) = ? "
            "GROUP BY hour ORDER BY hour",
            (date,),
        )
        rows = cursor.fetchall()
        conn.close()

        # Fill in missing hours with 0
        hour_map = {row["hour"]: row["calls"] for row in rows}
        return [{"hour": h, "calls": hour_map.get(h, 0)} for h in range(24)]

    except Exception as e:
        logger.error("get_hourly_distribution() error: %s", e)
        return [{"hour": h, "calls": 0} for h in range(24)]


# ─────────────────────────────────────────────────────────────────────────────
# EEL EXPOSED FUNCTIONS (for the dashboard)
# ─────────────────────────────────────────────────────────────────────────────

try:
    import eel

    @eel.expose
    def getMonitorStats():
        """Eel-exposed: get all dashboard data in one call."""
        return {
            "daily": get_daily_stats(),
            "weekly": get_usage_report(7),
            "services": get_service_breakdown(7),
            "hourly": get_hourly_distribution(),
            "recent_errors": get_recent_errors(10),
            "recent_calls": get_recent_api_calls(15),
        }

except Exception:
    pass  # Eel not available (e.g., during testing)
