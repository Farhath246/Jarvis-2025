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
import threading

import eel

from backend.config import CLI_MODE

# In CLI_MODE, replace eel with a no-op mock (same pattern as command.py)
if CLI_MODE:
    class _EelMock:
        def __getattr__(self, name):
            def _noop(*args, **kwargs):
                return lambda *a, **kw: None
            return _noop
        def expose(self, func):
            return func
    eel = _EelMock()
import pyautogui
import pygame
import pywhatkit as kit
import sqlite3

from backend.command import speak
from backend.config import (
    ASSISTANT_NAME, USER_CALL_NAME,
    SOUND_FILE, DB_PATH, NOTES_FILE,
    GEMINI_API_KEY, PREFERRED_LLM,
)
from backend.helper import extract_yt_term, remove_words
from backend.monitor import log_api_call, log_error

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Folder locations registry ─────────────────────────────────────────────────
# Maps friendly names / keywords → folder paths on this system.
FOLDER_LOCATIONS = {
    # Desktop items (folders)
    "test":              r"C:\Users\hp\OneDrive\Desktop\test",
    "old firefox data":  r"C:\Users\hp\OneDrive\Desktop\Old Firefox Data",
    "c language notes":  r"C:\Users\hp\OneDrive\Desktop\C language notes",
    "c notes":           r"C:\Users\hp\OneDrive\Desktop\C language notes",
    # Standard user folders
    "documents":         r"C:\Users\hp\OneDrive\Documents",
    "my documents":      r"C:\Users\hp\OneDrive\Documents",
    # Media folders
    "songs":             r"E:\SONGS VIDEOES",
    "video songs":       r"E:\SONGS VIDEOES",
    "song videos":       r"E:\SONGS VIDEOES",
    "music":             r"E:\SONGS VIDEOES",
    "music videos":      r"E:\SONGS VIDEOES",
    "movies":            r"F:\MOVIES",
    "movie":             r"F:\MOVIES",
    "films":             r"F:\MOVIES",
    # Pictures
    "pictures":          r"C:\Users\hp\OneDrive\Pictures\Saved Pictures",
    "saved pictures":    r"C:\Users\hp\OneDrive\Pictures\Saved Pictures",
    "photos":            r"C:\Users\hp\OneDrive\Pictures\Saved Pictures",
    "my pictures":       r"C:\Users\hp\OneDrive\Pictures\Saved Pictures",
}

