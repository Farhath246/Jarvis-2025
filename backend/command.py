"""
command.py — Voice I/O and main command dispatcher for Jarvis.
"""

import asyncio
import logging
import os
import threading
import time
import speech_recognition as sr

from backend.config import (
    ASSISTANT_NAME, VOICE_INDEX, SPEECH_RATE,
    EDGE_TTS_VOICE, EDGE_TTS_RATE, TTS_TEMP_DIR,
    PREFERRED_TTS, CLI_MODE,
)

# ── Conditional eel import (CLI_MODE uses a no-op mock) ──────────────────────
if CLI_MODE:
    # In headless CLI mode, replace eel with a simple mock so all
    # eel.XYZ() calls silently do nothing instead of crashing.
    import types
    eel = types.ModuleType("eel")
    # Make any attribute access return a no-op callable
    class _EelMock:
        def __getattr__(self, name):
            def _noop(*args, **kwargs):
                return lambda *a, **kw: None
            return _noop
        def expose(self, func):
            return func
    eel = _EelMock()
else:
    import eel

# ── Logging ──────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# Thread lock to ensure TTS is only used from one thread at a time
_speak_lock = threading.Lock()

# ── Pygame mixer (lazy init) ────────────────────────────────────────────────────
_pygame_ready = False


def _init_pygame():
    """Initialise pygame mixer once (safe to call multiple times)."""
    global _pygame_ready
    if _pygame_ready:
        return
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        _pygame_ready = True
    except Exception as e:
        logger.warning("pygame.mixer init failed: %s", e)


def clean_speech_text(text: str) -> str:
    """Remove markdown syntax, links, and formatting for clean text-to-speech."""
    import re
    # Remove markdown links: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove citation brackets: [1], [2], etc.
    text = re.sub(r'\[\d+\]', '', text)
    # Remove bold/italic markers: **, *
    text = re.sub(r'\*\*|__|\*|_', '', text)
    # Remove code blocks and inline code
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'`[^`]+`', '', text)
    # Clean up double spaces or trailing/leading whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ── Edge-TTS (async helper) ─────────────────────────────────────────────────────
async def _edge_tts_generate(text: str, output_path: str) -> None:
    """Generate an MP3 file from text using Edge-TTS neural voices."""
    import edge_tts
    communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE, rate=EDGE_TTS_RATE)
    await communicate.save(output_path)


def _speak_edge_tts(cleaned_text: str) -> bool:
    """
    Try to speak using Edge-TTS + pygame playback.
    Returns True on success, False on any failure.
    """
    import pygame

    _init_pygame()

    # Ensure temp directory exists
    os.makedirs(TTS_TEMP_DIR, exist_ok=True)

    # Generate a unique temp filename using thread id + timestamp
    temp_file = os.path.join(
        TTS_TEMP_DIR,
        f"tts_{threading.current_thread().ident}_{int(time.time() * 1000)}.mp3"
    )

    try:
        # Generate the audio file via Edge-TTS.
        # Use a dedicated event loop with proper cleanup instead of asyncio.run()
        # to avoid ResourceWarning from unclosed transports when eel's gevent
        # event loop is also running.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_edge_tts_generate(cleaned_text, temp_file))
        finally:
            # Shut down async generators and close the loop cleanly
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

        # Play the generated audio using pygame
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        # Wait for playback to finish (non-blocking poll)
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        return True

    except Exception as e:
        logger.warning("Edge-TTS failed (will fall back to pyttsx3): %s", e)
        return False

    finally:
        # Clean up: unload and delete temp file
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass


def _speak_pyttsx3(cleaned_text: str) -> None:
    """Fallback: speak using pyttsx3 SAPI5 engine (offline, robotic voice)."""
    import pyttsx3
    try:
        engine = pyttsx3.init("sapi5")
        voices = engine.getProperty("voices")
        # Safe voice selection — fall back to index 0 if preferred index missing
        if voices and VOICE_INDEX < len(voices):
            engine.setProperty("voice", voices[VOICE_INDEX].id)
        elif voices:
            logger.warning(
                "Voice index %d not available (%d voices found). Using index 0.",
                VOICE_INDEX, len(voices)
            )
            engine.setProperty("voice", voices[0].id)
        engine.setProperty("rate", SPEECH_RATE)
        engine.say(cleaned_text)
        engine.runAndWait()
    except Exception as e:
        logger.error("pyttsx3 fallback TTS error: %s", e)


