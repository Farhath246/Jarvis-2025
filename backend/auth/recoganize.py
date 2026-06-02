"""
recoganize.py — Real-time face recognition using OpenCV LBPH.
Authenticates the user and returns 1 on success, 0 on failure.

Improvements over the original:
- CLAHE preprocessing → lighting-invariant recognition
- Bilateral filter for noise reduction before face detection
- Multi-frame voting (N consecutive matches required) → prevents false positives
- Configurable confidence threshold from config
- Debounced failure counting → only increments after a full frame with no match
- Standardised face crop size matching training pipeline
"""

import logging
import time
import cv2
import base64
import numpy as np
import eel

from backend.config import (
    USER_CALL_NAME, USER_NAME,
    FACE_TRAINER_PATH, FACE_CASCADE_PATH,
    FACE_AUTH_TIMEOUT, FACE_AUTH_MAX_ATTEMPTS,
    FACE_CONFIDENCE_THRESHOLD, FACE_CONSECUTIVE_MATCHES,
    FACE_SAMPLE_SIZE
)

logger = logging.getLogger(__name__)

# CLAHE instance — reused across frames for efficiency
_clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def _preprocess_face(grey_crop: np.ndarray) -> np.ndarray:
    """Apply CLAHE histogram equalization and resize to the standard training size."""
    equalised = _clahe.apply(grey_crop)
    resized = cv2.resize(equalised, FACE_SAMPLE_SIZE, interpolation=cv2.INTER_AREA)
    return resized


def AuthenticateFace() -> int:
    """
    Capture webcam frames and attempt to recognise the authorised face.

    Uses multi-frame voting: the user must be recognised in N consecutive
    frames before authentication succeeds, preventing single-frame false
    positives.

    Returns:
        1  — face recognised successfully
        0  — face not recognised (timeout or max attempts exceeded)
    """
    # Tuned LBPH hyperparameters must match training
    recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=1,
        neighbors=8,
        grid_x=8,
        grid_y=8
    )

    try:
        recognizer.read(FACE_TRAINER_PATH)
    except cv2.error as e:
        logger.error("Could not load trainer model: %s", e)
        logger.error("Please run backend/auth/trainer.py first.")
        return 0

    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)

    # Recognised names — index matches face ID used during training
    names = ["", USER_CALL_NAME]   # ID 1 → USER_CALL_NAME

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cam.isOpened():
        logger.error("Could not open webcam. Check that a camera is connected.")
        return 0
    cam.set(3, 640)
    cam.set(4, 480)

    min_w = int(0.1 * cam.get(3))
    min_h = int(0.1 * cam.get(4))

    auth_result = 0
    failed_attempts = 0
    consecutive_matches = 0     # multi-frame voting counter
    start_time = time.time()

    logger.info(
        "Face auth started. Timeout: %ds, Max attempts: %d, Consecutive needed: %d, Confidence threshold: %d",
        FACE_AUTH_TIMEOUT, FACE_AUTH_MAX_ATTEMPTS,
        FACE_CONSECUTIVE_MATCHES, FACE_CONFIDENCE_THRESHOLD
    )

    while True:
        # ── Timeout check ─────────────────────────────────────────────────
        elapsed = time.time() - start_time
        if elapsed > FACE_AUTH_TIMEOUT:
            logger.warning("Face auth timed out after %.1fs", elapsed)
            break

        # ── Max attempts check ────────────────────────────────────────────
        if failed_attempts >= FACE_AUTH_MAX_ATTEMPTS:
            logger.warning("Max failed attempts (%d) reached.", FACE_AUTH_MAX_ATTEMPTS)
            break

        ret, img = cam.read()
        if not ret:
            logger.error("Could not read frame from webcam.")
            break

        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Bilateral filter — reduces noise while keeping edges sharp
        grey_filtered = cv2.bilateralFilter(grey, d=9, sigmaColor=75, sigmaSpace=75)

        faces = face_cascade.detectMultiScale(
            grey_filtered,
            scaleFactor=1.2,
            minNeighbors=5,
            minSize=(min_w, min_h)
        )

        time_left = max(0, int(FACE_AUTH_TIMEOUT - elapsed))
        best_confidence = 0
        frame_has_match = False

        for (x, y, w, h) in faces:
            # Draw rectangle on the raw frame
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Preprocess the face ROI identically to training pipeline
            face_roi = grey[y:y + h, x:x + w]
            processed_face = _preprocess_face(face_roi)

            face_id, distance = recognizer.predict(processed_face)
            confidence_pct = round(100 - distance)

            if distance < FACE_CONFIDENCE_THRESHOLD:
                frame_has_match = True
                best_confidence = max(best_confidence, confidence_pct)

        # ── Multi-frame voting ────────────────────────────────────────────
        if frame_has_match:
            consecutive_matches += 1
            if consecutive_matches >= FACE_CONSECUTIVE_MATCHES:
                auth_result = 1
        else:
            # Reset voting streak on a miss
            if consecutive_matches > 0:
                consecutive_matches = 0

            # Only count a failed attempt if faces were detected but none matched
            # (no face in frame ≠ a failed recognition attempt)
            if len(faces) > 0:
                failed_attempts += 1

        # ── Send frame to browser ─────────────────────────────────────────
        _, buffer = cv2.imencode('.jpg', img)
        jpg_as_text = base64.b64encode(buffer).decode('utf-8')

        try:
            eel.updateFacePreview(jpg_as_text)()
            eel.updateFaceStatus(time_left, failed_attempts, FACE_AUTH_MAX_ATTEMPTS)()

            if auth_result == 1:
                eel.showFaceDetected(best_confidence)()
            elif len(faces) > 0:
                eel.showFaceNotDetected()()
        except Exception as e:
            logger.warning("eel update preview error: %s", e)

        # ── Exit on success ───────────────────────────────────────────────
        if auth_result == 1:
            logger.info("Face authenticated successfully: %s (confidence %d%%, %d consecutive matches)",
                        USER_NAME, best_confidence, consecutive_matches)
            try:
                eel.playSuccessBeep()()
            except Exception:
                pass
            eel.sleep(0.5)   # brief pause so user sees the success frame
            break

        # Yield to allow eel to process network and keep framerate ~15-20fps
        eel.sleep(0.05)

    cam.release()
    return auth_result