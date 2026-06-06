"""
smoke_test_monitoring.py — Quick smoke test for the Jarvis performance monitoring system.
"""

import sys
sys.path.insert(0, ".")

import time
import sqlite3
from backend.config import DB_PATH, MONITOR_ENABLED
from backend.monitor import (
    log_api_call, log_error, timed_api_call,
    get_daily_stats, get_usage_report, get_recent_errors,
    get_recent_api_calls, get_service_breakdown, get_hourly_distribution
)

def cleanup_test_logs():
    """Remove test log entries from the database to avoid cluttering the dashboard."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM api_logs WHERE service LIKE 'test_%'")
    cursor.execute("DELETE FROM error_logs WHERE source LIKE 'test_%'")
    conn.commit()
    conn.close()

def main():
    print("=" * 60)
    print("JARVIS PERFORMANCE MONITORING SYSTEM — SMOKE TEST")
    print("=" * 60)

    # Clean up any leftover test runs first
    cleanup_test_logs()

    try:
        # ── Test 1: Log API Calls ─────────────────────────────────────────
        print("\n[TEST 1] Logging test API calls...")
        log_api_call("test_gemini", "gemini-2.5-flash", latency_ms=450, tokens_used=120, success=True)
        log_api_call("test_gemini", "gemini-2.5-flash", latency_ms=500, tokens_used=150, success=True)
        log_api_call("test_google_search", latency_ms=850, success=True)
        log_api_call("test_weather", latency_ms=320, success=False, error_msg="Timeout connecting to wttr.in")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM api_logs WHERE service LIKE 'test_%'")
        count = cursor.fetchone()[0]
        conn.close()

        print(f"  Logged {count} API calls in DB.")
        assert count == 4, f"FAILED: Expected 4 test API calls, got {count}"
        print("  PASSED ✅")

        # ── Test 2: Log Errors ────────────────────────────────────────────
        print("\n[TEST 2] Logging test errors...")
        log_error("test_chatbot", "Gemini API rate limit exceeded", severity="warning")
        log_error("test_weather", "wttr.in returned 502 Bad Gateway", severity="error")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM error_logs WHERE source LIKE 'test_%'")
        count = cursor.fetchone()[0]
        conn.close()

        print(f"  Logged {count} errors in DB.")
        assert count == 2, f"FAILED: Expected 2 test errors, got {count}"
        print("  PASSED ✅")

        # ── Test 3: Timed Decorator ───────────────────────────────────────
        print("\n[TEST 3] Testing timed_api_call decorator...")
        
        @timed_api_call("test_decorator_service", "test-model-1")
        def mock_api_call(should_fail=False):
            time.sleep(0.05) # simulate 50ms work
            if should_fail:
                raise ValueError("Decorator call mock error")
            return "ok"

        res = mock_api_call()
        assert res == "ok", f"FAILED: Expected 'ok', got {res}"

        try:
            mock_api_call(should_fail=True)
        except ValueError:
            pass # Expected

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*), SUM(success), SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) "
            "FROM api_logs WHERE service = 'test_decorator_service'"
        )
        total, ok, fail = cursor.fetchone()
        conn.close()

        print(f"  Decorator logged: {total} total, {ok} ok, {fail} failed.")
        assert total == 2, f"FAILED: Expected 2 decorator logs, got {total}"
        assert ok == 1, f"FAILED: Expected 1 successful decorator log, got {ok}"
        assert fail == 1, f"FAILED: Expected 1 failed decorator log, got {fail}"
        print("  PASSED ✅")

        # ── Test 4: Retrieve Stats ────────────────────────────────────────
        print("\n[TEST 4] Retrieving daily and hourly statistics...")
        stats = get_daily_stats()
        print(f"  Daily stats: {stats.get('total_calls')} total calls today, avg latency = {stats.get('avg_latency_ms')} ms")
        assert stats.get("total_calls", 0) >= 6, "FAILED: Expected at least 6 calls in stats today"

        hourly = get_hourly_distribution()
        total_hourly_calls = sum(h["calls"] for h in hourly)
        print(f"  Hourly activity distribution total: {total_hourly_calls} calls")
        assert total_hourly_calls >= 6, "FAILED: Expected at least 6 calls in hourly distribution"
        print("  PASSED ✅")

        # ── Test 5: Reports and Service Breakdown ─────────────────────────
        print("\n[TEST 5] Checking service breakdowns and logs lists...")
        breakdown = get_service_breakdown(1)
        print("  Service breakdown:")
        for b in breakdown:
            if b["service"].startswith("test_"):
                print(f"    - {b['service']}: {b['calls']} calls, {b['failures']} failures, avg={b['avg_latency_ms']}ms")

        recent_calls = get_recent_api_calls(10)
        recent_errors = get_recent_errors(10)
        print(f"  Recent API logs retrieved: {len(recent_calls)}")
        print(f"  Recent Error logs retrieved: {len(recent_errors)}")
        assert len(recent_calls) >= 6, "FAILED: Expected at least 6 recent API calls"
        assert len(recent_errors) >= 2, "FAILED: Expected at least 2 recent errors"
        print("  PASSED ✅")

        # ── Test 6: Disabled Monitoring ───────────────────────────────────
        print("\n[TEST 6] Testing MONITOR_ENABLED = False bypass...")
        
        # Temporarily mutate the import to simulate disabled config
        import backend.monitor
        original_val = backend.monitor.MONITOR_ENABLED
        backend.monitor.MONITOR_ENABLED = False

        try:
            log_api_call("test_disabled_service", success=True)
            log_error("test_disabled_source", "should not log")

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM api_logs WHERE service = 'test_disabled_service'")
            c1 = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM error_logs WHERE source = 'test_disabled_source'")
            c2 = cursor.fetchone()[0]
            conn.close()

            print(f"  Disabled logs count: api_logs={c1}, error_logs={c2}")
            assert c1 == 0, "FAILED: Logged API call while monitoring was disabled"
            assert c2 == 0, "FAILED: Logged error while monitoring was disabled"
            print("  PASSED ✅")
        finally:
            backend.monitor.MONITOR_ENABLED = original_val

    finally:
        # ── Cleanup ───────────────────────────────────────────────────────
        print("\nCleaning up test logs from database...")
        cleanup_test_logs()
        print("Cleanup done.")

    print("\n" + "=" * 60)
    print("ALL MONITORING TESTS PASSED! ✅ Monitoring is fully operational.")
    print("=" * 60)

if __name__ == "__main__":
    main()