def speak(text: str, sources: list = None) -> None:
    """
    Convert text to speech and display it in the UI.

    TTS priority is controlled by PREFERRED_TTS in config.py:
      - "pyttsx3" → pyttsx3 first, Edge-TTS fallback  (low-end / offline)
      - "edge"    → Edge-TTS first, pyttsx3 fallback  (full-featured)
    """
    text = str(text)
    logger.info("Jarvis says: %s", text)

    # ── Display in UI (or print in CLI mode) ──────────────────────────────
    if CLI_MODE:
        print(f"[Jarvis] {text}")
    else:
        try:
            eel.DisplayMessage(text)
        except Exception as e:
            logger.warning("eel.DisplayMessage failed: %s", e)

    with _speak_lock:
        cleaned_text = clean_speech_text(text)
        if not cleaned_text:
            logger.info("Nothing to speak after cleaning text.")
        else:
            # ── TTS routing based on PREFERRED_TTS ────────────────────────
            if PREFERRED_TTS == "pyttsx3":
                # Low-end mode: lightweight offline TTS first
                try:
                    _speak_pyttsx3(cleaned_text)
                except Exception:
                    logger.info("pyttsx3 failed — falling back to Edge-TTS.")
                    if not _speak_edge_tts(cleaned_text):
                        logger.warning("Both TTS engines failed.")
            else:
                # Full-featured mode: Edge-TTS first (existing behavior)
                if not _speak_edge_tts(cleaned_text):
                    logger.info("Using pyttsx3 (SAPI5) fallback for speech.")
                    _speak_pyttsx3(cleaned_text)

    if CLI_MODE:
        pass  # Already printed above
    else:
        try:
            eel.receiverText(text, sources)
        except Exception as e:
            logger.warning("eel.receiverText failed: %s", e)


def takecommand() -> str | None:
    """
    Listen to the microphone and return recognised text, or None on failure.

    STT priority:
      1. Whisper (offline, multilingual — if installed and enabled)
      2. Google Speech Recognition (online, English — fallback)
    """
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            logger.info("Listening...")
            eel.DisplayMessage("I'm listening...")
            r.pause_threshold = 1
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=10, phrase_time_limit=8)

        logger.info("Recognising...")
        eel.DisplayMessage("Recognising...")

        # ── Try Whisper first (offline, multilingual) ─────────────────
        try:
            from backend.audio_engine import transcribe_audio, is_whisper_available
            if is_whisper_available():
                whisper_result = transcribe_audio(audio)
                if whisper_result:
                    logger.info("Whisper recognised: %s", whisper_result)
                    eel.DisplayMessage(whisper_result)
                    return whisper_result.lower()
                else:
                    logger.info("Whisper returned empty — falling back to Google STT.")
        except Exception as whisper_err:
            logger.warning("Whisper failed, falling back to Google STT: %s", whisper_err)

        # ── Fallback: Google Speech Recognition (online) ──────────────
        query = r.recognize_google(audio, language="en-US")
        logger.info("Google STT recognised: %s", query)
        eel.DisplayMessage(query)
        return query.lower()

    except sr.WaitTimeoutError:
        logger.warning("No speech detected within timeout.")
        eel.DisplayMessage("I didn't hear anything. Please try again.")
        return None
    except sr.UnknownValueError:
        logger.warning("Could not understand audio.")
        eel.DisplayMessage("Sorry, I couldn't understand that.")
        return None
    except Exception as e:
        logger.error("takecommand() error: %s", e)
        return None


# ── Whisper model preload (non-blocking) ─────────────────────────────────────
try:
    from backend.audio_engine import preload_model as _preload_whisper
    _preload_whisper()
except Exception:
    pass  # Whisper not installed — no problem


