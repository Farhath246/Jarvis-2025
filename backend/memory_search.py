"""
memory_search.py -- Semantic search over Jarvis conversation history.

Uses ChromaDB for vector-based semantic search. Falls back to SQLite
keyword search if ChromaDB is not installed or ENABLE_CHROMA is False.

Usage:
    from backend.memory_search import index_conversation, search_memory

    # Index a conversation after saving it
    index_conversation(conv_id, "How do I bowl leg spin?", "Leg spin involves...")

    # Search by meaning (not just keywords)
    results = search_memory("bowling techniques")  # Finds leg spin conversation!
"""

import logging
import sqlite3

from backend.config import DB_PATH, CHROMADB_ENABLED, CHROMADB_PATH, ENABLE_CHROMA

logger = logging.getLogger(__name__)

# ── ChromaDB disabled check (logged once at import) ──────────────────────────
if not ENABLE_CHROMA:
    logger.info("ChromaDB disabled -- using SQLite keyword search")

# ── ChromaDB client (lazy-loaded) ────────────────────────────────────────────
_chroma_client = None
_chroma_collection = None
_chroma_available = False


def _init_chromadb():
    """
    Initialise ChromaDB client and collection.
    Returns True on success, False if ChromaDB isn't available or is disabled.
    """
    global _chroma_client, _chroma_collection, _chroma_available

    # Skip ChromaDB entirely when ENABLE_CHROMA is False (low-end mode)
    if not ENABLE_CHROMA or not CHROMADB_ENABLED:
        return False

    if _chroma_client is not None:
        return _chroma_available

    try:
        import chromadb

        _chroma_client = chromadb.PersistentClient(path=CHROMADB_PATH)
        _chroma_collection = _chroma_client.get_or_create_collection(
            name="jarvis_conversations",
            metadata={"description": "Jarvis conversation memory for semantic search"},
        )
        _chroma_available = True
        logger.info(
            "ChromaDB initialized at %s (%d documents).",
            CHROMADB_PATH,
            _chroma_collection.count(),
        )
        return True

    except ImportError:
        logger.info(
            "ChromaDB not installed -- semantic search disabled. "
            "Install with: pip install chromadb"
        )
        _chroma_available = False
        return False

    except Exception as e:
        logger.error("ChromaDB init error: %s", e)
        _chroma_available = False
        return False


# ─────────────────────────────────────────────────────────────────────────────
# INDEXING
# ─────────────────────────────────────────────────────────────────────────────

def index_conversation(conversation_id: int, user_msg: str, jarvis_msg: str) -> bool:
    """
    Add a conversation to the semantic search index.

    Args:
        conversation_id: The ID from the conversations table.
        user_msg:        What the user said.
        jarvis_msg:      What Jarvis responded.

    Returns:
        True on success, False on failure or if ChromaDB is unavailable.
    """
    if not _init_chromadb():
        return False

    try:
        # Combine user + jarvis messages for richer embeddings
        combined_text = f"User: {user_msg}\nJarvis: {jarvis_msg}"

        # Use conversation ID as the document ID (must be a string)
        doc_id = f"conv_{conversation_id}"

        _chroma_collection.upsert(
            documents=[combined_text],
            ids=[doc_id],
            metadatas=[{
                "conversation_id": conversation_id,
                "user_msg": user_msg[:500],  # Truncate for metadata storage
                "jarvis_msg": jarvis_msg[:500],
            }],
        )

        logger.debug("Indexed conversation #%d in ChromaDB.", conversation_id)
        return True

    except Exception as e:
        logger.warning("index_conversation() error: %s", e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def search_memory(query: str, top_k: int = 5) -> list[dict]:
    """
    Search conversation memory by meaning (semantic) or keywords (fallback).

    Args:
        query: The search query (e.g., "bowling techniques", "my cricket goals").
        top_k: Number of results to return.

    Returns:
        List of dicts with keys: conversation_id, user_msg, jarvis_msg, score
    """
    # Try ChromaDB first (semantic search)
    if _init_chromadb():
        results = _search_chromadb(query, top_k)
        if results:
            return results

    # Fallback to SQLite keyword search
    return _search_keyword(query, top_k)


def _search_chromadb(query: str, top_k: int) -> list[dict]:
    """Semantic search via ChromaDB embeddings."""
    try:
        results = _chroma_collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        if not results or not results.get("metadatas") or not results["metadatas"][0]:
            return []

        output = []
        metadatas = results["metadatas"][0]
        distances = results["distances"][0] if results.get("distances") else [0] * len(metadatas)

        for meta, distance in zip(metadatas, distances):
            # ChromaDB returns L2 distance — lower is better
            # Convert to a similarity score (0-1, higher is better)
            similarity = max(0, 1 - (distance / 2))

            output.append({
                "conversation_id": meta.get("conversation_id"),
                "user_msg": meta.get("user_msg", ""),
                "jarvis_msg": meta.get("jarvis_msg", ""),
                "score": round(similarity, 3),
                "source": "semantic",
            })

        logger.info("ChromaDB search for '%s' returned %d results.", query, len(output))
        return output

    except Exception as e:
        logger.warning("ChromaDB search error: %s", e)
        return []


def _search_keyword(query: str, top_k: int) -> list[dict]:
    """Fallback: keyword search via SQLite LIKE queries."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Split query into individual words for broader matching
        words = [w.strip() for w in query.split() if len(w.strip()) > 2]

        if not words:
            conn.close()
            return []

        # Build a query that matches ANY word in either user_msg or jarvis_msg
        conditions = []
        params = []
        for word in words:
            conditions.append("(user_msg LIKE ? OR jarvis_msg LIKE ?)")
            params.extend([f"%{word}%", f"%{word}%"])

        where_clause = " OR ".join(conditions)
        sql = (
            f"SELECT id, user_msg, jarvis_msg, topic, timestamp "
            f"FROM conversations WHERE {where_clause} "
            f"ORDER BY timestamp DESC LIMIT ?"
        )
        params.append(top_k)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        output = []
        for row in rows:
            # Simple relevance score based on word matches
            text = (row["user_msg"] + " " + row["jarvis_msg"]).lower()
            matches = sum(1 for w in words if w.lower() in text)
            score = matches / len(words)

            output.append({
                "conversation_id": row["id"],
                "user_msg": row["user_msg"],
                "jarvis_msg": row["jarvis_msg"],
                "score": round(score, 3),
                "source": "keyword",
            })

        # Sort by score descending
        output.sort(key=lambda x: x["score"], reverse=True)
        logger.info("Keyword search for '%s' returned %d results.", query, len(output))
        return output

    except Exception as e:
        logger.error("Keyword search error: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def get_index_stats() -> dict:
    """Return statistics about the semantic search index."""
    stats = {
        "chromadb_available": _chroma_available,
        "indexed_documents": 0,
    }

    if _init_chromadb():
        try:
            stats["indexed_documents"] = _chroma_collection.count()
        except Exception:
            pass

    return stats


def clear_index() -> bool:
    """Clear the ChromaDB index. Used when memory is wiped."""
    if not _init_chromadb():
        return True  # Nothing to clear

    try:
        global _chroma_collection
        _chroma_client.delete_collection("jarvis_conversations")
        _chroma_collection = _chroma_client.get_or_create_collection(
            name="jarvis_conversations",
            metadata={"description": "Jarvis conversation memory for semantic search"},
        )
        logger.info("ChromaDB index cleared.")
        return True
    except Exception as e:
        logger.error("clear_index() error: %s", e)
        return False
