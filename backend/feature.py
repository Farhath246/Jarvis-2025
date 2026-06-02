"""
feature.py — All Jarvis feature implementations.
"""

import logging
import os
import re
import subprocess
import time
import webbrowser
import datetime
import requests
import speech_recognition as sr

import eel
import pyautogui
import pygame
import pywhatkit as kit
import sqlite3

from backend.command import speak
from backend.config import (
    ASSISTANT_NAME, USER_CALL_NAME,
    SOUND_FILE, DB_PATH, NOTES_FILE,
    GEMINI_API_KEY
)
from backend.helper import extract_yt_term, remove_words

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Database helper ───────────────────────────────────────────────────────────
def get_db():
    """Return a new SQLite connection (thread-safe, no global state)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ── pygame mixer ─────────────────────────────────────────────────────────────
pygame.mixer.init()


# ─────────────────────────────────────────────────────────────────────────────
# SOUND
# ─────────────────────────────────────────────────────────────────────────────
@eel.expose
def play_assistant_sound() -> None:
    """Play the Jarvis startup sound."""
    try:
        pygame.mixer.music.load(SOUND_FILE)
        pygame.mixer.music.play()
    except Exception as e:
        logger.error("play_assistant_sound() error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# APP / URL COMMANDS
# ─────────────────────────────────────────────────────────────────────────────
def openCommand(query: str) -> None:
    """Open a system application or website based on the query."""
    query = query.lower()

    # Strip the assistant name and the word "open"
    query = query.replace(ASSISTANT_NAME.lower(), "")
    query = query.replace("open", "")

    # Strip common conversational filler words/phrases
    filler_words = [
        "please", "can you", "could you", "would you", "will you",
        "so", "just", "for me", "up", "the", "a", "an",
        "hey", "hi", "okay", "ok", "now", "go ahead and",
        "i want you to", "i need you to", "i'd like you to",
        "kindly",
    ]
    for filler in filler_words:
        query = query.replace(filler, "")

    # Collapse multiple spaces and strip
    query = re.sub(r"\s+", " ", query).strip()

    if not query:
        speak("Please tell me what to open.")
        return

    try:
        conn = get_db()
        cursor = conn.cursor()

        # Check system apps first
        cursor.execute("SELECT path FROM sys_command WHERE name = ?", (query,))
        result = cursor.fetchone()
        if result:
            speak(f"Opening {query}")
            os.startfile(result[0])
            conn.close()
            return

        # Check web URLs
        cursor.execute("SELECT url FROM web_command WHERE name = ?", (query,))
        result = cursor.fetchone()
        if result:
            speak(f"Opening {query}")
            webbrowser.open(result[0])
            conn.close()
            return

        conn.close()

        # Well-known websites fallback
        well_known_sites = {
            "wikipedia": "https://www.wikipedia.org",
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "gmail": "https://mail.google.com",
            "github": "https://www.github.com",
            "twitter": "https://www.twitter.com",
            "x": "https://www.x.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "linkedin": "https://www.linkedin.com",
            "reddit": "https://www.reddit.com",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://www.spotify.com",
            "whatsapp": "https://web.whatsapp.com",
            "stackoverflow": "https://www.stackoverflow.com",
            "stack overflow": "https://www.stackoverflow.com",
            "chatgpt": "https://chat.openai.com",
        }
        if query in well_known_sites:
            speak(f"Opening {query}")
            webbrowser.open(well_known_sites[query])
            return

        # Fallback — try OS start (sanitised via subprocess)
        speak(f"Opening {query}")
        subprocess.run(["cmd", "/c", "start", "", query], shell=False, timeout=10)

    except Exception as e:
        logger.error("openCommand() error: %s", e)
        speak("Sorry, I couldn't open that.")


def closeApp(query: str) -> None:
    """Close a running application by name using taskkill."""
    query = query.replace("close", "").strip()
    if not query:
        speak("Please tell me which app to close.")
        return
    try:
        # Sanitise: only allow alphanumeric + spaces in app name
        safe_name = re.sub(r'[^\w\s]', '', query).strip()
        if not safe_name:
            speak("I couldn't determine which app to close.")
            return
        subprocess.run(
            ["taskkill", "/f", "/im", f"{safe_name}.exe"],
            shell=False, timeout=10,
            capture_output=True
        )
        speak(f"Closing {safe_name}")
    except subprocess.TimeoutExpired:
        speak(f"Timed out trying to close {query}.")
    except Exception as e:
        logger.error("closeApp() error: %s", e)
        speak("I couldn't close that application.")


# ─────────────────────────────────────────────────────────────────────────────
# YOUTUBE
# ─────────────────────────────────────────────────────────────────────────────
def PlayYoutube(query: str) -> bool:
    """Extract search term and play it on YouTube. Returns True if handled, False otherwise."""
    search_term = extract_yt_term(query)
    if search_term:
        speak(f"Playing {search_term} on YouTube")
        kit.playonyt(search_term)
        return True

    # Fallback: if user says "play youtube" or similar, open the site
    if "youtube" in query.lower():
        speak("Opening YouTube")
        webbrowser.open("https://www.youtube.com")
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# TIME & DATE
# ─────────────────────────────────────────────────────────────────────────────
def tell_time() -> None:
    """Tell the current local time."""
    now = datetime.datetime.now()
    hour = now.strftime("%I")
    minute = now.strftime("%M")
    period = now.strftime("%p")
    speak(f"The time is {hour} {minute} {period}")


def tell_date() -> None:
    """Tell today's date."""
    now = datetime.datetime.now()
    day = now.strftime("%A")
    date = now.strftime("%d")
    month = now.strftime("%B")
    year = now.strftime("%Y")
    speak(f"Today is {day}, {date} {month} {year}")


