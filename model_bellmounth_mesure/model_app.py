"""
Keypoint Annotation Tool
========================
Capture → Select → Annotate → Dataset → Model
"""

import sys
import os
import json
import uuid
import csv
import shutil
import tempfile
import math
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# ── TensorFlow (optional) ────────────────────────────────────────────────────
try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR')
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow verbose logging
    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False
    tf = None

# ── Shared camera bridge ───────────────────────────────────────────────────────
try:
    from dino_camera import DinoCamera
    _DINO_CAMERA_AVAILABLE = True
except ImportError:
    _DINO_CAMERA_AVAILABLE = False
    DinoCamera = None

# ── Import modular sections ────────────────────────────────────────────────────
try:
    from capture_section import CaptureSection
    _CAPTURE_IMPORTED = True
except ImportError:
    _CAPTURE_IMPORTED = False

try:
    from inbox_section import InboxSection
    _INBOX_IMPORTED = True
except ImportError:
    _INBOX_IMPORTED = False

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QGridLayout, QFrame,
    QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QMessageBox, QFileDialog, QButtonGroup, QRadioButton,
    QStatusBar, QSizePolicy, QAbstractItemView, QCheckBox,
    QToolButton, QGroupBox, QProgressBar, QComboBox, QSpinBox, QLineEdit,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint, QRect,
    QSize, QPointF, QRectF, pyqtSlot, QObject
)
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QColor, QBrush, QFont,
    QCursor, QKeySequence, QShortcut, QPainterPath, QAction,
    QFontDatabase, QLinearGradient
)

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
CAPTURED_DIR = ROOT / "captured"
DATASET_DIR = ROOT / "dataset"
ORIG_DIR = DATASET_DIR / "original"
THRESH_DIR = DATASET_DIR / "thresholded"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
MODEL_DIR = ROOT / "model"
TEST_IMAGES_DIR = ROOT / "test_images"

for d in (CAPTURED_DIR, DATASET_DIR, ORIG_DIR, THRESH_DIR, MODEL_DIR, TEST_IMAGES_DIR):
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
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{
    background: {C['surface']}; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {C['border']}; border-radius: 4px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}
