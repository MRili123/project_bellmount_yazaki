"""
Shared utilities, constants, and helper functions - minimal version without PyQt6.
"""

from pathlib import Path
import cv2
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
CAPTURED_DIR = ROOT / "captured"
DATASET_DIR = ROOT / "dataset"
ORIG_DIR = DATASET_DIR / "original"
THRESH_DIR = DATASET_DIR / "thresholded"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
MODEL_DIR = ROOT / "model"

for d in (CAPTURED_DIR, DATASET_DIR, ORIG_DIR, THRESH_DIR, MODEL_DIR):
    d.mkdir(parents=True, exist_ok=True)

if not ANNOTATIONS_FILE.exists():
    ANNOTATIONS_FILE.write_text("[]")

def apply_threshold(bgr):
    """Apply threshold to convert image to binary - optimized.
    Kernel=21, C=5 for cable detection preprocessing.
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    th = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 21, 5)
    k = np.ones((2, 2), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k)
    return cv2.morphologyEx(th, cv2.MORPH_CLOSE, k)
