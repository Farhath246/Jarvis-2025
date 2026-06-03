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
        search_query = re.sub(r"\b(wikipedia|who is|what is|information about|info about)\b", "", query, flags=re.IGNORECASE).strip()
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
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=1))
            if results:
                return results[0].get("body", "No content found.")
            return "No search results found."
    except Exception as e:
        logger.error("web_search() error: %s", e)
        return "Sorry, I couldn't perform the web search right now."


def chatBot(query: str) -> str:
    """
    Smart search assistant using a Web-RAG pipeline:
    1. Intent Detection & Query Reformulation  (Gemini)
    2. Google Search + Deep Web Scraping       (requests + BeautifulSoup)
    3. LLM Context Synthesis with citations    (Gemini)
    Falls back to direct Gemini generation for non-search queries.
    """
    try:
        from backend.web_rag import run_rag_pipeline

        # Live status callback — updates the HUD + siri-text in the UI
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

        # ── Run the RAG pipeline ──────────────────────────────────────────
        logger.info("Running Web-RAG pipeline for query: %s", query)
        rag_answer, rag_sources = run_rag_pipeline(query, status_callback=_rag_status)

        if rag_answer is not None:
            logger.info("RAG pipeline succeeded with %d sources.", len(rag_sources or []))
            speak(rag_answer, rag_sources)
            return rag_answer

        # ── Fallback: Direct Gemini (no search needed) ────────────────────
        logger.info("No search required. Using direct Gemini generation...")
        from google import genai

        if not GEMINI_API_KEY:
            speak("The chatbot is not configured yet. Please add your Gemini API key to config dot py.")
            return ""

        client = genai.Client(api_key=GEMINI_API_KEY)
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_instruction = (
            "You are Jarvis, an AI desktop assistant. "
            f"The current date and time is {current_time}. "
            "Detect the language of the user's input. "
            "If the user talks in Hinglish (Hindi written in Latin/Roman script), reply in Hinglish. "
            "If the user talks in Urdu (either in Urdu script or Romanized Urdu), do NOT reply in Urdu script; "
            "instead, understand their Urdu/English query and reply in English. "
            "Otherwise, respond in the language of the query or English. Keep your responses short and concise."
        )

        try:
            eel.DisplayMessage("💡 Thinking...")
        except Exception:
            pass

        response = None
        models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]

        for idx, model_name in enumerate(models_to_try):
            try:
                logger.info("Direct Gemini — trying model: %s", model_name)
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        {"role": "user", "parts": [{"text": f"System: {system_instruction}\n\n{query}"}]}
                    ],
                )
                break
            except Exception as api_err:
                logger.warning("Model %s failed: %s", model_name, api_err)
                if idx < len(models_to_try) - 1:
                    continue
                else:
                    raise api_err

        if not response or not response.text:
            raise Exception("No response received from Gemini API.")

        result = response.text.strip()
        logger.info("Direct Gemini response: %s", result)
        speak(result)
        return result

    except Exception as e:
        logger.error("chatBot() error: %s", e)
        err_msg = str(e).lower()
        if "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
            speak("I have exceeded the Gemini API free tier rate limit. Please try again in a minute.")
        else:
            speak("I had trouble connecting to the chatbot.")
        return ""


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