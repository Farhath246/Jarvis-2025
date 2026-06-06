"""
memory.py — Persistent Memory System for Jarvis (Phase 1).

Gives Jarvis the ability to remember conversations, user preferences,
and learned facts across sessions. All data is stored in the existing
jarvis.db SQLite database.

Usage:
    from backend.memory import (
        save_conversation, get_recent_conversations,
        save_user_preference, get_user_preference, get_all_preferences,
        save_learned_fact, get_learned_facts,
        forget_all, get_memory_summary,
    )
"""

import datetime
import logging
import sqlite3
import threading

from backend.config import (
    DB_PATH, MEMORY_ENABLED, MEMORY_RETENTION_DAYS,
    MEMORY_FACT_EXTRACTION, GEMINI_API_KEY,
)

logger = logging.getLogger(__name__)

# Thread lock for DB writes (SQLite is thread-safe for reads but not concurrent writes)
_db_lock = threading.Lock()


# ── Database helpers ─────────────────────────────────────────────────────────

def _get_conn() -> sqlite3.Connection:
    """Return a new SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables():
    """Create memory tables if they don't exist (safe to call multiple times)."""
    conn = _get_conn()
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()


# Run once on import to ensure tables exist
_ensure_tables()


# ─────────────────────────────────────────────────────────────────────────────
# CONVERSATION HISTORY
# ─────────────────────────────────────────────────────────────────────────────

def save_conversation(user_msg: str, jarvis_msg: str, topic: str = None) -> int | None:
    """
    Save a conversation exchange to the database.

    Args:
        user_msg:   What the user said.
        jarvis_msg: What Jarvis responded.
        topic:      Optional topic tag (e.g., "cricket", "coding", "weather").

    Returns:
        The conversation ID, or None on failure.
    """
    if not MEMORY_ENABLED:
        return None

    try:
        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (user_msg, jarvis_msg, topic) VALUES (?, ?, ?)",
                (user_msg.strip(), jarvis_msg.strip(), topic),
            )
            conv_id = cursor.lastrowid
            conn.commit()
            conn.close()

        logger.info("Saved conversation #%d (topic: %s)", conv_id, topic or "none")

        # Trigger async cleanup of old conversations
        _cleanup_old_conversations()

        return conv_id

    except Exception as e:
        logger.error("save_conversation() error: %s", e)
        return None


def get_recent_conversations(limit: int = 10) -> list[dict]:
    """
    Retrieve the most recent conversations.

    Returns:
        List of dicts with keys: id, user_msg, jarvis_msg, topic, timestamp
    """
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_msg, jarvis_msg, topic, timestamp "
            "FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("get_recent_conversations() error: %s", e)
        return []


def get_conversations_by_topic(topic: str, limit: int = 10) -> list[dict]:
    """Retrieve conversations filtered by topic."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_msg, jarvis_msg, topic, timestamp "
            "FROM conversations WHERE topic LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{topic}%", limit),
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("get_conversations_by_topic() error: %s", e)
        return []


def get_conversation_count() -> int:
    """Return the total number of stored conversations."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM conversations")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error("get_conversation_count() error: %s", e)
        return 0


def build_memory_context(limit: int = 5) -> str:
    """
    Build a formatted string of recent conversations for inclusion
    in the LLM system prompt. This gives Jarvis conversational context.

    Returns:
        A formatted string like:
        --- Recent Memory ---
        [2024-06-05 14:30] User: How do I bowl leg spin?
        [2024-06-05 14:30] Jarvis: Leg spin involves...
        ...
    """
    conversations = get_recent_conversations(limit)
    if not conversations:
        return ""

    # Reverse so oldest is first (chronological order)
    conversations.reverse()

    lines = ["--- Recent Memory (last {} exchanges) ---".format(len(conversations))]
    for conv in conversations:
        ts = conv.get("timestamp", "")[:16]  # Trim to YYYY-MM-DD HH:MM
        lines.append(f"[{ts}] User: {conv['user_msg']}")
        lines.append(f"[{ts}] Jarvis: {conv['jarvis_msg'][:200]}")  # Truncate long responses

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# USER PREFERENCES
# ─────────────────────────────────────────────────────────────────────────────