QTableWidget {{
    background: {C['surface']}; border: 1px solid {C['border']};
    border-radius: 6px; gridline-color: {C['border']};
    selection-background-color: {C['hover']};
}}
QTableWidget::item {{ padding: 4px 8px; border-bottom: 1px solid {C['border']}; }}
QTableWidget::item:selected {{ background: {C['hover']}; color: {C['text']}; }}
QHeaderView::section {{
    background: {C['panel']}; color: {C['muted']}; font-size: 10px;
    font-weight: bold; letter-spacing: 1px; text-transform: uppercase;
    padding: 6px 8px; border: none; border-bottom: 1px solid {C['border']};
}}
QDialog {{ background: {C['panel']}; }}
QCheckBox {{ spacing: 6px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px; border-radius: 3px;
    border: 1px solid {C['border']}; background: {C['surface']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent']}; border-color: {C['accent']};
}}
QGroupBox {{
    border: 1px solid {C['border']}; border-radius: 6px;
    margin-top: 12px; padding-top: 8px;
    font-size: 10px; color: {C['muted']}; letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    padding: 0 6px; left: 10px;
}}
QProgressBar {{
    background: {C['surface']}; border: 1px solid {C['border']};
    border-radius: 4px; text-align: center; color: {C['text']};
    font-size: 11px; font-weight: bold;
}}
QProgressBar::chunk {{
    background: {C['green']}; border-radius: 4px;
}}
QComboBox {{
    background: {C['surface']}; border: 1px solid {C['border']};
    border-radius: 4px; color: {C['text']}; padding: 3px 8px; font-size: 11px;
}}
QComboBox::drop-down {{ border: none; }}
QComboBox QAbstractItemView {{
    background: {C['panel']}; color: {C['text']}; border: 1px solid {C['border']};
}}
QSpinBox {{
    background: {C['surface']}; border: 1px solid {C['border']};
    border-radius: 4px; color: {C['text']}; padding: 2px 4px;
    font-size: 11px; font-family: 'Consolas','Courier New',monospace;
}}
QSpinBox:focus {{ border-color: {C['accent']}; }}
QSpinBox::up-button, QSpinBox::down-button {{
    width: 14px; background: {C['panel']}; border: none;
}}
"""


def btn(text, color=None, small=False):
    """Factory for styled QPushButton."""
    b = QPushButton(text)
    bg = color or C["accent"]
    sz = "10px" if small else "12px"
    pad = "4px 10px" if small else "7px 16px"
    b.setStyleSheet(f"""
        QPushButton {{
            background: {bg}22; border: 1px solid {bg}88;
            border-radius: 5px; color: {bg}; font-size: {sz};
            font-weight: bold; padding: {pad}; letter-spacing: 0.5px;
        }}
        QPushButton:hover {{ background: {bg}44; border-color: {bg}; }}
        QPushButton:pressed {{ background: {bg}66; }}
        QPushButton:disabled {{
            background: {C['surface']}; border-color: {C['border']};
            color: {C['muted']};
        }}
    """)
    return b


def label(text, color=None, size=12, bold=False):
    lbl = QLabel(text)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(f"""
        color: {color or C['text']}; font-size: {size}px;
        font-weight: {weight};
    """)
    return lbl


def separator():
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {C['border']}; background: {C['border']}; max-height: 1px;")
    return line


# ── Image Processing ──────────────────────────────────────────────────────────

def apply_threshold(bgr_image: np.ndarray) -> np.ndarray:
    """Apply fixed adaptive threshold pipeline. Returns same-size single-channel image."""
    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    th = cv2.adaptiveThreshold(
        blur, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31, 5
    )
    kernel = np.ones((3, 3), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel, iterations=1)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=1)
    return th


def ndarray_to_qpixmap(arr: np.ndarray) -> QPixmap:
    """Convert numpy BGR or grayscale array to QPixmap."""
    if len(arr.shape) == 2:
        h, w = arr.shape
        qimg = QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8)
    else:
        h, w, ch = arr.shape
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def draw_points_on_pixmap(pixmap: QPixmap, points: list, scale_x=1.0, scale_y=1.0) -> QPixmap:
    """Draw annotation points + line on a pixmap. Points are in original coords."""
    pm = pixmap.copy()
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    colors = [QColor(0, 220, 80), QColor(80, 160, 255)]
    labels = ["P1", "P2"]
    radius = max(5, int(8 * min(scale_x, scale_y)))

    screen_pts = []
    for i, pt in enumerate(points[:2]):
        sx = int(pt[0] * scale_x)
        sy = int(pt[1] * scale_y)
        screen_pts.append((sx, sy))
        pen = QPen(colors[i], 2)
        painter.setPen(pen)
        painter.setBrush(QBrush(colors[i], Qt.BrushStyle.SolidPattern))
        painter.drawEllipse(QPoint(sx, sy), radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setFont(QFont("Consolas", max(8, radius - 2), QFont.Weight.Bold))
        painter.drawText(sx + radius + 3, sy + 4, labels[i])

    if len(screen_pts) == 2:
        painter.setPen(QPen(QColor(255, 80, 80), 2, Qt.PenStyle.DashLine))
        painter.drawLine(screen_pts[0][0], screen_pts[0][1],
                         screen_pts[1][0], screen_pts[1][1])

    painter.end()
    return pm


# ── Data Layer ─────────────────────────────────────────────────────────────────

class DataStore:
    def load(self) -> list:
        try:
            return json.loads(ANNOTATIONS_FILE.read_text())
        except Exception:
            return []

    def save(self, entries: list):
        tmp = ANNOTATIONS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(entries, indent=2))
        tmp.replace(ANNOTATIONS_FILE)

    def add(self, entry: dict):
        entries = self.load()
        entries = [e for e in entries if e["filename"] != entry["filename"]]
        entries.append(entry)
        self.save(entries)

    def update(self, entry_id: str, entry: dict):
        entries = self.load()
        for i, e in enumerate(entries):
            if e["id"] == entry_id:
                entries[i] = entry
                break
        self.save(entries)

    def delete(self, entry_id: str):
        entries = self.load()
        entries = [e for e in entries if e["id"] != entry_id]
        self.save(entries)

    def get_by_id(self, entry_id: str):
        for e in self.load():
            if e["id"] == entry_id:
                return e
        return None

    def export_csv(self, path: str):
        entries = self.load()
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id","filename","width","height",
                         "p1_x","p1_y","p2_x","p2_y","pixel_distance"])
            for e in entries:
                pts = e.get("points", [{}, {}])
                p1 = pts[0] if len(pts) > 0 else {}
                p2 = pts[1] if len(pts) > 1 else {}
                w.writerow([
                    e.get("id"), e.get("filename"),
                    e.get("width"), e.get("height"),
                    p1.get("x"), p1.get("y"),
                    p2.get("x"), p2.get("y"),
                    e.get("pixel_distance"),
                ])


STORE = DataStore()


# ── Status Bar ─────────────────────────────────────────────────────────────────

class AppStatusBar(QStatusBar):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"""
            QStatusBar {{
                background: {C['surface']}; border-top: 1px solid {C['border']};
                color: {C['muted']}; font-size: 11px; padding: 2px 8px;
            }}
        """)
        self._total = label("Dataset: 0", C['muted'], 11)
        self._pending = label("Pending: 0", C['muted'], 11)
        self._queue = label("Queue: 0", C['muted'], 11)
        for w in (self._total, self._pending, self._queue):
            self.addPermanentWidget(w)
        self.addPermanentWidget(label("  ", C['muted'], 11))

    def update_stats(self, total=None, pending=None, queue=None):
        if total is not None:
            self._total.setText(f"Dataset: {total}")
        if pending is not None:
            self._pending.setText(f"Pending: {pending}")
        if queue is not None:
            self._queue.setText(f"Queue: {queue}")


# ── Toast Notification ─────────────────────────────────────────────────────────

class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"""
            background: {C['green']}22; border: 1px solid {C['green']}88;
            border-radius: 6px; color: {C['green']}; font-size: 12px;
            padding: 8px 18px; font-weight: bold;
        """)
        self.hide()
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, msg, duration=2500, error=False):
        col = C['red'] if error else C['green']
        self.setStyleSheet(f"""
            background: {col}22; border: 1px solid {col}88;
            border-radius: 6px; color: {col}; font-size: 12px;
            padding: 8px 18px; font-weight: bold;
        """)
        self.setText(msg)
        self.adjustSize()
        pw = self.parent().width()
        self.move((pw - self.width()) // 2, 20)
        self.show()
        self.raise_()
        self._timer.start(duration)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1 – CAPTURE
# ─────────────────────────────────────────────────────────────────────────────

class CaptureSection(QWidget):
    def __init__(self, status_bar: AppStatusBar):
        super().__init__()
        self.status_bar = status_bar
        self._cap = None
        self._dino = None
        self._sdk = None
        self._session_count = 0
        self._capturing = False
        self._device_index = 0
        self._amr_value = 0.0

        self._preview_timer = QTimer()
        self._capture_timer = QTimer()
        self._amr_timer = QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._capture_timer.timeout.connect(self._capture_frame)
        self._amr_timer.timeout.connect(self._poll_amr)

        self._build_ui()
        self._init_sdk()
        self._start_preview()

    def _init_sdk(self):
        if not _DINO_CAMERA_AVAILABLE:
            self._sdk_status_lbl.setText("SDK: dino_camera.py not found — plain webcam mode")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
            self._sdk_panel.hide()
            return

        self._dino = DinoCamera()
        self._cap  = self._dino.cap
        self._sdk  = self._dino.sdk

        if self._sdk is None:
            self._sdk_status_lbl.setText("SDK: DNX64 unavailable — plain webcam mode")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
            self._sdk_panel.hide()
            return

        devices = self._dino.list_devices()
        self._device_combo.clear()
        if not devices:
            self._sdk_status_lbl.setText("SDK: loaded  |  No Dino-Lite devices found")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['yellow']}; font-size:10px;")
        else:
            for i, name in enumerate(devices):
                self._device_combo.addItem(f"[{i}] {name}", userData=i)
            self._sdk_status_lbl.setText(f"SDK: loaded  |  {len(devices)} device(s) found")
            self._sdk_status_lbl.setStyleSheet(f"color:{C['green']}; font-size:10px;")
            self._sdk_panel.show()
            self._amr_timer.start(500)

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        hdr = QHBoxLayout()
        hdr.addWidget(label("◉  CAPTURE", C['accent'], 13, True))
        hdr.addStretch()
        self._session_lbl = label("Session: 0 frames", C['muted'], 11)
        hdr.addWidget(self._session_lbl)
        lay.addLayout(hdr)

        self._sdk_status_lbl = label("SDK: initialising…", C['muted'], 10)
        lay.addWidget(self._sdk_status_lbl)
        lay.addWidget(separator())

        self._sdk_panel = QGroupBox("DINO-LITE CONTROLS")
        self._sdk_panel.hide()
        sdk_lay = QVBoxLayout(self._sdk_panel)
        sdk_lay.setSpacing(8)

        dev_row = QHBoxLayout()
        dev_row.addWidget(label("Device:", C['muted'], 10))
        self._device_combo = QComboBox()
        self._device_combo.setStyleSheet(STYLE)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        dev_row.addWidget(self._device_combo, 1)
        sdk_lay.addLayout(dev_row)

        amr_row = QHBoxLayout()
        self._amr_lbl  = label("Magnification: —×", C['accent'],  11)
        self._fov_lbl  = label("FOV: — µm",         C['accent2'], 11)
        amr_row.addWidget(self._amr_lbl)
        amr_row.addStretch()
        amr_row.addWidget(self._fov_lbl)
        sdk_lay.addLayout(amr_row)

        led_row = QHBoxLayout()
        led_row.addWidget(label("LED:", C['muted'], 10))
        self._led_on_btn  = btn("ON",  C['green'],  True)
        self._led_off_btn = btn("OFF", C['red'],    True)
        self._led_on_btn.clicked.connect(lambda: self._set_led(1))
        self._led_off_btn.clicked.connect(lambda: self._set_led(0))
        led_row.addWidget(self._led_on_btn)
        led_row.addWidget(self._led_off_btn)
        led_row.addStretch()
        sdk_lay.addLayout(led_row)

        ae_row = QHBoxLayout()
        ae_row.addWidget(label("Auto-Exposure:", C['muted'], 10))
        self._ae_on_btn  = btn("ON",  C['green'], True)
        self._ae_off_btn = btn("OFF", C['red'],   True)
        self._ae_on_btn.clicked.connect(lambda: self._set_ae(1))
        self._ae_off_btn.clicked.connect(lambda: self._set_ae(0))
        ae_row.addWidget(self._ae_on_btn)
        ae_row.addWidget(self._ae_off_btn)
        ae_row.addStretch()
        sdk_lay.addLayout(ae_row)

        lay.addWidget(self._sdk_panel)

        self._cam_label = QLabel()
        self._cam_label.setMinimumSize(480, 360)
        self._cam_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_label.setStyleSheet(f"""
            background: {C['surface']}; border: 1px solid {C['border']};
            border-radius: 8px; color: {C['muted']}; font-size: 13px;
        """)
        self._cam_label.setText("⬡  No camera feed")
        lay.addWidget(self._cam_label, 1)

        ctrl = QHBoxLayout()
        self._btn_start = btn("▶  Start Capture", C['green'])
        self._btn_stop  = btn("■  Stop Capture",  C['red'])
        self._btn_stop.setEnabled(False)
        self._btn_start.clicked.connect(self._start_capture)
        self._btn_stop.clicked.connect(self._stop_capture)
        ctrl.addWidget(self._btn_start)
        ctrl.addWidget(self._btn_stop)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        info = QHBoxLayout()
        info.addWidget(label("Interval: 3 sec  |  Format: PNG  |  Color: BGR  |  "
                             "Video frames via cv2.VideoCapture", C['muted'], 10))
        lay.addLayout(info)

    def _on_device_changed(self, combo_idx: int):
        if self._device_combo.count() == 0:
            return
        sdk_idx = self._device_combo.itemData(combo_idx)
        if sdk_idx is None:
            sdk_idx = combo_idx
        self._device_index = sdk_idx
        if self._dino:
            self._preview_timer.stop()
            self._dino.switch_device(sdk_idx)
            self._cap = self._dino.cap
            if self._cap and self._cap.isOpened():
                self._preview_timer.start(50)
        else:
            self._reopen_cap(sdk_idx)

    def _poll_amr(self):
        if self._dino is None:
            return
        amr = self._dino.get_amr(self._device_index)
        if amr > 0:
            self._amr_value = amr
            self._amr_lbl.setText(f"Magnification: {amr:.1f}×")
            fov = self._dino.get_fov(amr, self._device_index)
            if fov > 0:
                self._fov_lbl.setText(f"FOV: {fov:.1f} µm")

    def _set_led(self, state: int):
        if self._sdk:
            try:
                self._sdk.SetLEDState(self._device_index, state)
            except Exception:
                pass

    def _set_ae(self, state: int):
        if self._sdk:
            try:
                self._sdk.SetAutoExposure(self._device_index, state)
            except Exception:
                pass

    def _reopen_cap(self, index: int):
        if self._cap:
            self._preview_timer.stop()
            self._cap.release()
        self._cap = cv2.VideoCapture(index)
        if self._cap.isOpened():
            self._preview_timer.start(50)

    def _start_preview(self):
        if self._cap is None:
            self._cap = cv2.VideoCapture(self._device_index)
        if self._cap and self._cap.isOpened():
            self._preview_timer.start(50)

    def _update_preview(self):
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                self._last_frame = frame
                if self._amr_value > 0:
                    cv2.putText(
                        frame, f"{self._amr_value:.1f}x",
                        (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (80, 220, 255), 2, cv2.LINE_AA
                    )
                pm = ndarray_to_qpixmap(frame)
                pm = pm.scaled(
                    self._cam_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._cam_label.setPixmap(pm)

    def _start_capture(self):
        self._capturing = True
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._capture_timer.start(3000)

    def _stop_capture(self):
        self._capturing = False
        self._capture_timer.stop()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _capture_frame(self):
        if not (self._cap and self._cap.isOpened()):
            return
        ret, frame = self._cap.read()
        if ret:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            fname = f"capture_{ts}.png"
            fpath = CAPTURED_DIR / fname
            cv2.imwrite(str(fpath), frame)
            self._session_count += 1
            self._session_lbl.setText(f"Session: {self._session_count} frames")
            self.status_bar.showMessage(f"Captured: {fname}  |  {self._amr_value:.1f}×", 2000)

    def closeEvent(self, event):
        self._preview_timer.stop()
        self._capture_timer.stop()
        self._amr_timer.stop()
        if self._dino:
            self._dino.release()
        elif self._cap:
            self._cap.release()
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2 – INBOX
# ─────────────────────────────────────────────────────────────────────────────

class ImageCard(QFrame):
    toggled      = pyqtSignal(str, bool)
    delete_requested = pyqtSignal(str)
    preview_requested = pyqtSignal(str)

    def __init__(self, img_path: Path, in_dataset: bool):
        super().__init__()
        self.img_path = img_path
        self.selected = False
        self.in_dataset = in_dataset
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._build()

    def _build(self):
        self.setFixedSize(160, 210)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._refresh_style(False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(3)

        self._thumb = QLabel()
        self._thumb.setFixedSize(148, 108)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(f"background:{C['bg']}; border-radius:4px;")
        self._load_thumb()
        lay.addWidget(self._thumb)

        name = self.img_path.name
        short = name[:18] + "…" if len(name) > 20 else name
        n_lbl = QLabel(short)
        n_lbl.setStyleSheet(f"color:{C['text']}; font-size:9px;")
        n_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(n_lbl)

        try:
            img = cv2.imread(str(self.img_path))
            h, w = img.shape[:2]
            dim_text = f"{w}×{h}"
        except Exception:
            dim_text = "?×?"
        d_lbl = QLabel(dim_text)
        d_lbl.setStyleSheet(f"color:{C['muted']}; font-size:9px;")
        d_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(d_lbl)

        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        bottom.setContentsMargins(0, 0, 0, 0)

        if self.in_dataset:
            badge_col, badge_txt = C['green'], "✓ Done"
        else:
            badge_col, badge_txt = C['yellow'], "● Pending"
        badge = QLabel(badge_txt)
        badge.setStyleSheet(f"""
            background:{badge_col}22; border:1px solid {badge_col}66;
            border-radius:3px; color:{badge_col}; font-size:9px;
            padding:2px 4px; font-weight:bold;
        """)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom.addWidget(badge, 1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(22, 20)
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['red']}22; border:1px solid {C['red']}66;
                border-radius:3px; color:{C['red']}; font-size:10px;
                font-weight:bold; padding:0px;
            }}
            QPushButton:hover {{ background:{C['red']}55; border-color:{C['red']}; }}
            QPushButton:pressed {{ background:{C['red']}88; }}
        """)
        del_btn.setToolTip("Delete this image file")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(str(self.img_path)))
        bottom.addWidget(del_btn)

        lay.addLayout(bottom)

    def _load_thumb(self):
        try:
            img = cv2.imread(str(self.img_path))
            pm = ndarray_to_qpixmap(img)
            pm = pm.scaled(148, 108, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            self._thumb.setPixmap(pm)
        except Exception:
            self._thumb.setText("?")

    def _refresh_style(self, selected):
        if selected:
            border = C['accent']
            bg = C['hover']
        else:
            border = C['border']
            bg = C['card']
        self.setStyleSheet(f"""
            QFrame {{ background:{bg}; border:2px solid {border};
                      border-radius:8px; }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.in_dataset:
            self.selected = not self.selected
            self._refresh_style(self.selected)
            self.toggled.emit(str(self.img_path), self.selected)

    def mouseDoubleClickEvent(self, event):
        self.preview_requested.emit(str(self.img_path))
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:{C['panel']}; border:1px solid {C['border']};
                     color:{C['text']}; font-size:11px; padding:4px; }}
            QMenu::item {{ padding:5px 20px; border-radius:3px; }}
            QMenu::item:selected {{ background:{C['hover']}; }}
        """)
        if not self.in_dataset:
            sel_action = menu.addAction("☑  Select / Deselect")
            sel_action.triggered.connect(lambda: self._toggle_select())
        menu.addSeparator()
        del_action = menu.addAction("✕  Delete file")
        del_action.triggered.connect(lambda: self.delete_requested.emit(str(self.img_path)))
        menu.exec(self.mapToGlobal(pos))

    def _toggle_select(self):
        if not self.in_dataset:
            self.selected = not self.selected
            self._refresh_style(self.selected)
            self.toggled.emit(str(self.img_path), self.selected)


class InboxSection(QWidget):
    send_to_annotation = pyqtSignal(list)

    def __init__(self, status_bar: AppStatusBar):
        super().__init__()
        self.status_bar = status_bar
        self._selected = set()
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        hdr = QHBoxLayout()
        hdr.addWidget(label("◈  INBOX", C['accent2'], 13, True))
        hdr.addStretch()
        self._count_lbl = label("0 images", C['muted'], 11)
        hdr.addWidget(self._count_lbl)
        refresh_btn = btn("↺ Refresh", C['muted'], True)
        refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(refresh_btn)
        lay.addLayout(hdr)
        lay.addWidget(separator())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"background:{C['surface']}; border:none;")
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet(f"background:{C['surface']};")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._scroll.setWidget(self._grid_widget)
        lay.addWidget(self._scroll, 1)

        ctrl = QHBoxLayout()
        self._sel_lbl = label("0 selected", C['muted'], 11)
        ctrl.addWidget(self._sel_lbl)
        ctrl.addStretch()
        self._del_btn = btn("✕  Delete Selected", C['red'])
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._delete_selected)
        ctrl.addWidget(self._del_btn)
        self._send_btn = btn("→  Send to Annotation", C['accent'])
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._send)
        ctrl.addWidget(self._send_btn)
        lay.addLayout(ctrl)

        self.refresh()

    def refresh(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._selected.clear()

        dataset_files = {e["filename"] for e in STORE.load()}
        images = sorted(CAPTURED_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        self._count_lbl.setText(f"{len(images)} images")

        cols = 4
        for i, img_path in enumerate(images):
            in_ds = img_path.name in dataset_files
            card = ImageCard(img_path, in_ds)
            card.toggled.connect(self._on_toggle)
            card.delete_requested.connect(self._delete_one)
            card.preview_requested.connect(self._show_preview)
            self._grid.addWidget(card, i // cols, i % cols)

        self._grid.setRowStretch(max(1, (len(images) // cols) + 1), 1)
        self._update_controls()

        pending = sum(1 for img in images if img.name not in dataset_files)
        self.status_bar.update_stats(total=len(dataset_files), pending=pending)

    def _on_toggle(self, path, selected):
        if selected:
            self._selected.add(path)
        else:
            self._selected.discard(path)
        self._update_controls()

    def _update_controls(self):
        n = len(self._selected)
        self._sel_lbl.setText(f"{n} selected")
        self._send_btn.setEnabled(n > 0)
        self._del_btn.setEnabled(n > 0)

    def _delete_one(self, path_str: str):
        path = Path(path_str)
        reply = QMessageBox.question(
            self, "Delete Image",
            f"Permanently delete:\n{path.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                path.unlink()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete file:\n{e}")
            self._selected.discard(path_str)
            self.refresh()

    def _delete_selected(self):
        if not self._selected:
            return
        n = len(self._selected)
        reply = QMessageBox.question(
            self, "Delete Images",
            f"Permanently delete {n} selected image(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            errors = []
            for path_str in list(self._selected):
                try:
                    Path(path_str).unlink()
                except Exception as e:
                    errors.append(f"{Path(path_str).name}: {e}")
            if errors:
                QMessageBox.warning(self, "Some files not deleted", "\n".join(errors))
            self._selected.clear()
            self.refresh()

    def _send(self):
        paths = [Path(p) for p in self._selected]
        self.send_to_annotation.emit(paths)
        self._selected.clear()
        self._update_controls()
        self.refresh()

    def _show_preview(self, path_str: str):
        dialog = QDialog(self)
        dialog.setWindowTitle("Preview — " + Path(path_str).name)
        dialog.setStyleSheet(STYLE)
        dialog.setMinimumSize(400, 300)

        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(12, 12, 12, 12)

        img = cv2.imread(path_str)
        if img is not None:
            pm = ndarray_to_qpixmap(img)
            h, w = img.shape[:2]
            sc = min(1200 / w, 800 / h, 1.0)
            disp_w, disp_h = int(w * sc), int(h * sc)
            pm = pm.scaled(disp_w, disp_h,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)

            lbl = QLabel()
            lbl.setPixmap(pm)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"background:{C['bg']}; border:1px solid {C['border']}; border-radius:6px;")
            lay.addWidget(lbl)

            info = QLabel(f"{w} × {h} px  |  {Path(path_str).name}")
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
            lay.addWidget(info)
        else:
            err = QLabel("Could not load image.")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            err.setStyleSheet(f"color:{C['red']};")
            lay.addWidget(err)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = btn("Close", C['accent'])
        close_btn.clicked.connect(dialog.accept)
        btn_row.addWidget(close_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        dialog.exec()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3 – ANNOTATION CANVAS
# ─────────────────────────────────────────────────────────────────────────────

class AnnotationCanvas(QLabel):
    point_placed = pyqtSignal(int, int)
    mouse_moved = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"background:{C['bg']}; border:1px solid {C['border']}; border-radius:6px;")
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        self._orig_image = None
        self._thresh_image = None
        self._points = []
        self._replace_mode = "nearest"
        self._show_gray = False

        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self._pan_start = None
        self._pan_offset_start = None

        self._disp_w = 0
        self._disp_h = 0
        self._img_x = 0
        self._img_y = 0

    def load_image(self, bgr: np.ndarray):
        self._orig_image = bgr
        self._thresh_image = apply_threshold(bgr)
        self._points = []
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self._redraw()

    def set_points(self, pts: list):
        self._points = list(pts)
        self._redraw()

    def set_replace_mode(self, mode: str):
        self._replace_mode = mode

    def set_preview_mode(self, show_gray: bool):
        self._show_gray = show_gray

    def get_points(self):
        return list(self._points)

    def reset_points(self):
        self._points = []
        self._redraw()

    def _redraw(self):
        if self._thresh_image is None:
            return

        if self._show_gray and self._orig_image is not None:
            base_img = cv2.cvtColor(self._orig_image, cv2.COLOR_BGR2GRAY)
        else:
            base_img = self._thresh_image

        oh, ow = base_img.shape[:2]

        cw = self.width() or 600
        ch = self.height() or 500
        scale = min(cw / ow, ch / oh) * self._zoom
        self._disp_w = int(ow * scale)
        self._disp_h = int(oh * scale)

        pm = ndarray_to_qpixmap(base_img)
        pm = pm.scaled(self._disp_w, self._disp_h,
                       Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = [QColor(0, 220, 80), QColor(80, 160, 255)]
        labels_txt = ["P1", "P2"]
        r = max(5, int(7 * min(self._zoom, 2)))

        sx_pts = []
        for i, (ox, oy) in enumerate(self._points[:2]):
            sx = int(ox * scale)
            sy = int(oy * scale)
            sx_pts.append((sx, sy))
            painter.setPen(QPen(colors[i], 2))
            painter.setBrush(QBrush(colors[i]))
            painter.drawEllipse(QPoint(sx, sy), r, r)
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setFont(QFont("Consolas", max(8, r), QFont.Weight.Bold))
            painter.drawText(sx + r + 3, sy + 4, labels_txt[i])

        if len(sx_pts) == 2:
            painter.setPen(QPen(QColor(255, 80, 80), 2, Qt.PenStyle.DashLine))
            painter.drawLine(sx_pts[0][0], sx_pts[0][1],
                             sx_pts[1][0], sx_pts[1][1])
        painter.end()

        canvas_pm = QPixmap(cw, ch)
        canvas_pm.fill(QColor(C['bg']))
        p2 = QPainter(canvas_pm)
        ix = int((cw - self._disp_w) / 2 + self._offset.x())
        iy = int((ch - self._disp_h) / 2 + self._offset.y())
        self._img_x = ix
        self._img_y = iy
        p2.drawPixmap(ix, iy, pm)
        p2.end()
        self.setPixmap(canvas_pm)

    def _canvas_to_orig(self, cx, cy):
        if self._thresh_image is None:
            return None, None
        oh, ow = self._thresh_image.shape[:2]
        cw = self.width()
        ch = self.height()
        scale = min(cw / ow, ch / oh) * self._zoom
        ix = self._img_x
        iy = self._img_y
        ox = (cx - ix) / scale
        oy = (cy - iy) / scale
        if 0 <= ox < ow and 0 <= oy < oh:
            return int(ox), int(oy)
        return None, None

    def mouseMoveEvent(self, event):
        ox, oy = self._canvas_to_orig(event.position().x(), event.position().y())
        if ox is not None:
            self.mouse_moved.emit(ox, oy)

        if self._pan_start and event.buttons() & Qt.MouseButton.MiddleButton:
            delta = event.position() - self._pan_start
            self._offset = self._pan_offset_start + delta
            self._redraw()
        elif self._pan_start and event.buttons() & Qt.MouseButton.LeftButton and self._zoom > 1.05:
            delta = event.position() - self._pan_start
            self._offset = self._pan_offset_start + delta
            self._redraw()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = event.position()
            self._pan_offset_start = QPointF(self._offset)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            if self._zoom > 1.05:
                self._pan_start = event.position()
                self._pan_offset_start = QPointF(self._offset)
                return
            ox, oy = self._canvas_to_orig(event.position().x(), event.position().y())
            if ox is not None:
                self.point_placed.emit(ox, oy)

    def mouseReleaseEvent(self, event):
        self._pan_start = None

    def wheelEvent(self, event):
        if self._thresh_image is None:
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_zoom = max(0.2, min(8.0, self._zoom * factor))

        cx = event.position().x()
        cy = event.position().y()
        cw = self.width()
        ch = self.height()
        base_ix = (cw - self._disp_w) / 2 + self._offset.x()
        base_iy = (ch - self._disp_h) / 2 + self._offset.y()

        ratio = new_zoom / self._zoom
        new_ix = cx - ratio * (cx - base_ix)
        new_iy = cy - ratio * (cy - base_iy)
        oh, ow = self._thresh_image.shape[:2]
        scale_new = min(cw / ow, ch / oh) * new_zoom
        new_w = ow * scale_new
        new_h = oh * scale_new
        self._offset = QPointF(new_ix - (cw - new_w) / 2,
                               new_iy - (ch - new_h) / 2)
        self._zoom = new_zoom
        self._redraw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._redraw()


class AnnotationSection(QWidget):
    dataset_updated = pyqtSignal()

    def __init__(self, status_bar: AppStatusBar, toast: Toast):
        super().__init__()
        self.status_bar = status_bar
        self.toast = toast
        self._queue = []
        self._queue_idx = 0
        self._edit_id = None
        self._current_orig = None
        self._build_ui()

    def _build_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        left = QWidget()
        left.setStyleSheet(f"background:{C['bg']};")
        llay = QVBoxLayout(left)
        llay.setContentsMargins(16, 16, 8, 16)
        llay.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.addWidget(label("⬡  ANNOTATION", C['green'], 13, True))
        hdr.addStretch()
        self._dim_lbl = label("No image", C['muted'], 11)
        hdr.addWidget(self._dim_lbl)
        llay.addLayout(hdr)
        llay.addWidget(separator())

        self._coord_lbl = label("X: —  Y: —", C['muted'], 10)
        llay.addWidget(self._coord_lbl)

        self.canvas = AnnotationCanvas()
        self.canvas.point_placed.connect(self._on_point_placed)
        self.canvas.mouse_moved.connect(self._on_mouse_moved)
        llay.addWidget(self.canvas, 1)

        prev_row = QHBoxLayout()
        self._preview_chk = QCheckBox("Show original (grayscale)")
        self._preview_chk.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
        self._preview_chk.toggled.connect(self._toggle_preview)
        prev_row.addWidget(self._preview_chk)
        prev_row.addStretch()
        prev_row.addWidget(label("Scroll to zoom  |  Drag to pan", C['muted'], 10))
        llay.addLayout(prev_row)
        main.addWidget(left, 1)

        right = QWidget()
        right.setFixedWidth(260)
        right.setStyleSheet(f"background:{C['panel']}; border-left:1px solid {C['border']};")
        rlay = QVBoxLayout(right)
        rlay.setContentsMargins(14, 16, 14, 16)
        rlay.setSpacing(12)

        rlay.addWidget(label("CONTROLS", C['muted'], 10, True))
        rlay.addWidget(separator())

        self._file_lbl = label("—", C['text'], 11)
        self._file_lbl.setWordWrap(True)
        rlay.addWidget(self._file_lbl)
        self._size_lbl = label("—", C['muted'], 10)
        rlay.addWidget(self._size_lbl)
        rlay.addWidget(separator())

        rlay.addWidget(label("POINTS", C['muted'], 10, True))

        spin_style = f"""
            QSpinBox {{
                background:{C['surface']}; border:1px solid {C['border']};
                border-radius:4px; color:{C['text']}; padding:2px 4px;
                font-size:11px; font-family:'Consolas','Courier New',monospace;
            }}
            QSpinBox:focus {{ border-color:{C['accent']}; }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width:14px; background:{C['panel']}; border:none;
            }}
        """

        p1_hdr = QHBoxLayout()
        p1_dot = QLabel("●")
        p1_dot.setStyleSheet(f"color:{C['green']}; font-size:13px;")
        p1_hdr.addWidget(p1_dot)
        p1_hdr.addWidget(label("P1", C['green'], 11, True))
        p1_hdr.addStretch()
        self._p1_apply_btn = QPushButton("Apply")
        self._p1_apply_btn.setFixedSize(44, 20)
        self._p1_apply_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['green']}22; border:1px solid {C['green']}66;
                border-radius:3px; color:{C['green']}; font-size:9px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{C['green']}44; }}
        """)
        p1_hdr.addWidget(self._p1_apply_btn)
        rlay.addLayout(p1_hdr)

        p1_coords = QHBoxLayout()
        p1_coords.setSpacing(4)
        p1_coords.addWidget(label("X", C['muted'], 10))
        self._p1_x = QSpinBox(); self._p1_x.setRange(0, 99999)
        self._p1_x.setStyleSheet(spin_style); self._p1_x.setFixedWidth(72)
        p1_coords.addWidget(self._p1_x)
        p1_coords.addWidget(label("Y", C['muted'], 10))
        self._p1_y = QSpinBox(); self._p1_y.setRange(0, 99999)
        self._p1_y.setStyleSheet(spin_style); self._p1_y.setFixedWidth(72)
        p1_coords.addWidget(self._p1_y)
        rlay.addLayout(p1_coords)

        p2_hdr = QHBoxLayout()
        p2_dot = QLabel("●")
        p2_dot.setStyleSheet(f"color:{C['accent']}; font-size:13px;")
        p2_hdr.addWidget(p2_dot)
        p2_hdr.addWidget(label("P2", C['accent'], 11, True))
        p2_hdr.addStretch()
        self._p2_apply_btn = QPushButton("Apply")
        self._p2_apply_btn.setFixedSize(44, 20)
        self._p2_apply_btn.setStyleSheet(f"""
            QPushButton {{
                background:{C['accent']}22; border:1px solid {C['accent']}66;
                border-radius:3px; color:{C['accent']}; font-size:9px; font-weight:bold;
            }}
            QPushButton:hover {{ background:{C['accent']}44; }}
        """)
        p2_hdr.addWidget(self._p2_apply_btn)
        rlay.addLayout(p2_hdr)

        p2_coords = QHBoxLayout()
        p2_coords.setSpacing(4)
        p2_coords.addWidget(label("X", C['muted'], 10))
        self._p2_x = QSpinBox(); self._p2_x.setRange(0, 99999)
        self._p2_x.setStyleSheet(spin_style); self._p2_x.setFixedWidth(72)
        p2_coords.addWidget(self._p2_x)
        p2_coords.addWidget(label("Y", C['muted'], 10))
        self._p2_y = QSpinBox(); self._p2_y.setRange(0, 99999)
        self._p2_y.setStyleSheet(spin_style); self._p2_y.setFixedWidth(72)
        p2_coords.addWidget(self._p2_y)
        rlay.addLayout(p2_coords)

        self._dist_lbl = label("Distance: —", C['muted'], 11)
        rlay.addWidget(self._dist_lbl)

        self._p1_apply_btn.clicked.connect(self._apply_p1_manual)
        self._p2_apply_btn.clicked.connect(self._apply_p2_manual)

        rlay.addWidget(separator())

        rlay.addWidget(label("3rd CLICK BEHAVIOR", C['muted'], 10, True))
        self._replace_grp = QButtonGroup()
        r1 = QRadioButton("Replace nearest")
        r2 = QRadioButton("Block third")
        r1.setChecked(True)
        for r in (r1, r2):
            r.setStyleSheet(f"color:{C['muted']}; font-size:10px;")
            self._replace_grp.addButton(r)
            rlay.addWidget(r)
        self._replace_grp.buttonToggled.connect(self._update_replace_mode)
        rlay.addWidget(separator())

        rlay.addWidget(label("QUEUE", C['muted'], 10, True))
        self._queue_lbl = label("No queue", C['muted'], 10)
        rlay.addWidget(self._queue_lbl)
        nav = QHBoxLayout()
        self._prev_btn = btn("◀ Prev", C['muted'], True)
        self._next_btn = btn("Next ▶", C['muted'], True)
        self._prev_btn.clicked.connect(self._prev_image)
        self._next_btn.clicked.connect(self._next_image)
        nav.addWidget(self._prev_btn)
        nav.addWidget(self._next_btn)
        rlay.addLayout(nav)
        rlay.addWidget(separator())

        rlay.addStretch()

        self._reset_btn = btn("↺  Reset Points", C['yellow'])
        self._save_btn = btn("✓  Save to Dataset", C['green'])
        self._reset_btn.clicked.connect(self._reset_points)
        self._save_btn.clicked.connect(self._save_entry)
        rlay.addWidget(self._reset_btn)
        rlay.addWidget(self._save_btn)

        main.addWidget(right)

    def load_queue(self, paths: list, prepend=False):
        if prepend:
            self._queue = list(paths) + self._queue
            self._queue_idx = 0
        else:
            self._queue.extend(paths)
            if len(paths) > 0 and self._current_orig is None:
                self._queue_idx = len(self._queue) - len(paths)
        self._load_current()
        self.status_bar.update_stats(queue=len(self._queue))

    def load_for_edit(self, entry: dict):
        self._edit_id = entry["id"]
        img_path = Path(entry["original_path"])
        if not img_path.exists():
            img_path = CAPTURED_DIR / entry["filename"]
        if not img_path.exists():
            self.toast.show_message("Original image not found!", error=True)
            return
        self._queue.insert(0, img_path)
        self._queue_idx = 0
        pts = [(p["x"], p["y"]) for p in entry.get("points", [])]
        self._load_current()
        self.canvas.set_points(pts)
        self._update_point_display()

    def _load_current(self):
        if not self._queue or self._queue_idx >= len(self._queue):
            self._dim_lbl.setText("Queue empty")
            self._file_lbl.setText("—")
            self._size_lbl.setText("—")
            self._queue_lbl.setText("Queue empty")
            return

        path = self._queue[self._queue_idx]
        bgr = cv2.imread(str(path))
        if bgr is None:
            self.toast.show_message(f"Cannot read: {path.name}", error=True)
            return

        self._current_orig = bgr
        self._current_path = path
        h, w = bgr.shape[:2]
        self._dim_lbl.setText(f"{w} × {h} px")
        self._file_lbl.setText(path.name)
        self._size_lbl.setText(f"{w}×{h}")
        self.canvas.load_image(bgr)
        self._preview_chk.setChecked(False)

        pos = self._queue_idx + 1
        total = len(self._queue)
        self._queue_lbl.setText(f"{pos} / {total}")
        self._prev_btn.setEnabled(self._queue_idx > 0)
        self._next_btn.setEnabled(self._queue_idx < total - 1)
        self._update_point_display()
        self.status_bar.update_stats(queue=total - self._queue_idx)

    def _on_point_placed(self, ox, oy):
        pts = self.canvas.get_points()
        mode = "nearest" if self._replace_grp.buttons()[0].isChecked() else "block"
        if len(pts) < 2:
            pts.append((ox, oy))
        else:
            if mode == "block":
                return
            else:
                d0 = math.dist((ox, oy), pts[0])
                d1 = math.dist((ox, oy), pts[1])
                idx = 0 if d0 < d1 else 1
                pts[idx] = (ox, oy)
        self.canvas.set_points(pts)
        self._update_point_display()

    def _on_mouse_moved(self, ox, oy):
        self._coord_lbl.setText(f"X: {ox}  Y: {oy}")

    def _update_point_display(self):
        pts = self.canvas.get_points()
        for w in (self._p1_x, self._p1_y, self._p2_x, self._p2_y):
            w.blockSignals(True)
        if len(pts) >= 1:
            self._p1_x.setValue(pts[0][0])
            self._p1_y.setValue(pts[0][1])
        else:
            self._p1_x.setValue(0)
            self._p1_y.setValue(0)
        if len(pts) >= 2:
            self._p2_x.setValue(pts[1][0])
            self._p2_y.setValue(pts[1][1])
            d = math.dist(pts[0], pts[1])
            self._dist_lbl.setText(f"Distance: {d:.1f} px")
        else:
            self._p2_x.setValue(0)
            self._p2_y.setValue(0)
            self._dist_lbl.setText("Distance: —")
        for w in (self._p1_x, self._p1_y, self._p2_x, self._p2_y):
            w.blockSignals(False)

    def _apply_p1_manual(self):
        if self._current_orig is None:
            return
        h, w = self._current_orig.shape[:2]
        x = max(0, min(self._p1_x.value(), w - 1))
        y = max(0, min(self._p1_y.value(), h - 1))
        pts = self.canvas.get_points()
        if len(pts) >= 1:
            pts[0] = (x, y)
        else:
            pts = [(x, y)]
        self.canvas.set_points(pts)
        self._update_point_display()

    def _apply_p2_manual(self):
        if self._current_orig is None:
            return
        h, w = self._current_orig.shape[:2]
        x = max(0, min(self._p2_x.value(), w - 1))
        y = max(0, min(self._p2_y.value(), h - 1))
        pts = self.canvas.get_points()
        if len(pts) == 0:
            pts = [(0, 0), (x, y)]
        elif len(pts) == 1:
            pts.append((x, y))
        else:
            pts[1] = (x, y)
        self.canvas.set_points(pts)
        self._update_point_display()

    def _update_replace_mode(self):
        mode = "nearest" if self._replace_grp.buttons()[0].isChecked() else "block"
        self.canvas.set_replace_mode(mode)

    def _reset_points(self):
        self.canvas.reset_points()
        self._update_point_display()

    def _prev_image(self):
        if self._queue_idx > 0:
            self._queue_idx -= 1
            self._edit_id = None
            self._load_current()

    def _next_image(self):
        if self._queue_idx < len(self._queue) - 1:
            self._queue_idx += 1
            self._edit_id = None
            self._load_current()

    def _toggle_preview(self, checked):
        self.canvas.set_preview_mode(checked)
        self.canvas._redraw()

    def _save_entry(self):
        pts = self.canvas.get_points()
        if len(pts) < 2:
            self.toast.show_message("Place exactly 2 points first!", error=True)
            return
        if self._current_orig is None:
            return

        path = self._current_path
        fname = path.name
        h, w = self._current_orig.shape[:2]
        thresh = apply_threshold(self._current_orig)

        out_orig = ORIG_DIR / fname
        out_thresh = THRESH_DIR / fname
        cv2.imwrite(str(out_orig), self._current_orig)
        cv2.imwrite(str(out_thresh), thresh)

        dist = math.dist(pts[0], pts[1])
        entry_id = self._edit_id if self._edit_id else str(uuid.uuid4())

        entry = {
            "id": entry_id,
            "filename": fname,
            "original_path": str(out_orig),
            "thresholded_path": str(out_thresh),
            "width": w,
            "height": h,
            "points": [
                {"label": "point_1", "x": pts[0][0], "y": pts[0][1]},
                {"label": "point_2", "x": pts[1][0], "y": pts[1][1]},
            ],
            "pixel_distance": round(dist, 2),
            "timestamp": datetime.now().isoformat(timespec='seconds'),
        }

        if self._edit_id:
            STORE.update(self._edit_id, entry)
        else:
            STORE.add(entry)

        self._edit_id = None
        self._queue.pop(self._queue_idx)
        if self._queue_idx >= len(self._queue):
            self._queue_idx = max(0, len(self._queue) - 1)

        remaining = len(self._queue)
        self.toast.show_message(f"Saved! {remaining} images remaining in queue.")
        self.dataset_updated.emit()
        self.status_bar.update_stats(queue=remaining)
        self._load_current()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_R:
            self._reset_points()
        elif key == Qt.Key.Key_Space:
            self._next_image()
        elif event.modifiers() == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_S:
            self._save_entry()
        else:
            super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4 – DATASET
# ─────────────────────────────────────────────────────────────────────────────

class ViewDialog(QDialog):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"View: {entry['filename']}")
        self.setMinimumSize(900, 500)
        self.setStyleSheet(STYLE)
        lay = QHBoxLayout(self)

        for key, title_txt in [("original_path", "Original"),
                               ("thresholded_path", "Thresholded + Points")]:
            box = QVBoxLayout()
            box.addWidget(label(title_txt, C['muted'], 10, True))
            img_lbl = QLabel()
            img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_lbl.setMinimumSize(380, 420)
            path = Path(entry.get(key, ""))
            if path.exists():
                arr = cv2.imread(str(path))
                h_o, w_o = arr.shape[:2]
                pts_orig = [(p["x"], p["y"]) for p in entry.get("points", [])]
                pm = ndarray_to_qpixmap(arr)
                if key == "thresholded_path" and pts_orig:
                    pm = draw_points_on_pixmap(pm, pts_orig)
                pm = pm.scaled(380, 420, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                img_lbl.setPixmap(pm)
            else:
                img_lbl.setText("File not found")
            box.addWidget(img_lbl)
            lay.addLayout(box)


class DatasetSection(QWidget):
    edit_requested = pyqtSignal(dict)

    def __init__(self, status_bar: AppStatusBar, toast: Toast):
        super().__init__()
        self.status_bar = status_bar
        self.toast = toast
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        hdr = QHBoxLayout()
        hdr.addWidget(label("◫  DATASET", C['yellow'], 13, True))
        hdr.addStretch()
        self._count_lbl = label("0 entries", C['muted'], 11)
        hdr.addWidget(self._count_lbl)
        refresh_btn = btn("↺ Refresh", C['muted'], True)
        refresh_btn.clicked.connect(self.refresh)
        hdr.addWidget(refresh_btn)
        export_btn = btn("↓ Export CSV", C['yellow'], True)
        export_btn.clicked.connect(self._export_csv)
        hdr.addWidget(export_btn)
        lay.addLayout(hdr)
        lay.addWidget(separator())

        self._table = QTableWidget()
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels([
            "Filename", "Original", "Thresholded+pts", "P1", "P2", "Distance", "", ""
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in (1, 2):
            self._table.setColumnWidth(i, 90)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setColumnWidth(6, 60)
        self._table.setColumnWidth(7, 60)
        self._table.verticalHeader().setDefaultSectionSize(80)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self._table, 1)
        self.refresh()

    def refresh(self):
        entries = STORE.load()
        self._count_lbl.setText(f"{len(entries)} entries")
        self._table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            self._table.setItem(row, 0, QTableWidgetItem(entry.get("filename", "")))

            for col, path_key in [(1, "original_path"), (2, "thresholded_path")]:
                path = Path(entry.get(path_key, ""))
                thumb_lbl = QLabel()
                thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                if path.exists():
                    arr = cv2.imread(str(path))
                    pts_orig = [(p["x"], p["y"]) for p in entry.get("points", [])]
                    pm = ndarray_to_qpixmap(arr)
                    if col == 2 and pts_orig:
                        h_o, w_o = arr.shape[:2]
                        pm = draw_points_on_pixmap(pm, pts_orig)
                    pm = pm.scaled(80, 70, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                    thumb_lbl.setPixmap(pm)
                else:
                    thumb_lbl.setText("N/A")
                    thumb_lbl.setStyleSheet(f"color:{C['muted']};")
                self._table.setCellWidget(row, col, thumb_lbl)

            pts = entry.get("points", [{}, {}])
            p1 = pts[0] if pts else {}
            p2 = pts[1] if len(pts) > 1 else {}
            self._table.setItem(row, 3, QTableWidgetItem(
                f"({p1.get('x','?')}, {p1.get('y','?')})"))
            self._table.setItem(row, 4, QTableWidgetItem(
                f"({p2.get('x','?')}, {p2.get('y','?')})"))
            self._table.setItem(row, 5, QTableWidgetItem(
                str(entry.get("pixel_distance", "?"))))

            view_btn = btn("View", C['accent'], True)
            edit_btn = btn("Edit", C['yellow'], True)
            del_btn  = btn("Del",  C['red'],    True)
            view_btn.clicked.connect(lambda _, e=entry: self._view(e))
            edit_btn.clicked.connect(lambda _, e=entry: self.edit_requested.emit(e))
            del_btn.clicked.connect(lambda _, e=entry: self._delete(e))

            cell_w = QWidget()
            cell_lay = QHBoxLayout(cell_w)
            cell_lay.setContentsMargins(2, 2, 2, 2)
            cell_lay.setSpacing(4)
            cell_lay.addWidget(view_btn)
            cell_lay.addWidget(edit_btn)
            cell_lay.addWidget(del_btn)
            self._table.setCellWidget(row, 6, cell_w)
            self._table.setSpan(row, 6, 1, 2)

        self.status_bar.update_stats(total=len(entries))

    def _view(self, entry: dict):
        dlg = ViewDialog(entry, self)
        dlg.exec()

    def _delete(self, entry: dict):
        reply = QMessageBox.question(
            self, "Delete Entry",
            f"Delete annotation for:\n{entry['filename']}\n\nAlso delete image files?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return
        delete_files = (reply == QMessageBox.StandardButton.Yes)
        STORE.delete(entry["id"])
        if delete_files:
            for key in ("original_path", "thresholded_path"):
                p = Path(entry.get(key, ""))
                if p.exists():
                    p.unlink()
        self.toast.show_message("Entry deleted.")
        self.refresh()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", str(ROOT / "dataset_export.csv"), "CSV Files (*.csv)")
        if path:
            STORE.export_csv(path)
            self.toast.show_message(f"Exported to {Path(path).name}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5 – MODEL TRAINING
# ─────────────────────────────────────────────────────────────────────────────

class TrainingThread(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, entries, img_size, epochs, test_split_percent, parent=None):
        super().__init__(parent)
        self.entries = entries
        self.img_size = img_size
        self.epochs = epochs
        self.test_split = test_split_percent / 100.0

    def _load_data(self):
        X, y, sizes = [], [], []
        for entry in self.entries:
            path = Path(entry.get("thresholded_path", ""))
            if not path.exists():
                orig = Path(entry.get("original_path", ""))
                if orig.exists():
                    img = apply_threshold(cv2.imread(str(orig)))
                else:
                    continue
            else:
                img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

            if img is None:
                continue

            img = cv2.resize(img, self.img_size)
            img = img.astype(np.float32) / 255.0
            img = np.expand_dims(img, axis=-1)

            w, h = entry["width"], entry["height"]
            pts = entry["points"]
            coords = [
                pts[0]["x"] / w, pts[0]["y"] / h,
                pts[1]["x"] / w, pts[1]["y"] / h,
            ]

            X.append(img)
            y.append(coords)
            sizes.append((w, h))

        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32), sizes

    def _build_model(self, input_shape):
        model = tf.keras.Sequential([
            tf.keras.layers.Input(shape=input_shape),
            tf.keras.layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(256, (3, 3), activation='relu', padding='same'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Conv2D(256, (3, 3), activation='relu', padding='same'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(512, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.4),
            tf.keras.layers.Dense(256, activation='relu'),
            tf.keras.layers.BatchNormalization(),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(128, activation='relu'),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(4, activation='sigmoid')
        ])
        optimizer = tf.keras.optimizers.Adam(learning_rate=1e-3)
        model.compile(optimizer=optimizer, loss='mse', metrics=['mae'])
        return model

    def run(self):
        try:
            self.log.emit("Loading dataset...")
            X, y, sizes = self._load_data()

            if len(X) < 10:
                self.error.emit("Not enough valid images after loading.")
                return

            n = len(X)
            indices = np.random.RandomState(42).permutation(n)
            split_idx = int(n * (1 - self.test_split))
            train_idx = indices[:split_idx]
            test_idx = indices[split_idx:]

            X_train, y_train = X[train_idx], y[train_idx]
            X_test, y_test = X[test_idx], y[test_idx]
            test_sizes = [sizes[i] for i in test_idx]

            self.log.emit(f"Train: {len(X_train)}  |  Test: {len(X_test)}")

            model = self._build_model((self.img_size[0], self.img_size[1], 1))

            class ProgressCallback(tf.keras.callbacks.Callback):
                def __init__(self, signal):
                    super().__init__()
                    self.signal = signal
                def on_epoch_end(self, epoch, logs=None):
                    pct = int((epoch + 1) / self.params['epochs'] * 100)
                    self.signal.emit(pct)

            callbacks = [
                tf.keras.callbacks.EarlyStopping(patience=20, restore_best_weights=True, verbose=0),
                ProgressCallback(self.progress)
            ]

            self.log.emit("Training started...")
            history = model.fit(
                X_train, y_train,
                validation_split=0.1,
                epochs=self.epochs,
                batch_size=16,
                callbacks=callbacks,
                verbose=0
            )

            actual_epochs = len(history.history['loss'])

            self.log.emit("Evaluating...")
            test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)
            y_pred = model.predict(X_test, verbose=0)

            # Pixel-distance accuracy
            pixel_errors = []
            for i in range(len(y_test)):
                w, h = test_sizes[i]
                true_pts = y_test[i] * [w, h, w, h]
                pred_pts = y_pred[i] * [w, h, w, h]
                d1 = np.linalg.norm(true_pts[0:2] - pred_pts[0:2])
                d2 = np.linalg.norm(true_pts[2:4] - pred_pts[2:4])
                pixel_errors.append((d1, d2))

            pixel_errors = np.array(pixel_errors)
            acc_10 = np.mean((pixel_errors[:, 0] < 10) & (pixel_errors[:, 1] < 10)) * 100
            acc_20 = np.mean((pixel_errors[:, 0] < 20) & (pixel_errors[:, 1] < 20)) * 100
            mean_err = np.mean(pixel_errors)

            # Versioned save
            version = 1
            while True:
                fname = f"CNN_BELMOUNTH_MODEL_V{version}.h5"
                fpath = MODEL_DIR / fname
                if not fpath.exists():
                    break
                version += 1

            # Save model without optimizer for better Keras 3 compatibility
            model.save(str(fpath))

            self.finished.emit({
                "test_loss": float(test_loss),
                "test_mae": float(test_mae),
                "acc_10px": float(acc_10),
                "acc_20px": float(acc_20),
                "mean_pixel_error": float(mean_err),
                "epochs": actual_epochs,
                "saved_path": str(fpath),
                "train_count": len(X_train),
                "test_count": len(X_test),
            })

        except Exception as e:
            self.error.emit(str(e))


class PreviewWorker(QObject):
    finished = pyqtSignal(dict)  # {pixmap, size_text}

    def __init__(self, img_path):
        super().__init__()
        self.img_path = img_path

    def run(self):
        try:
            # Load image
            bgr = cv2.imread(self.img_path)
            if bgr is None:
                self.finished.emit({"pixmap": None, "size_text": "Failed to load"})
                return

            h, w = bgr.shape[:2]
            size_text = f"Image size: {w}×{h}"

            # Apply same threshold as model training (CRITICAL!)
            thresh = apply_threshold(bgr)

            # Convert grayscale to RGB for QImage
            rgb = cv2.cvtColor(thresh, cv2.COLOR_GRAY2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            pixmap = pixmap.scaledToHeight(180, Qt.TransformationMode.FastTransformation)

            self.finished.emit({"pixmap": pixmap, "size_text": size_text})
        except Exception as e:
            self.finished.emit({"pixmap": None, "size_text": f"Error: {str(e)}"})


class InferenceThread(QThread):
    finished = pyqtSignal(dict)  # {p1, p2, distance, preview_pixmap}
    error = pyqtSignal(str)

    _model_cache = {}  # {path: model}

    def __init__(self, img_path: Path, model_path: Path, img_size=(640, 480), parent=None):
        super().__init__(parent)
        self.img_path = img_path
        self.model_path = model_path
        self.img_size = img_size

    def run(self):
        if not self.model_path.exists():
            self.error.emit("No trained model found.")
            return
        if not _TF_AVAILABLE:
            self.error.emit("TensorFlow is not installed.")
            return

        try:
            # Load image
            bgr = cv2.imread(str(self.img_path))
            if bgr is None:
                self.error.emit("Failed to load image.")
                return

            h, w = bgr.shape[:2]
            if (w, h) != self.img_size:
                self.error.emit(f"Image must be {self.img_size[0]}×{self.img_size[1]} pixels. Got {w}×{h}.")
                return

            # Apply SAME thresholding as training (CRITICAL!)
            thresh = apply_threshold(bgr)
            # Normalize to [0, 1]
            gray = thresh.astype(np.float32) / 255.0

            # Load model (with caching) - use compile=False for Keras 3 compatibility
            model_key = str(self.model_path)
            if model_key not in InferenceThread._model_cache:
                try:
                    model = tf.keras.models.load_model(model_key, compile=False)
                    InferenceThread._model_cache[model_key] = model
                except Exception as e:
                    self.error.emit(f"Model loading failed: {str(e)}\n\nTry retraining the model.")
                    return
            model = InferenceThread._model_cache[model_key]

            # Predict
            pred = model.predict(np.array([gray]), verbose=0)[0]  # [x1, y1, x2, y2] normalized

            # Convert to pixel coordinates
            p1_x, p1_y = int(pred[0] * self.img_size[0]), int(pred[1] * self.img_size[1])
            p2_x, p2_y = int(pred[2] * self.img_size[0]), int(pred[3] * self.img_size[1])
            p1 = (p1_x, p1_y)
            p2 = (p2_x, p2_y)
            distance = math.dist(p1, p2)

            # Draw on thresholded image (same as what model saw)
            vis = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            cv2.circle(vis, p1, 8, (0, 220, 80), -1)   # Green P1
            cv2.circle(vis, p2, 8, (80, 160, 255), -1)  # Blue P2
            cv2.line(vis, p1, p2, (255, 80, 80), 2)     # Red line
            cv2.putText(vis, "P1", (p1[0] + 12, p1[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 80), 2)
            cv2.putText(vis, "P2", (p2[0] + 12, p2[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80, 160, 255), 2)
            cv2.putText(vis, f"{distance:.1f}px", ((p1[0] + p2[0]) // 2 - 30, (p1[1] + p2[1]) // 2 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 80, 80), 2)

            # Convert to QPixmap
            rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)

            self.finished.emit({
                "p1": p1,
                "p2": p2,
                "distance": round(distance, 2),
                "preview": pixmap
            })
        except Exception as e:
            self.error.emit(f"Inference error: {str(e)}")


class ZoomableImageViewer(QDialog):
    def __init__(self, image_path: str, p1=None, p2=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Viewer")
        self.setGeometry(100, 100, 900, 700)
        self.p1 = p1
        self.p2 = p2
        self.zoom_level = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Load original image and draw points
        pixmap = QPixmap(image_path)
        if p1 is not None and p2 is not None:
            pixmap = self._draw_points_on_pixmap(pixmap, p1, p2)

        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self.pixmap_item)

        layout.addWidget(self.view)

        controls_layout = QHBoxLayout()

        zoom_in_btn = QPushButton("🔍+ (Scroll Up)")
        zoom_in_btn.clicked.connect(self.zoom_in)
        controls_layout.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("🔍- (Scroll Down)")
        zoom_out_btn.clicked.connect(self.zoom_out)
        controls_layout.addWidget(zoom_out_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_zoom)
        controls_layout.addWidget(reset_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        self.view.wheelEvent = self.wheelEvent

    def _draw_points_on_pixmap(self, pixmap: QPixmap, p1, p2):
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw line between points
        pen = QPen(QColor(0, 255, 0))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

        # Draw circle at p1 (red)
        painter.setBrush(QBrush(QColor(255, 0, 0, 100)))
        painter.setPen(QPen(QColor(255, 0, 0), 2))
        painter.drawEllipse(int(p1[0]) - 5, int(p1[1]) - 5, 10, 10)

        # Draw circle at p2 (blue)
        painter.setBrush(QBrush(QColor(0, 0, 255, 100)))
        painter.setPen(QPen(QColor(0, 0, 255), 2))
        painter.drawEllipse(int(p2[0]) - 5, int(p2[1]) - 5, 10, 10)

        painter.end()
        return pixmap

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()

    def zoom_in(self):
        self.zoom_level *= 1.1
        self.apply_zoom()

    def zoom_out(self):
        self.zoom_level /= 1.1
        self.apply_zoom()

    def reset_zoom(self):
        self.zoom_level = 1.0
        self.apply_zoom()
        self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def apply_zoom(self):
        self.view.resetTransform()
        self.view.scale(self.zoom_level, self.zoom_level)


class ModelSection(QWidget):
    def __init__(self, status_bar: AppStatusBar, toast: Toast):
        super().__init__()
        self.status_bar = status_bar
        self.toast = toast
        self._thread = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(14)
        lay.setContentsMargins(16, 16, 16, 16)

        # Header
        hdr = QHBoxLayout()
        hdr.addWidget(label("◉  MODEL", C['accent2'], 13, True))
        hdr.addStretch()
        self._count_lbl = label("Dataset: 0", C['muted'], 11)
        hdr.addWidget(self._count_lbl)
        lay.addLayout(hdr)
        lay.addWidget(separator())

        # TensorFlow warning
        if not _TF_AVAILABLE:
            warn = QLabel("⚠  TensorFlow not installed. Training is disabled.\n"
                          "Run:  pip install tensorflow")
            warn.setStyleSheet(f"color:{C['red']}; font-size:11px; padding:4px;")
            warn.setWordWrap(True)
            lay.addWidget(warn)

        # Requirement note
        req = QLabel("Minimum 500 annotated images required to unlock training.")
        req.setStyleSheet(f"color:{C['yellow']}; font-size:11px;")
        req.setWordWrap(True)
        lay.addWidget(req)

        # Config row
        cfg = QHBoxLayout()
        cfg.setSpacing(10)

        cfg.addWidget(label("Img Size:", C['muted'], 10))
        self._size_combo = QComboBox()
        self._size_combo.addItems(["640×480"])
        self._size_combo.setCurrentIndex(0)
        self._size_combo.setEnabled(False)
        cfg.addWidget(self._size_combo)

        cfg.addWidget(label("Epochs:", C['muted'], 10))
        self._epoch_spin = QSpinBox()
        self._epoch_spin.setRange(10, 500)
        self._epoch_spin.setValue(150)
        cfg.addWidget(self._epoch_spin)

        cfg.addWidget(label("Test %:", C['muted'], 10))
        self._split_spin = QSpinBox()
        self._split_spin.setRange(10, 40)
        self._split_spin.setValue(20)
        self._split_spin.setSuffix("%")
        cfg.addWidget(self._split_spin)

        cfg.addStretch()
        lay.addLayout(cfg)

        # Train button
        self._train_btn = btn("▶  Start Training", C['green'])
        self._train_btn.setMinimumHeight(40)
        self._train_btn.clicked.connect(self._start_training)
        lay.addWidget(self._train_btn)

        # Progress
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        lay.addWidget(self._progress)

        # Log
        self._log_lbl = QLabel("Ready")
        self._log_lbl.setStyleSheet(f"color:{C['muted']}; font-size:11px;")
        self._log_lbl.setWordWrap(True)
        lay.addWidget(self._log_lbl)

        lay.addWidget(separator())

        # Results panel
        self._results_box = QGroupBox("TRAINING RESULTS")
        self._results_box.hide()
        rlay = QVBoxLayout(self._results_box)
        rlay.setSpacing(6)

        self._res_loss   = label("Test Loss (MSE): —", C['text'], 11)
        self._res_mae    = label("Test MAE: —", C['text'], 11)
        self._res_acc10  = label("Accuracy (<10 px): —", C['green'], 11)
        self._res_acc20  = label("Accuracy (<20 px): —", C['green'], 11)
        self._res_mean   = label("Mean Pixel Error: —", C['text'], 11)
        self._res_epochs = label("Epochs Trained: —", C['muted'], 11)
        self._res_path   = label("Saved: —", C['muted'], 10)
        self._res_path.setWordWrap(True)

        for w in (self._res_loss, self._res_mae, self._res_acc10,
                  self._res_acc20, self._res_mean, self._res_epochs, self._res_path):
            rlay.addWidget(w)

        lay.addWidget(self._results_box)
        lay.addWidget(separator())

        # Model selector section
        model_row = QHBoxLayout()
        model_row.addWidget(label("Select Model:", C['muted'], 10))
        self._model_combo = QComboBox()
        self._model_combo.setMinimumWidth(150)
        self._refresh_model_list()
        model_row.addWidget(self._model_combo)
        model_row.addStretch()
        lay.addLayout(model_row)

        # Test image section
        lay.addWidget(label("TEST IMAGE", C['muted'], 10, True))

        test_path_row = QHBoxLayout()
        test_path_row.addWidget(label("Path:", C['muted'], 10))
        self._test_path_input = QLineEdit()
        self._test_path_input.setPlaceholderText("Paste image path here or drag & drop")
        self._test_path_input.setStyleSheet(f"""
            QLineEdit {{
                background:{C['surface']}; border:1px solid {C['border']};
                border-radius:4px; color:{C['text']}; padding:4px;
                font-size:10px; font-family:'Consolas','Courier New',monospace;
            }}
            QLineEdit:focus {{ border-color:{C['accent']}; }}
        """)
        self._test_path_input.textChanged.connect(self._on_test_path_changed)
        test_path_row.addWidget(self._test_path_input)
        lay.addLayout(test_path_row)

        test_btn_row = QHBoxLayout()
        self._run_test_btn = btn("▶ Infer", C['accent'], True)
        self._run_test_btn.setEnabled(False)
        self._run_test_btn.clicked.connect(self._run_inference)
        test_btn_row.addWidget(self._run_test_btn)
        test_btn_row.addStretch()
        lay.addLayout(test_btn_row)

        self._test_preview = QLabel()
        self._test_preview.setMinimumHeight(180)
        self._test_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._test_preview.setStyleSheet(f"""
            background:{C['surface']}; border:1px solid {C['border']};
            border-radius:6px; color:{C['muted']}; font-size:10px;
        """)
        self._test_preview.setText("Preview will appear here")
        lay.addWidget(self._test_preview)

        self._test_result_lbl = label("—", C['muted'], 10)
        self._test_result_lbl.setWordWrap(True)
        lay.addWidget(self._test_result_lbl)

        lay.addStretch()

        self._test_image_path = None
        self._infer_thread = None
        self._full_inference_pixmap = None
        self._inference_p1 = None
        self._inference_p2 = None
        self._test_preview.mousePressEvent = self._on_preview_clicked

    def refresh(self):
        entries = STORE.load()
        n = len(entries)
        self._count_lbl.setText(f"Dataset: {n}")
        if n < 500 or not _TF_AVAILABLE:
            self._train_btn.setEnabled(False)
            if n < 500:
                self._train_btn.setToolTip(f"Need {500 - n} more images")
            else:
                self._train_btn.setToolTip("TensorFlow not available")
        else:
            self._train_btn.setEnabled(True)
            self._train_btn.setToolTip("")

    def _start_training(self):
        entries = STORE.load()
        if len(entries) < 500:
            self.toast.show_message("Dataset too small! Need 500+ images.", error=True)
            return

        size_txt = self._size_combo.currentText()
        img_size = tuple(int(x) for x in size_txt.split("×"))
        epochs = self._epoch_spin.value()
        split = self._split_spin.value()

        self._train_btn.setEnabled(False)
        self._progress.setValue(0)
        self._results_box.hide()
        self._log_lbl.setText("Initializing...")

        self._thread = TrainingThread(entries, img_size, epochs, split)
        self._thread.progress.connect(self._progress.setValue)
        self._thread.log.connect(self._log_lbl.setText)
        self._thread.finished.connect(self._on_training_finished)
        self._thread.error.connect(self._on_training_error)
        self._thread.start()

    def _on_training_finished(self, results: dict):
        self._train_btn.setEnabled(True)
        self._progress.setValue(100)

        self._res_loss.setText(f"Test Loss (MSE): {results['test_loss']:.4f}")
        self._res_mae.setText(f"Test MAE: {results['test_mae']:.4f}")
        self._res_acc10.setText(f"Accuracy (<10 px): {results['acc_10px']:.1f}%")
        self._res_acc20.setText(f"Accuracy (<20 px): {results['acc_20px']:.1f}%")
        self._res_mean.setText(f"Mean Pixel Error: {results['mean_pixel_error']:.2f} px")
        self._res_epochs.setText(f"Epochs Trained: {results['epochs']}")
        self._res_path.setText(f"Saved: {results['saved_path']}")

        self._results_box.show()
        self._log_lbl.setText(
            f"Done — Train: {results['train_count']}  Test: {results['test_count']}"
        )
        self._refresh_model_list()
        self.toast.show_message("Training complete! Model saved.")

    def _on_training_error(self, msg: str):
        self._train_btn.setEnabled(True)
        self._log_lbl.setText(f"Error: {msg}")
        self.toast.show_message(f"Training failed: {msg}", error=True)

    def _on_test_path_changed(self, text: str):
        """Handle image path input (no file dialog to avoid freezing)."""
        text = text.strip()
        if not text:
            self._run_test_btn.setEnabled(False)
            self._test_preview.setText("No image selected")
            self._test_result_lbl.setText("—")
            return

        path = Path(text)
        if not path.exists():
            self._run_test_btn.setEnabled(False)
            self._test_preview.setText(f"File not found:\n{text}")
            self._test_result_lbl.setText("—")
            return

        if path.is_file():
            self._test_image_path = path
            self._run_test_btn.setEnabled(True)
            self._test_preview.setText("Loading preview...")
            self._test_result_lbl.setText("—")

            # Load preview in background thread
            if hasattr(self, '_preview_thread') and self._preview_thread:
                self._preview_thread.quit()
                self._preview_thread.wait()

            thread = QThread()
            worker = PreviewWorker(str(path))
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            worker.finished.connect(self._on_preview_loaded)
            worker.finished.connect(thread.quit)
            worker.finished.connect(lambda: self._cleanup_thread(thread))
            thread.start()
            self._preview_thread = thread

    def _cleanup_thread(self, thread):
        """Safely clean up thread."""
        thread.wait()

    def _on_preview_loaded(self, result: dict):
        pixmap = result.get("pixmap")
        if pixmap:
            self._test_preview.setPixmap(pixmap)
        self._test_result_lbl.setText(result.get("size_text", "—"))

    def _refresh_model_list(self):
        self._model_combo.clear()
        models = sorted([p.name for p in MODEL_DIR.glob("CNN_BELMOUNTH_MODEL_V*.h5")])
        if models:
            self._model_combo.addItems(models)
            self._model_combo.setCurrentIndex(len(models) - 1)
        else:
            self._model_combo.addItem("No models found")
            self._model_combo.setEnabled(False)

    def _run_inference(self):
        if not self._test_image_path or not self._test_image_path.exists():
            self.toast.show_message("No image selected.", error=True)
            return

        # Get selected model
        selected = self._model_combo.currentText()
        if selected == "No models found":
            self.toast.show_message("No trained model found. Train first.", error=True)
            return

        model_path = MODEL_DIR / selected

        if not model_path.exists():
            self.toast.show_message("Selected model not found.", error=True)
            return

        self._run_test_btn.setEnabled(False)
        self._test_result_lbl.setText("Running inference...")

        size_txt = self._size_combo.currentText()
        img_size = tuple(int(x) for x in size_txt.split("×"))

        self._infer_thread = InferenceThread(self._test_image_path, model_path, img_size)
        self._infer_thread.finished.connect(self._on_inference_finished)
        self._infer_thread.error.connect(self._on_inference_error)
        self._infer_thread.start()

    def _on_inference_finished(self, result: dict):
        self._run_test_btn.setEnabled(True)
        p1 = result["p1"]
        p2 = result["p2"]
        dist = result["distance"]
        pm = result["preview"]
        self._full_inference_pixmap = pm
        self._inference_p1 = p1
        self._inference_p2 = p2
        pm = pm.scaledToHeight(180, Qt.TransformationMode.SmoothTransformation)
        self._test_preview.setPixmap(pm)
        self._test_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._test_result_lbl.setText(
            f"✓ P1: ({p1[0]}, {p1[1]})  |  P2: ({p2[0]}, {p2[1]})\n"
            f"Pixel Distance: {dist} px"
        )
        self._test_result_lbl.setStyleSheet(f"color:{C['green']}; font-size:10px;")
        self.toast.show_message(f"Inference done! Distance: {dist} px")

    def _on_preview_clicked(self, event):
        if self._test_image_path and self._test_image_path.exists():
            viewer = ZoomableImageViewer(str(self._test_image_path), self._inference_p1, self._inference_p2, self)
            viewer.exec()

    def _on_inference_error(self, msg: str):
        self._run_test_btn.setEnabled(True)
        self._test_result_lbl.setText(f"✕ {msg}")
        self._test_result_lbl.setStyleSheet(f"color:{C['red']}; font-size:10px;")
        self.toast.show_message(f"Inference failed: {msg}", error=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class NavButton(QPushButton):
    def __init__(self, idx, icon, text, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.setText(f"{icon}  {text}")
        self.setCheckable(True)
        self.setFixedHeight(48)
        self._update_style(False)

    def _update_style(self, active):
        if active:
            bg = C['accent'] + "22"
            border = C['accent']
            col = C['accent']
        else:
            bg = "transparent"
            border = "transparent"
            col = C['muted']
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg}; border: none;
                border-left: 3px solid {border};
                color: {col}; font-size: 12px; font-weight: bold;
                text-align: left; padding-left: 16px;
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: {C['hover']}; color: {C['text']};
                border-left: 3px solid {C['accent']};
            }}
        """)

    def setActive(self, active: bool):
        self._update_style(active)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Keypoint Annotation Tool")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        self.setStyleSheet(STYLE)

        self._status = AppStatusBar()
        self.setStatusBar(self._status)

        root = QWidget()
        self.setCentralWidget(root)
        main_lay = QHBoxLayout(root)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setFixedWidth(190)
        sidebar.setStyleSheet(f"""
            background: {C['surface']};
            border-right: 1px solid {C['border']};
        """)
        s_lay = QVBoxLayout(sidebar)
        s_lay.setContentsMargins(0, 0, 0, 0)
        s_lay.setSpacing(0)

        title_frame = QFrame()
        title_frame.setFixedHeight(60)
        title_frame.setStyleSheet(f"background:{C['panel']}; border-bottom:1px solid {C['border']};")
        tf_lay = QVBoxLayout(title_frame)
        tf_lay.setContentsMargins(16, 8, 16, 8)
        tf_lay.addWidget(label("KEYPOINT", C['accent'], 14, True))
        tf_lay.addWidget(label("ANNOTATOR", C['muted'], 10))
        s_lay.addWidget(title_frame)

        s_lay.addSpacing(16)
        self._nav_btns = []
        nav_items = [
            (0, "◉", "CAPTURE"),
            (1, "◈", "INBOX"),
            (2, "⬡", "ANNOTATE"),
            (3, "◫", "DATASET"),
            (4, "◉", "MODEL"),
        ]
        for idx, icon, text in nav_items:
            nb = NavButton(idx, icon, text)
            nb.clicked.connect(lambda _, i=idx: self._switch_tab(i))
            self._nav_btns.append(nb)
            s_lay.addWidget(nb)

        s_lay.addStretch()
        version_lbl = label("v1.0", C['muted'], 9)
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s_lay.addWidget(version_lbl)
        s_lay.addSpacing(8)
        main_lay.addWidget(sidebar)

        # ── Content stack ──
        self._stack = QWidget()
        content_lay = QVBoxLayout(self._stack)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.setSpacing(0)

        self._toast = Toast(self._stack)

        self._sections = []

        self._capture = CaptureSection(self._status)
        self._inbox = InboxSection(self._status)
        self._annotate = AnnotationSection(self._status, self._toast)
        self._dataset = DatasetSection(self._status, self._toast)
        self._model = ModelSection(self._status, self._toast)

        for sec in (self._capture, self._inbox, self._annotate, self._dataset, self._model):
            content_lay.addWidget(sec)
            self._sections.append(sec)

        main_lay.addWidget(self._stack, 1)

        # ── Wire signals ──
        self._inbox.send_to_annotation.connect(self._on_send_to_annotation)
        self._annotate.dataset_updated.connect(self._on_dataset_updated)
        self._dataset.edit_requested.connect(self._on_edit_requested)

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(
            self._annotate._save_entry)

        self._switch_tab(0)
        self._refresh_stats()

    def _switch_tab(self, idx: int):
        for i, (sec, nb) in enumerate(zip(self._sections, self._nav_btns)):
            sec.setVisible(i == idx)
            nb.setActive(i == idx)
            nb.setChecked(i == idx)
        if idx == 1:
            self._inbox.refresh()
        elif idx == 3:
            self._dataset.refresh()
        elif idx == 4:
            self._model.refresh()

    def _on_send_to_annotation(self, paths: list):
        self._annotate.load_queue(paths)
        self._switch_tab(2)
        self._toast.show_message(f"{len(paths)} image(s) added to annotation queue.")

    def _on_dataset_updated(self):
        self._refresh_stats()
        self._model.refresh()

    def _on_edit_requested(self, entry: dict):
        self._annotate.load_for_edit(entry)
        self._switch_tab(2)

    def _refresh_stats(self):
        entries = STORE.load()
        captured = list(CAPTURED_DIR.glob("*.png"))
        ds_names = {e["filename"] for e in entries}
        pending = sum(1 for p in captured if p.name not in ds_names)
        self._status.update_stats(
            total=len(entries),
            pending=pending,
            queue=len(self._annotate._queue)
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_toast'):
            pw = self._stack.width()
            self._toast.adjustSize()
            self._toast.move((pw - self._toast.width()) // 2, 20)

    def closeEvent(self, event):
        self._capture.closeEvent(event)
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Keypoint Annotator")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()