<div align="center">

# 🤖 JARVIS — AI Desktop Assistant

**A voice-controlled, AI-powered desktop assistant with biometric face authentication, persistent memory, offline/online speech recognition, and a sleek web-based dashboard.**

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Eel](https://img.shields.io/badge/UI-Eel%20Web%20GUI-4FC08D?style=for-the-badge)
![OpenCV](https://img.shields.io/badge/Face%20Auth-OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)
![Ollama](https://img.shields.io/badge/LLM-Local%20Ollama-orange?style=for-the-badge&logo=ollama&logoColor=white)

</div>

---

## ✨ Overview

Jarvis is a multi-process desktop assistant for Windows that bridges a Python backend with an HTML/CSS/JS frontend using **Eel**. It features voice recognition, biometric face login, and a modern browser-based UI, providing a seamless and highly interactive user experience.

The system runs via two concurrent processes:
1. **Main Application**: Drives the web server, face login, core commands, APIs, and machine learning models.
2. **Background Listener**: Continuously monitors audio for wake-words (**"Jarvis"** or **"Alexa"**).

---

## ⚡ Key Features

### 🔐 Biometric Face Authentication
- **LBPH (Local Binary Patterns Histograms)** face recognition via OpenCV.
- Advanced pre-processing (CLAHE, Bilateral filtering) for improved accuracy across lighting conditions.
- Multi-frame voting to ensure secure and accurate login.

### 🗣️ Voice Interaction & Offline Speech
- **Hotword Detection**: Listens in the background for wake-words.
- **Offline STT**: High-accuracy local speech-to-text using **OpenAI Whisper**.
- **Online STT Fallback**: Uses Google Speech Recognition API when offline models are unavailable.
- **Cloud TTS**: Natural voice responses via **Edge-TTS**.
- **Offline TTS Fallback**: Windows **SAPI5 engine** (`pyttsx3`) when offline.

### 🧠 Persistent Memory System
- **SQLite & ChromaDB**: Securely stores conversation history, user preferences, and learned facts for long-term recall.
- **Fact Extraction**: Automatically extracts and saves key user details using Gemini.

### 🎵 Advanced Integrations & Capabilities
- **Spotify**: Control music playback.
- **Email & Calendar**: Read emails, check events, and schedule meetings via Google APIs.
- **Code Execution**: Run Python scripts in a secure sandbox.
- **Live Web Search**: Uses DuckDuckGo to answer questions and provide real-time information.
- **AutoML Pipeline**: Automatically load, clean, and train machine learning models from CSV datasets via voice.

### 🤖 AI Chatbot Engine
- Powered by **Google Gemini** (cloud) and **Ollama** (local), supporting multilingual queries and intelligent fallback routing.

---

## 🛠️ Installation & Setup

### Prerequisites
- **OS**: Windows 10 / 11
- **Python**: 3.10 - 3.13
- **Hardware**: Webcam & Microphone required for full GUI mode.

### 1. Clone & Install
```bash
git clone https://github.com/Farhath246/Jarvis-2025.git
cd Jarvis-2025
python -m venv envJarvis
envJarvis\Scripts\activate
pip install -r requirements.txt
```

### 2. Database Initialization
```bash
python -m backend.db
```

### 3. Face Authentication Setup (For GUI)
1. Capture your face data:
   ```bash
   python -m backend.auth.sample
   ```
2. Train the model:
   ```bash
   python -m backend.auth.trainer
   ```

### 4. Configuration
Create a `.env` file from the example:
```bash
copy .env.example .env
```
Populate `.env` with your API keys (Gemini, Spotify, Email, etc.).

---

## ▶️ Running Jarvis

### Web GUI Mode (Default)
Runs in your default browser with full UI and biometric login.
```bash
python run.py
```
*(Or run `start.bat`)*

### Native Desktop Mode
Runs as a standalone PyWebView desktop application.
```bash
python desktop.py
```

### Headless CLI Mode
Optimized for low-end hardware. Bypasses the UI and runs directly in the terminal.
1. Set `CLI_MODE = True` in `backend/config.py`.
2. Run: `python main.py`

---

## 🧪 Smoke Tests

Ensure all components are working correctly using the provided test scripts:
```bash
python smoke_test.py
python smoke_test_memory.py
python smoke_test_audio.py
python smoke_test_monitoring.py
python smoke_test_automl.py
```

---

## 🤝 Contributing
Contributions, issues, and feature requests are welcome!

## 📄 License
This project is open-source. Please see the repository for licensing details.

<div align="center">
<b>Built with ❤️ using Python, OpenCV, Google Gemini, and Ollama</b>
</div>