# ── Database helper ───────────────────────────────────────────────────────────
def get_db():
    """Return a new SQLite connection (thread-safe, no global state)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ── pygame mixer (guarded — command.py may also init for Edge-TTS playback) ──
if not pygame.mixer.get_init():
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

    # Strip the assistant name and the word "open" as whole words/phrases
    query = re.sub(rf"\b{re.escape(ASSISTANT_NAME.lower())}\b", "", query)
    query = re.sub(r"\bopen\b", "", query)

    # Strip common conversational filler words/phrases as whole words/phrases
    filler_words = [
        "please", "can you", "could you", "would you", "will you",
        "so", "just", "for me", "up", "the", "a", "an",
        "hey", "hi", "okay", "ok", "now", "go ahead and",
        "i want you to", "i need you to", "i'd like you to",
        "kindly",
    ]
    for filler in filler_words:
        query = re.sub(rf"\b{re.escape(filler)}\b", "", query)

    # Collapse multiple spaces and strip
    query = re.sub(r"\s+", " ", query).strip()

    if not query:
        speak("Please tell me what to open.")
        return

    # ── Check folder locations first ─────────────────────────────────────
    # 1. Exact match (e.g. "movies", "documents", "saved pictures")
    if query in FOLDER_LOCATIONS:
        folder_path = FOLDER_LOCATIONS[query]
        if os.path.exists(folder_path):
            speak(f"Opening {query} folder")
            os.startfile(folder_path)
            return
        else:
            speak(f"The {query} folder path doesn't exist on this system.")
            return

    # 2. Partial match — query contains a folder keyword
    #    e.g. "telugu movies" → base folder is "movies" (F:\MOVIES),
    #    then look for a "telugu" subfolder inside it.
    for folder_key in sorted(FOLDER_LOCATIONS.keys(), key=len, reverse=True):
        if folder_key in query:
            base_folder = FOLDER_LOCATIONS[folder_key]
            # Extract the extra part (e.g. "telugu" from "telugu movies")
            extra = query.replace(folder_key, "").strip()

            if extra and os.path.isdir(base_folder):
                # Search for a subfolder that matches the extra keyword
                matched_subfolder = None
                try:
                    for item in os.listdir(base_folder):
                        item_path = os.path.join(base_folder, item)
                        if os.path.isdir(item_path) and extra.lower() in item.lower():
                            matched_subfolder = item_path
                            break
                except Exception as e:
                    logger.error("Subfolder search error: %s", e)

                if matched_subfolder:
                    speak(f"Opening {extra} {folder_key} folder")
                    os.startfile(matched_subfolder)
                    return
                else:
                    # No matching subfolder — open the base folder anyway
                    speak(f"I couldn't find a {extra} folder inside {folder_key}. Opening the main {folder_key} folder instead.")
                    os.startfile(base_folder)
                    return
            elif os.path.exists(base_folder):
                speak(f"Opening {folder_key} folder")
                os.startfile(base_folder)
                return

    # ── Check database and web ───────────────────────────────────────────
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
        res = subprocess.run(
            ["cmd", "/c", "start", "", query],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        if res.returncode == 0:
            speak(f"Opening {query}")
            return

        # If it failed to start locally, search Google / open in browser
        speak(f"I couldn't find {query} on your system. Opening in browser instead.")
        
        # Check if the query looks like a URL
        is_url = False
        if query.startswith(("http://", "https://")):
            is_url = True
        elif any(ext in query for ext in [".com", ".org", ".net", ".edu", ".gov", ".io", ".in", ".co"]):
            if " " not in query:
                is_url = True

        if is_url:
            url = query if query.startswith(("http://", "https://")) else "https://" + query
        else:
            url = f"https://www.google.com/search?q={query}"

        try:
            # Try opening in Chrome specifically, fall back to default browser
            chrome = webbrowser.get("chrome")
            chrome.open(url)
        except Exception:
            webbrowser.open(url)

    except Exception as e:
        logger.error("openCommand() error: %s", e)
        speak("Sorry, I couldn't open that.")


def closeApp(query: str) -> None:
    """Close a running application by name using taskkill."""
    query = re.sub(r"\bclose\b", "", query, flags=re.IGNORECASE).strip()
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
    city = match.group(1).strip() if match else ""
    
    # Strip common filler/time words
    for word in ["today", "tomorrow", "now", "like", "for", "the", "currently", "outside"]:
        city = re.sub(rf"\b{word}\b", "", city, flags=re.IGNORECASE).strip()
        
    if not city:
        city = "Hyderabad"

    start = time.time()
    try:
        speak(f"Fetching weather for {city}...")
        url = f"https://wttr.in/{city}?format=3"
        response = requests.get(url, timeout=5)
        elapsed = int((time.time() - start) * 1000)
        if response.status_code == 200:
            log_api_call("wttr_weather", latency_ms=elapsed, success=True)
            speak(response.text)
        else:
            log_api_call("wttr_weather", latency_ms=elapsed, success=False, error_msg=f"HTTP status {response.status_code}")
            speak(f"I couldn't get the weather for {city} right now.")
    except requests.exceptions.Timeout as e:
        elapsed = int((time.time() - start) * 1000)
        log_api_call("wttr_weather", latency_ms=elapsed, success=False, error_msg="Timeout")
        log_error("tell_weather", f"Timeout fetching weather: {e}", severity="warning")
        speak("The weather service is taking too long to respond.")
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log_api_call("wttr_weather", latency_ms=elapsed, success=False, error_msg=str(e))
        log_error("tell_weather", f"Error fetching weather: {e}", severity="error")
        logger.error("tell_weather() error: %s", e)
        speak("I had trouble fetching the weather.")


# ─────────────────────────────────────────────────────────────────────────────
# WIKIPEDIA
# ─────────────────────────────────────────────────────────────────────────────
def search_wikipedia(query: str) -> None:
    """Search Wikipedia and read a short summary. Fall back to Google search if not found."""
    raw_query = query
    start = time.time()
    try:
        import wikipedia
        # Set a custom user agent to prevent rate limiting / API blocks
        wikipedia.set_user_agent("JarvisAssistant/1.0 (contact@example.com)")
        search_query = re.sub(r"\b(wikipedia|who is|what is|information about|info about)\b", "", query, flags=re.IGNORECASE).strip()
        speak(f"Searching Wikipedia for {search_query}...")
        results = wikipedia.search(search_query)
        if not results:
            elapsed = int((time.time() - start) * 1000)
            log_api_call("wikipedia", latency_ms=elapsed, success=True)
            speak("I couldn't find anything on Wikipedia. Searching Google instead.")
            webbrowser.open(f"https://www.google.com/search?q={search_query}")
            return
        summary = wikipedia.summary(results[0], sentences=2)
        elapsed = int((time.time() - start) * 1000)
        log_api_call("wikipedia", latency_ms=elapsed, success=True)
        speak(summary)
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log_api_call("wikipedia", latency_ms=elapsed, success=False, error_msg=str(e))
        log_error("search_wikipedia", f"Wikipedia search failed: {e}", severity="warning")
        logger.error("search_wikipedia() error: %s", e)
        speak("I had trouble searching Wikipedia. Searching Google instead.")
        search_query = re.sub(r"\b(wikipedia|who is|what is|information about|info about)\b", "", raw_query, flags=re.IGNORECASE).strip()
        webbrowser.open(f"https://www.google.com/search?q={search_query}")


# ─────────────────────────────────────────────────────────────────────────────
# SCREENSHOT
# ─────────────────────────────────────────────────────────────────────────────
def take_screenshot() -> None:
    """Take a screenshot and save it to the desktop."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            onedrive_desktop = os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop")
            if os.path.exists(onedrive_desktop):
                desktop = onedrive_desktop
        path = os.path.join(desktop, f"jarvis_screenshot_{timestamp}.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(path)
        speak(f"Screenshot saved to your desktop as jarvis screenshot {timestamp}")
    except Exception as e:
        logger.error("take_screenshot() error: %s", e)
        speak("I couldn't take the screenshot.")


# ─────────────────────────────────────────────────────────────────────────────
# HARDWARE MONITORING
# ─────────────────────────────────────────────────────────────────────────────
def tell_hardware_status(query: str) -> None:
    """Check system hardware status (CPU, RAM, Battery) using Windows WMI/PowerShell."""
    query = query.lower()
    try:
        import json
        import subprocess

        # Helper to execute PowerShell commands
        def run_ps(cmd: str) -> str:
            res = subprocess.run(
                ["powershell", "-Command", cmd],
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            return res.stdout.strip() if res.returncode == 0 else ""

        speak_parts = []

        # ── CPU Check ─────────────────────────────────────────────────────
        if "cpu" in query or "hardware" in query or "system" in query:
            cpu_load = run_ps("Get-CimInstance Win32_Processor | Select-Object -ExpandProperty LoadPercentage")
            if cpu_load:
                speak_parts.append(f"CPU usage is currently at {cpu_load} percent.")
            else:
                speak_parts.append("I couldn't retrieve the CPU load details.")

        # ── RAM Check ─────────────────────────────────────────────────────
        if "ram" in query or "memory" in query or "hardware" in query or "system" in query:
            ram_json = run_ps("Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory, TotalVisibleMemorySize | ConvertTo-Json")
            if ram_json:
                try:
                    data = json.loads(ram_json)
                    # Convert KB to GB
                    total_gb = round(data["TotalVisibleMemorySize"] / 1024 / 1024, 1)
                    free_gb = round(data["FreePhysicalMemory"] / 1024 / 1024, 1)
                    used_gb = round(total_gb - free_gb, 1)
                    used_pct = round((used_gb / total_gb) * 100)
                    speak_parts.append(f"Memory usage is {used_gb} gigabytes out of {total_gb} gigabytes, which is about {used_pct} percent.")
                except Exception:
                    speak_parts.append("I encountered an issue parsing the memory status.")
            else:
                speak_parts.append("I couldn't retrieve the RAM details.")

        # ── Battery Check ─────────────────────────────────────────────────
        if "battery" in query or "charge" in query or "hardware" in query or "system" in query:
            battery_json = run_ps("Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus | ConvertTo-Json")
            if battery_json:
                try:
                    data = json.loads(battery_json)
                    if isinstance(data, list):
                        data = data[0] if data else None
                    
                    if data and "EstimatedChargeRemaining" in data:
                        pct = data["EstimatedChargeRemaining"]
                        status = data.get("BatteryStatus", 1)
                        # WMI BatteryStatus: 2 = AC Power (Charging/Full), 1 = Discharging
                        charging_str = "charging" if status == 2 else "discharging"
                        speak_parts.append(f"Battery is at {pct} percent and is currently {charging_str}.")
                    else:
                        speak_parts.append("Battery details are currently unavailable.")
                except Exception:
                    speak_parts.append("I encountered an issue parsing the battery details.")
            else:
                # Desktop PC with no battery
                speak_parts.append("The system is running on AC power. No battery was detected.")

        if speak_parts:
            speak(" ".join(speak_parts))
        else:
            speak("Please ask specifically for CPU, RAM, battery, or overall hardware status.")

    except Exception as e:
        logger.error("tell_hardware_status() error: %s", e)
        speak("I had trouble accessing the hardware monitoring utilities.")


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
    note_text = re.sub(r"\b(note this down|make a note|note this|note)\b", "", query, flags=re.IGNORECASE).strip()
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
    """Search the contacts database and return (phone, name, message) or (0, 0, None)."""
    # Look for message separators like "that" or "saying"
    message = None
    match = re.search(r"\b(?:that|saying)\b\s+(.+)$", query, re.IGNORECASE)
    if match:
        message = match.group(1).strip()
        # Remove the message part from the contact query
        query = query[:match.start()].strip()

    words_to_remove = [ASSISTANT_NAME, "make", "a", "to", "phone", "call",
                       "send", "message", "whatsapp", "video"]
    contact_query = remove_words(query, words_to_remove).strip().lower()

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT Phone, name FROM contacts WHERE LOWER(name) LIKE ? OR LOWER(name) LIKE ?",
            (f"%{contact_query}%", f"{contact_query}%")
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            speak("That contact doesn't exist.")
            return 0, 0, None

        phone = str(result[0])
        contact_name = result[1]
        if not phone.startswith("+91"):
            phone = "+91" + phone
        return phone, contact_name, message

    except Exception as e:
        logger.error("findContact() error: %s", e)
        speak("I had trouble finding that contact.")
        return 0, 0, None


def whatsApp(phone: str, message: str, flag: str, name: str) -> None:
    """Open WhatsApp and initiate a message, call, or video call."""
    import urllib.parse

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

    encoded_message = urllib.parse.quote(message)
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
def wikipedia_search_local(query: str) -> tuple[str | None, list | None]:
    """Search Wikipedia, returning (summary_text, sources_list) or (None, None)."""
    try:
        import wikipedia
        # Set a custom user agent to prevent rate limiting / API blocks
        wikipedia.set_user_agent("JarvisAssistant/1.0 (contact@example.com)")
        
        # Clean query: strip typical query words
        search_query = re.sub(r"\b(wikipedia|who is|what is|information about|info about)\b", "", query, flags=re.IGNORECASE).strip()
        if not search_query:
            return None, None
            
        results = wikipedia.search(search_query)
        if not results:
            return None, None
            
        page = wikipedia.page(results[0])
        summary = wikipedia.summary(results[0], sentences=2)
        if summary:
            sources = [{"title": f"Wikipedia: {page.title}", "url": page.url}]
            return summary, sources
        return None, None
    except Exception as e:
        logger.warning("wikipedia_search_local failed: %s", e)
        return None, None


def google_search_scrape(query: str) -> tuple[str | None, list | None]:
    """Perform a Google Search via lightweight scraping, returning (summary, sources) or (None, None)."""
    try:
        import urllib.parse
        from bs4 import BeautifulSoup
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        }
        # gbv=1 forces basic HTML version of Google search
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&gbv=1"
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return None, None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        snippets = []
        sources = []
        
        for g in soup.find_all("div", class_="g"):
            link_el = g.find("a")
            title_el = g.find("h3")
            snippet_el = g.find("span", class_="st") or g.find("div", class_="VwiC3b") or g.find("span", class_="aCOpRe")
            
            if not snippet_el:
                spans = g.find_all("span")
                for s in spans:
                    if len(s.get_text().strip()) > 30:
                        snippet_el = s
                        break
                        
            if link_el and snippet_el:
                uri = link_el.get("href")
                if uri and uri.startswith("/url?q="):
                    parsed = urllib.parse.urlparse(uri)
                    qs = urllib.parse.parse_qs(parsed.query)
                    if "q" in qs:
                        uri = qs["q"][0]
                        
                title = title_el.get_text().strip() if title_el else "Search Result"
                snippet = snippet_el.get_text().strip()
                
                if uri and uri.startswith("http") and snippet:
                    if uri not in [s["url"] for s in sources]:
                        snippets.append(snippet)
                        sources.append({"title": title, "url": uri})
                        if len(snippets) >= 2:
                            break
                            
        if snippets:
            summary = " ".join(snippets)
            return summary, sources
        return None, None
    except Exception as e:
        logger.error("google_search_scrape failed: %s", e)
        return None, None


def web_search(query: str) -> str:
    """Search the web using DuckDuckGo and return the body of the top result."""
    start = time.time()
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=1))
            elapsed = int((time.time() - start) * 1000)
            log_api_call("duckduckgo_search", latency_ms=elapsed, success=True)
            if results:
                return results[0].get("body", "No content found.")
            return "No search results found."
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        log_api_call("duckduckgo_search", latency_ms=elapsed, success=False, error_msg=str(e))
        log_error("web_search", f"DuckDuckGo search failed: {e}", severity="warning")
        logger.error("web_search() error: %s", e)
        return "Sorry, I couldn't perform the web search right now."


