"""
face_debug.py — Live face alignment & confidence debug tool.
Run this to visually align your face and check recognition scores in real time.
Press ESC or Q to quit.
"""
import sys

import cv2
import numpy as np

CASCADE_PATH  = "backend/auth/haarcascade_frontalface_default.xml"
TRAINER_PATH  = "backend/auth/trainer/trainer.yml"
THRESHOLD     = 45   # must match config.py FACE_CONFIDENCE_THRESHOLD

# ── Setup ──────────────────────────────────────────────────────────────────────
print("[DEBUG] Opening camera...")
sys.stdout.flush()
cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
if not cam.isOpened():
    print("[ERROR] Could not open camera! Make sure no other app is using it.")
    sys.exit(1)
cam.set(3, 640)
cam.set(4, 480)
print("[DEBUG] Camera opened OK")
sys.stdout.flush()

cascade    = cv2.CascadeClassifier(CASCADE_PATH)
if cascade.empty():
    print("[ERROR] Could not load cascade file:", CASCADE_PATH)
    sys.exit(1)
recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
try:
    recognizer.read(TRAINER_PATH)
    print("[DEBUG] Trainer model loaded OK")
except Exception as e:
    print("[ERROR] Could not load trainer model:", e)
    sys.exit(1)
clahe      = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

FONT       = cv2.FONT_HERSHEY_SIMPLEX
W, H       = 640, 480

# Target box in the centre to guide face alignment
BOX_X1, BOX_Y1 = 200, 100
BOX_X2, BOX_Y2 = 440, 380

print("[DEBUG] All resources loaded. Starting live feed...")
print("Face Debug Tool running. Press ESC or Q to quit.")
print(f"Confidence threshold: distance < {THRESHOLD}  →  match")
sys.stdout.flush()

frame_count = 0

while True:
    ret, frame = cam.read()
    if not ret:
        print("[ERROR] Could not read frame from camera.")
        break

    frame_count += 1

    grey      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    grey_filt = cv2.bilateralFilter(grey, 9, 75, 75)
    faces     = cascade.detectMultiScale(grey_filt, scaleFactor=1.2, minNeighbors=5)

    # ── Draw alignment guide box ───────────────────────────────────────────────
    cv2.rectangle(frame, (BOX_X1, BOX_Y1), (BOX_X2, BOX_Y2), (80, 80, 80), 1)
    cv2.putText(frame, "Align face here", (BOX_X1, BOX_Y1 - 8), FONT, 0.5, (180, 180, 180), 1)

    # ── Centre crosshair ───────────────────────────────────────────────────────
    cx, cy = W // 2, H // 2
    cv2.line(frame, (cx - 15, cy), (cx + 15, cy), (80, 80, 80), 1)
    cv2.line(frame, (cx, cy - 15), (cx, cy + 15), (80, 80, 80), 1)

    status_text  = "No face detected"
    status_color = (0, 100, 255)  # orange

    for (x, y, w, h) in faces:
        roi     = grey[y:y + h, x:x + w]
        eq      = clahe.apply(roi)
        resized = cv2.resize(eq, (200, 200), interpolation=cv2.INTER_AREA)

        face_id, distance = recognizer.predict(resized)
        confidence = round(100 - distance)
        is_match   = distance < THRESHOLD

        # ── Colour coding: green = match, red = no match ───────────────────────
        color = (0, 220, 0) if is_match else (0, 0, 220)
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

        # ── Confidence bar ─────────────────────────────────────────────────────
        bar_len    = min(max(confidence, 0), 100) * w // 100
        cv2.rectangle(frame, (x, y + h + 5), (x + w, y + h + 18), (40, 40, 40), -1)
        cv2.rectangle(frame, (x, y + h + 5), (x + bar_len, y + h + 18), color, -1)

        # ── Labels ─────────────────────────────────────────────────────────────
        label = f"Dist: {distance:.1f}  Conf: {confidence}%"
        cv2.putText(frame, label, (x, y - 10), FONT, 0.55, color, 1)

        match_text = "MATCH" if is_match else "NO MATCH"
        cv2.putText(frame, match_text, (x, y + h + 36), FONT, 0.6, color, 2)

        status_text  = f"{'MATCH' if is_match else 'NO MATCH'} — distance={distance:.1f}  (threshold={THRESHOLD})"
        status_color = (0, 220, 0) if is_match else (0, 0, 220)

        # Print to console every 15 frames
        if frame_count % 15 == 0:
            print(f"[FRAME {frame_count}] Faces={len(faces)} | Dist={distance:.1f} | Conf={confidence}% | {'MATCH ✓' if is_match else 'NO MATCH ✗'}")
            sys.stdout.flush()

    if len(faces) == 0 and frame_count % 30 == 0:
        print(f"[FRAME {frame_count}] No face detected — move closer or improve lighting")
        sys.stdout.flush()

    # ── Status bar at bottom ───────────────────────────────────────────────────
    cv2.rectangle(frame, (0, H - 30), (W, H), (20, 20, 20), -1)
    cv2.putText(frame, status_text, (8, H - 10), FONT, 0.5, status_color, 1)

    # ── Header ────────────────────────────────────────────────────────────────
    cv2.rectangle(frame, (0, 0), (W, 28), (20, 20, 20), -1)
    cv2.putText(frame, "Jarvis Face Debug — Press Q to quit", (8, 18), FONT, 0.5, (200, 200, 200), 1)

    cv2.imshow("Jarvis Face Debug", frame)
    # Force window to front on first frame
    if frame_count == 1:
        cv2.setWindowProperty("Jarvis Face Debug", cv2.WND_PROP_TOPMOST, 1)
    key = cv2.waitKey(1) & 0xFF
    if key in (27, ord('q')):   # ESC or Q
        break

cam.release()
cv2.destroyAllWindows()
print("Debug tool closed.")
