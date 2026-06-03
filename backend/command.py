"""
command.py — Voice I/O and main command dispatcher for Jarvis.
"""

import logging
import threading
import speech_recognition as sr
import eel

from backend.config import ASSISTANT_NAME, VOICE_INDEX, SPEECH_RATE

# ── Logging ──────────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# Thread lock to ensure pyttsx3 is only used from one thread at a time
_speak_lock = threading.Lock()


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


def speak(text: str, sources: list = None) -> None:
    """
    Convert text to speech and display it in the UI.
    Creates a fresh pyttsx3 engine per call to avoid COM/threading issues on Windows.
    """
    import pyttsx3
    text = str(text)
    logger.info("Jarvis says: %s", text)

    try:
        eel.DisplayMessage(text)
    except Exception as e:
        logger.warning("eel.DisplayMessage failed: %s", e)

    with _speak_lock:
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
            
            cleaned_text = clean_speech_text(text)
            engine.say(cleaned_text)
            engine.runAndWait()
        except Exception as e:
            logger.error("speak() TTS error: %s", e)

    try:
        eel.receiverText(text, sources)
    except Exception as e:
        logger.warning("eel.receiverText failed: %s", e)


def takecommand() -> str | None:
    """Listen to the microphone and return recognised text, or None on failure."""
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
        query = r.recognize_google(audio, language="en-US")
        logger.info("User said: %s", query)
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

        # ── YouTube / Play ───────────────────────────────────────────────
        elif "play" in query:
            from backend.feature import PlayYoutube
            success = PlayYoutube(query)
            if not success and "open" in query:
                from backend.feature import openCommand
                openCommand(query)

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