def chatBot(query: str) -> str:
    """
    Smart search assistant using a Web-RAG pipeline:
    1. Intent Detection & Query Reformulation  (LLM)
    2. Google Search + Deep Web Scraping       (requests + BeautifulSoup)
    3. LLM Context Synthesis with citations    (LLM)
    Falls back to direct LLM generation for non-search queries.

    LLM routing is controlled by PREFERRED_LLM in config.py:
      - "ollama" -> try local Ollama first, Gemini as fallback  (low-end)
      - "gemini" -> try Gemini first, Ollama as fallback       (full-featured)

    Memory-aware: includes recent conversation history, user preferences,
    and learned facts in the LLM prompt for persistent context.
    """
    try:
        from backend.web_rag import run_rag_pipeline

        # Live status callback -- updates the HUD + siri-text in the UI
        def _rag_status(emoji: str, message: str):
            display_msg = f"{emoji} {message}"
            try:
                eel.DisplayMessage(display_msg)
            except Exception:
                pass
            try:
                eel.setWebStatus("processing", display_msg)
            except Exception:
                pass

        # -- Run the RAG pipeline --
        logger.info("Running Web-RAG pipeline for query: %s", query)
        rag_answer, rag_sources = run_rag_pipeline(query, status_callback=_rag_status)

        if rag_answer is not None:
            logger.info("RAG pipeline succeeded with %d sources.", len(rag_sources or []))
            speak(rag_answer, rag_sources)
            _save_to_memory(query, rag_answer)
            return rag_answer

        # -- No search required -- use direct LLM generation --
        logger.info("No search required. Using direct LLM (PREFERRED_LLM=%s)...", PREFERRED_LLM)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # -- Build memory-enriched system prompt --
        system_instruction = (
            "You are Jarvis, an AI desktop assistant. "
            f"The current date and time is {current_time}. "
            "Detect the language of the user's input. "
            "If the user talks in Hinglish (Hindi written in Latin/Roman script), reply in Hinglish. "
            "If the user talks in Urdu (either in Urdu script or Romanized Urdu), do NOT reply in Urdu script; "
            "instead, understand their Urdu/English query and reply in English. "
            "Otherwise, respond in the language of the query or English. Keep your responses short and concise."
        )

        memory_context = _build_memory_prompt()
        if memory_context:
            system_instruction += "\n\n" + memory_context

        # -- LLM routing based on PREFERRED_LLM --
        if PREFERRED_LLM == "ollama":
            # Low-end mode: try local Ollama first, Gemini as fallback
            result = _try_ollama(query, system_instruction)
            if result:
                _save_to_memory(query, result)
                return result
            logger.info("Ollama unavailable, falling back to Gemini...")
            result = _try_gemini(query, system_instruction)
            if result:
                _save_to_memory(query, result)
                return result
        else:
            # Full-featured mode: try Gemini first, Ollama as fallback
            result = _try_gemini(query, system_instruction)
            if result:
                _save_to_memory(query, result)
                return result
            logger.info("Gemini failed, falling back to Ollama...")
            result = _try_ollama(query, system_instruction)
            if result:
                _save_to_memory(query, result)
                return result

        # Both LLMs failed
        speak("I had trouble connecting to the chatbot.")
        return ""

    except Exception as e:
        logger.error("chatBot() error: %s", e)
        speak("Sorry, something went wrong with the chatbot.")
        return ""


def _try_ollama(query: str, system_instruction: str) -> str | None:
    """
    Attempt to generate a response using local Ollama.
    Returns the response text on success, None on failure.
    """
    from backend.config import OLLAMA_HOST, OLLAMA_MODEL
    start = time.time()
    try:
        try:
            eel.DisplayMessage("🦙 Thinking (Local LLM)...")
        except Exception:
            pass

        # Quick health check first
        try:
            requests.get(f"{OLLAMA_HOST}/api/tags", timeout=2)
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama server unreachable: {e}")

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"System: {system_instruction}\n\nUser: {query}\n\nJarvis:",
            "stream": False
        }
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=30)
        elapsed = int((time.time() - start) * 1000)

        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            if result:
                logger.info("Ollama response: %s", result)
                log_api_call("ollama", OLLAMA_MODEL, latency_ms=elapsed, success=True)
                speak(result)
                return result

        raise Exception(f"Ollama returned status {response.status_code}")

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.warning("Ollama call failed: %s", e)
        log_api_call("ollama", OLLAMA_MODEL, latency_ms=elapsed, success=False, error_msg=str(e))
        return None


