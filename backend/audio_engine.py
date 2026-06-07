"""
audio_engine.py — Offline Speech-to-Text engine for Jarvis (Phase 2).

Uses OpenAI Whisper for fully offline, multilingual speech recognition.
Supports English, Hindi, Telugu, and auto-language detection.

Falls back gracefully if Whisper is not installed — the existing
Google Speech Recognition remains available as a fallback.

Usage:
    from backend.audio_engine import transcribe_audio, is_whisper_available

    if is_whisper_available():
        text = transcribe_audio(audio_data)
"""

import io
import logging
import os
import tempfile
import threading
import time
import wave

from backend.config import (
    WHISPER_MODEL, WHISPER_LANGUAGE, WHISPER_ENABLED,
)

logger = logging.getLogger(__name__)

# ── Whisper model (lazy-loaded, shared across threads) ───────────────────────
_whisper_model = None
_whisper_lock = threading.Lock()
_whisper_available = None  # None = not yet checked, True/False after check


def is_whisper_available() -> bool:
    """Check if Whisper is installed and enabled."""
    global _whisper_available

    if not WHISPER_ENABLED:
        return False

    if _whisper_available is not None:
        return _whisper_available

    try:
        import whisper  # noqa: F401
        _whisper_available = True
        logger.info("Whisper is available.")
        return True
    except ImportError:
        _whisper_available = False
        logger.info(
            "Whisper not installed — offline STT disabled. "
            "Install with: pip install openai-whisper"
        )
        return False


def _load_model():
    """
    Load the Whisper model (lazy, thread-safe).
    The model is loaded once and kept in memory for fast inference.
    Falls back gracefully if Whisper fails to load (OOM, missing package, etc.)
    — callers should use Google Speech Recognition instead.
    """
    global _whisper_model, _whisper_available

    if _whisper_model is not None:
        return _whisper_model

    with _whisper_lock:
        # Double-check after acquiring lock
        if _whisper_model is not None:
            return _whisper_model

        if not is_whisper_available():
            return None

        try:
            import whisper

            logger.info("Loading Whisper '%s' model (this may take a moment)...", WHISPER_MODEL)
            start = time.time()
            _whisper_model = whisper.load_model(WHISPER_MODEL)
            elapsed = time.time() - start
            logger.info("Whisper '%s' model loaded in %.1f seconds.", WHISPER_MODEL, elapsed)
            return _whisper_model

        except Exception as e:
            # Catch OOM, missing package, CUDA errors, etc.
            logger.warning(
                "Failed to load Whisper model '%s': %s. "
                "Falling back to Google Speech Recognition.",
                WHISPER_MODEL, e,
            )
            _whisper_available = False   # Prevent further load attempts
            return None



def preload_model() -> None:
    """
    Pre-load the Whisper model in a background thread.
    Call this at startup to avoid delay on the first voice command.
    """
    if not is_whisper_available():
        return

    def _preload():
        _load_model()

    thread = threading.Thread(target=_preload, daemon=True, name="WhisperPreload")
    thread.start()
    logger.info("Whisper model preload started in background.")


# ─────────────────────────────────────────────────────────────────────────────
# AUDIO CONVERSION
# ─────────────────────────────────────────────────────────────────────────────

def _audio_data_to_wav_file(audio_data) -> str | None:
    """
    Convert a SpeechRecognition AudioData object to a temporary WAV file.

    Whisper requires a file path (not raw bytes), so we write the audio
    to a temp file and return its path. The caller is responsible for cleanup.

    Args:
        audio_data: A speech_recognition.AudioData object.

    Returns:
        Path to the temporary WAV file, or None on failure.
    """
    try:
        # Get the raw WAV data from SpeechRecognition's AudioData
        wav_bytes = audio_data.get_wav_data(
            convert_rate=16000,     # Whisper expects 16kHz
            convert_width=2,        # 16-bit samples
        )

        # Write to a temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="jarvis_whisper_")
        try:
            with os.fdopen(temp_fd, "wb") as f:
                f.write(wav_bytes)
        except Exception:
            os.close(temp_fd)
            raise

        return temp_path

    except Exception as e:
        logger.error("Audio conversion error: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TRANSCRIPTION
# ─────────────────────────────────────────────────────────────────────────────

def transcribe_audio(audio_data) -> str | None:
    """
    Transcribe speech from a SpeechRecognition AudioData object using Whisper.

    Args:
        audio_data: A speech_recognition.AudioData object captured from the mic.

    Returns:
        The transcribed text (lowercase), or None on failure.
    """
    model = _load_model()
    if model is None:
        return None

    temp_path = None
    try:
        # Convert AudioData to a WAV file
        temp_path = _audio_data_to_wav_file(audio_data)
        if not temp_path:
            return None

        # Run Whisper transcription
        logger.info("Whisper transcribing...")
        start = time.time()

        # Build transcription options
        options = {
            "fp16": False,      # CPU-safe (no GPU needed)
            "verbose": False,   # Don't print to stdout
        }

        if WHISPER_LANGUAGE:
            options["language"] = WHISPER_LANGUAGE
            # When language is specified, skip detection for faster inference
            options["task"] = "transcribe"

        result = model.transcribe(temp_path, **options)

        elapsed = time.time() - start
        text = result.get("text", "").strip()
        detected_lang = result.get("language", "unknown")

        logger.info(
            "Whisper result (%.1fs, lang=%s): %s",
            elapsed, detected_lang, text,
        )

        if not text:
            return None

        return text.lower()

    except Exception as e:
        logger.error("Whisper transcription error: %s", e)
        return None

    finally:
        # Cleanup temp file
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


def detect_language(audio_data) -> str | None:
    """
    Detect the language of speech using Whisper.

    Returns:
        ISO 639-1 language code (e.g., 'en', 'hi', 'te') or None.
    """
    model = _load_model()
    if model is None:
        return None

    temp_path = None
    try:
        temp_path = _audio_data_to_wav_file(audio_data)
        if not temp_path:
            return None

        import whisper

        # Load audio and pad/trim to 30 seconds
        audio = whisper.load_audio(temp_path)
        audio = whisper.pad_or_trim(audio)

        # Make log-Mel spectrogram
        mel = whisper.log_mel_spectrogram(audio).to(model.device)

        # Detect language
        _, probs = model.detect_language(mel)
        detected = max(probs, key=probs.get)

        logger.info("Detected language: %s (confidence: %.2f)", detected, probs[detected])
        return detected

    except Exception as e:
        logger.error("Language detection error: %s", e)
        return None

    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


def get_whisper_info() -> dict:
    """Return info about the Whisper engine status."""
    return {
        "available": is_whisper_available(),
        "enabled": WHISPER_ENABLED,
        "model": WHISPER_MODEL,
        "language": WHISPER_LANGUAGE or "auto-detect",
        "loaded": _whisper_model is not None,
    }
