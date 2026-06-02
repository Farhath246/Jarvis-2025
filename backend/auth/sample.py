"""
sample.py — Capture face samples from the webcam for training.
Run this before trainer.py to collect your face images.

Improvements over the original:
- CLAHE histogram equalization → lighting-invariant samples
- Resize all crops to a standard size → consistent training input
- Data augmentation via horizontal flip → effectively doubles samples
- Blurry frame rejection → higher-quality training data
"""

import logging
import os
import cv2
import numpy as np

from backend.config import FACE_SAMPLES_DIR, FACE_CASCADE_PATH, USER_CALL_NAME, FACE_SAMPLE_SIZE

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TOTAL_SAMPLES = 200
BLUR_THRESHOLD = 50.0   # Laplacian variance below this → frame too blurry


def _is_blurry(image: np.ndarray, threshold: float = BLUR_THRESHOLD) -> bool:
    """Return True if the image is too blurry for a quality sample."""
    return cv2.Laplacian(image, cv2.CV_64F).var() < threshold


def _preprocess_face(grey_crop: np.ndarray) -> np.ndarray:
    """Apply CLAHE histogram equalization and resize to the standard size."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalised = clahe.apply(grey_crop)
    resized = cv2.resize(equalised, FACE_SAMPLE_SIZE, interpolation=cv2.INTER_AREA)
    return resized


def capture_samples(face_id: int = 1) -> None:
    """
    Capture face samples from the webcam and save them for training.

    Args:
        face_id: Numeric ID to associate with this person's face (default 1).
    """
    os.makedirs(FACE_SAMPLES_DIR, exist_ok=True)

    cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cam.set(3, 640)
    cam.set(4, 480)

    detector = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    count = 0
    saved = 0
    skipped_blur = 0
    font = cv2.FONT_HERSHEY_SIMPLEX

    logger.info("Capturing samples for face ID %d (%s). Look at the camera…", face_id, USER_CALL_NAME)
    logger.info("Press ESC to stop early.")

    while True:
        ret, img = cam.read()
        if not ret:
            logger.error("Webcam read failed.")
            break

        grey = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(grey, scaleFactor=1.3, minNeighbors=5)

        for (x, y, w, h) in faces:
            face_crop = grey[y:y + h, x:x + w]

            # Skip blurry crops
            if _is_blurry(face_crop):
                skipped_blur += 1
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(img, "Blurry — skipped", (x, y - 10), font, 0.6, (0, 0, 255), 1)
                continue

            count += 1
            processed = _preprocess_face(face_crop)

            # Save the preprocessed sample
            sample_path = os.path.join(FACE_SAMPLES_DIR, f"face.{face_id}.{count}.jpg")
            cv2.imwrite(sample_path, processed)
            saved += 1

            # Save a horizontally-flipped copy for augmentation
            flipped = cv2.flip(processed, 1)
            flip_path = os.path.join(FACE_SAMPLES_DIR, f"face.{face_id}.{count}_flip.jpg")
            cv2.imwrite(flip_path, flipped)
            saved += 1

            cv2.rectangle(img, (x, y), (x + w, y + h), (255, 0, 0), 2)

            # Progress overlay
            cv2.putText(img, f"Samples: {count}/{TOTAL_SAMPLES}", (10, 30), font, 0.8, (0, 255, 0), 2)
            logger.info("Sample %d/%d captured (+ flip)", count, TOTAL_SAMPLES)

        cv2.imshow(f"Capturing Face — {USER_CALL_NAME}", img)

        k = cv2.waitKey(100) & 0xFF
        if k == 27 or count >= TOTAL_SAMPLES:
            break

    cam.release()
    cv2.destroyAllWindows()
    logger.info("Done! %d unique samples captured (%d total with augmentation)", count, saved)
    if skipped_blur:
        logger.info("Skipped %d blurry frames", skipped_blur)
    logger.info("Samples saved to: %s", FACE_SAMPLES_DIR)
    logger.info("Now run trainer.py to train the model.")


if __name__ == "__main__":
    face_id_input = input(f"Enter numeric face ID for {USER_CALL_NAME} [default: 1]: ").strip()
    fid = int(face_id_input) if face_id_input.isdigit() else 1
    capture_samples(fid)