def _try_gemini(query: str, system_instruction: str) -> str | None:
    """
    Attempt to generate a response using Google Gemini API.
    Returns the response text on success, None on failure.
    """
    if not GEMINI_API_KEY:
        logger.warning("Gemini API key not configured.")
        return None

    start = time.time()
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)

        try:
            eel.DisplayMessage("💡 Thinking...")
        except Exception:
            pass

        from backend.web_rag import _gemini_generate_with_retry
        
        contents = [
            {"role": "user", "parts": [{"text": f"System: {system_instruction}\n\n{query}"}]}
        ]
        response, used_model = _gemini_generate_with_retry(client, contents)

        elapsed = int((time.time() - start) * 1000)
        tokens_used = 0
        if response and hasattr(response, 'usage_metadata') and response.usage_metadata:
            tokens_used = getattr(response.usage_metadata, 'total_token_count', 0)

        log_api_call(
            service="gemini", model=used_model or "gemini-2.5-flash",
            latency_ms=elapsed, tokens_used=tokens_used, success=True,
        )

        if not response or not response.text:
            raise Exception("No response received from Gemini API.")

        result = response.text.strip()
        logger.info("Gemini response: %s", result)
        speak(result)
        return result

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.warning("Gemini call failed: %s", e)
        log_api_call("gemini", "gemini-2.5-flash", latency_ms=elapsed, success=False, error_msg=str(e))
        log_error("chatBot", f"Gemini call failed: {e}", severity="warning")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY HELPERS (used by chatBot and voice commands)
# ─────────────────────────────────────────────────────────────────────────────

def _build_memory_prompt() -> str:
    """
    Build a memory context string to inject into the LLM system prompt.
    Combines recent conversations, user preferences, and learned facts.
    """
    try:
        from backend.memory import (
            build_memory_context, build_preferences_context, build_facts_context,
        )
        from backend.config import MEMORY_ENABLED, MEMORY_MAX_CONTEXT

        if not MEMORY_ENABLED:
            return ""

        parts = []

        # User preferences (always included — they're compact)
        prefs_ctx = build_preferences_context()
        if prefs_ctx:
            parts.append(prefs_ctx)

        # Learned facts (always included — they're compact)
        facts_ctx = build_facts_context()
        if facts_ctx:
            parts.append(facts_ctx)

        # Recent conversation history
        memory_ctx = build_memory_context(limit=MEMORY_MAX_CONTEXT)
        if memory_ctx:
            parts.append(memory_ctx)

        if parts:
            header = (
                "You have persistent memory. Use the information below to provide "
                "contextual, personalised responses. Reference past conversations "
                "naturally when relevant, but don't repeat old answers verbatim."
            )
            return header + "\n\n" + "\n\n".join(parts)

        return ""

    except Exception as e:
        logger.warning("_build_memory_prompt() error (non-critical): %s", e)
        return ""


