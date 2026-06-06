<div align="center">

# 🤖 JARVIS — AI Desktop Assistant

**A voice-controlled, AI-powered desktop assistant with biometric face authentication, persistent memory, offline Whisper speech recognition, and a sleek web-based monitoring dashboard.**

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

### 🗣️ Voice Interaction & Offline Speech
- **Hotword detection** — continuously listens for "Jarvis" or "Alexa" in the background.
- **Local STT (Whisper)** — Uses **OpenAI Whisper** for high-accuracy local, offline speech-to-text.
- **Online STT (Fallback)** — Gracefully falls back to the online Google Speech Recognition API if Whisper is not installed or enabled.
- **Text-to-speech** — Powered primarily by **Edge-TTS** (Microsoft Edge Neural Voices) for natural, high-quality, cloud-based voice response.
- **Offline TTS Fallback** — Automatically falls back to the local Windows **SAPI5 engine** (`pyttsx3`) if offline.
- Text input also supported directly through the web dashboard.

### 🧠 Persistent Memory System
- **SQLite Memory Store**: Securely stores structured conversation histories, user preferences, and learned facts.
- **Automatic Fact Extraction**: Extracts user facts and preferences from conversation context using Gemini.
- **ChromaDB Semantic Search (Optional)**: Performs high-performance vector search over memories (falls back to keyword-based search if ChromaDB is not installed).

### 🎵 Advanced Integrations
- **Spotify Music Control**: Play specific tracks, pause, resume, skip, or get the currently playing song via the Spotify Web API.
- **Email Client**: Check/read your latest Gmail/IMAP inbox messages and send emails via SMTP (supports Gmail App Passwords).
- **Google Calendar**: View daily schedules, upcoming calendar events, and dynamically create new events using the Google Calendar API.
- **Secure Sandbox Execution**: Run generated python scripts in an isolated subprocess sandbox with configurable timeouts.

### 📊 Performance & API Monitoring
- **Log Tracking**: Records all API call latencies, model parameters, token counts, and error details in the local SQLite database.
- **Analytics Dashboard**: Sleek monitoring interface (`frontend/monitor.html`) displaying daily statistics, hourly activity histograms, service breakdown, and recent errors.

### 🤖 AutoML & Data Pipeline
- **Data Ingestion**: Standardizes CSV/JSON data and automatically imputes missing values.
- **Auto Task Detection**: Analyzes target column values to automatically detect whether a task is classification or regression.
- **Lightweight scikit-learn training**: Trains and evaluates optimized Decision Trees with a single command.
- **Interactive Prediction**: Make predictions using trained models directly through voice commands.

### 🧠 AI Chatbot (Google Gemini)
- Falls back to **Gemini 2.5 Flash** (free tier) or local **Ollama** when no built-in command matches.
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

---

## 📁 Project Structure