def save_user_preference(key: str, value: str) -> bool:
    """
    Save or update a user preference.

    Examples:
        save_user_preference("language", "Telugu")
        save_user_preference("favorite_cricketer", "Virat Kohli")
    """
    if not MEMORY_ENABLED:
        return False

    try:
        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_preferences (key, value, updated_at) "
                "VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key.strip().lower(), value.strip()),
            )
            conn.commit()
            conn.close()
        logger.info("Saved preference: %s = %s", key, value)
        return True
    except Exception as e:
        logger.error("save_user_preference() error: %s", e)
        return False


def get_user_preference(key: str) -> str | None:
    """Retrieve a single user preference by key."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM user_preferences WHERE key = ?",
            (key.strip().lower(),),
        )
        row = cursor.fetchone()
        conn.close()
        return row["value"] if row else None
    except Exception as e:
        logger.error("get_user_preference() error: %s", e)
        return None


def get_all_preferences() -> dict:
    """Retrieve all user preferences as a dict."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_preferences ORDER BY key")
        rows = cursor.fetchall()
        conn.close()
        return {row["key"]: row["value"] for row in rows}
    except Exception as e:
        logger.error("get_all_preferences() error: %s", e)
        return {}


def build_preferences_context() -> str:
    """
    Build a formatted string of user preferences for inclusion
    in the LLM system prompt.
    """
    prefs = get_all_preferences()
    if not prefs:
        return ""

    lines = ["--- User Preferences ---"]
    for key, value in prefs.items():
        lines.append(f"- {key}: {value}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# LEARNED FACTS
# ─────────────────────────────────────────────────────────────────────────────

def save_learned_fact(fact: str, source: str = "conversation", confidence: float = 1.0) -> bool:
    """
    Save a learned fact about the user.

    Examples:
        save_learned_fact("User plays cricket as a leg spinner", "conversation")
        save_learned_fact("User studies in 10th class", "user_stated", 1.0)
    """
    if not MEMORY_ENABLED:
        return False

    try:
        # Check for duplicate facts (fuzzy match using LIKE)
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM learned_facts WHERE fact LIKE ?",
            (f"%{fact.strip()[:50]}%",),  # Check first 50 chars
        )
        existing = cursor.fetchone()
        conn.close()

        if existing:
            logger.info("Fact already exists (id=%d), skipping.", existing["id"])
            return True

        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO learned_facts (fact, source, confidence) VALUES (?, ?, ?)",
                (fact.strip(), source, confidence),
            )
            conn.commit()
            conn.close()

        logger.info("Saved fact: %s (source: %s, confidence: %.1f)", fact, source, confidence)
        return True

    except Exception as e:
        logger.error("save_learned_fact() error: %s", e)
        return False