def _save_to_memory(user_msg: str, jarvis_msg: str) -> None:
    """
    Save a conversation exchange to memory and trigger fact extraction.
    Runs indexing and extraction in background threads to avoid blocking.
    """
    try:
        from backend.memory import save_conversation, extract_and_save_facts
        from backend.memory_search import index_conversation
        from backend.config import MEMORY_ENABLED

        if not MEMORY_ENABLED:
            return

        # Save to SQLite
        conv_id = save_conversation(user_msg, jarvis_msg)

        if conv_id:
            # Index for semantic search (background-safe, ChromaDB handles threading)
            index_conversation(conv_id, user_msg, jarvis_msg)

            # Extract personal facts (runs in background thread)
            extract_and_save_facts(user_msg, jarvis_msg)

    except Exception as e:
        logger.warning("_save_to_memory() error (non-critical): %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# MEMORY VOICE COMMANDS
# ─────────────────────────────────────────────────────────────────────────────

def memory_summary() -> None:
    """Tell the user what Jarvis remembers about them."""
    try:
        from backend.memory import get_memory_summary
        summary = get_memory_summary()
        speak(summary)
    except Exception as e:
        logger.error("memory_summary() error: %s", e)
        speak("I had trouble accessing my memory.")


def memory_forget() -> None:
    """Wipe all of Jarvis's memory (conversations, preferences, facts)."""
    try:
        from backend.memory import forget_all
        from backend.memory_search import clear_index

        success = forget_all()
        clear_index()

        if success:
            speak("Done. I've forgotten everything. My memory is now completely clear.")
        else:
            speak("I had trouble clearing my memory.")
    except Exception as e:
        logger.error("memory_forget() error: %s", e)
        speak("I had trouble clearing my memory.")


def memory_remember(query: str) -> None:
    """Save a user-stated preference or fact. E.g., 'Remember that I like cricket'."""
    try:
        from backend.memory import save_user_preference, save_learned_fact

        # Extract the thing to remember
        text = re.sub(
            r"\b(remember|remember that|note that|keep in mind)\b",
            "", query, flags=re.IGNORECASE
        ).strip()

        if not text:
            speak("What would you like me to remember?")
            return

        # Check if it's a preference pattern: "I like X", "my favorite X is Y"
        pref_match = re.search(
            r"(?:i (?:like|love|prefer|enjoy)|my (?:favorite|favourite) (\w+) is)\s+(.+)",
            text, re.IGNORECASE,
        )
        if pref_match:
            if pref_match.group(1):
                # "my favorite X is Y"
                key = f"favorite_{pref_match.group(1).lower()}"
                value = pref_match.group(2).strip()
            else:
                # "I like X"
                key = "likes"
                value = pref_match.group(2).strip()
            save_user_preference(key, value)
        else:
            # Save as a learned fact
            save_learned_fact(text, source="user_stated", confidence=1.0)

        speak(f"Got it! I'll remember that: {text}")

    except Exception as e:
        logger.error("memory_remember() error: %s", e)
        speak("I had trouble saving that to memory.")


def memory_search(query: str) -> None:
    """Search conversation memory for a topic. E.g., 'Search memory for cricket'."""
    try:
        from backend.memory_search import search_memory

        search_query = re.sub(
            r"\b(search memory|search my memory|recall|search conversations)\s*(?:for|about)?\s*",
            "", query, flags=re.IGNORECASE,
        ).strip()

        if not search_query:
            speak("What would you like me to search my memory for?")
            return

        results = search_memory(search_query, top_k=3)

        if not results:
            speak(f"I don't have any memories related to {search_query}.")
            return

        speak(f"I found {len(results)} related conversation{'s' if len(results) != 1 else ''} in my memory.")
        for i, r in enumerate(results[:3], 1):
            speak(f"Memory {i}: You asked '{r['user_msg'][:100]}'")

    except Exception as e:
        logger.error("memory_search() error: %s", e)
        speak("I had trouble searching my memory.")


# ─────────────────────────────────────────────────────────────────────────────
# CODE GENERATION
# ─────────────────────────────────────────────────────────────────────────────
def generate_code(query: str) -> None:
    """Generate programming code using Gemini API, save it to a file, and open it."""
    try:
        from google import genai
        import json
        from backend.config import BASE_DIR

        if not GEMINI_API_KEY:
            speak("The code generator is not configured yet. Please add your Gemini API key to config dot py.")
            return

        client = genai.Client(api_key=GEMINI_API_KEY)
        
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
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
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
            subprocess.run(["code", filepath], shell=True, check=True)
        except Exception:
            try:
                os.startfile(filepath)
            except Exception as open_err:
                logger.error("Could not open file: %s", open_err)
                
    except Exception as e:
        logger.error("generate_code() error: %s", e)
        speak("Sorry, I encountered an error while generating the code.")


# ─────────────────────────────────────────────────────────────────────────────
# BACKGROUND ALARMS & TIMERS
# ─────────────────────────────────────────────────────────────────────────────
_active_timers = []
_active_alarms = []
_scheduler_lock = threading.Lock()
_scheduler_started = False

def _scheduler_loop():
    """Background thread loop that checks timers and alarms every second."""
    import time
    from backend.feature import play_assistant_sound
    
    while True:
        try:
            now = datetime.datetime.now()
            current_time_str = now.strftime("%H:%M")
            current_seconds = time.time()
            
            triggered_timers = []
            triggered_alarms = []
            
            with _scheduler_lock:
                # Check timers
                remaining_timers = []
                for timer in _active_timers:
                    if current_seconds >= timer["target_time"]:
                        triggered_timers.append(timer)
                    else:
                        remaining_timers.append(timer)
                _active_timers[:] = remaining_timers
                
                # Check alarms
                remaining_alarms = []
                for alarm in _active_alarms:
                    # Match HH:MM
                    if current_time_str == alarm["time"]:
                        triggered_alarms.append(alarm)
                    else:
                        remaining_alarms.append(alarm)
                _active_alarms[:] = remaining_alarms
            
            # Handle triggered timers
            for timer in triggered_timers:
                label = timer.get("label", "Timer")
                logger.info("Timer expired: %s", label)
                speak(f"Alert! Your timer for {label} has expired!")
                # Play sound
                play_assistant_sound()
                
            # Handle triggered alarms
            for alarm in triggered_alarms:
                label = alarm.get("label", "Alarm")
                logger.info("Alarm triggered: %s", label)
                speak(f"Alert! Your alarm for {label} is ringing!")
                play_assistant_sound()
                
        except Exception as e:
            logger.error("Error in scheduler loop: %s", e)
            
        time.sleep(1)

def start_scheduler():
    """Start the background timer/alarm scheduler thread if not already running."""
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        _scheduler_started = True
        import threading
        thread = threading.Thread(target=_scheduler_loop, daemon=True, name="JarvisScheduler")
        thread.start()
        logger.info("Background scheduler thread started.")

def set_timer_command(query: str) -> None:
    """Parse timer query and add it to the background scheduler."""
    query = query.lower()
    start_scheduler()  # Ensure scheduler is running
    
    # regex: timer (for) X seconds/minutes/hours
    match = re.search(r"timer\s+(?:for\s+)?(\d+)\s*(second|sec|minute|min|hour|hr)s?", query)
    if not match:
        speak("Please specify a duration, for example: set a timer for 10 seconds.")
        return
        
    duration = int(match.group(1))
    unit = match.group(2)
    
    multiplier = 1
    unit_str = "seconds"
    if unit in ["minute", "min"]:
        multiplier = 60
        unit_str = "minutes"
    elif unit in ["hour", "hr"]:
        multiplier = 3600
        unit_str = "hours"
        
    total_seconds = duration * multiplier
    
    with _scheduler_lock:
        _active_timers.append({
            "target_time": time.time() + total_seconds,
            "duration": total_seconds,
            "label": f"{duration} {unit_str}"
        })
        
    speak(f"I've set a timer for {duration} {unit_str}.")

def set_alarm_command(query: str) -> None:
    """Parse alarm query and add it to the background scheduler."""
    query = query.lower()
    start_scheduler()  # Ensure scheduler is running
    
    # Match formats like: "alarm for 8:30 am", "alarm for 15:45", "alarm for 9 pm"
    match = re.search(r"alarm\s+(?:for\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", query)
    if not match:
        speak("Please specify a time, for example: set alarm for 7:30 AM.")
        return
        
    h = int(match.group(1))
    m = int(match.group(2)) if match.group(2) else 0
    period = match.group(3)
    
    # Validate hours/minutes
    if h < 0 or h > 23 or m < 0 or m > 59:
        speak("That doesn't seem like a valid time.")
        return
        
    # Convert to 24-hour format
    if period:
        if period == "pm" and h < 12:
            h += 12
        elif period == "am" and h == 12:
            h = 0
            
    time_str = f"{h:02d}:{m:02d}"
    
    with _scheduler_lock:
        _active_alarms.append({
            "time": time_str,
            "label": f"{h:02d}:{m:02d}"
        })
        
    display_time = f"{h:02d}:{m:02d}" if not period else f"{h % 12 or 12}:{m:02d} {period.upper()}"
    speak(f"I've set an alarm for {display_time}.")


# Start the background scheduler on module import
start_scheduler()


# ─────────────────────────────────────────────────────────────────────────────
# SPOTIFY PLAYBACK CONTROL
# ─────────────────────────────────────────────────────────────────────────────
_spotify_client = None

def _get_spotify():
    """Lazy-init and return a Spotipy client with user auth."""
    global _spotify_client
    if _spotify_client is not None:
        return _spotify_client

    from backend.config import (
        SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI, EXE_DIR,
    )

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth

        cache_path = os.path.join(EXE_DIR, ".spotify_cache")
        auth_manager = SpotifyOAuth(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
            redirect_uri=SPOTIFY_REDIRECT_URI,
            scope="user-modify-playback-state user-read-playback-state user-read-currently-playing",
            cache_path=cache_path,
            open_browser=True,
        )
        _spotify_client = spotipy.Spotify(auth_manager=auth_manager)
        return _spotify_client
    except Exception as e:
        logger.error("Spotify init error: %s", e)
        return None


def spotify_play(query: str) -> None:
    """Search Spotify and start playback on the active device."""
    sp = _get_spotify()
    if sp is None:
        speak("Spotify is not configured. Please add your Spotify API credentials to the dot env file.")
        return

    # Extract the search term: strip "spotify play ...", "play ... on spotify" etc.
    search_term = re.sub(
        r"\b(spotify|play|on|the|song|track|music)\b", "", query, flags=re.IGNORECASE
    ).strip()
    if not search_term:
        speak("What would you like me to play on Spotify?")
        return

    try:
        # Search for tracks
        results = sp.search(q=search_term, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        if not tracks:
            speak(f"I couldn't find '{search_term}' on Spotify.")
            return

        track = tracks[0]
        track_name = track["name"]
        artist = track["artists"][0]["name"]
        uri = track["uri"]

        # Try to play on the active device
        try:
            sp.start_playback(uris=[uri])
            speak(f"Now playing {track_name} by {artist} on Spotify.")
        except Exception as playback_err:
            # No active device — open Spotify URI in browser as fallback
            logger.warning("No active Spotify device: %s", playback_err)
            webbrowser.open(track["external_urls"]["spotify"])
            speak(f"Opening {track_name} by {artist} in Spotify.")

    except Exception as e:
        logger.error("spotify_play() error: %s", e)
        speak("I had trouble playing that on Spotify.")


def spotify_pause() -> None:
    """Pause Spotify playback."""
    sp = _get_spotify()
    if sp is None:
        speak("Spotify is not configured.")
        return
    try:
        sp.pause_playback()
        speak("Spotify paused.")
    except Exception as e:
        logger.error("spotify_pause() error: %s", e)
        speak("I couldn't pause Spotify. Make sure a device is active.")


def spotify_resume() -> None:
    """Resume Spotify playback."""
    sp = _get_spotify()
    if sp is None:
        speak("Spotify is not configured.")
        return
    try:
        sp.start_playback()
        speak("Resuming Spotify playback.")
    except Exception as e:
        logger.error("spotify_resume() error: %s", e)
        speak("I couldn't resume Spotify.")


def spotify_next() -> None:
    """Skip to the next track on Spotify."""
    sp = _get_spotify()
    if sp is None:
        speak("Spotify is not configured.")
        return
    try:
        sp.next_track()
        time.sleep(0.5)
        current = sp.current_playback()
        if current and current.get("item"):
            name = current["item"]["name"]
            artist = current["item"]["artists"][0]["name"]
            speak(f"Now playing {name} by {artist}.")
        else:
            speak("Skipped to the next track.")
    except Exception as e:
        logger.error("spotify_next() error: %s", e)
        speak("I couldn't skip the track.")


def spotify_previous() -> None:
    """Go back to the previous track on Spotify."""
    sp = _get_spotify()
    if sp is None:
        speak("Spotify is not configured.")
        return
    try:
        sp.previous_track()
        time.sleep(0.5)
        current = sp.current_playback()
        if current and current.get("item"):
            name = current["item"]["name"]
            artist = current["item"]["artists"][0]["name"]
            speak(f"Now playing {name} by {artist}.")
        else:
            speak("Went back to the previous track.")
    except Exception as e:
        logger.error("spotify_previous() error: %s", e)
        speak("I couldn't go back.")


def spotify_now_playing() -> None:
    """Tell the user what's currently playing on Spotify."""
    sp = _get_spotify()
    if sp is None:
        speak("Spotify is not configured.")
        return
    try:
        current = sp.current_playback()
        if current and current.get("item"):
            name = current["item"]["name"]
            artist = current["item"]["artists"][0]["name"]
            album = current["item"]["album"]["name"]
            speak(f"Currently playing {name} by {artist}, from the album {album}.")
        else:
            speak("Nothing is currently playing on Spotify.")
    except Exception as e:
        logger.error("spotify_now_playing() error: %s", e)
        speak("I couldn't check what's playing.")


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL INTEGRATION (IMAP / SMTP)
# ─────────────────────────────────────────────────────────────────────────────
def read_emails(query: str) -> None:
    """Read the latest unread emails via IMAP."""
    from backend.config import (
        EMAIL_ADDRESS, EMAIL_PASSWORD, IMAP_SERVER, IMAP_PORT,
    )

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        speak("Email is not configured. Please add your email credentials to the dot env file.")
        return

    try:
        import imaplib
        import email
        from email.header import decode_header

        speak("Checking your inbox...")

        # Connect to IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        mail.select("inbox")

        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            speak("You have no unread emails.")
            mail.logout()
            return

        email_ids = messages[0].split()
        # Get the latest 5 unread emails
        latest_ids = email_ids[-5:] if len(email_ids) > 5 else email_ids

        speak(f"You have {len(email_ids)} unread email{'s' if len(email_ids) > 1 else ''}. Here are the latest:")

        for eid in reversed(latest_ids):
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1])

            # Decode subject
            subject_raw = msg["Subject"] or "(No Subject)"
            subject_parts = decode_header(subject_raw)
            subject = ""
            for part, charset in subject_parts:
                if isinstance(part, bytes):
                    subject += part.decode(charset or "utf-8", errors="replace")
                else:
                    subject += part

            # Decode sender
            from_raw = msg["From"] or "Unknown"
            from_parts = decode_header(from_raw)
            sender = ""
            for part, charset in from_parts:
                if isinstance(part, bytes):
                    sender += part.decode(charset or "utf-8", errors="replace")
                else:
                    sender += part

            # Trim sender to just the name if possible
            name_match = re.match(r'^"?([^"<]+)"?\s*<', sender)
            sender_name = name_match.group(1).strip() if name_match else sender

            speak(f"From {sender_name}: {subject}")

        mail.logout()

    except Exception as e:
        logger.error("read_emails() error: %s", e)
        speak("I had trouble reading your emails.")


