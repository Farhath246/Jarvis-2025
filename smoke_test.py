"""
smoke_test.py — Pre-launch sanity check for Jarvis-2025.
Run: python smoke_test.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 55)
print("  Jarvis-2025 Pre-Launch Smoke Test")
print("=" * 55)

# ── 1. Config paths ──────────────────────────────────────
print("\n[1] config.py path resolution")
try:
    from backend.config import (
        EXE_DIR, _BUNDLE_DIR, DB_PATH, FACE_CASCADE_PATH,
        FACE_TRAINER_PATH, SOUND_FILE, TTS_TEMP_DIR, GEMINI_API_KEY
    )
    print(f"  EXE_DIR      : {EXE_DIR}")
    print(f"  _BUNDLE_DIR  : {_BUNDLE_DIR}")
    print(f"  DB_PATH      : {DB_PATH}")
    print(f"    -> exists  : {os.path.exists(DB_PATH)}")
    print(f"  CASCADE      : {FACE_CASCADE_PATH}")
    print(f"    -> exists  : {os.path.exists(FACE_CASCADE_PATH)}")
    print(f"  TRAINER YML  : {FACE_TRAINER_PATH}")
    print(f"    -> exists  : {os.path.exists(FACE_TRAINER_PATH)}")
    print(f"  SOUND_FILE   : {SOUND_FILE}")
    print(f"    -> exists  : {os.path.exists(SOUND_FILE)}")
    key_status = "SET ({} chars)".format(len(GEMINI_API_KEY)) if GEMINI_API_KEY else "NOT SET"
    print(f"  GEMINI KEY   : {key_status}")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

# ── 2. Database ──────────────────────────────────────────
print("\n[2] SQLite database init")
try:
    from backend.db import init_db
    init_db()
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

# ── 3. OpenCV + haarcascade ──────────────────────────────
print("\n[3] OpenCV cascade load")
try:
    import cv2
    from backend.config import FACE_CASCADE_PATH
    cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    loaded = not cascade.empty()
    print(f"  Cascade loaded: {loaded}")
    print(f"  RESULT: {'PASS' if loaded else 'FAIL — cascade file may be missing or corrupt'}")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

# ── 4. Gemini API ────────────────────────────────────────
print("\n[4] google-genai import")
try:
    from google import genai
    print("  Import: OK")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

# ── 5. Edge-TTS ──────────────────────────────────────────
print("\n[5] edge-tts import")
try:
    import edge_tts
    print("  Import: OK")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

# ── 6. Eel ───────────────────────────────────────────────
print("\n[6] eel import")
try:
    import eel
    print("  Import: OK")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

# ── 7. Speech recognition ────────────────────────────────
print("\n[7] SpeechRecognition import")
try:
    import speech_recognition as sr
    print("  Import: OK")
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

# ── 8. Pygame ────────────────────────────────────────────
print("\n[8] pygame mixer init")
try:
    import pygame
    pygame.mixer.init()
    print("  Mixer init: OK")
    pygame.mixer.quit()
    print("  RESULT: PASS")
except Exception as e:
    print(f"  RESULT: FAIL -> {e}")

print("\n" + "=" * 55)
print("  Smoke test complete. Review any FAIL lines above.")
print("=" * 55)
