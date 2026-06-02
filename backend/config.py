import os
from dotenv import load_dotenv

# Load environment variables from .env file at the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Assistant identity
ASSISTANT_NAME = "jarvis"

# User identity
USER_NAME = "Syed Farhatullah"   # full name, used in face recognition label
USER_CALL_NAME = "Farhath"       # friendly name Jarvis uses when speaking

# TTS voice settings
VOICE_INDEX = 1       # preferred SAPI5 voice index — system has 2 voices (0 & 1)
SPEECH_RATE = 174     # words per minute

# Project root (absolute path, resolved from this file's location)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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