"""
run.py — Multi-process launcher for Jarvis.
Process 1: Main Jarvis app (eel web server + face auth)
Process 2: Background hotword detection (listens for "jarvis" / "alexa")
"""

import logging
import multiprocessing
import signal
import sys

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def startJarvis():
    """Launch the main Jarvis eel application."""
    logger.info("Process 1 — Jarvis App starting...")
    from main import start
    start()


def listenHotword():
    """Run continuous background hotword detection."""
    logger.info("Process 2 — Hotword detection starting...")
    from backend.feature import hotword
    hotword()


if __name__ == "__main__":
    # Required for PyInstaller / frozen executables on Windows
    multiprocessing.freeze_support()

    process1 = multiprocessing.Process(target=startJarvis,   name="JarvisApp")
    process2 = multiprocessing.Process(target=listenHotword, name="HotwordDetector")

    def shutdown(signum=None, frame=None):
        """Gracefully terminate both processes."""
        logger.info("Shutdown requested. Terminating processes...")
        for proc in [process1, process2]:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    logger.warning("Force-killing %s (didn't stop in 5s)", proc.name)
                    proc.kill()
                    proc.join()
                logger.info("Process %s terminated.", proc.name)
        logger.info("Jarvis has shut down.")
        sys.exit(0)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        process1.start()
        process2.start()
        process1.join()  # Wait for main app to finish

    except KeyboardInterrupt:
        shutdown()

    finally:
        # Clean up hotword process if main app exits
        if process2.is_alive():
            process2.terminate()
            process2.join(timeout=5)
            logger.info("Process 2 (HotwordDetector) terminated.")
        logger.info("Jarvis has shut down.")