def send_email(query: str) -> None:
    """Send an email via SMTP. Expects 'send email to <address> saying <message>'."""
    from backend.config import (
        EMAIL_ADDRESS, EMAIL_PASSWORD, SMTP_SERVER, SMTP_PORT,
    )

    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        speak("Email is not configured. Please add your email credentials to the dot env file.")
        return

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        # Parse recipient and message from query
        # Patterns: "send email to user@example.com saying ..."
        #           "email user@example.com that ..."
        match = re.search(
            r"(?:send\s+)?email\s+(?:to\s+)?(\S+@\S+\.\S+)\s+(?:saying|that|with message|message)\s+(.+)",
            query, re.IGNORECASE
        )
        if not match:
            speak("Please say something like: send email to user at example dot com saying hello.")
            return

        recipient = match.group(1).strip()
        body = match.group(2).strip()

        # Construct message
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = recipient
        msg["Subject"] = f"Message from Jarvis ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M')})"
        msg.attach(MIMEText(body, "plain"))

        speak(f"Sending email to {recipient}...")

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient, msg.as_string())

        speak(f"Email sent to {recipient} successfully.")

    except Exception as e:
        logger.error("send_email() error: %s", e)
        speak("I had trouble sending the email.")


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE CALENDAR INTEGRATION
# ─────────────────────────────────────────────────────────────────────────────
def _get_calendar_service():
    """Authenticate and return a Google Calendar API service object."""
    from backend.config import GOOGLE_CALENDAR_CREDENTIALS, GOOGLE_CALENDAR_TOKEN

    if not os.path.exists(GOOGLE_CALENDAR_CREDENTIALS):
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request as GAuthRequest
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/calendar.readonly",
                  "https://www.googleapis.com/auth/calendar.events"]

        creds = None
        if os.path.exists(GOOGLE_CALENDAR_TOKEN):
            creds = Credentials.from_authorized_user_file(GOOGLE_CALENDAR_TOKEN, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(GAuthRequest())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CALENDAR_CREDENTIALS, SCOPES
                )
                creds = flow.run_local_server(port=0)
            # Save token for next time
            with open(GOOGLE_CALENDAR_TOKEN, "w") as token_file:
                token_file.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    except Exception as e:
        logger.error("Google Calendar auth error: %s", e)
        return None


def read_calendar_events(query: str) -> None:
    """Read today's (or tomorrow's) events from Google Calendar."""
    service = _get_calendar_service()
    if service is None:
        speak("Google Calendar is not configured. Please add your credentials dot json file to the project folder.")
        return

    try:
        # Determine if user asks for tomorrow
        is_tomorrow = "tomorrow" in query.lower()
        target_date = datetime.datetime.now()
        if is_tomorrow:
            target_date += datetime.timedelta(days=1)

        day_label = "tomorrow" if is_tomorrow else "today"

        # Start and end of the target day (UTC)
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + datetime.timedelta(days=1)

        time_min = start_of_day.isoformat() + "Z"
        time_max = end_of_day.isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()

        events = events_result.get("items", [])

        if not events:
            speak(f"You have no events scheduled for {day_label}.")
            return

        speak(f"You have {len(events)} event{'s' if len(events) > 1 else ''} for {day_label}:")

        for event in events:
            summary = event.get("summary", "Untitled event")
            start = event["start"].get("dateTime", event["start"].get("date", ""))
            if "T" in start:
                # Parse time from ISO format
                event_time = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
                time_str = event_time.strftime("%I:%M %p")
                speak(f"At {time_str}: {summary}")
            else:
                speak(f"All day: {summary}")

    except Exception as e:
        logger.error("read_calendar_events() error: %s", e)
        speak("I had trouble reading your calendar.")


