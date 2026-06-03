"""
main.py — Jarvis application entry point.
Initialises the eel web server and handles the startup / face-auth flow.
"""

import logging
import webbrowser
import eel

from backend.auth import recoganize
from backend.feature import play_assistant_sound
from backend.command import speak
from backend.config import USER_CALL_NAME

logger = logging.getLogger(__name__)


def run_face_auth():
    """
    Run the face authentication flow and update the UI accordingly.
    Returns True on success, False on failure.
    """
    try:
        flag = recoganize.AuthenticateFace()
    except Exception as e:
        logger.error("Face auth error: %s", e)
        flag = 0

    if flag == 1:
        speak("Face recognised successfully")
        try:
            eel.hideFaceAuth()
            eel.hideFaceAuthSuccess()
        except Exception as e:
            logger.warning("eel UI update error: %s", e)
        speak(f"Welcome, {USER_CALL_NAME}. How can I help you?")
        try:
            eel.hideStart()
        except Exception as e:
            logger.warning("eel.hideStart error: %s", e)
        play_assistant_sound()
        return True
    else:
        speak("Face not recognised. Please try again.")
        try:
            eel.showAuthFailed()
        except Exception as e:
            logger.warning("eel.showAuthFailed error: %s", e)
        return False


def start() -> None:
    """Start the Jarvis eel app and run the startup / face-auth flow."""
    eel.init("frontend")
    play_assistant_sound()

    @eel.expose
    def init():
        """Called by JavaScript when the page is ready."""
        logger.info("init() called from JS — starting face auth flow")
        try:
            eel.hideLoader()
        except Exception as e:
            logger.warning("eel.hideLoader error: %s", e)

        # Inject user name into the frontend
        try:
            eel.setUserName(USER_CALL_NAME)
        except Exception as e:
            logger.warning("eel.setUserName error: %s", e)

        speak(f"Welcome to Jarvis")
        speak("Ready for face authentication")
        run_face_auth()

    @eel.expose
    def retryFaceAuth():
        """Called by the Retry button in the UI."""
        logger.info("retryFaceAuth() called from JS")
        speak("Retrying face authentication")
        run_face_auth()

    # Open in default browser unless in desktop mode
    import os
    if os.environ.get("JARVIS_DESKTOP_MODE") != "1":
        webbrowser.open("http://127.0.0.1:8000/index.html")
    eel.start("index.html", mode=None, host="localhost", block=True)



if __name__ == "__main__":
    start()