```
Jarvis-2025/
├── run.py                      # Entry point — multi-process launcher
├── main.py                     # Process 1: Eel web server + face auth flow
├── desktop.py                  # Standalone desktop client using PyWebView
├── requirements.txt            # Python dependencies
├── activate_terminal.bat       # Helper to open a shell with activated virtualenv
├── start.bat                   # Helper to activate virtualenv and launch Jarvis
├── TECH_STACK.md               # Technology integration overview
├── backend/
│   ├── __init__.py
│   ├── config.py               # All configuration constants & thresholds
│   ├── command.py              # Voice I/O engine + dispatcher
│   ├── feature.py              # Feature implementations (YouTube, weather, APIs, sandbox)
│   ├── helper.py               # Text processing utilities
│   ├── db.py                   # SQLite schema initialisation
│   ├── audio_engine.py         # OpenAI Whisper speech transcription engine
│   ├── automl.py               # Machine learning model training pipeline
│   ├── data_pipeline.py        # Dataset loading & cleaning module
│   ├── memory.py               # User preferences & memory context manager
│   ├── memory_search.py        # SQLite keyword + ChromaDB semantic memory search
│   ├── monitor.py              # Performance logs & error tracking recorder
│   ├── web_rag.py              # Real-time Web RAG using BeautifulSoup & Gemini
│   ├── cookie.json             # [gitignored] HuggingChat session cookies
│   └── auth/
│       ├── sample.py           # Webcam face dataset capture
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
│   ├── monitor.html            # Performance analytics dashboard GUI
│   └── assets/
│       ├── audio/              # Startup sound effects
│       ├── img/                # UI images & icons
│       └── vendore/            # Vendor scripts
├── smoke_test.py               # General pre-launch sanity checker
├── smoke_test_audio.py         # Whisper offline speech recognition verification test
├── smoke_test_automl.py        # AutoML data cleaning, training & prediction verification test
├── smoke_test_memory.py        # SQLite + ChromaDB memory & context extraction test
├── smoke_test_monitoring.py    # Performance & API log tracking verification test
├── .tts_cache/                 # [gitignored] Temporary neural voice audio cache
├── .models/                    # [gitignored] Saved AutoML model pkl files
├── .chromadb/                  # [gitignored] ChromaDB vector database files
├── generated_codes/            # [gitignored] AI-generated code output
└── jarvis.db                   # [gitignored] Local SQLite database
```

---

## 🛠️ Installation & Setup

### Prerequisites

| Requirement | Details |
|---|---|
| **OS** | Windows 10 / 11 (uses SAPI5 fallback and DirectShow camera) |
| **Python** | 3.10 - 3.13 recommended |
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

Create the SQLite tables for apps, websites, contacts, performance logs, AutoML models, and memories:

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

Edit [`backend/config.py`](backend/config.py) or set environment variables in `.env` to personalize your assistant:

```bash
copy .env.example .env
```

Open [`.env`](.env) and configure the services you want to use:

```env
# Google Gemini API (Required for chatbot features)
GEMINI_API_KEY=your_gemini_api_key

# Local LLM Fallback (Optional)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:1.5b

# Spotify Web API
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# Email Configuration
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password

# IMAP/SMTP details if not using standard Gmail
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
```

---

## ▶️ Running Jarvis

### Browser Mode (Default)

To run the application in your default web browser, execute:

```bash
python run.py
```
Or simply double-click the `start.bat` script.

### Standalone Desktop Mode

To run in a dedicated PyWebView desktop window:

```bash
python desktop.py
```

### Analytics Dashboard

To view the performance logs and API call statistics, open [`frontend/monitor.html`](frontend/monitor.html) directly in your browser or navigate to `http://localhost:8000/monitor.html` while Jarvis is running.

---

## 🎙️ Voice Commands

Once authenticated, click the **Mic** button or say the hotword to start listening:

| Category | Example Commands |
|---|---|
| **Memory** | *"what do you remember"*, *"remember that I love playing cricket"*, *"search my memory for cricket"*, *"forget everything"* |
| **AutoML & Data** | *"train model on dataset.csv target outcome"*, *"predict outcome with spin_rate=2000, speed=85"*, *"analyze dataset.csv"* |
| **Spotify** | *"play Shape of You on Spotify"*, *"pause spotify"*, *"resume music"*, *"next song"*, *"what is playing"* |
| **Emails** | *"check my email"*, *"read my latest emails"*, *"send email to John"* |
| **Google Calendar** | *"what are my events today"*, *"schedule a meeting tomorrow at 3pm"*, *"add event: cricket practice at 5pm"* |
| **Code & Sandbox**| *"run the code"*, *"execute python script"*, *"generate calculator code"* |
| **Open Apps/Sites** | *"Open YouTube"*, *"Open Calculator"*, *"Open GitHub"* |
| **YouTube** | *"Play Shape of You on YouTube"*, *"Play Believer"* |
| **Weather** | *"Weather in Tokyo"*, *"What's the weather in London"* |
| **Wikipedia** | *"Who is Albert Einstein"*, *"What is quantum physics"* |
| **WhatsApp** | *"Send a message to John"*, *"Call Alice"*, *"Video call Bob"* |
| **Volume** | *"Increase volume"*, *"Volume down"* |
| **Screenshot** | *"Take a screenshot"* |
| **Notes** | *"Make a note: buy groceries"*, *"Read my notes"* |
| **Time/Date** | *"What time is it"*, *"What's today's date"* |
| **Jokes** | *"Tell me a joke"* |
| **Close App** | *"Close notepad"*, *"Close chrome"* |
| **Web Search** | *"Search for quantum mechanics"*, *"Who is Nikola Tesla"* |
| **AI Chat** | Any unrecognised query is routed to Gemini (or Ollama fallback) |
| **Exit** | *"Stop"*, *"Shutdown"*, *"Exit"* |