def get_learned_facts(topic: str = None, limit: int = 20) -> list[dict]:
    """Retrieve learned facts, optionally filtered by topic keyword."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        if topic:
            cursor.execute(
                "SELECT id, fact, source, confidence, created_at "
                "FROM learned_facts WHERE fact LIKE ? ORDER BY confidence DESC, created_at DESC LIMIT ?",
                (f"%{topic}%", limit),
            )
        else:
            cursor.execute(
                "SELECT id, fact, source, confidence, created_at "
                "FROM learned_facts ORDER BY confidence DESC, created_at DESC LIMIT ?",
                (limit,),
            )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error("get_learned_facts() error: %s", e)
        return []


def build_facts_context() -> str:
    """
    Build a formatted string of learned facts for inclusion
    in the LLM system prompt.
    """
    facts = get_learned_facts(limit=15)
    if not facts:
        return ""

    lines = ["--- Known Facts About the User ---"]
    for f in facts:
        lines.append(f"- {f['fact']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# FACT EXTRACTION (via Gemini)
# ─────────────────────────────────────────────────────────────────────────────

def extract_and_save_facts(user_msg: str, jarvis_msg: str) -> None:
    """
    Use Gemini to extract personal facts from a conversation exchange
    and save them to the learned_facts table.

    This runs in a background thread to avoid blocking the main loop.
    """
    if not MEMORY_ENABLED or not MEMORY_FACT_EXTRACTION or not GEMINI_API_KEY:
        return

    def _extract():
        try:
            from google import genai

            client = genai.Client(api_key=GEMINI_API_KEY)

            prompt = (
                "Extract any personal facts about the user from this conversation exchange. "
                "Personal facts include: name, age, grade/class, location, hobbies, interests, "
                "favorite things, goals, skills, family members, school, profession, etc.\n\n"
                "If NO personal facts are present, respond with exactly: NONE\n\n"
                "If facts ARE present, list each fact on a separate line, one fact per line. "
                "Keep each fact short (under 15 words). Do NOT include any other text.\n\n"
                f"User said: \"{user_msg}\"\n"
                f"Jarvis replied: \"{jarvis_msg}\"\n\n"
                "Extracted facts:"
            )

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )

            if not response or not response.text:
                return

            text = response.text.strip()

            if text.upper() == "NONE" or len(text) < 5:
                return

            # Parse facts (one per line)
            for line in text.splitlines():
                line = line.strip().lstrip("•-–*0123456789. ")
                if line and len(line) > 5 and len(line) < 200:
                    save_learned_fact(line, source="auto_extracted", confidence=0.8)

        except Exception as e:
            logger.warning("Fact extraction failed (non-critical): %s", e)

    # Run in background thread so it doesn't slow down the response
    thread = threading.Thread(target=_extract, daemon=True, name="FactExtractor")
    thread.start()


# ─────────────────────────────────────────────────────────────────────────────
# PRIVACY & MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def forget_all() -> bool:
    """
    Wipe ALL memory — conversations, preferences, and learned facts.
    This is the 'nuclear option' for privacy.
    """
    try:
        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations")
            cursor.execute("DELETE FROM user_preferences")
            cursor.execute("DELETE FROM learned_facts")
            conn.commit()
            conn.close()
        logger.info("All memory wiped successfully.")
        return True
    except Exception as e:
        logger.error("forget_all() error: %s", e)
        return False


def forget_conversations() -> bool:
    """Wipe only conversation history (keep preferences and facts)."""
    try:
        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations")
            conn.commit()
            conn.close()
        logger.info("Conversation history wiped.")
        return True
    except Exception as e:
        logger.error("forget_conversations() error: %s", e)
        return False


def get_memory_summary() -> str:
    """
    Generate a human-readable summary of what Jarvis remembers.
    Used when the user asks "What do you remember about me?"
    """
    try:
        conv_count = get_conversation_count()
        prefs = get_all_preferences()
        facts = get_learned_facts(limit=10)

        parts = []

        # Conversation count
        if conv_count > 0:
            parts.append(f"I have {conv_count} conversation{'s' if conv_count != 1 else ''} stored in my memory.")
        else:
            parts.append("I don't have any conversations stored yet.")

        # Preferences
        if prefs:
            pref_items = [f"{k}: {v}" for k, v in prefs.items()]
            parts.append("Your preferences: " + ", ".join(pref_items) + ".")

        # Facts
        if facts:
            fact_items = [f["fact"] for f in facts[:5]]
            parts.append("Things I've learned about you: " + ". ".join(fact_items) + ".")

        if not prefs and not facts:
            parts.append("I haven't learned any personal details about you yet.")

        return " ".join(parts)

    except Exception as e:
        logger.error("get_memory_summary() error: %s", e)
        return "I had trouble accessing my memory."


# ─────────────────────────────────────────────────────────────────────────────
# CLEANUP
# ─────────────────────────────────────────────────────────────────────────────

def _cleanup_old_conversations() -> None:
    """Delete conversations older than MEMORY_RETENTION_DAYS (if configured)."""
    if MEMORY_RETENTION_DAYS <= 0:
        return  # Keep forever

    try:
        cutoff = datetime.datetime.now() - datetime.timedelta(days=MEMORY_RETENTION_DAYS)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

        with _db_lock:
            conn = _get_conn()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM conversations WHERE timestamp < ?",
                (cutoff_str,),
            )
            deleted = cursor.rowcount
            conn.commit()
            conn.close()

        if deleted > 0:
            logger.info("Cleaned up %d conversation(s) older than %d days.", deleted, MEMORY_RETENTION_DAYS)

    except Exception as e:
        logger.warning("_cleanup_old_conversations() error: %s", e)
