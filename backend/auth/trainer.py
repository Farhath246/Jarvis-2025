"""
trainer.py — Train the LBPH face recogniser from collected samples.
Run this after capturing face samples with sample.py.

Improvements over the original:
- Removed redundant detectMultiScale on already-cropped samples
- Applies CLAHE histogram equalization to match recognition-time preprocessing
- Resizes all images to a consistent standard size
- Tuned LBPH hyperparameters (radius=2, neighbors=16, grid 8x8) for finer detail
- Logs training statistics (sample count, time)
"""

import logging
import os
import time
import numpy as np
import cv2
from PIL import Image

from backend.config import FACE_SAMPLES_DIR, FACE_TRAINER_PATH, FACE_SAMPLE_SIZE

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _preprocess_face(img_arr: np.ndarray) -> np.ndarray:
    """Apply CLAHE histogram equalization and resize to the standard size."""
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    equalised = clahe.apply(img_arr)
    resized = cv2.resize(equalised, FACE_SAMPLE_SIZE, interpolation=cv2.INTER_AREA)
    return resized


def get_images_and_labels(samples_dir: str):
    """
    Load face sample images and prepare them for training.

    Since sample.py already saves cropped, preprocessed faces, we no longer
    run face detection again here — this was discarding most samples.

    Returns:
        (face_samples, ids) — lists suitable for recognizer.train()
    """
    image_paths = [
        os.path.join(samples_dir, f)
        for f in os.listdir(samples_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ]

    if not image_paths:
        raise FileNotFoundError(f"No sample images found in: {samples_dir}")

    face_samples = []
    ids = []
    skipped = 0

    for i, image_path in enumerate(image_paths):
        if (i + 1) % 50 == 0 or i == 0:
            logger.info("Processing sample %d/%d…", i + 1, len(image_paths))

        grey_img = Image.open(image_path).convert("L")
        img_arr = np.array(grey_img, dtype="uint8")

        # Extract face ID from filename: face.<id>.<count>.jpg or face.<id>.<count>_flip.jpg
        try:
            face_id = int(os.path.basename(image_path).split(".")[1])
        except (IndexError, ValueError):
            logger.warning("Skipping file with unexpected name format: %s", image_path)
            skipped += 1
            continue

        # Preprocess to match recognition-time pipeline (CLAHE + resize)
        processed = _preprocess_face(img_arr)
        face_samples.append(processed)
        ids.append(face_id)

    if skipped:
        logger.warning("Skipped %d files with bad naming format", skipped)

    return face_samples, ids


def train() -> None:
    """Train and save the face recogniser model."""
    if not os.path.isdir(FACE_SAMPLES_DIR):
        logger.error("Samples directory not found: %s", FACE_SAMPLES_DIR)
        logger.error("Please run sample.py first to capture face images.")
        return

    logger.info("Training face recogniser… this may take a moment.")
    try:
        # Tuned LBPH hyperparameters (reverted to radius=1, neighbors=8 to fix 8GB model explosion)
        recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1,
            neighbors=8,
            grid_x=8,
            grid_y=8
        )

        t_start = time.time()
        faces, ids = get_images_and_labels(FACE_SAMPLES_DIR)

        if not faces:
            logger.error("No usable face samples found. Training aborted.")
            return

        logger.info("Training on %d samples…", len(faces))
        recognizer.train(faces, np.array(ids))

        os.makedirs(os.path.dirname(FACE_TRAINER_PATH), exist_ok=True)
        recognizer.write(FACE_TRAINER_PATH)

        elapsed = time.time() - t_start
        logger.info("Model trained and saved to: %s", FACE_TRAINER_PATH)
        logger.info("Training completed in %.1fs using %d samples.", elapsed, len(faces))
        logger.info("You can now run Jarvis with face authentication.")

    except Exception as e:
        logger.error("Training failed: %s", e)


if __name__ == "__main__":
    train()