---

## 🧪 Verification & Smoke Tests

Jarvis is equipped with a comprehensive smoke testing suite located in the project root. To verify that all components are working correctly, run the following scripts inside your virtual environment:

```bash
# 1. Verify basic configuration, imports, database, and libraries
python smoke_test.py

# 2. Test the SQLite memory store and preference retrieval
python smoke_test_memory.py

# 3. Test OpenAI Whisper STT model preloading and transcribing fallbacks
python smoke_test_audio.py

# 4. Test the performance tracking database logging and error reporting
python smoke_test_monitoring.py

# 5. Test AutoML data cleansing, classifier & regressor training, and predictions
python smoke_test_automl.py
```

---

## ⚙️ Configuration Reference

All settings are configured in [`backend/config.py`](backend/config.py):

| Setting | Default | Description |
|---|---|---|
| `USER_NAME` | `"Syed Farhatullah"` | Full name for face recognition label |
| `USER_CALL_NAME` | `"Farhath"` | Friendly name Jarvis uses when speaking |
| `EDGE_TTS_VOICE` | `"en-US-GuyNeural"` | Primary Edge-TTS neural voice |
| `WHISPER_ENABLED` | `True` | Master switch for local OpenAI Whisper STT |
| `WHISPER_MODEL` | `"base"` | Model size: tiny (~39MB), base (~74MB), small (~244MB) |
| `MEMORY_ENABLED` | `True` | Master switch for persistent conversation memory |
| `CHROMADB_ENABLED` | `True` | Vector index for memory semantic search |
| `MONITOR_ENABLED` | `True` | Master switch for latency and error logging |
| `AUTOML_ENABLED` | `True` | Master switch for automated machine learning model trainer |
| `FACE_CONFIDENCE_THRESHOLD` | `45` | LBPH distance threshold (lower = stricter matching) |
| `FACE_CONSECUTIVE_MATCHES` | `3` | Consecutive high-confidence frames needed to confirm identity |

---

## 📦 Dependencies

Major packages defined in [`requirements.txt`](requirements.txt):
- `eel`: Python ↔ JavaScript bridge for the web UI.
- `opencv-contrib-python`: Biometric face detection & LBPH recognition.
- `google-genai`: Google Gemini API client for AI chatbot & context parsing.
- `edge-tts`: Cloud-based Microsoft neural text-to-speech.
- `openai-whisper`: Offline local speech-to-text model.
- `scikit-learn`: Decision tree training & evaluation for AutoML.
- `spotipy`: Spotify Web API wrapper.
- `google-api-python-client` & `google-auth-oauthlib`: Google Calendar API.
- `pywebview`: Native app window rendering for desktop mode.
- `pyinstaller`: Packager for compiling script into standalone Windows `.exe`.
- `SpeechRecognition`, `pyaudio`, `pyautogui`, `pygame`, `pywhatkit`, `requests`, `wikipedia`, `beautifulsoup4`, `duckduckgo-search`, `pyjokes`.

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
