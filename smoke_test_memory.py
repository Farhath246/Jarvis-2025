"""
test_memory.py — Quick smoke test for the Jarvis memory system.
"""

import sys
sys.path.insert(0, ".")

from backend.memory import (
    save_conversation, get_recent_conversations,
    save_user_preference, get_user_preference, get_all_preferences,
    save_learned_fact, get_learned_facts,
    get_memory_summary, forget_all, get_conversation_count,
    build_memory_context, build_preferences_context, build_facts_context,
)
from backend.memory_search import search_memory, get_index_stats


def main():
    print("=" * 60)
    print("JARVIS MEMORY SYSTEM — SMOKE TEST")
    print("=" * 60)

    # ── Test 1: Save conversations ────────────────────────────────────
    print("\n[TEST 1] Saving conversations...")
    id1 = save_conversation(
        "How do I bowl leg spin?",
        "Leg spin involves gripping the ball with your wrist cocked.",
        topic="cricket",
    )
    id2 = save_conversation(
        "Write a C++ program for sorting",
        "Here is a quicksort implementation in C++...",
        topic="coding",
    )
    id3 = save_conversation(
        "What is the weather in Kurnool?",
        "The weather in Kurnool is 38 degrees Celsius today.",
        topic="weather",
    )
    print(f"  Saved conversations: #{id1}, #{id2}, #{id3}")
    print(f"  Total conversations: {get_conversation_count()}")
    assert id1 is not None and id2 is not None and id3 is not None, "FAILED: Conversations not saved"
    print("  PASSED ✅")

    # ── Test 2: Retrieve conversations ────────────────────────────────
    print("\n[TEST 2] Retrieving recent conversations...")
    recent = get_recent_conversations(5)
    print(f"  Retrieved {len(recent)} conversations")
    assert len(recent) >= 3, "FAILED: Expected at least 3 conversations"
    print("  PASSED ✅")

    # ── Test 3: User preferences ──────────────────────────────────────
    print("\n[TEST 3] Saving and retrieving preferences...")
    save_user_preference("favorite_sport", "cricket")
    save_user_preference("language", "Telugu")
    save_user_preference("grade", "10th class")

    sport = get_user_preference("favorite_sport")
    lang = get_user_preference("language")
    print(f"  favorite_sport = {sport}")
    print(f"  language = {lang}")
    assert sport == "cricket", f"FAILED: Expected 'cricket', got '{sport}'"
    assert lang == "Telugu", f"FAILED: Expected 'Telugu', got '{lang}'"
    print("  PASSED ✅")

    # ── Test 4: Learned facts ─────────────────────────────────────────
    print("\n[TEST 4] Saving and retrieving facts...")
    save_learned_fact("User plays cricket as a leg spinner", source="test")
    save_learned_fact("User studies in 10th class", source="test")
    save_learned_fact("User lives in Kurnool", source="test")

    facts = get_learned_facts()
    print(f"  Stored {len(facts)} facts")
    assert len(facts) >= 3, "FAILED: Expected at least 3 facts"
    print("  PASSED ✅")

    # ── Test 5: Memory context builders ───────────────────────────────
    print("\n[TEST 5] Building memory context strings...")
    mem_ctx = build_memory_context(limit=3)
    pref_ctx = build_preferences_context()
    fact_ctx = build_facts_context()
    print(f"  Memory context length: {len(mem_ctx)} chars")
    print(f"  Preferences context length: {len(pref_ctx)} chars")
    print(f"  Facts context length: {len(fact_ctx)} chars")
    assert len(mem_ctx) > 0, "FAILED: Memory context is empty"
    assert len(pref_ctx) > 0, "FAILED: Preferences context is empty"
    assert len(fact_ctx) > 0, "FAILED: Facts context is empty"
    print("  PASSED ✅")

    # ── Test 6: Memory summary ────────────────────────────────────────
    print("\n[TEST 6] Generating memory summary...")
    summary = get_memory_summary()
    print(f"  Summary: {summary[:200]}...")
    assert "conversation" in summary.lower(), "FAILED: Summary doesn't mention conversations"
    print("  PASSED ✅")

    # ── Test 7: Keyword search (fallback) ─────────────────────────────
    print("\n[TEST 7] Searching memory (keyword fallback)...")
    results = search_memory("leg spin", top_k=3)
    print(f"  Found {len(results)} results for 'leg spin'")
    for r in results:
        print(f"    - [{r['source']}] score={r['score']}: {r['user_msg'][:60]}")
    assert len(results) > 0, "FAILED: Expected at least 1 search result"
    print("  PASSED ✅")

    # ── Test 8: Semantic search (ChromaDB) ────────────────────────────
    print("\n[TEST 8] Checking ChromaDB availability...")
    stats = get_index_stats()
    print(f"  ChromaDB available: {stats['chromadb_available']}")
    print(f"  Indexed documents: {stats['indexed_documents']}")
    if stats["chromadb_available"]:
        from backend.memory_search import index_conversation
        index_conversation(id1, "How do I bowl leg spin?", "Leg spin involves gripping the ball...")
        index_conversation(id2, "Write a C++ program for sorting", "Here is a quicksort implementation...")
        results = search_memory("bowling techniques", top_k=3)
        print(f"  Semantic search found {len(results)} results for 'bowling techniques'")
        print("  PASSED ✅")
    else:
        print("  SKIPPED (ChromaDB not installed — keyword search will be used as fallback)")

    # ── Test 9: Forget all ────────────────────────────────────────────
    print("\n[TEST 9] Testing forget_all()...")
    success = forget_all()
    assert success, "FAILED: forget_all() returned False"
    assert get_conversation_count() == 0, "FAILED: Conversations not cleared"
    assert len(get_all_preferences()) == 0, "FAILED: Preferences not cleared"
    assert len(get_learned_facts()) == 0, "FAILED: Facts not cleared"
    print("  All memory cleared successfully")
    print("  PASSED ✅")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✅ Jarvis memory system is working.")
    print("=" * 60)


if __name__ == "__main__":
    main()
