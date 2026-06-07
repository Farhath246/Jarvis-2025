import os
import sys
from dotenv import load_dotenv

# ── Path resolution (handles both normal Python and PyInstaller frozen exe) ───
#
# When frozen by PyInstaller (sys.frozen is True):
#   - sys._MEIPASS  → the temp directory where bundled assets are unpacked
#                     (frontend/, backend/auth/haarcascade, etc.)
#   - EXE_DIR       → the directory containing desktop.exe
#                     (used for user-data files: .env, jarvis.db, trainer.yml,
#                      .tts_cache, notes — things that must persist between runs)
#
# When running normally (python run.py / python desktop.py):
#   - Both _BUNDLE_DIR and EXE_DIR point to the project root.

if getattr(sys, "frozen", False):
    # Running as a PyInstaller bundle
    _BUNDLE_DIR = sys._MEIPASS                          # bundled read-only assets
    EXE_DIR     = os.path.dirname(sys.executable)       # writable runtime dir (next to .exe)
else:
    # Running from source
    _BUNDLE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    EXE_DIR     = _BUNDLE_DIR

# Load .env from the exe/project directory (not the temp bundle)
load_dotenv(os.path.join(EXE_DIR, ".env"))

# Assistant identity
ASSISTANT_NAME = "jarvis"

# User identity
USER_NAME = "Syed Farhatullah"   # full name, used in face recognition label
USER_CALL_NAME = "Farhath"       # friendly name Jarvis uses when speaking

# ── Low-End Device Optimization Flags ─────────────────────────────────
# These flags let Jarvis run on machines with 2-4 GB RAM, no GPU.
# Set them to their "full-featured" values on capable hardware.

PREFERRED_TTS = "pyttsx3"        # "pyttsx3" = offline first (low-end), "edge" = Edge-TTS first (default)
PREFERRED_LLM = "ollama"         # "ollama" = local LLM first (low-end), "gemini" = cloud Gemini first
                                 # Suggested Ollama models: gemma2:2b, phi3:mini, tinyllama
ENABLE_CHROMA = False            # False = use lightweight SQLite keyword search instead of ChromaDB
ENABLE_AUTOML = False            # False = disable AutoML, lazy-load sklearn/pandas only when invoked
CLI_MODE = False                 # True = headless terminal mode (no Eel GUI, no face auth)

# TTS voice settings — pyttsx3 / SAPI5 (offline fallback)
VOICE_INDEX = 0       # preferred SAPI5 voice index — system has 2 voices (0 & 1)
SPEECH_RATE = 174     # words per minute

# Edge-TTS settings — Microsoft Edge neural voices (primary, cloud-based)
# Run `python -m edge_tts --list-voices` to see all available voices.
# Popular choices:
#   en-US-GuyNeural          — natural American male (default, fits "Jarvis")
#   en-US-ChristopherNeural  — deeper, calm male
#   en-US-AriaNeural         — friendly American female
#   en-IN-PrabhatNeural      — Indian English male
#   en-IN-NeerjaNeural       — Indian English female
EDGE_TTS_VOICE = "en-US-GuyNeural"
EDGE_TTS_RATE = "+0%"   # speed adjustment: "+10%", "-10%", etc.

# Project root — for source runs only (frozen builds use _BUNDLE_DIR / EXE_DIR above)
BASE_DIR = EXE_DIR

# Temp directory for Edge-TTS generated audio files (writable — next to exe)
TTS_TEMP_DIR = os.path.join(EXE_DIR, ".tts_cache")

# Audio — bundled asset, lives in _MEIPASS when frozen
SOUND_FILE = os.path.join(_BUNDLE_DIR, "frontend", "assets", "audio", "start_sound.mp3")

# Database — user data, must persist next to exe
DB_PATH = os.path.join(EXE_DIR, "jarvis.db")

