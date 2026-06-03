<div align="center">

# 🤖 JARVIS — AI Desktop Assistant

**A voice-controlled, AI-powered desktop assistant with biometric face authentication and a sleek web-based dashboard.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Eel](https://img.shields.io/badge/UI-Eel%20Web%20GUI-4FC08D?style=for-the-badge)
![OpenCV](https://img.shields.io/badge/Face%20Auth-OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)

</div>

---

## ✨ Overview

Jarvis is a multi-process desktop assistant for Windows that combines voice recognition, biometric face authentication, and a modern browser-based UI. It uses **Eel** to bridge a Python backend with an HTML/CSS/JS frontend, delivering a seamless voice-interactive experience.

The assistant runs two concurrent processes — the main application (web dashboard + face login + command dispatcher) and a background hotword listener — so it's always ready to respond when you say **"Jarvis"**.

---

## 🚀 Key Features

### 🔐 Biometric Face Authentication
- **LBPH (Local Binary Patterns Histograms)** face recogniser via OpenCV.
- **CLAHE** preprocessing for lighting-invariant detection.
- **Bilateral filtering** to reduce background noise while preserving facial edges.
- **Multi-frame voting** — requires consecutive high-confidence matches to confirm identity.
- Automatic blur detection during dataset capture for high-quality training samples.
- Configurable confidence threshold and frame count in `config.py`.

### 🗣️ Voice Interaction
- **Hotword detection** — continuously listens for "Jarvis" or "Alexa" using Google Speech Recognition.
- **Speech-to-text** via Google Speech Recognition API.
- **Text-to-speech** — Powered primarily by **Edge-TTS** (Microsoft Edge Neural Voices) for natural, high-quality, cloud-based voice response.
- **Offline Fallback** — Automatically falls back to the local Windows **SAPI5 engine** (`pyttsx3`) if offline.
- Text input also supported directly through the web dashboard.

### 🧠 AI Chatbot (Google Gemini)
- Falls back to **Gemini 2.5 Flash** (free tier) when no built-in command matches.
- Supports Hinglish and multilingual query detection.
- Configurable via API key in `.env` file.

### 🖥️ Standalone Desktop Mode
- Runs the entire assistant in a standalone desktop window using **PyWebView**.
- Supports packaging into a single executable (.exe) for convenient Windows distribution.
- Avoids opening the dashboard in a default web browser.

### 🌐 Real-Time Web Search
- Performs live web searching using the **DuckDuckGo Search** API.
- Automatically triggered by informational voice queries ("search for...", "who is...", "what is...").
- Returns key summary snippets directly to the text-to-speech engine.

### 🛠️ System & Web Automation
| Command Category | Capabilities |
|---|---|
| **App / Website Launcher** | Opens local apps and web URLs from a SQLite database, plus 18+ well-known sites as fallback |
| **YouTube Player** | Extracts search terms and plays videos via `pywhatkit` |
| **WhatsApp Integration** | Send messages, make voice calls, or start video calls via WhatsApp URI schemes + PyAutoGUI |
| **Weather** | Free weather via `wttr.in` (no API key needed) |
| **Wikipedia** | Search and read 2-sentence summaries; falls back to Google if nothing found |
| **Screenshot** | Captures and saves to Desktop with timestamp |
| **Volume Control** | System volume up / down |
| **Typing** | Dictates text directly into any focused application |
| **Notes** | Save and read back timestamped notes (`jarvis_notes.txt`) |
| **Jokes** | Random programming jokes via `pyjokes` |
| **Code Generation** | Uses Gemini to generate code files, saves to `generated_codes/`, and opens in VS Code |
| **Close App** | Terminates running applications by name via `taskkill` |
| **Date & Time** | Reads out the current date and time |

---

## 📁 Project Structure

```
Jarvis-2025/
├── run.py                      # Entry point — multi-process launcher
├── main.py                     # Process 1: Eel web server + face auth flow
├── requirements.txt            # Python dependencies
├── activate_terminal.bat       # Helper to open a shell with activated virtualenv
├── start.bat                   # Helper to activate virtualenv and launch Jarvis
├── backend/
│   ├── __init__.py
│   ├── config.py               # All configuration constants & thresholds
│   ├── command.py              # Voice I/O engine (Edge-TTS / pyttsx3 fallback) + dispatcher
│   ├── feature.py              # All feature implementations (YouTube, weather, etc.)
│   ├── helper.py               # Text processing utilities
│   ├── db.py                   # SQLite schema initialisation
│   ├── cookie.json             # [gitignored] HuggingChat session cookies
│   └── auth/
│       ├── sample.py           # Webcam face dataset capture (200 frames + augmentation)
│       ├── trainer.py          # LBPH model training script
│       ├── recoganize.py       # Real-time face authentication
│       ├── haarcascade_frontalface_default.xml  # OpenCV Haar cascade
│       ├── samples/            # [gitignored] Captured face images
│       └── trainer/            # [gitignored] Trained model (trainer.yml)
├── frontend/
│   ├── index.html              # Main dashboard HTML
│   ├── style.css               # Custom CSS with animations
│   ├── controller.js           # JavaScript ↔ Eel bridge
│   ├── main.js                 # Page initialisation logic
│   ├── script.js               # Canvas animations & visual effects
│   └── assets/
│       ├── audio/              # Startup sound effects
│       ├── img/                # UI images & icons
│       └── vendore/            # Vendor scripts
├── .tts_cache/                 # [gitignored] Temporary neural voice audio cache
├── generated_codes/            # [gitignored] AI-generated code output
└── jarvis.db                   # [gitignored] Local SQLite database
```

---

## 🛠️ Installation & Setup

### Prerequisites

| Requirement | Details |
|---|---|
| **OS** | Windows 10 / 11 (uses SAPI5 fallback and DirectShow camera) |
| **Python** | 3.10.x recommended |
| **Webcam** | Required for face authentication |
| **Microphone** | Required for voice commands & hotword detection |

### Step 1 — Clone & Install Dependencies

```bash
git clone https://github.com/Farhath246/Jarvis-2025.git
cd Jarvis-2025
python -m venv envJarvis
envJarvis\Scripts\activate
pip install -r requirements.txt
```

> [!NOTE]
> If `pyaudio` fails to install, use the pre-compiled wheel:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

### Step 2 — Initialise the Database

Create the SQLite tables for apps, websites, and contacts:

```bash
python -m backend.db
```

### Step 3 — Capture Face Samples

Sit in front of your webcam. The script captures 200 high-quality frames with horizontal flip augmentation:

```bash
python -m backend.auth.sample
```

### Step 4 — Train the Face Model

Analyse captured samples and generate the LBPH model:

```bash
python -m backend.auth.trainer
```

### Step 5 — Configure Your Settings

Edit [`backend/config.py`](backend/config.py) to personalise:

```python
USER_NAME      = "Your Full Name"     # Used as face recognition label
USER_CALL_NAME = "Your Nickname"      # How Jarvis addresses you
EDGE_TTS_VOICE = "en-US-GuyNeural"    # Primary Edge-TTS neural voice
EDGE_TTS_RATE  = "+0%"                # Speech rate modifier
```

### Step 6 — Set Up Gemini API Key (Optional)

To enable the AI chatbot and code generation features:

1. Copy the environment template:
   ```bash
   copy .env.example .env
   ```
2. Get a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey)
3. Open [`.env`](.env) and set your key:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```

> [!CAUTION]
> The `.env` file is gitignored. Never commit API keys to version control.

---

## ▶️ Running Jarvis

### Browser Mode (Default)

To run the application in your default web browser, execute:

```bash
python run.py
```
Or simply double-click the `start.bat` script.

This launches two concurrent processes:

| Process | Role |
|---|---|
| **Process 1 — JarvisApp** | Starts the Eel web server, opens the dashboard in your browser, runs face authentication, then enters the voice command loop |
| **Process 2 — HotwordDetector** | Continuously listens for the wake words "Jarvis" or "Alexa" in the background |

The web dashboard opens automatically at `http://127.0.0.1:8000/index.html`.

### 🖥️ Desktop Mode (Standalone Window)

To run the application in a standalone windowed desktop interface using `pywebview`:

```bash
python desktop.py
```

### 📦 Compiling into a Standalone Executable (.exe)

You can package Jarvis into a single, standalone Windows executable using PyInstaller:

```bash
pyinstaller desktop.spec
```

The compiled application will be generated in the `dist/` directory.

---

## 🎙️ Voice Commands

Once authenticated, click the **Mic** button or say the hotword to start listening:

| Category | Example Commands |
|---|---|
| **Open Apps/Sites** | *"Open YouTube"*, *"Open Calculator"*, *"Open GitHub"* |
| **YouTube** | *"Play Shape of You on YouTube"*, *"Play Believer"* |
| **Weather** | *"Weather in Tokyo"*, *"What's the weather in London"* |
| **Wikipedia** | *"Who is Albert Einstein"*, *"What is quantum physics"* |
| **WhatsApp** | *"Send a message to John"*, *"Call Alice"*, *"Video call Bob"* |
| **Volume** | *"Increase volume"*, *"Volume down"* |
| **Screenshot** | *"Take a screenshot"* |
| **Notes** | *"Make a note: buy groceries"*, *"Read my notes"* |
| **Time/Date** | *"What time is it"*, *"What's today's date"* |
| **Typing** | *"Type hello world"* |
| **Code Gen** | *"Write a Python script for sorting"*, *"Generate a calculator program"* |
| **Jokes** | *"Tell me a joke"* |
| **Close App** | *"Close notepad"*, *"Close chrome"* |
| **Web Search** | *"Search for quantum mechanics"*, *"Who is Nikola Tesla"*, *"What is photosynthesis"* |
| **AI Chat** | Any unrecognised query is routed to Gemini |
| **Exit** | *"Stop"*, *"Shutdown"*, *"Exit"* |

---

## ⚙️ Configuration Reference

All settings are in [`backend/config.py`](backend/config.py):

| Setting | Default | Description |
|---|---|---|
| `USER_NAME` | `"Syed Farhatullah"` | Full name for face recognition label |
| `USER_CALL_NAME` | `"Farhath"` | Friendly name Jarvis uses when speaking |
| `VOICE_INDEX` | `0` | SAPI5 fallback voice index (0 = male, 1 = female) |
| `SPEECH_RATE` | `174` | Fallback SAPI5 speech rate (words per minute) |
| `EDGE_TTS_VOICE` | `"en-US-GuyNeural"` | Primary Edge-TTS neural voice |
| `EDGE_TTS_RATE` | `"+0%"` | Edge-TTS speech speed adjustment |
| `FACE_CONFIDENCE_THRESHOLD` | `45` | LBPH distance threshold (lower = stricter matching) |
| `FACE_CONSECUTIVE_MATCHES` | `3` | Consecutive high-confidence frames needed to confirm identity |
| `FACE_AUTH_TIMEOUT` | `30` | Seconds before face auth gives up |
| `FACE_AUTH_MAX_ATTEMPTS` | `5` | Failed attempts before lockout |
| `GEMINI_API_KEY` | `""` | Google Gemini API key for chatbot & code generation |

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `eel` | Python ↔ JavaScript bridge for the web UI |
| `opencv-contrib-python` | Face detection & LBPH recognition |
| `pyttsx3` | Text-to-speech fallback (Windows SAPI5) |
| `edge-tts` | Primary high-quality neural voice text-to-speech |
| `python-dotenv` | Load environment variables from `.env` file |
| `SpeechRecognition` | Microphone input → text |
| `pyaudio` | Audio stream for speech recognition |
| `google-genai` | Google Gemini API for AI chatbot & code gen |
| `pyautogui` | Keyboard/mouse automation (volume, typing, WhatsApp) |
| `pywhatkit` | YouTube playback |
| `pygame` | Audio playback for startup and Edge-TTS playback |
| `requests` | HTTP requests (weather API) |
| `wikipedia` | Wikipedia search & summaries |
| `pyjokes` | Random jokes |
| `numpy` | Numerical operations for image processing |
| `Pillow` | Image handling |
| `pywebview` | Standalone app window for desktop mode |
| `duckduckgo-search` | Live search fallback engine |
| `pyinstaller` | Standalone Windows executable packaging |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m "Add amazing feature"`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is open source. See the repository for license details.

---

<div align="center">

**Built with ❤️ using Python, OpenCV, and Google Gemini**

</div>
