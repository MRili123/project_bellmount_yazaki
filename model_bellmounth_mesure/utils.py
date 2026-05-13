"""
Shared utilities, constants, and helper functions used across all modules.
"""

from pathlib import Path
import cv2
import numpy as np

from PyQt6.QtWidgets import QLabel, QPushButton, QFrame, QStatusBar
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt

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

# ── Palette ────────────────────────────────────────────────────────────────────
C = {
    "bg":        "#0D0F14",
    "surface":   "#141720",
    "panel":     "#1A1E2A",
    "border":    "#252A38",
    "accent":    "#4F8EF7",
    "accent2":   "#7C5CFC",
    "green":     "#3DDB7E",
    "red":       "#F75F5F",
    "yellow":    "#F7C948",
    "text":      "#E8ECF5",
    "muted":     "#6B7394",
    "card":      "#1E2330",
    "hover":     "#252C3F",
}

STYLE = f"""
QMainWindow, QWidget {{
    background: {C['bg']};
    color: {C['text']};
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}}
QSplitter::handle {{ background: {C['border']}; width: 2px; height: 2px; }}
QScrollBar:vertical {{
    background: {C['surface']}; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::sub-line:vertical {{ background: none; }}
QScrollBar::add-line:vertical {{ background: none; }}
"""

# ── Helper functions ───────────────────────────────────────────────────────────

def label(text, color=None, size=12, bold=False):
    """Create a styled label."""
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color:{color or C['text']}; font-size:{size}px; font-weight:{'bold' if bold else 'normal'};")
    return lbl


def btn(text, color=None, small=False):
    """Create a styled button."""
    b = QPushButton(text)
    bg = color or C["accent"]
    sz, pad = ("10px", "4px 10px") if small else ("12px", "7px 16px")
    b.setStyleSheet(f"""
        QPushButton {{ background:{bg}22; border:1px solid {bg}88; border-radius:5px;
            color:{bg}; font-size:{sz}; font-weight:bold; padding:{pad}; }}
        QPushButton:hover {{ background:{bg}44; border-color:{bg}; }}
        QPushButton:pressed {{ background:{bg}66; }}
        QPushButton:disabled {{ background:{C['surface']}; border-color:{C['border']}; color:{C['muted']}; }}
    """)
    return b


def separator():
    """Create a horizontal separator line."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color:{C['border']}; background:{C['border']}; max-height:1px;")
    return line


def ndarray_to_qpixmap(arr):
    """Convert numpy array to QPixmap."""
    if len(arr.shape) == 2:
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8)
    else:
        h, w, ch = arr.shape
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def apply_threshold(bgr):
    """Apply threshold to convert image to binary."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    th = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 31, 5)
    k = np.ones((3, 3), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k)
    return cv2.morphologyEx(th, cv2.MORPH_CLOSE, k)


class AppStatusBar(QStatusBar):
    """Custom status bar with stats display."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C['surface']}; color:{C['text']}; font-size:10px; padding:4px;")
        self._stats = {}

    def update_stats(self, **kwargs):
        """Update statistics display."""
        self._stats.update(kwargs)
        msg_parts = []
        if 'queue' in self._stats:
            msg_parts.append(f"Queue: {self._stats['queue']}")
        if 'total' in self._stats:
            msg_parts.append(f"Dataset: {self._stats['total']}")
        if 'pending' in self._stats:
            msg_parts.append(f"Pending: {self._stats['pending']}")
        if msg_parts:
            self.showMessage(" | ".join(msg_parts))