# Face auth
FACE_AUTH_TIMEOUT = 30       # seconds before auth gives up (increased for multi-frame voting)
FACE_AUTH_MAX_ATTEMPTS = 5   # failed recognitions before lockout (debounced — only full-frame misses count)
FACE_SAMPLES_DIR  = os.path.join(EXE_DIR,     "backend", "auth", "samples")          # writable
FACE_TRAINER_PATH = os.path.join(EXE_DIR,     "backend", "auth", "trainer", "trainer.yml")  # writable
FACE_CASCADE_PATH = os.path.join(_BUNDLE_DIR, "backend", "auth", "haarcascade_frontalface_default.xml")  # bundled

# Face recognition tuning
FACE_CONFIDENCE_THRESHOLD = 45   # LBPH distance below this value = match (lower = stricter)
FACE_CONSECUTIVE_MATCHES = 3     # consecutive high-confidence frames needed to confirm identity
FACE_SAMPLE_SIZE = (200, 200)    # standard face crop size for training & recognition

# Notes — user data, must persist next to exe
NOTES_FILE = os.path.join(EXE_DIR, "jarvis_notes.txt")

# Google Gemini chatbot (FREE tier — 1500 requests/day)
# Get your free key at: https://aistudio.google.com/app/apikey
# Set GEMINI_API_KEY in your .env file (see .env.example)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Local Ollama Fallback (default values, configurable via .env)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b")

# ── Spotify API (Phase 2) ─────────────────────────────────────────────────────
# Register your app at https://developer.spotify.com/dashboard
# Set redirect URI to http://localhost:8888/callback in your Spotify app settings
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")

# ── Email Integration (Phase 2) ───────────────────────────────────────────────
# Works with Gmail (enable "App Passwords" in Google Account Security)
# or any standard IMAP/SMTP provider
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")       # App password, NOT your real password
IMAP_SERVER = os.environ.get("IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# ── Google Calendar API (Phase 2) ─────────────────────────────────────────────
# Download credentials.json from Google Cloud Console → APIs & Services → Credentials
# Place the file next to desktop.exe or in the project root
GOOGLE_CALENDAR_CREDENTIALS = os.path.join(EXE_DIR, "credentials.json")
GOOGLE_CALENDAR_TOKEN = os.path.join(EXE_DIR, "calendar_token.json")

# ── Secure Sandbox (Phase 2) ──────────────────────────────────────────────────
SANDBOX_DIR = os.path.join(EXE_DIR, "sandbox_runs")
SANDBOX_TIMEOUT = 15  # max seconds a sandboxed script can run

# ── Persistent Memory (Phase 1) ──────────────────────────────────────
MEMORY_ENABLED = True                # Master switch for the memory system
MEMORY_MAX_CONTEXT = 5               # Recent conversations to include in LLM prompts
MEMORY_RETENTION_DAYS = 90           # Auto-delete conversations older than this (0 = keep forever)
MEMORY_FACT_EXTRACTION = True        # Auto-extract user facts from conversations via Gemini
CHROMADB_ENABLED = ENABLE_CHROMA     # Controlled by ENABLE_CHROMA flag above
CHROMADB_PATH = os.path.join(EXE_DIR, ".chromadb")

# ── Offline Audio / Whisper (Phase 2) ────────────────────────────────
WHISPER_ENABLED = True               # Master switch for Whisper offline STT
WHISPER_MODEL = "tiny"               # Model size: tiny (~39MB, low-end), base (~74MB), small (~244MB)
WHISPER_LANGUAGE = None              # None = auto-detect, "en" = English only, "hi" = Hindi, "te" = Telugu

# ── Performance Monitoring (Phase 3) ─────────────────────────────────
MONITOR_ENABLED = True               # Master switch for API & performance logging

# ── AutoML / Machine Learning (Phase 4) ──────────────────────────────
AUTOML_ENABLED = ENABLE_AUTOML       # Controlled by ENABLE_AUTOML flag above
AUTOML_MODELS_DIR = os.path.join(EXE_DIR, ".models")