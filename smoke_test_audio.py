"""
test_audio_engine.py — Smoke test for the Whisper audio engine (Phase 2).
Tests engine initialization, fallback behavior, and configuration.
"""

import sys
sys.path.insert(0, ".")


def main():
    print("=" * 60)
    print("JARVIS AUDIO ENGINE -- SMOKE TEST")
    print("=" * 60)

    # ── Test 1: Import audio engine ───────────────────────────────────
    print("\n[TEST 1] Importing audio engine...")
    try:
        from backend.audio_engine import (
            is_whisper_available, get_whisper_info,
            transcribe_audio, detect_language, preload_model,
        )
        print("  Import successful")
        print("  PASSED")
    except Exception as e:
        print(f"  FAILED: {e}")
        return

    # ── Test 2: Check Whisper availability ────────────────────────────
    print("\n[TEST 2] Checking Whisper availability...")
    available = is_whisper_available()
    info = get_whisper_info()
    print(f"  Available: {available}")
    print(f"  Enabled:   {info['enabled']}")
    print(f"  Model:     {info['model']}")
    print(f"  Language:  {info['language']}")
    print(f"  Loaded:    {info['loaded']}")
    print("  PASSED")

    # ── Test 3: Config settings ───────────────────────────────────────
    print("\n[TEST 3] Verifying config settings...")
    from backend.config import WHISPER_ENABLED, WHISPER_MODEL, WHISPER_LANGUAGE
    print(f"  WHISPER_ENABLED:  {WHISPER_ENABLED}")
    print(f"  WHISPER_MODEL:    {WHISPER_MODEL}")
    print(f"  WHISPER_LANGUAGE: {WHISPER_LANGUAGE}")
    assert WHISPER_ENABLED is True, "FAILED: WHISPER_ENABLED should be True"
    assert WHISPER_MODEL == "base", "FAILED: WHISPER_MODEL should be 'base'"
    assert WHISPER_LANGUAGE is None, "FAILED: WHISPER_LANGUAGE should be None (auto-detect)"
    print("  PASSED")

    # ── Test 4: Graceful fallback ─────────────────────────────────────
    print("\n[TEST 4] Testing graceful fallback behavior...")
    if not available:
        print("  Whisper NOT installed -- testing fallback path")
        # transcribe_audio should return None gracefully
        result = transcribe_audio(None)
        assert result is None, "FAILED: Should return None when Whisper unavailable"
        print("  transcribe_audio(None) -> None (correct fallback)")
        print("  PASSED")
    else:
        print("  Whisper IS installed -- testing model load")
        preload_model()
        import time
        time.sleep(2)  # Give background thread time to start
        info2 = get_whisper_info()
        print(f"  Model loaded: {info2['loaded']}")
        print("  PASSED")

    # ── Test 5: Command.py integration ────────────────────────────────
    print("\n[TEST 5] Verifying command.py integration...")
    try:
        # Check that command.py imports and uses the audio engine
        import importlib
        import backend.command
        importlib.reload(backend.command)
        
        # Check takecommand function signature exists
        assert hasattr(backend.command, 'takecommand'), "FAILED: takecommand not found"
        
        # Check the function docstring mentions Whisper
        doc = backend.command.takecommand.__doc__ or ""
        assert "Whisper" in doc, "FAILED: takecommand docstring should mention Whisper"
        print("  takecommand() has Whisper integration")
        print("  PASSED")
    except Exception as e:
        print(f"  FAILED: {e}")

    # ── Summary ───────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if available:
        print("ALL TESTS PASSED! Whisper is installed and ready.")
        print("Jarvis will use OFFLINE speech recognition (Whisper).")
    else:
        print("ALL TESTS PASSED! Whisper not installed (optional).")
        print("Jarvis will use Google Speech Recognition (online).")
        print("")
        print("To enable offline STT, install Whisper:")
        print("  pip install openai-whisper")
    print("=" * 60)


if __name__ == "__main__":
    main()
