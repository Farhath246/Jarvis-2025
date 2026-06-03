import os
import sys
import threading
import multiprocessing
import logging
import webview

# Configure logging for the desktop entry point
logging.basicConfig(level=logging.INFO, format="[DESKTOP] %(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def resolve_path(relative_path):
    """
    Resolve absolute path for PyInstaller bundled assets.
    When compiled, PyInstaller unpacks data files to a temporary folder sys._MEIPASS.
    """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)

if __name__ == '__main__':
    # Required for PyInstaller / frozen executables on Windows
    multiprocessing.freeze_support()

    # Set desktop mode environment variable so main.py doesn't spawn standard browser
    os.environ["JARVIS_DESKTOP_MODE"] = "1"

    # Import backend main here after setting environment variables and freeze support
    from run import main

    logger.info("Starting backend main in a background daemon thread...")
    backend_thread = threading.Thread(target=main, daemon=True)
    backend_thread.start()

    logger.info("Launching PyWebView window pointing to http://localhost:8000...")
    # Create webview window
    webview.create_window(
        title="Jarvis Assistant",
        url="http://localhost:8000",
        width=1000,
        height=700,
        resizable=True
    )
    # Start webview. This blocks until the GUI window is closed.
    webview.start()

    logger.info("WebView window closed. Shutting down child processes...")
    # Clean up any active child processes (e.g., JarvisApp and HotwordDetector processes)
    for child in multiprocessing.active_children():
        logger.info("Terminating child process: %s", child.name)
        child.terminate()
        child.join(timeout=3)
        if child.is_alive():
            logger.warning("Force-killing child process: %s", child.name)
            child.kill()
            child.join()

    logger.info("Shutdown complete.")
    sys.exit(0)
