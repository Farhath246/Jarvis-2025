import os
from dotenv import load_dotenv

# Load environment variables from .env file at the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Assistant identity
ASSISTANT_NAME = "jarvis"

# User identity
USER_NAME = "Syed Farhatullah"   # full name, used in face recognition label
USER_CALL_NAME = "Farhath"       # friendly name Jarvis uses when speaking

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

# Project root (absolute path, resolved from this file's location)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Temp directory for Edge-TTS generated audio files
TTS_TEMP_DIR = os.path.join(BASE_DIR, ".tts_cache")

# Audio
SOUND_FILE = os.path.join(BASE_DIR, "frontend", "assets", "audio", "start_sound.mp3")

# Database
DB_PATH = os.path.join(BASE_DIR, "jarvis.db")

# Face auth
FACE_AUTH_TIMEOUT = 30       # seconds before auth gives up (increased for multi-frame voting)
FACE_AUTH_MAX_ATTEMPTS = 5   # failed recognitions before lockout (debounced — only full-frame misses count)
FACE_SAMPLES_DIR = os.path.join(BASE_DIR, "backend", "auth", "samples")
FACE_TRAINER_PATH = os.path.join(BASE_DIR, "backend", "auth", "trainer", "trainer.yml")
FACE_CASCADE_PATH = os.path.join(BASE_DIR, "backend", "auth", "haarcascade_frontalface_default.xml")

# Face recognition tuning
FACE_CONFIDENCE_THRESHOLD = 45   # LBPH distance below this value = match (lower = stricter)
FACE_CONSECUTIVE_MATCHES = 3     # consecutive high-confidence frames needed to confirm identity
FACE_SAMPLE_SIZE = (200, 200)    # standard face crop size for training & recognition

# Notes
NOTES_FILE = os.path.join(BASE_DIR, "jarvis_notes.txt")

# Google Gemini chatbot (FREE tier — 1500 requests/day)
# Get your free key at: https://aistudio.google.com/app/apikey
# Set GEMINI_API_KEY in your .env file (see .env.example)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")