# ── Main Dispatcher ───────────────────────────────────────────────────────────
@eel.expose
def takeAllCommands(message: str = None) -> None:
    """
    Central command dispatcher.
    Accepts either a voice recording (message=None) or a text message from the UI.
    """
    if message is None:
        query = takecommand()
        if not query:
            return
    else:
        query = message.lower()
        logger.info("Text command received: %s", query)

    try:
        eel.senderText(query)
    except Exception as e:
        logger.warning("eel.senderText failed: %s", e)

    try:
        if not query:
            speak("No command was given.")
            return

        # ── Stop / Shutdown / Exit ───────────────────────────────────────
        if any(kw in query for kw in ["stop", "exit", "quit", "shutdown", "shut down", "bye"]):
            speak("Goodbye! Shutting down.")
            import os
            os._exit(0)

        # ── Memory Commands ──────────────────────────────────────────────
        elif any(kw in query for kw in ["what do you remember", "what you remember", "my memory", "your memory"]):
            from backend.feature import memory_summary
            memory_summary()

        elif any(kw in query for kw in ["forget everything", "clear memory", "wipe memory", "erase memory", "delete memory"]):
            from backend.feature import memory_forget
            memory_forget()

        elif any(kw in query for kw in ["remember that", "remember this", "keep in mind"]):
            from backend.feature import memory_remember
            memory_remember(query)

        elif any(kw in query for kw in ["search memory", "search my memory", "recall"]):
            from backend.feature import memory_search
            memory_search(query)

        # ── Data & AutoML Commands ───────────────────────────────────────
        elif any(kw in query for kw in ["analyze data", "analyze stats", "analyze csv", "analyze json", "dataset statistics"]):
            from backend.feature import analyze_dataset_voice
            analyze_dataset_voice(query)

        elif any(kw in query for kw in ["train model", "train machine learning", "automl training"]):
            from backend.feature import train_automl_model_voice
            train_automl_model_voice(query)

        elif any(kw in query for kw in ["predict", "model prediction", "make a prediction"]):
            from backend.feature import predict_automl_model_voice
            predict_automl_model_voice(query)

        # ── WhatsApp / call / message ────────────────────────────────────
        elif any(kw in query for kw in ["send message", "call", "video call"]):
            from backend.feature import findContact, whatsApp
            Phone, name, msg = findContact(query)
            if Phone != 0:
                if "send message" in query:
                    flag = "message"
                    if not msg:
                        if message is not None:
                            speak("Please specify the message. For example: send message to John that I am running late.")
                            return
                        else:
                            speak("What message should I send?")
                            msg = takecommand() or ""
                elif "video call" in query:
                    flag = "video call"
                    msg = ""
                else:
                    flag = "call"
                    msg = ""
                whatsApp(Phone, msg, flag, name)

        # ── Spotify Controls ─────────────────────────────────────────────
        elif "spotify" in query and "play" in query:
            from backend.feature import spotify_play
            spotify_play(query)

        elif any(kw in query for kw in ["pause spotify", "spotify pause", "pause music"]):
            from backend.feature import spotify_pause
            spotify_pause()

        elif any(kw in query for kw in ["resume spotify", "spotify resume", "unpause spotify", "continue music"]):
            from backend.feature import spotify_resume
            spotify_resume()

        elif any(kw in query for kw in ["next track", "skip track", "next song", "spotify next"]):
            from backend.feature import spotify_next
            spotify_next()

        elif any(kw in query for kw in ["previous track", "last track", "go back track", "spotify previous"]):
            from backend.feature import spotify_previous
            spotify_previous()

        elif any(kw in query for kw in ["what's playing", "now playing", "current song", "current track", "which song"]):
            from backend.feature import spotify_now_playing
            spotify_now_playing()

        # ── Email ────────────────────────────────────────────────────────
        elif any(kw in query for kw in ["read email", "check email", "read my email", "check my email", "check inbox", "read inbox"]):
            from backend.feature import read_emails
            read_emails(query)

        elif "send email" in query or "email to" in query:
            from backend.feature import send_email
            send_email(query)

        # ── Google Calendar ──────────────────────────────────────────────
        elif any(kw in query for kw in ["my events", "my calendar", "today's events", "tomorrow's events", "calendar events"]):
            from backend.feature import read_calendar_events
            read_calendar_events(query)

        elif any(kw in query for kw in ["schedule ", "add event", "create event", "calendar event"]):
            from backend.feature import add_calendar_event
            add_calendar_event(query)

        # ── Sandbox Code Execution ───────────────────────────────────────
        elif any(kw in query for kw in ["run code", "run the code", "execute code", "execute script", "run script", "test the code", "run the script"]):
            from backend.feature import run_sandboxed_code
            run_sandboxed_code(query)

        # ── YouTube / Play ───────────────────────────────────────────────
        elif "play" in query:
            from backend.feature import PlayYoutube
            success = PlayYoutube(query)
            if not success:
                if "open" in query:
                    from backend.feature import openCommand
                    openCommand(query)
                else:
                    from backend.feature import chatBot
                    chatBot(query)

        # ── Code Generation ──────────────────────────────────────────────
        elif ("code" in query or "program" in query or "script" in query) and any(kw in query for kw in ["write", "generate", "create", "make"]):
            from backend.feature import generate_code
            generate_code(query)

        # ── Typing ───────────────────────────────────────────────────────
        elif any(kw in query for kw in ["type ", "write "]) or query in ["type", "write"]:
            from backend.feature import type_text
            type_text(query)

        # ── Time ─────────────────────────────────────────────────────────
        elif any(kw in query for kw in ["what time", "current time", "time please"]):
            from backend.feature import tell_time
            tell_time()

        # ── Date ─────────────────────────────────────────────────────────
        elif any(kw in query for kw in ["what date", "today's date", "current date"]):
            from backend.feature import tell_date
            tell_date()

        # ── Weather ──────────────────────────────────────────────────────
        elif "weather" in query:
            from backend.feature import tell_weather
            tell_weather(query)

        # ── Hardware Monitoring ──────────────────────────────────────────
        elif any(kw in query for kw in ["cpu", "ram status", "battery", "hardware status", "system status"]):
            from backend.feature import tell_hardware_status
            tell_hardware_status(query)

        # ── App / URL open — checked BEFORE wikipedia so "open wikipedia"
        #    opens the site instead of searching wikipedia for "open" ─────
        elif "open" in query:
            from backend.feature import openCommand
            openCommand(query)

        # ── Wikipedia / Information (only when explicitly asked for wikipedia) ────
        elif "wikipedia" in query:
            from backend.feature import search_wikipedia
            search_wikipedia(query)

        # ── Screenshot ───────────────────────────────────────────────────
        elif any(kw in query for kw in ["screenshot", "screen short", "screen shot"]):
            from backend.feature import take_screenshot
            take_screenshot()

        # ── Timers & Alarms ──────────────────────────────────────────────
        elif "timer" in query:
            from backend.feature import set_timer_command
            set_timer_command(query)

        elif "alarm" in query:
            from backend.feature import set_alarm_command
            set_alarm_command(query)

        # ── Volume ───────────────────────────────────────────────────────
        elif "increase volume" in query or "volume up" in query:
            from backend.feature import volume_up
            volume_up()

        elif "decrease volume" in query or "volume down" in query:
            from backend.feature import volume_down
            volume_down()

        # ── Close app ────────────────────────────────────────────────────
        elif "close" in query:
            from backend.feature import closeApp
            closeApp(query)

        # ── Jokes ────────────────────────────────────────────────────────
        elif "joke" in query:
            from backend.feature import tell_joke
            tell_joke()

        # ── Notes ────────────────────────────────────────────────────────
        elif "note this" in query or "make a note" in query:
            from backend.feature import save_note
            save_note(query)

        elif "read my notes" in query or "read notes" in query:
            from backend.feature import read_notes
            read_notes()

        # ── Web Search (DuckDuckGo) ──────────────────────────────────────
        elif any(kw in query for kw in ["search", "who is", "what is"]):
            import re as _re
            from backend.feature import web_search
            search_query = _re.sub(
                r"\b(search|search for|who is|what is)\b", "", query, flags=_re.IGNORECASE
            ).strip()
            if search_query:
                speak(f"Searching the web for {search_query}...")
                result = web_search(search_query)
                speak(result)
            else:
                speak("Please tell me what to search for.")

        # ── AI Chatbot fallback ───────────────────────────────────────────
        else:
            from backend.feature import chatBot
            chatBot(query)

    except Exception as e:
        logger.error("takeAllCommands() error: %s", e)
        speak("Sorry, something went wrong.")

    try:
        eel.ShowHood()
    except Exception as e:
        logger.warning("eel.ShowHood failed: %s", e)