def add_calendar_event(query: str) -> None:
    """Add a quick event to Google Calendar. E.g. 'schedule meeting at 3pm'."""
    service = _get_calendar_service()
    if service is None:
        speak("Google Calendar is not configured.")
        return

    try:
        # Parse: "schedule <event> at <time>" or "add event <event> at <time>"
        match = re.search(
            r"(?:schedule|add event|create event|calendar event)\s+(.+?)\s+(?:at|for)\s+(\d{1,2})(?:[:.:](\d{2}))?\s*(am|pm)?",
            query, re.IGNORECASE
        )
        if not match:
            speak("Please say something like: schedule team meeting at 3 PM.")
            return

        event_title = match.group(1).strip()
        hour = int(match.group(2))
        minute = int(match.group(3)) if match.group(3) else 0
        period = match.group(4)

        if period:
            if period.lower() == "pm" and hour < 12:
                hour += 12
            elif period.lower() == "am" and hour == 12:
                hour = 0

        # Create event for today
        now = datetime.datetime.now()
        start_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if start_dt < now:
            start_dt += datetime.timedelta(days=1)  # Schedule for tomorrow if time passed
        end_dt = start_dt + datetime.timedelta(hours=1)  # Default 1-hour duration

        event = {
            "summary": event_title,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "Asia/Kolkata",
            },
        }

        service.events().insert(calendarId="primary", body=event).execute()
        speak(f"Done! I've added '{event_title}' to your calendar at {start_dt.strftime('%I:%M %p')}.")

    except Exception as e:
        logger.error("add_calendar_event() error: %s", e)
        speak("I had trouble adding the event to your calendar.")