# ─────────────────────────────────────────────────────────────────────────────
# WEATHER  (free wttr.in — no API key required)
# ─────────────────────────────────────────────────────────────────────────────
def tell_weather(query: str) -> None:
    """Fetch and speak the weather for a city extracted from the query."""
    # Extract city from query e.g. "weather in Hyderabad"
    match = re.search(r"weather\s+(?:in\s+)?(.+)", query, re.IGNORECASE)
    city = match.group(1).strip() if match else "Hyderabad"

    try:
        speak(f"Fetching weather for {city}...")
        url = f"https://wttr.in/{city}?format=3"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            speak(response.text)
        else:
            speak(f"I couldn't get the weather for {city} right now.")
    except requests.exceptions.Timeout:
        speak("The weather service is taking too long to respond.")
    except Exception as e:
        logger.error("tell_weather() error: %s", e)
        speak("I had trouble fetching the weather.")


# ─────────────────────────────────────────────────────────────────────────────
# WIKIPEDIA
# ─────────────────────────────────────────────────────────────────────────────
def search_wikipedia(query: str) -> None:
    """Search Wikipedia and read a short summary. Fall back to Google search if not found."""
    raw_query = query
    try:
        import wikipedia
        # Set a custom user agent to prevent rate limiting / API blocks
        wikipedia.set_user_agent("JarvisAssistant/1.0 (contact@example.com)")
        search_query = re.sub(r"(wikipedia|who is|what is|information about|info about)", "", query, flags=re.IGNORECASE).strip()
        speak(f"Searching Wikipedia for {search_query}...")
        results = wikipedia.search(search_query)
        if not results:
            speak("I couldn't find anything on Wikipedia. Searching Google instead.")
            webbrowser.open(f"https://www.google.com/search?q={search_query}")
            return
        summary = wikipedia.summary(results[0], sentences=2)
        speak(summary)
    except Exception as e:
        logger.error("search_wikipedia() error: %s", e)
        speak("I had trouble searching Wikipedia. Searching Google instead.")
        search_query = re.sub(r"(wikipedia|who is|what is|information about|info about)", "", raw_query, flags=re.IGNORECASE).strip()
        webbrowser.open(f"https://www.google.com/search?q={search_query}")


# ─────────────────────────────────────────────────────────────────────────────
# SCREENSHOT
# ─────────────────────────────────────────────────────────────────────────────
def take_screenshot() -> None:
    """Take a screenshot and save it to the desktop."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        path = os.path.join(desktop, f"jarvis_screenshot_{timestamp}.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(path)
        speak(f"Screenshot saved to your desktop as jarvis screenshot {timestamp}")
    except Exception as e:
        logger.error("take_screenshot() error: %s", e)
        speak("I couldn't take the screenshot.")


# ─────────────────────────────────────────────────────────────────────────────
# TYPING
# ─────────────────────────────────────────────────────────────────────────────
def type_text(query: str) -> None:
    """Type the text specified in the query using pyautogui."""
    # Remove "type" or "write" prefix
    text_to_type = re.sub(r"^(type|write)\s+", "", query, flags=re.IGNORECASE).strip()
    if not text_to_type:
        speak("What would you like me to type?")
        return

    speak(f"Typing: {text_to_type}")
    # Give the user a brief moment to focus their cursor where they want to type
    time.sleep(2)
    pyautogui.write(text_to_type, interval=0.05)


# ─────────────────────────────────────────────────────────────────────────────
# VOLUME CONTROL
# ─────────────────────────────────────────────────────────────────────────────
def volume_up() -> None:
    """Increase system volume by pressing the volume-up key 5 times."""
    for _ in range(5):
        pyautogui.press("volumeup")
    speak("Volume increased")


def volume_down() -> None:
    """Decrease system volume by pressing the volume-down key 5 times."""
    for _ in range(5):
        pyautogui.press("volumedown")
    speak("Volume decreased")


# ─────────────────────────────────────────────────────────────────────────────
# JOKES
# ─────────────────────────────────────────────────────────────────────────────
def tell_joke() -> None:
    """Tell a random joke using pyjokes."""
    try:
        import pyjokes
        joke = pyjokes.get_joke()
        speak(joke)
    except Exception as e:
        logger.error("tell_joke() error: %s", e)
        speak("I'm all out of jokes right now!")


# ─────────────────────────────────────────────────────────────────────────────
# NOTES
# ─────────────────────────────────────────────────────────────────────────────
def save_note(query: str) -> None:
    """Save a spoken note to the notes file."""
    note_text = re.sub(r"(note this down|make a note|note this|note)", "", query, flags=re.IGNORECASE).strip()
    if not note_text:
        speak("What would you like me to note?")
        return
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {note_text}\n")
        speak(f"Note saved: {note_text}")
    except Exception as e:
        logger.error("save_note() error: %s", e)
        speak("I couldn't save the note.")


def read_notes() -> None:
    """Read saved notes aloud."""
    try:
        if not os.path.exists(NOTES_FILE):
            speak("You have no saved notes yet.")
            return
        with open(NOTES_FILE, "r", encoding="utf-8") as f:
            notes = f.read().strip()
        if not notes:
            speak("Your notes are empty.")
        else:
            speak("Here are your notes.")
            speak(notes)
    except Exception as e:
        logger.error("read_notes() error: %s", e)
        speak("I couldn't read the notes.")


# ─────────────────────────────────────────────────────────────────────────────
# CONTACTS & WHATSAPP
# ─────────────────────────────────────────────────────────────────────────────
def findContact(query: str):
    """Search the contacts database and return (phone, name) or (0, 0)."""
    words_to_remove = [ASSISTANT_NAME, "make", "a", "to", "phone", "call",
                       "send", "message", "whatsapp", "video"]
    query = remove_words(query, words_to_remove).strip().lower()

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Phone FROM contacts WHERE LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
            (f"%{query}%", f"{query}%")
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            speak("That contact doesn't exist.")
            return 0, 0

        phone = str(result[0])
        if not phone.startswith("+91"):
            phone = "+91" + phone
        return phone, query

    except Exception as e:
        logger.error("findContact() error: %s", e)
        speak("I had trouble finding that contact.")
        return 0, 0


def whatsApp(phone: str, message: str, flag: str, name: str) -> None:
    """Open WhatsApp and initiate a message, call, or video call."""
    from shlex import quote

    if flag == "message":
        target_tab = 12
        jarvis_message = f"Message sent to {name}"
    elif flag == "call":
        target_tab = 7
        message = ""
        jarvis_message = f"Calling {name}"
    else:
        target_tab = 6
        message = ""
        jarvis_message = f"Starting video call with {name}"

    encoded_message = quote(message)
    whatsapp_url = f"whatsapp://send?phone={phone}&text={encoded_message}"
    full_command = f'start "" "{whatsapp_url}"'

    try:
        subprocess.run(full_command, shell=True)
        time.sleep(5)
        subprocess.run(full_command, shell=True)

        pyautogui.hotkey("ctrl", "f")
        for _ in range(1, target_tab):
            pyautogui.hotkey("tab")
        pyautogui.hotkey("enter")
        speak(jarvis_message)
    except Exception as e:
        logger.error("whatsApp() error: %s", e)
        speak("I had trouble with WhatsApp.")


# ─────────────────────────────────────────────────────────────────────────────
# HOTWORD DETECTION
# ─────────────────────────────────────────────────────────────────────────────
def hotword() -> None:
    """Listen continuously for 'jarvis' wake word using Google Speech Recognition (free)."""
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 3000
    recognizer.dynamic_energy_threshold = True

    logger.info("Hotword detection active (free mode). Say 'Jarvis' to wake.")

    while True:
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=3)

            text = recognizer.recognize_google(audio).lower()
            logger.info("Hotword listener heard: %s", text)

            if "jarvis" in text or "alexa" in text:
                logger.info("Hotword detected!")
                pyautogui.hotkey("win", "j")
                time.sleep(2)

        except sr.WaitTimeoutError:
            pass   # silence — keep listening
        except sr.UnknownValueError:
            pass   # couldn't understand — keep listening
        except sr.RequestError as e:
            logger.error("Speech Recognition request failed: %s", e)
            time.sleep(3)
        except Exception as e:
            logger.error("hotword() error: %s", e)
            time.sleep(1)


# ─────────────────────────────────────────────────────────────────────────────
# AI CHATBOT
# ─────────────────────────────────────────────────────────────────────────────
def chatBot(query: str) -> str:
    """Send a query to Google Gemini (free tier) and speak the response."""
    try:
        import google.generativeai as genai

        if not GEMINI_API_KEY:
            speak("The chatbot is not configured yet. Please add your Gemini API key to config dot py.")
            return ""

        genai.configure(api_key=GEMINI_API_KEY)
        # Configure model with system instructions to handle language detection constraints
        system_instruction = (
            "You are Jarvis, an AI desktop assistant. "
            "Detect the language of the user's input. "
            "If the user talks in Hinglish (Hindi written in Latin/Roman script), reply in Hinglish. "
            "If the user talks in Urdu (either in Urdu script or Romanized Urdu), do NOT reply in Urdu script; "
            "instead, understand their Urdu/English query and reply in English. "
            "Otherwise, respond in the language of the query or English. Keep your responses short and concise."
        )
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=system_instruction
        )
        response = model.generate_content(query)
        result = response.text.strip()
        logger.info("Chatbot response: %s", result)
        speak(result)
        return result
    except Exception as e:
        logger.error("chatBot() error: %s", e)
        speak("I had trouble connecting to the chatbot.")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# CODE GENERATION
# ─────────────────────────────────────────────────────────────────────────────
def generate_code(query: str) -> None:
    """Generate programming code using Gemini API, save it to a file, and open it."""
    try:
        import google.generativeai as genai
        import json
        from backend.config import BASE_DIR

        if not GEMINI_API_KEY:
            speak("The code generator is not configured yet. Please add your Gemini API key to config dot py.")
            return

        genai.configure(api_key=GEMINI_API_KEY)
        
        prompt = (
            f"You are an expert programming code assistant. The user wants you to generate code: '{query}'. "
            "Generate the complete, working, high-quality code. "
            "Respond ONLY with a JSON object. Do NOT wrap the JSON in Markdown code blocks (like ```json ... ```), just return the raw JSON text. "
            "The JSON structure must be exactly as follows:\n"
            "{\n"
            '  "code": "full source code here as a single string",\n'
            '  "filename": "suggested_filename.ext",\n'
            '  "explanation": "a short one-sentence explanation of what the code does"\n'
            "}"
        )
        
        speak("Generating code, please wait...")
        
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up markdown code blocks if the model returned them
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n", "", text)
            text = re.sub(r"\n```$", "", text)
            text = text.strip()
            
        try:
            data = json.loads(text)
            code = data.get("code", "")
            filename = data.get("filename", "generated_code.txt")
            explanation = data.get("explanation", "Here is your generated code.")
        except Exception as json_err:
            logger.error("JSON parsing failed: %s. Response was: %s", json_err, text)
            speak("I had trouble structuring the generated code. Let me save the raw text instead.")
            code = text
            filename = "raw_output.txt"
            explanation = "I saved the raw output from the AI."

        # Save the code to a file in a 'generated_codes' folder
        output_dir = os.path.join(BASE_DIR, "generated_codes")
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
            
        speak(f"Code generated successfully. {explanation} I have saved it as {filename} and am opening it now.")
        
        # Open the file
        time.sleep(1)
        try:
            # Attempt to open in VS Code if it's in system PATH
            subprocess.run(["code", filepath], shell=True)
        except Exception:
            try:
                os.startfile(filepath)
            except Exception as open_err:
                logger.error("Could not open file: %s", open_err)
                
    except Exception as e:
        logger.error("generate_code() error: %s", e)
        speak("Sorry, I encountered an error while generating the code.")