# ─────────────────────────────────────────────────────────────────────────────
# SECURE SANDBOX CODE EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
def run_sandboxed_code(query: str) -> None:
    """
    Execute generated Python scripts in a restricted subprocess sandbox.
    - Isolated working directory
    - Timeout guard (configurable via SANDBOX_TIMEOUT)
    - stdout / stderr capture and readback
    """
    from backend.config import SANDBOX_DIR, SANDBOX_TIMEOUT, BASE_DIR

    try:
        # Look for the latest generated code file
        generated_dir = os.path.join(BASE_DIR, "generated_codes")
        if not os.path.isdir(generated_dir):
            speak("There are no generated code files to run.")
            return

        # Find the most recent .py file
        py_files = [
            f for f in os.listdir(generated_dir)
            if f.endswith(".py")
        ]
        if not py_files:
            speak("I couldn't find any Python files in the generated codes folder.")
            return

        # If user specifies a filename, try to match it
        target_file = None
        for fname in py_files:
            if fname.lower().replace("_", " ").replace(".py", "") in query.lower():
                target_file = fname
                break

        if target_file is None:
            # Default to the most recently modified file
            py_files.sort(
                key=lambda f: os.path.getmtime(os.path.join(generated_dir, f)),
                reverse=True,
            )
            target_file = py_files[0]

        source_path = os.path.join(generated_dir, target_file)

        # Create sandbox directory
        os.makedirs(SANDBOX_DIR, exist_ok=True)
        sandbox_run_dir = os.path.join(
            SANDBOX_DIR,
            f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        os.makedirs(sandbox_run_dir, exist_ok=True)

        # Copy the script to sandbox
        import shutil
        sandbox_script = os.path.join(sandbox_run_dir, target_file)
        shutil.copy2(source_path, sandbox_script)

        speak(f"Running {target_file} in sandbox with a {SANDBOX_TIMEOUT} second timeout...")

        # Execute in subprocess with timeout and restricted environment
        result = subprocess.run(
            [
                "python", "-u",
                "-c",
                # Wrapper that restricts dangerous builtins
                (
                    "import sys, os; "
                    "os.chdir(sys.argv[1]); "
                    "exec(open(sys.argv[2], encoding='utf-8').read(), "
                    "{'__builtins__': {k: v for k, v in __builtins__.__dict__.items() "
                    "if k not in ('eval', 'exec', 'compile', '__import__', 'open')}, "
                    "'print': print, 'range': range, 'len': len, 'int': int, "
                    "'float': float, 'str': str, 'list': list, 'dict': dict, "
                    "'tuple': tuple, 'set': set, 'bool': bool, 'input': input, "
                    "'enumerate': enumerate, 'zip': zip, 'map': map, 'filter': filter, "
                    "'sum': sum, 'min': min, 'max': max, 'abs': abs, 'round': round, "
                    "'sorted': sorted, 'reversed': reversed, 'type': type, "
                    "'isinstance': isinstance, 'hasattr': hasattr, 'getattr': getattr})"
                ),
                sandbox_run_dir,
                sandbox_script,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=SANDBOX_TIMEOUT,
            cwd=sandbox_run_dir,
        )

        # Save output to log file
        log_path = os.path.join(sandbox_run_dir, "output.log")
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}\n")
            log_file.write(f"\nReturn code: {result.returncode}\n")

    except subprocess.TimeoutExpired:
        speak(f"The script exceeded the {SANDBOX_TIMEOUT} second time limit and was terminated.")
    except Exception as e:
        logger.error("run_sandboxed_code() error: %s", e)
        speak("I had trouble running the code in the sandbox.")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Data Pipeline & AutoML Voice Commands
# ─────────────────────────────────────────────────────────────────────────────

def _find_csv_or_json_file(filename_query: str = "") -> str | None:
    """Helper to locate a CSV or JSON file in the root directory."""
    from backend.config import BASE_DIR
    # 1. Search for matching files in query
    root_files = os.listdir(BASE_DIR)
    
    if filename_query:
        # Extract filename from query using simple regex
        match = re.search(r"(\w+\.(?:csv|json))", filename_query, re.IGNORECASE)
        if match:
            fn = match.group(1)
            full_path = os.path.join(BASE_DIR, fn)
            if os.path.exists(full_path):
                return full_path
                
        # Try substring match
        clean_q = filename_query.lower()
        for f in root_files:
            if f.endswith(('.csv', '.json')):
                # E.g. "cricket" in "cricket stats"
                name_without_ext = os.path.splitext(f.lower())[0]
                if name_without_ext in clean_q or f.lower() in clean_q:
                    return os.path.join(BASE_DIR, f)

    # 2. Check default names
    for default_name in ["bowling_stats.csv", "cricket_stats.csv", "cricket_data.csv"]:
        full_path = os.path.join(BASE_DIR, default_name)
        if os.path.exists(full_path):
            return full_path

    # 3. Fallback: return first CSV/JSON found in root
    for f in root_files:
        if f.endswith(('.csv', '.json')) and not f.startswith('.'):
            return os.path.join(BASE_DIR, f)
            
    return None


def analyze_dataset_voice(query: str) -> None:
    """Voice command to analyze a CSV or JSON dataset and report statistics."""
    try:
        from backend.data_pipeline import load_and_clean_data, get_summary_statistics
        
        filepath = _find_csv_or_json_file(query)
        if not filepath:
            speak("I couldn't find any CSV or JSON data files to analyze in the directory. Please make sure your stats file is in the project root.")
            return
            
        filename = os.path.basename(filepath)
        speak(f"Ingesting and analyzing {filename}...")
        
        data = load_and_clean_data(filepath)
        if not data:
            speak(f"The file {filename} appears to be empty.")
            return
            
        stats = get_summary_statistics(data)
        rows_count = len(data)
        cols_count = len(stats)
        
        speak(f"Analysis complete. {filename} contains {rows_count} records and {cols_count} attributes.")
        
        # Build UI and spoken summary
        spoken_parts = []
        ui_lines = [f"📊 DATASET SUMMARY: {filename}", f"Total Records: {rows_count}", f"Total Columns: {cols_count}", ""]
        
        # Read/report on up to 4 columns to keep it concise
        reported_cols = 0
        for col, info in stats.items():
            if info["type"] == "numeric":
                ui_lines.append(f"• {col} (Numeric): Mean={info['mean']}, Median={info['median']}, Range={info['min']} to {info['max']}")
                if reported_cols < 3:
                    spoken_parts.append(f"Column {col} has an average of {info['mean']} and range from {info['min']} to {info['max']}.")
                    reported_cols += 1
            else:
                ui_lines.append(f"• {col} (Categorical): {info['unique']} unique values, Top='{info['top']}' (Freq={info['freq']})")
                if reported_cols < 3:
                    spoken_parts.append(f"Column {col} is categorical with {info['unique']} values, the most frequent being {info['top']}.")
                    reported_cols += 1
                    
        ui_text = "\n".join(ui_lines)
        try:
            eel.DisplayMessage(ui_text)
        except Exception:
            pass
            
        if spoken_parts:
            speak(" ".join(spoken_parts))
        else:
            speak("Analysis finished successfully.")
            
    except Exception as e:
        logger.error("analyze_dataset_voice() error: %s", e)
        speak("I ran into an error trying to clean and analyze the dataset.")


def train_automl_model_voice(query: str) -> None:
    """Voice command to train an AutoML Decision Tree model."""
    try:
        from backend.automl import train_and_save_model
        
        # 1. Parse model name
        # "train model bowling_predictor"
        model_match = re.search(r"model\s+(\w+)", query, re.IGNORECASE)
        model_name = model_match.group(1).strip() if model_match else "cricket_model"
        
        # 2. Parse filepath
        filepath = _find_csv_or_json_file(query)
        if not filepath:
            speak("I couldn't locate the data file for training. Please check that the file is in the root directory.")
            return
            
        # Load columns to find/default target_col
        from backend.data_pipeline import load_and_clean_data
        data = load_and_clean_data(filepath)
        if not data:
            speak("The dataset is empty. I cannot train a model on empty data.")
            return
            
        columns = list(data[0].keys())
        
        # 3. Parse target column
        # "targeting success_rate"
        target_match = re.search(r"(?:targeting|target)\s+(\w+)", query, re.IGNORECASE)
        target_col = target_match.group(1).strip() if target_match else None
        
        if not target_col or target_col not in columns:
            # Fallback targets
            fallback_options = ["success", "outcome", "label", "target", "class", "result"]
            for opt in fallback_options:
                if opt in columns:
                    target_col = opt
                    break
            if not target_col:
                # Default to the last column
                target_col = columns[-1]
                
        speak(f"Training decision tree model {model_name} on {os.path.basename(filepath)} targeting {target_col}...")
        
        result = train_and_save_model(filepath, model_name, target_col)
        
        if not result["success"]:
            speak(f"Training failed. {result.get('error', 'Unknown error')}")
            return
            
        task_type = result["task_type"]
        metrics = result["metrics"]
        features = result["features"]
        
        try:
            metrics_summary = ", ".join(f"{k}: {v}" for k, v in metrics.items())
            eel.DisplayMessage(f"🤖 AutoML Model Trained: {model_name}\nTask: {task_type.capitalize()}\nTarget: {target_col}\nFeatures: {', '.join(features)}\nMetrics: {metrics_summary}")
        except Exception:
            pass
            
        if task_type == "classification":
            speak(f"Success! Model {model_name} trained successfully. Test accuracy is {int(metrics['accuracy'] * 100)} percent.")
        else:
            speak(f"Success! Model {model_name} trained successfully. Test R-squared score is {metrics['r2']}.")
            
    except Exception as e:
        logger.error("train_automl_model_voice() error: %s", e)
        speak("I encountered an error while training the machine learning model.")


def predict_automl_model_voice(query: str) -> None:
    """Voice command to perform model predictions."""
    try:
        from backend.automl import predict_with_model, list_trained_models
        
        # 1. Resolve model name
        model_match = re.search(r"model\s+(\w+)", query, re.IGNORECASE)
        model_name = model_match.group(1).strip() if model_match else None
        
        if not model_name:
            # Fallback to the latest trained model
            models = list_trained_models()
            if not models:
                speak("No trained models are registered. Please train a model first using: train model name on dataset.")
                return
            model_name = models[0]["name"]
            
        # Load model structure to extract expected features
        from backend.config import AUTOML_MODELS_DIR
        import pickle
        try:
            import joblib
            _ser = joblib
        except ImportError:
            _ser = pickle
            
        model_filepath = os.path.join(AUTOML_MODELS_DIR, f"{model_name}.pkl")
        if not os.path.exists(model_filepath):
            speak(f"I couldn't find the model file for {model_name}.")
            return
            
        with open(model_filepath, 'rb') as f:
            model_data = _ser.load(f)
            
        expected_features = model_data["features"]
        
        # 2. Extract values for expected features from user query
        # We look for "[feature] [number]" or similar in the spoken query
        features_dict = {}
        
        for feat in expected_features:
            # Normalize feature name search (ignore underscores/spaces)
            feat_norm = feat.lower().replace("_", "")
            
            # Regex: feature name followed by optional separator (is/at/of/:) and a number or word
            # E.g. "speed 75", "spin is 1500"
            pattern = rf"\b{re.escape(feat_norm)}\b\s*(?:is|at|of|value|:)?\s*(-?\d+(?:\.\d+)?|\w+)"
            # Check query
            clean_query = query.lower().replace("_", "")
            match = re.search(pattern, clean_query)
            if match:
                val = match.group(1)
                # Check if it's numeric
                try:
                    if '.' in val:
                        features_dict[feat] = float(val)
                    else:
                        features_dict[feat] = int(val)
                except ValueError:
                    features_dict[feat] = val
            else:
                # Prompt/fallback if missing, default to 0.0 or prompt
                pass
                
        # Prompt for missing features if the dictionary is completely empty
        if not features_dict:
            speak(f"To make a prediction using {model_name}, please tell me the values for its features: {', '.join(expected_features)}.")
            return
            
        speak(f"Predicting outcome using model {model_name}...")
        
        result = predict_with_model(model_name, features_dict)
        if not result["success"]:
            speak(f"Prediction failed. {result.get('error')}")
            return
            
        prediction = result["prediction"]
        task_type = result["task_type"]
        probability = result.get("probability")
        
        try:
            eel.DisplayMessage(f"🎯 Prediction Output [{model_name}]\nInput Features: {features_dict}\nPredicted Result: {prediction}" + (f"\nProbability: {probability}" if probability else ""))
        except Exception:
            pass
            
        if task_type == "classification" and probability:
            speak(f"The predicted output is {prediction}, with a confidence of {int(probability * 100)} percent.")
        else:
            speak(f"The predicted outcome is {prediction}.")
            
    except Exception as e:
        logger.error("predict_automl_model_voice() error: %s", e)
        speak("I had trouble executing the model prediction.")