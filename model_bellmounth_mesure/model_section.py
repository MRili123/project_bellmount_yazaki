"""
Model Section – CNN Keypoint Predictor
=======================================
Drop-in section for the Keypoint Annotation Tool (app.py).

Add to MainWindow:
    self._model_section = ModelSection(self._status, self._toast)
    # add to self._sections list at index 4
    # add nav button (4, "⬟", "MODEL") to nav_items

Requires:
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
    (or CUDA variant)
    pip install pillow
"""

import os
import json
import math
import time
import threading
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QScrollArea, QSplitter, QGroupBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QAbstractItemView,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QComboBox, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont, QBrush

# Re-use palette + helpers from app.py  (import at runtime to avoid circular)
try:
    from __main__ import C, STYLE, btn, label, separator, DATASET_DIR, ORIG_DIR, THRESH_DIR
    from __main__ import ANNOTATIONS_FILE, MODEL_DIR, STORE, ndarray_to_qpixmap, apply_threshold
except ImportError:
    # Standalone testing fallback – define minimal stubs
    C = {
        "bg": "#0D0F14", "surface": "#141720", "panel": "#1A1E2A",
        "border": "#252A38", "accent": "#4F8EF7", "accent2": "#7C5CFC",
        "green": "#3DDB7E", "red": "#F75F5F", "yellow": "#F7C948",
        "text": "#E8ECF5", "muted": "#6B7394", "card": "#1E2330", "hover": "#252C3F",
    }
    ROOT = Path(__file__).parent
    DATASET_DIR = ROOT / "dataset"
    ORIG_DIR = DATASET_DIR / "original"
    THRESH_DIR = DATASET_DIR / "thresholded"
    ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
    MODEL_DIR = ROOT / "model"

    def label(text, color=None, size=12, bold=False):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color:{color or C['text']}; font-size:{size}px; font-weight:{'bold' if bold else 'normal'};")
        return lbl

    def btn(text, color=None, small=False):
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
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{C['border']}; background:{C['border']}; max-height:1px;")
        return line

    def ndarray_to_qpixmap(arr):
        if len(arr.shape) == 2:
            h, w = arr.shape
            qimg = QImage(arr.data, w, h, w, QImage.Format.Format_Grayscale8)
        else:
            h, w, ch = arr.shape
            rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(qimg.copy())

    def apply_threshold(bgr):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        th = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 31, 5)
        k = np.ones((3, 3), np.uint8)
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, k)
        return cv2.morphologyEx(th, cv2.MORPH_CLOSE, k)

    class STORE:
        @staticmethod
        def load():
            try:
                return json.loads(ANNOTATIONS_FILE.read_text())
            except Exception:
                return []

# ── Minimum dataset size ───────────────────────────────────────────────────────
MIN_SAMPLES_REQUIRED = 10   # warn below this
RECOMMENDED_SAMPLES  = 30   # flag as "good" above this

# ── Model input resolution ─────────────────────────────────────────────────────
INPUT_H, INPUT_W = 480, 640   # Test images must be exactly 640x480

# ── Model file ─────────────────────────────────────────────────────────────────
MODEL_PATH      = MODEL_DIR / "keypoint_cnn.pth"
HISTORY_PATH    = MODEL_DIR / "train_history.json"
META_PATH       = MODEL_DIR / "model_meta.json"

# ─────────────────────────────────────────────────────────────────────────────
# PyTorch / Torchvision – optional import
# ─────────────────────────────────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    import torchvision.transforms as T
    import torchvision.models as models
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    torch = None


# ─────────────────────────────────────────────────────────────────────────────
# Dataset
# ─────────────────────────────────────────────────────────────────────────────

class KeypointDataset:
    """Pure-numpy dataset loader (no torch dependency)."""

    def __init__(self, entries: list, input_h=INPUT_H, input_w=INPUT_W, augment=False):
        self.entries  = entries
        self.input_h  = input_h
        self.input_w  = input_w
        self.augment  = augment

    def __len__(self):
        return len(self.entries)

    def _load_sample(self, entry):
        path = Path(entry.get("thresholded_path", ""))
        if not path.exists():
            path = THRESH_DIR / entry["filename"]
        arr = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if arr is None:
            arr = np.zeros((840, 640), dtype=np.uint8)
        orig_h, orig_w = arr.shape[:2]
        img = cv2.resize(arr, (self.input_w, self.input_h)).astype(np.float32) / 255.0

        pts = entry.get("points", [])
        p1 = pts[0] if len(pts) > 0 else {"x": 0, "y": 0}
        p2 = pts[1] if len(pts) > 1 else {"x": 0, "y": 0}
        # Normalise to [0, 1]
        kps = np.array([
            p1["x"] / orig_w, p1["y"] / orig_h,
            p2["x"] / orig_w, p2["y"] / orig_h,
        ], dtype=np.float32)

        if self.augment:
            img, kps = self._augment(img, kps)

        return img, kps, orig_w, orig_h

    def _augment(self, img, kps):
        """Lightweight augmentation: flip-H, brightness jitter."""
        if np.random.rand() > 0.5:
            img = np.fliplr(img).copy()
            kps[0] = 1.0 - kps[0]   # p1_x
            kps[2] = 1.0 - kps[2]   # p2_x
        # Brightness
        scale = np.random.uniform(0.8, 1.2)
        img = np.clip(img * scale, 0, 1)
        return img, kps

    def __getitem__(self, idx):
        return self._load_sample(self.entries[idx])


# ─────────────────────────────────────────────────────────────────────────────
# PyTorch Dataset wrapper (only used when torch is available)
# ─────────────────────────────────────────────────────────────────────────────

def make_torch_dataset(entries, augment=False):
    if not _TORCH_AVAILABLE:
        return None

    class _TorchDS(torch.utils.data.Dataset):
        def __init__(self):
            self._ds = KeypointDataset(entries, augment=augment)
        def __len__(self):
            return len(self._ds)
        def __getitem__(self, idx):
            img, kps, _, _ = self._ds[idx]
            # Grayscale → 3-channel (MobileNet expects RGB)
            img3 = np.stack([img, img, img], axis=0)  # (3, H, W)
            return torch.tensor(img3), torch.tensor(kps)

    return _TorchDS()


# ─────────────────────────────────────────────────────────────────────────────
# Model definition
# ─────────────────────────────────────────────────────────────────────────────

def build_model():
    """MobileNetV2 backbone → 4 output neurons (x1,y1,x2,y2 normalised)."""
    if not _TORCH_AVAILABLE:
        return None
    backbone = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
    backbone.features[0][0] = nn.Conv2d(3, 32, kernel_size=3, stride=2,
                                        padding=1, bias=False)
    in_features = backbone.classifier[1].in_features
    backbone.classifier = nn.Sequential(
        nn.Dropout(0.2),
        nn.Linear(in_features, 256),
        nn.ReLU(),
        nn.Linear(256, 4),
        nn.Sigmoid(),   # output in [0, 1]
    )
    return backbone


# ─────────────────────────────────────────────────────────────────────────────
# Worker threads
# ─────────────────────────────────────────────────────────────────────────────

class TrainWorker(QObject):
    progress    = pyqtSignal(int, str)          # epoch%, message
    epoch_done  = pyqtSignal(int, float, float) # epoch, train_loss, val_loss
    finished    = pyqtSignal(dict)              # final metrics dict
    error       = pyqtSignal(str)

    def __init__(self, entries, cfg: dict):
        super().__init__()
        self.entries = entries
        self.cfg     = cfg
        self._stop   = False

    def stop(self):
        self._stop = True

    def run(self):
        if not _TORCH_AVAILABLE:
            self.error.emit("PyTorch is not installed.\n\npip install torch torchvision")
            return

        try:
            self._train()
        except Exception as e:
            self.error.emit(str(e))

    def _train(self):
        cfg   = self.cfg
        n     = len(self.entries)
        split = max(1, int(n * 0.8))
        train_entries = self.entries[:split]
        val_entries   = self.entries[split:]

        train_ds = make_torch_dataset(train_entries, augment=cfg.get("augment", True))
        val_ds   = make_torch_dataset(val_entries,   augment=False)

        bs = cfg.get("batch_size", 8)
        train_loader = DataLoader(train_ds, batch_size=bs, shuffle=True,  num_workers=0)
        val_loader   = DataLoader(val_ds,   batch_size=bs, shuffle=False, num_workers=0)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model  = build_model().to(device)

        # Load existing weights if fine-tuning
        if cfg.get("finetune") and MODEL_PATH.exists():
            model.load_state_dict(torch.load(str(MODEL_PATH), map_location=device))

        lr      = cfg.get("lr", 1e-3)
        epochs  = cfg.get("epochs", 30)
        optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
        loss_fn   = nn.MSELoss()
        align_weight = 0.1  # Weight for y1=y2 alignment constraint

        history = {"train_loss": [], "val_loss": [], "epoch": []}
        best_val = float("inf")
        start_t  = time.time()

        for ep in range(1, epochs + 1):
            if self._stop:
                break

            # ── Train ──
            model.train()
            t_loss = 0.0
            for imgs, kps in train_loader:
                imgs, kps = imgs.to(device), kps.to(device)
                optimizer.zero_grad()
                pred = model(imgs)
                mse_loss = loss_fn(pred, kps)
                # Add alignment constraint: y1 should equal y2 (y-coords at indices 1 and 3)
                align_loss = torch.mean((pred[:, 1] - pred[:, 3]) ** 2)
                loss = mse_loss + align_weight * align_loss
                loss.backward()
                optimizer.step()
                t_loss += loss.item() * len(imgs)
            t_loss /= len(train_ds)

            # ── Val ──
            model.eval()
            v_loss = 0.0
            with torch.no_grad():
                for imgs, kps in val_loader:
                    imgs, kps = imgs.to(device), kps.to(device)
                    pred = model(imgs)
                    v_loss += loss_fn(pred, kps).item() * len(imgs)
            v_loss /= max(len(val_ds), 1)

            scheduler.step()
            history["epoch"].append(ep)
            history["train_loss"].append(round(t_loss, 6))
            history["val_loss"].append(round(v_loss, 6))

            if v_loss < best_val:
                best_val = v_loss
                torch.save(model.state_dict(), str(MODEL_PATH))

            pct = int(ep / epochs * 100)
            eta = int((time.time() - start_t) / ep * (epochs - ep))
            msg = (f"Epoch {ep}/{epochs}  |  train {t_loss:.5f}  |  val {v_loss:.5f}"
                   f"  |  best {best_val:.5f}  |  ETA {eta}s")
            self.progress.emit(pct, msg)
            self.epoch_done.emit(ep, t_loss, v_loss)

        HISTORY_PATH.write_text(json.dumps(history, indent=2))
        elapsed = round(time.time() - start_t, 1)

        # Save meta
        device_name = "CUDA" if torch.cuda.is_available() else "CPU"
        meta = {
            "trained_on": datetime.now().isoformat(timespec="seconds"),
            "samples": n,
            "epochs": epochs,
            "best_val_loss": round(best_val, 6),
            "elapsed_sec": elapsed,
            "device": device_name,
            "architecture": "MobileNetV2 + Keypoint Head",
            "input_size": f"{INPUT_W}×{INPUT_H}",
            "batch_size": bs,
            "lr": lr,
        }
        META_PATH.write_text(json.dumps(meta, indent=2))

        self.finished.emit({
            "best_val_loss": best_val,
            "elapsed": elapsed,
            "device": device_name,
            "epochs": epochs,
        })


class EvalWorker(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, entries):
        super().__init__()
        self.entries = entries

    def run(self):
        if not _TORCH_AVAILABLE:
            self.error.emit("PyTorch is not installed.")
            return
        if not MODEL_PATH.exists():
            self.error.emit("No trained model found. Train first.")
            return
        try:
            self._eval()
        except Exception as e:
            self.error.emit(str(e))

    def _eval(self):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model  = build_model().to(device)
        model.load_state_dict(torch.load(str(MODEL_PATH), map_location=device))
        model.eval()

        ds = KeypointDataset(self.entries)
        pixel_errors = []   # per-point pixel error
        dist_errors  = []   # error on pixel_distance

        for i, entry in enumerate(self.entries):
            img, kps_norm, orig_w, orig_h = ds._load_sample(entry)
            img3 = np.stack([img, img, img], axis=0)[np.newaxis]  # (1,3,H,W)
            t_img = torch.tensor(img3).to(device)
            with torch.no_grad():
                pred = model(t_img).cpu().numpy()[0]   # [px1,py1,px2,py2]

            # Convert normalised → pixel
            pred_p1_x, pred_p1_y = pred[0] * orig_w, pred[1] * orig_h
            pred_p2_x, pred_p2_y = pred[2] * orig_w, pred[3] * orig_h
            # Enforce horizontal alignment for predictions
            y_aligned = (pred_p1_y + pred_p2_y) / 2.0
            pred_p1 = np.array([pred_p1_x, y_aligned])
            pred_p2 = np.array([pred_p2_x, y_aligned])
            gt_p1   = np.array([kps_norm[0] * orig_w, kps_norm[1] * orig_h])
            gt_p2   = np.array([kps_norm[2] * orig_w, kps_norm[3] * orig_h])

            e1 = float(np.linalg.norm(pred_p1 - gt_p1))
            e2 = float(np.linalg.norm(pred_p2 - gt_p2))
            pixel_errors.append((e1 + e2) / 2)

            pred_dist = float(np.linalg.norm(pred_p2 - pred_p1))
            gt_dist   = float(np.linalg.norm(gt_p2 - gt_p1))
            dist_errors.append(abs(pred_dist - gt_dist))

            pct = int((i + 1) / len(self.entries) * 100)
            self.progress.emit(pct, f"Evaluating {i+1}/{len(self.entries)}…")

        mean_px_err  = float(np.mean(pixel_errors))
        mean_dist_err = float(np.mean(dist_errors))
        # Pseudo-accuracy: % of samples with mean point error < 10 px
        within_10 = sum(1 for e in pixel_errors if e < 10) / len(pixel_errors) * 100
        within_20 = sum(1 for e in pixel_errors if e < 20) / len(pixel_errors) * 100

        self.finished.emit({
            "mean_px_error":   round(mean_px_err, 2),
            "mean_dist_error": round(mean_dist_err, 2),
            "within_10px":     round(within_10, 1),
            "within_20px":     round(within_20, 1),
            "n_samples":       len(self.entries),
            "pixel_errors":    [round(e, 2) for e in pixel_errors],
        })


class TestImageWorker(QObject):
    finished = pyqtSignal(dict)   # {p1, p2, pixel_distance, preview_pixmap, is_clear}
    error    = pyqtSignal(str)

    def __init__(self, img_path: Path):
        super().__init__()
        self.img_path = img_path

    def _detect_blur(self, img_gray):
        """Detect blur using Laplacian variance. Returns (is_clear, blur_score)."""
        laplacian_var = cv2.Laplacian(img_gray, cv2.CV_64F).var()
        threshold = 100.0
        return laplacian_var > threshold, laplacian_var

    def run(self):
        if not _TORCH_AVAILABLE:
            self.error.emit("PyTorch not installed.")
            return
        if not MODEL_PATH.exists():
            self.error.emit("No trained model found.")
            return
        try:
            self._test()
        except Exception as e:
            self.error.emit(str(e))

    def _test(self):
        bgr = cv2.imread(str(self.img_path))
        if bgr is None:
            self.error.emit("Failed to load image.")
            return

        # Validate image dimensions: must be exactly 640x480
        h, w = bgr.shape[:2]
        if (w, h) != (INPUT_W, INPUT_H):
            self.error.emit(f"Image must be exactly {INPUT_W}×{INPUT_H} pixels. Got {w}×{h}.")
            return

        # Check blur
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        is_clear, blur_score = self._detect_blur(gray)
        if not is_clear:
            self.error.emit(f"Image is too blurry (score: {blur_score:.1f}). Use a clear image.")
            return

        # Apply threshold and run inference
        thresh = apply_threshold(bgr)
        resized = cv2.resize(thresh, (INPUT_W, INPUT_H)).astype(np.float32) / 255.0
        img3 = np.stack([resized, resized, resized], axis=0)[np.newaxis]

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = build_model().to(device)
        model.load_state_dict(torch.load(str(MODEL_PATH), map_location=device))
        model.eval()

        t_img = torch.tensor(img3).to(device)
        with torch.no_grad():
            pred = model(t_img).cpu().numpy()[0]

        # Convert to pixel coordinates (already at 640x480)
        p1_x, p1_y = pred[0] * INPUT_W, pred[1] * INPUT_H
        p2_x, p2_y = pred[2] * INPUT_W, pred[3] * INPUT_H
        y_aligned = (p1_y + p2_y) / 2.0
        p1 = (int(p1_x), int(y_aligned))
        p2 = (int(p2_x), int(y_aligned))
        dist = math.dist(p1, p2)

        # Draw result on thresholded image
        vis = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        cv2.circle(vis, p1, 10, (0, 220, 80), -1)
        cv2.circle(vis, p2, 10, (80, 160, 255), -1)
        cv2.line(vis, p1, p2, (255, 80, 80), 3)
        cv2.putText(vis, "P1", (p1[0]+15, p1[1]+5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,220,80), 2)
        cv2.putText(vis, "P2", (p2[0]+15, p2[1]+5), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80,160,255), 2)
        cv2.putText(vis, f"{dist:.1f} px", ((p1[0]+p2[0])//2 - 40, (p1[1]+p2[1])//2 - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,80,80), 2)

        pm = ndarray_to_qpixmap(vis)
        self.finished.emit({
            "p1": p1, "p2": p2, "pixel_distance": round(dist, 2),
            "preview": pm, "is_clear": is_clear, "blur_score": round(blur_score, 2)
        })


class InferWorker(QObject):
    finished = pyqtSignal(dict)   # {p1, p2, pixel_distance, preview_pixmap}
    error    = pyqtSignal(str)

    def __init__(self, img_path: Path):
        super().__init__()
        self.img_path = img_path

    def run(self):
        if not _TORCH_AVAILABLE:
            self.error.emit("PyTorch not installed.")
            return
        if not MODEL_PATH.exists():
            self.error.emit("No trained model found.")
            return
        try:
            self._infer()
        except Exception as e:
            self.error.emit(str(e))

    def _infer(self):
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model  = build_model().to(device)
        model.load_state_dict(torch.load(str(MODEL_PATH), map_location=device))
        model.eval()

        bgr    = cv2.imread(str(self.img_path))
        thresh = apply_threshold(bgr)
        orig_h, orig_w = thresh.shape[:2]
        resized = cv2.resize(thresh, (INPUT_W, INPUT_H)).astype(np.float32) / 255.0
        img3 = np.stack([resized, resized, resized], axis=0)[np.newaxis]
        t_img = torch.tensor(img3).to(device)

        with torch.no_grad():
            pred = model(t_img).cpu().numpy()[0]

        p1_x, p1_y = pred[0] * orig_w, pred[1] * orig_h
        p2_x, p2_y = pred[2] * orig_w, pred[3] * orig_h
        # Enforce horizontal alignment: use average y-coordinate for both points
        y_aligned = (p1_y + p2_y) / 2.0
        p1 = (int(p1_x), int(y_aligned))
        p2 = (int(p2_x), int(y_aligned))
        dist = math.dist(p1, p2)

        # Draw preview on thresholded image
        vis = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
        cv2.circle(vis, p1, 8, (0, 220, 80),  -1)
        cv2.circle(vis, p2, 8, (80, 160, 255), -1)
        cv2.line(vis,   p1, p2, (255, 80, 80), 2)
        cv2.putText(vis, "P1", (p1[0]+10, p1[1]+4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,220,80),  2)
        cv2.putText(vis, "P2", (p2[0]+10, p2[1]+4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (80,160,255),2)
        cv2.putText(vis, f"{dist:.1f} px", ((p1[0]+p2[0])//2, (p1[1]+p2[1])//2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,80,80), 2)

        pm = ndarray_to_qpixmap(vis)
        self.finished.emit({"p1": p1, "p2": p2, "pixel_distance": round(dist, 2), "preview": pm})


# ─────────────────────────────────────────────────────────────────────────────
# Mini chart widget (loss curve)
# ─────────────────────────────────────────────────────────────────────────────

class LossChart(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(160)
        self._train = []
        self._val   = []
        self.setStyleSheet(f"background:{C['surface']}; border:1px solid {C['border']}; border-radius:6px;")

    def update_data(self, train_losses, val_losses):
        self._train = list(train_losses)
        self._val   = list(val_losses)
        self.update()

    def load_from_file(self):
        if HISTORY_PATH.exists():
            h = json.loads(HISTORY_PATH.read_text())
            self._train = h.get("train_loss", [])
            self._val   = h.get("val_loss",   [])
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._train:
            painter = QPainter(self)
            painter.setPen(QColor(C['muted']))
            painter.setFont(QFont("Consolas", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No training history yet")
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = 52, 16, 16, 32

        all_vals = self._train + self._val
        mn, mx = min(all_vals), max(all_vals)
        rng = mx - mn if mx != mn else 1.0

        def to_screen(i, v):
            x = pad_l + (i / max(len(self._train) - 1, 1)) * (W - pad_l - pad_r)
            y = pad_t + (1 - (v - mn) / rng) * (H - pad_t - pad_b)
            return int(x), int(y)

        # Grid lines
        painter.setPen(QPen(QColor(C['border']), 1))
        for step in range(5):
            y = int(pad_t + step / 4 * (H - pad_t - pad_b))
            painter.drawLine(pad_l, y, W - pad_r, y)
            v = mx - step / 4 * rng
            painter.setFont(QFont("Consolas", 8))
            painter.setPen(QColor(C['muted']))
            painter.drawText(2, y + 4, f"{v:.4f}")
            painter.setPen(QPen(QColor(C['border']), 1))

        # X axis labels
        painter.setPen(QColor(C['muted']))
        painter.setFont(QFont("Consolas", 8))
        n = len(self._train)
        for i in [0, n // 4, n // 2, 3 * n // 4, n - 1]:
            if i < n:
                x, _ = to_screen(i, mn)
                painter.drawText(x - 10, H - 4, str(i + 1))

        # Train loss line
        pen_tr = QPen(QColor(C['accent']), 2)
        painter.setPen(pen_tr)
        for i in range(1, len(self._train)):
            x0, y0 = to_screen(i - 1, self._train[i - 1])
            x1, y1 = to_screen(i,     self._train[i])
            painter.drawLine(x0, y0, x1, y1)

        # Val loss line
        pen_val = QPen(QColor(C['green']), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen_val)
        for i in range(1, len(self._val)):
            x0, y0 = to_screen(i - 1, self._val[i - 1])
            x1, y1 = to_screen(i,     self._val[i])
            painter.drawLine(x0, y0, x1, y1)

        # Legend
        painter.fillRect(W - 130, 8, 10, 10, QColor(C['accent']))
        painter.setPen(QColor(C['accent']))
        painter.setFont(QFont("Consolas", 9))
        painter.drawText(W - 116, 18, "Train")
        painter.fillRect(W - 130, 24, 10, 10, QColor(C['green']))
        painter.setPen(QColor(C['green']))
        painter.drawText(W - 116, 34, "Val")

        # Y axis label
        painter.save()
        painter.setPen(QColor(C['muted']))
        painter.translate(10, H // 2)
        painter.rotate(-90)
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(-20, 0, "MSE Loss")
        painter.restore()


# ─────────────────────────────────────────────────────────────────────────────
# Metric Card
# ─────────────────────────────────────────────────────────────────────────────

def metric_card(title, value, color=None, unit=""):
    col = color or C["accent"]
    card = QFrame()
    card.setStyleSheet(f"""
        QFrame {{
            background:{C['card']}; border:1px solid {C['border']};
            border-radius:8px; padding:4px;
        }}
    """)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(2)
    t = QLabel(title.upper())
    t.setStyleSheet(f"color:{C['muted']}; font-size:9px; letter-spacing:1px; font-weight:bold;")
    v = QLabel(f"{value}{unit}")
    v.setStyleSheet(f"color:{col}; font-size:18px; font-weight:bold; font-family:'Consolas','Courier New',monospace;")
    lay.addWidget(t)
    lay.addWidget(v)
    return card, v   # return the value label so it can be updated


# ─────────────────────────────────────────────────────────────────────────────
# MODEL SECTION
# ─────────────────────────────────────────────────────────────────────────────

class ModelSection(QWidget):
    """
    Full CNN model section.

    Sub-panels:
        • Dataset Overview   – sample count, readiness indicator
        • Hyperparameters    – epochs, lr, batch size, augment, finetune toggle
        • Train              – progress bar, loss chart, status log
        • Evaluate / Test    – accuracy metrics table + metric cards
        • Inference          – drop an image, see predicted points
        • Model Info         – architecture, file size, meta
    """

    def __init__(self, status_bar=None, toast=None):
        super().__init__()
        self.status_bar = status_bar
        self.toast      = toast

        self._train_thread  = None
        self._train_worker  = None
        self._eval_thread   = None
        self._eval_worker   = None
        self._test_thread   = None
        self._test_worker   = None
        self._infer_thread  = None
        self._infer_worker  = None

        self._train_losses = []
        self._val_losses   = []

        self._build_ui()
        self._refresh_dataset_info()
        self._refresh_model_info()
        self._loss_chart.load_from_file()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ══════════════════════════════════════════════════════════════════════
        # LEFT COLUMN  (scroll)
        # ══════════════════════════════════════════════════════════════════════
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet(f"background:{C['bg']}; border:none;")
        left_w = QWidget()
        left_w.setStyleSheet(f"background:{C['bg']};")
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(16, 16, 12, 16)
        left_lay.setSpacing(16)
        left_scroll.setWidget(left_w)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.addWidget(label("⬟  MODEL", "#7C5CFC", 13, True))
        hdr.addStretch()
        self._model_status_lbl = label("—", C['muted'], 11)
        hdr.addWidget(self._model_status_lbl)
        left_lay.addLayout(hdr)
        left_lay.addWidget(separator())

        # ── Dataset overview ─────────────────────────────────────────────────
        ds_box = QGroupBox("DATASET OVERVIEW")
        ds_box.setStyleSheet(self._groupbox_style())
        ds_lay = QGridLayout(ds_box)
        ds_lay.setSpacing(8)

        self._ds_count_lbl  = label("—",    C['text'],    12)
        self._ds_ready_lbl  = label("—",    C['muted'],   11)
        self._ds_split_lbl  = label("—",    C['muted'],   11)
        self._ds_status_bar = QProgressBar()
        self._ds_status_bar.setRange(0, RECOMMENDED_SAMPLES)
        self._ds_status_bar.setFixedHeight(8)
        self._ds_status_bar.setTextVisible(False)
        self._ds_status_bar.setStyleSheet(f"""
            QProgressBar {{ background:{C['surface']}; border-radius:4px; border:none; }}
            QProgressBar::chunk {{ background:{C['green']}; border-radius:4px; }}
        """)

        ds_lay.addWidget(label("Annotations:", C['muted'], 10), 0, 0)
        ds_lay.addWidget(self._ds_count_lbl, 0, 1)
        ds_lay.addWidget(label("Readiness:", C['muted'], 10),   1, 0)
        ds_lay.addWidget(self._ds_ready_lbl, 1, 1)
        ds_lay.addWidget(label("Train/Val:", C['muted'], 10),   2, 0)
        ds_lay.addWidget(self._ds_split_lbl, 2, 1)
        ds_lay.addWidget(label("Progress:", C['muted'], 10),    3, 0)
        ds_lay.addWidget(self._ds_status_bar, 3, 1)
        left_lay.addWidget(ds_box)

        # ── Hyperparameters ───────────────────────────────────────────────────
        hp_box = QGroupBox("HYPERPARAMETERS")
        hp_box.setStyleSheet(self._groupbox_style())
        hp_lay = QGridLayout(hp_box)
        hp_lay.setSpacing(8)

        spin_style = f"""
            QSpinBox, QDoubleSpinBox {{
                background:{C['surface']}; border:1px solid {C['border']};
                border-radius:4px; color:{C['text']}; padding:2px 4px;
                font-size:11px; font-family:'Consolas','Courier New',monospace;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus {{ border-color:{C['accent']}; }}
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                width:14px; background:{C['panel']}; border:none;
            }}
        """

        self._epoch_spin = QSpinBox(); self._epoch_spin.setRange(1, 300); self._epoch_spin.setValue(30)
        self._epoch_spin.setStyleSheet(spin_style)
        self._lr_spin = QDoubleSpinBox(); self._lr_spin.setRange(1e-5, 0.1)
        self._lr_spin.setValue(1e-3); self._lr_spin.setDecimals(5); self._lr_spin.setSingleStep(1e-4)
        self._lr_spin.setStyleSheet(spin_style)
        self._bs_spin = QSpinBox(); self._bs_spin.setRange(1, 64); self._bs_spin.setValue(8)
        self._bs_spin.setStyleSheet(spin_style)

        self._augment_chk  = QCheckBox("Data Augmentation (flip + brightness)")
        self._finetune_chk = QCheckBox("Fine-tune from existing weights")
        for chk in (self._augment_chk, self._finetune_chk):
            chk.setChecked(True)
            chk.setStyleSheet(f"color:{C['muted']}; font-size:10px;")

        hp_lay.addWidget(label("Epochs:", C['muted'], 10), 0, 0)
        hp_lay.addWidget(self._epoch_spin, 0, 1)
        hp_lay.addWidget(label("Learning Rate:", C['muted'], 10), 1, 0)
        hp_lay.addWidget(self._lr_spin, 1, 1)
        hp_lay.addWidget(label("Batch Size:", C['muted'], 10), 2, 0)
        hp_lay.addWidget(self._bs_spin, 2, 1)
        hp_lay.addWidget(self._augment_chk, 3, 0, 1, 2)
        hp_lay.addWidget(self._finetune_chk, 4, 0, 1, 2)
        left_lay.addWidget(hp_box)

        # ── Train controls ────────────────────────────────────────────────────
        tr_box = QGroupBox("TRAINING")
        tr_box.setStyleSheet(self._groupbox_style())
        tr_lay = QVBoxLayout(tr_box)
        tr_lay.setSpacing(8)

        btn_row = QHBoxLayout()
        self._train_btn = btn("▶  Train Model", C['green'])
        self._stop_btn  = btn("■  Stop",        C['red'], True)
        self._stop_btn.setEnabled(False)
        self._train_btn.clicked.connect(self._start_training)
        self._stop_btn.clicked.connect(self._stop_training)
        btn_row.addWidget(self._train_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        tr_lay.addLayout(btn_row)

        self._train_progress = QProgressBar()
        self._train_progress.setRange(0, 100)
        self._train_progress.setValue(0)
        self._train_progress.setFixedHeight(12)
        self._train_progress.setStyleSheet(f"""
            QProgressBar {{ background:{C['surface']}; border-radius:6px; border:none; }}
            QProgressBar::chunk {{ background:{C['green']}; border-radius:6px; }}
        """)
        tr_lay.addWidget(self._train_progress)

        self._train_status_lbl = label("Ready to train.", C['muted'], 10)
        self._train_status_lbl.setWordWrap(True)
        tr_lay.addWidget(self._train_status_lbl)

        # Log
        self._log_widget = QLabel()
        self._log_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._log_widget.setWordWrap(True)
        self._log_widget.setStyleSheet(f"""
            background:{C['bg']}; border:1px solid {C['border']}; border-radius:4px;
            color:{C['muted']}; font-size:9px; font-family:'Consolas','Courier New',monospace;
            padding:6px;
        """)
        self._log_widget.setFixedHeight(80)
        self._log_lines = []
        tr_lay.addWidget(self._log_widget)
        left_lay.addWidget(tr_box)

        # ── Loss chart ────────────────────────────────────────────────────────
        chart_box = QGroupBox("LOSS CURVE")
        chart_box.setStyleSheet(self._groupbox_style())
        chart_lay = QVBoxLayout(chart_box)
        self._loss_chart = LossChart()
        chart_lay.addWidget(self._loss_chart)
        left_lay.addWidget(chart_box)

        left_lay.addStretch()
        outer.addWidget(left_scroll, 1)

        # ══════════════════════════════════════════════════════════════════════
        # RIGHT COLUMN (with scroll)
        # ══════════════════════════════════════════════════════════════════════
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet(f"background:{C['panel']}; border-left:1px solid {C['border']}; border:none;")
        right_w = QWidget()
        right_w.setStyleSheet(f"background:{C['panel']};")
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(14, 16, 14, 16)
        right_lay.setSpacing(14)
        right_scroll.setWidget(right_w)

        # ── Evaluate / Test panel ─────────────────────────────────────────────
        right_lay.addWidget(label("EVALUATE MODEL", C['muted'], 10, True))
        right_lay.addWidget(separator())

        eval_btn_row = QHBoxLayout()
        self._eval_btn = btn("⬟  Test Model", C['accent2'])
        self._eval_btn.clicked.connect(self._start_eval)
        eval_btn_row.addWidget(self._eval_btn)
        right_lay.addLayout(eval_btn_row)

        self._eval_progress = QProgressBar()
        self._eval_progress.setRange(0, 100)
        self._eval_progress.setValue(0)
        self._eval_progress.setFixedHeight(8)
        self._eval_progress.setStyleSheet(f"""
            QProgressBar {{ background:{C['surface']}; border-radius:4px; border:none; }}
            QProgressBar::chunk {{ background:{C['accent2']}; border-radius:4px; }}
        """)
        right_lay.addWidget(self._eval_progress)

        # Metric cards grid
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(8)

        self._m_px_card,   self._m_px_val   = metric_card("Mean Pt. Error", "—", C['accent'],  " px")
        self._m_dist_card, self._m_dist_val = metric_card("Dist. Error",    "—", C['yellow'],  " px")
        self._m_10_card,   self._m_10_val   = metric_card("Within 10 px",   "—", C['green'],   "%")
        self._m_20_card,   self._m_20_val   = metric_card("Within 20 px",   "—", C['accent2'], "%")

        metrics_grid.addWidget(self._m_px_card,   0, 0)
        metrics_grid.addWidget(self._m_dist_card, 0, 1)
        metrics_grid.addWidget(self._m_10_card,   1, 0)
        metrics_grid.addWidget(self._m_20_card,   1, 1)
        right_lay.addLayout(metrics_grid)

        self._eval_status_lbl = label("No evaluation run yet.", C['muted'], 10)
        self._eval_status_lbl.setWordWrap(True)
        right_lay.addWidget(self._eval_status_lbl)
        right_lay.addWidget(separator())

        # ── Test panel (strict 640x480 validation) ────────────────────────────
        right_lay.addWidget(label("TEST IMAGE", C['muted'], 10, True))

        self._test_path_lbl = label("No image selected", C['muted'], 10)
        self._test_path_lbl.setWordWrap(True)
        right_lay.addWidget(self._test_path_lbl)

        test_btn_row = QHBoxLayout()
        test_pick_btn = btn("📂 Pick Image", C['muted'], True)
        test_pick_btn.clicked.connect(self._pick_test_image)
        self._run_test_btn = btn("▶ Test", C['green'], True)
        self._run_test_btn.setEnabled(False)
        self._run_test_btn.clicked.connect(self._run_test)
        test_btn_row.addWidget(test_pick_btn)
        test_btn_row.addWidget(self._run_test_btn)
        right_lay.addLayout(test_btn_row)

        self._test_preview = QLabel()
        self._test_preview.setFixedSize(290, 200)
        self._test_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._test_preview.setStyleSheet(f"""
            background:{C['surface']}; border:1px solid {C['border']};
            border-radius:6px; color:{C['muted']}; font-size:10px;
        """)
        self._test_preview.setText("Preview will appear here")
        right_lay.addWidget(self._test_preview)

        self._test_result_lbl = label("—", C['muted'], 10)
        self._test_result_lbl.setWordWrap(True)
        right_lay.addWidget(self._test_result_lbl)
        right_lay.addWidget(separator())

        # ── Inference panel ───────────────────────────────────────────────────
        right_lay.addWidget(label("INFERENCE", C['muted'], 10, True))

        self._infer_path_lbl = label("No image selected", C['muted'], 10)
        self._infer_path_lbl.setWordWrap(True)
        right_lay.addWidget(self._infer_path_lbl)

        infer_btn_row = QHBoxLayout()
        pick_btn = btn("📂 Pick Image", C['muted'], True)
        pick_btn.clicked.connect(self._pick_infer_image)
        self._run_infer_btn = btn("▶ Run", C['accent'], True)
        self._run_infer_btn.setEnabled(False)
        self._run_infer_btn.clicked.connect(self._run_inference)
        infer_btn_row.addWidget(pick_btn)
        infer_btn_row.addWidget(self._run_infer_btn)
        right_lay.addLayout(infer_btn_row)

        self._infer_preview = QLabel()
        self._infer_preview.setFixedSize(290, 200)
        self._infer_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._infer_preview.setStyleSheet(f"""
            background:{C['surface']}; border:1px solid {C['border']};
            border-radius:6px; color:{C['muted']}; font-size:10px;
        """)
        self._infer_preview.setText("Preview will appear here")
        right_lay.addWidget(self._infer_preview)

        self._infer_result_lbl = label("—", C['muted'], 10)
        self._infer_result_lbl.setWordWrap(True)
        right_lay.addWidget(self._infer_result_lbl)
        right_lay.addWidget(separator())

        # ── Model Info panel ──────────────────────────────────────────────────
        right_lay.addWidget(label("MODEL INFO", C['muted'], 10, True))

        self._info_table = QTableWidget(0, 2)
        self._info_table.horizontalHeader().hide()
        self._info_table.verticalHeader().hide()
        self._info_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._info_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._info_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._info_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._info_table.setStyleSheet(f"""
            QTableWidget {{
                background:{C['surface']}; border:1px solid {C['border']};
                border-radius:6px; gridline-color:{C['border']};
            }}
            QTableWidget::item {{ padding:3px 6px; border-bottom:1px solid {C['border']}; }}
        """)
        self._info_table.setMaximumHeight(200)
        right_lay.addWidget(self._info_table)

        refresh_info_btn = btn("↺ Refresh Info", C['muted'], True)
        refresh_info_btn.clicked.connect(self._refresh_model_info)
        right_lay.addWidget(refresh_info_btn)

        right_lay.addStretch()
        outer.addWidget(right_scroll)

        self._test_image_path = None
        self._infer_image_path = None

    # ── Style helpers ─────────────────────────────────────────────────────────

    def _groupbox_style(self):
        return f"""
            QGroupBox {{
                border:1px solid {C['border']}; border-radius:6px;
                margin-top:14px; padding-top:10px;
                font-size:10px; color:{C['muted']}; letter-spacing:1px;
            }}
            QGroupBox::title {{
                subcontrol-origin:margin; subcontrol-position:top left;
                padding:0 6px; left:10px;
            }}
        """

    # ── Dataset info ──────────────────────────────────────────────────────────

    def _refresh_dataset_info(self):
        entries = STORE.load()
        n = len(entries)
        self._ds_count_lbl.setText(str(n))
        self._ds_status_bar.setValue(min(n, RECOMMENDED_SAMPLES))

        if n == 0:
            color, text = C['red'],    "✕  No annotations found"
        elif n < MIN_SAMPLES_REQUIRED:
            color, text = C['red'],    f"✕  Insufficient (need ≥ {MIN_SAMPLES_REQUIRED})"
        elif n < RECOMMENDED_SAMPLES:
            color, text = C['yellow'], f"△  Marginal (recommend ≥ {RECOMMENDED_SAMPLES})"
        else:
            color, text = C['green'],  "✓  Good — ready to train"

        self._ds_ready_lbl.setText(text)
        self._ds_ready_lbl.setStyleSheet(f"color:{color}; font-size:11px;")

        split_n  = max(1, int(n * 0.8))
        val_n    = n - split_n
        self._ds_split_lbl.setText(f"Train: {split_n}   Val: {val_n}")

    # ── Model info ────────────────────────────────────────────────────────────

    def _refresh_model_info(self):
        rows = []
        rows.append(("Architecture", "MobileNetV2 + Keypoint Head"))
        rows.append(("Input Size",   f"{INPUT_W}×{INPUT_H} (grayscale→3ch)"))
        rows.append(("Output",       "4 neurons (x1,y1,x2,y2 normalised)"))
        rows.append(("Loss",         "MSE (Mean Squared Error)"))
        rows.append(("Optimizer",    "Adam + CosineAnnealingLR"))

        if MODEL_PATH.exists():
            size_kb = MODEL_PATH.stat().st_size // 1024
            rows.append(("Model File", f"keypoint_cnn.pth  ({size_kb} KB)"))
            self._model_status_lbl.setText("● Model saved")
            self._model_status_lbl.setStyleSheet(f"color:{C['green']}; font-size:11px;")
        else:
            rows.append(("Model File", "Not trained yet"))
            self._model_status_lbl.setText("○ No model saved")
            self._model_status_lbl.setStyleSheet(f"color:{C['muted']}; font-size:11px;")

        if META_PATH.exists():
            meta = json.loads(META_PATH.read_text())
            rows.append(("Trained On",   meta.get("trained_on", "—")))
            rows.append(("Samples",      str(meta.get("samples", "—"))))
            rows.append(("Best Val MSE", str(meta.get("best_val_loss", "—"))))
            rows.append(("Train Time",   f"{meta.get('elapsed_sec', '—')} s"))
            rows.append(("Device",       meta.get("device", "—")))

        if not _TORCH_AVAILABLE:
            rows.append(("⚠ PyTorch", "NOT installed  (pip install torch torchvision)"))

        self._info_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            ki = QTableWidgetItem(k)
            vi = QTableWidgetItem(v)
            ki.setForeground(QColor(C['muted']))
            vi.setForeground(QColor(C['text']))
            ki.setFont(QFont("Consolas", 9))
            vi.setFont(QFont("Consolas", 9))
            self._info_table.setItem(i, 0, ki)
            self._info_table.setItem(i, 1, vi)
        self._info_table.resizeRowsToContents()

    # ── Training ──────────────────────────────────────────────────────────────

    def _start_training(self):
        self._refresh_dataset_info()
        entries = STORE.load()
        n = len(entries)

        if n < MIN_SAMPLES_REQUIRED:
            QMessageBox.warning(
                self, "Insufficient Dataset",
                f"Only {n} annotation(s) found.\n\n"
                f"A minimum of {MIN_SAMPLES_REQUIRED} samples is required to train.\n"
                f"Recommended: {RECOMMENDED_SAMPLES}+ for reliable results.\n\n"
                "Please annotate more images in the Annotate section first."
            )
            return

        if n < RECOMMENDED_SAMPLES:
            reply = QMessageBox.question(
                self, "Small Dataset Warning",
                f"Only {n} samples found (recommended: {RECOMMENDED_SAMPLES}+).\n\n"
                f"Training may overfit or produce poor accuracy.\n"
                f"Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        if not _TORCH_AVAILABLE:
            QMessageBox.critical(self, "PyTorch Not Installed",
                "PyTorch is required for training.\n\n"
                "Install it with:\n"
                "pip install torch torchvision torchaudio\n\n"
                "See https://pytorch.org/get-started/locally/ for GPU (CUDA) builds.")
            return

        cfg = {
            "epochs":     self._epoch_spin.value(),
            "lr":         self._lr_spin.value(),
            "batch_size": self._bs_spin.value(),
            "augment":    self._augment_chk.isChecked(),
            "finetune":   self._finetune_chk.isChecked(),
        }

        self._train_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._train_progress.setValue(0)
        self._log_lines.clear()
        self._train_losses.clear()
        self._val_losses.clear()

        self._train_worker = TrainWorker(entries, cfg)
        self._train_thread = QThread()
        self._train_worker.moveToThread(self._train_thread)
        self._train_thread.started.connect(self._train_worker.run)
        self._train_worker.progress.connect(self._on_train_progress)
        self._train_worker.epoch_done.connect(self._on_epoch_done)
        self._train_worker.finished.connect(self._on_train_finished)
        self._train_worker.error.connect(self._on_train_error)
        self._train_thread.start()

    def _stop_training(self):
        if self._train_worker:
            self._train_worker.stop()
        self._stop_btn.setEnabled(False)

    def _on_train_progress(self, pct: int, msg: str):
        self._train_progress.setValue(pct)
        self._train_status_lbl.setText(msg)
        self._log_lines.append(msg)
        if len(self._log_lines) > 8:
            self._log_lines = self._log_lines[-8:]
        self._log_widget.setText("\n".join(self._log_lines))

    def _on_epoch_done(self, epoch: int, t_loss: float, v_loss: float):
        self._train_losses.append(t_loss)
        self._val_losses.append(v_loss)
        self._loss_chart.update_data(self._train_losses, self._val_losses)

    def _on_train_finished(self, metrics: dict):
        self._train_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._train_progress.setValue(100)
        msg = (f"✓ Training complete  |  Best Val MSE: {metrics['best_val_loss']:.5f}  "
               f"|  {metrics['epochs']} epochs  |  {metrics['elapsed']}s  |  Device: {metrics['device']}")
        self._train_status_lbl.setText(msg)
        self._refresh_model_info()
        if self.toast:
            self.toast.show_message("Model trained & saved!")

    def _on_train_error(self, msg: str):
        self._train_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._train_status_lbl.setText(f"✕ Error: {msg}")
        QMessageBox.critical(self, "Training Error", msg)

    # ── Evaluation ────────────────────────────────────────────────────────────

    def _start_eval(self):
        entries = STORE.load()
        if not entries:
            QMessageBox.warning(self, "No Data", "No annotations found to evaluate on.")
            return
        if not MODEL_PATH.exists():
            QMessageBox.warning(self, "No Model", "No trained model found. Please train first.")
            return
        if not _TORCH_AVAILABLE:
            QMessageBox.critical(self, "PyTorch Not Installed", "PyTorch is required for evaluation.")
            return

        self._eval_btn.setEnabled(False)
        self._eval_progress.setValue(0)
        self._eval_status_lbl.setText("Evaluating…")

        self._eval_worker = EvalWorker(entries)
        self._eval_thread = QThread()
        self._eval_worker.moveToThread(self._eval_thread)
        self._eval_thread.started.connect(self._eval_worker.run)
        self._eval_worker.progress.connect(lambda p, m: self._eval_progress.setValue(p))
        self._eval_worker.finished.connect(self._on_eval_finished)
        self._eval_worker.error.connect(self._on_eval_error)
        self._eval_thread.start()

    def _on_eval_finished(self, metrics: dict):
        self._eval_btn.setEnabled(True)
        self._eval_progress.setValue(100)

        self._m_px_val.setText(f"{metrics['mean_px_error']} px")
        self._m_dist_val.setText(f"{metrics['mean_dist_error']} px")
        self._m_10_val.setText(f"{metrics['within_10px']}%")
        self._m_20_val.setText(f"{metrics['within_20px']}%")

        self._eval_status_lbl.setText(
            f"Evaluated on {metrics['n_samples']} samples  |  "
            f"Avg pt error: {metrics['mean_px_error']} px  |  "
            f"Dist error: {metrics['mean_dist_error']} px"
        )
        if self.toast:
            self.toast.show_message(
                f"Accuracy: {metrics['within_10px']}% within 10 px  |  {metrics['within_20px']}% within 20 px"
            )

    def _on_eval_error(self, msg: str):
        self._eval_btn.setEnabled(True)
        self._eval_status_lbl.setText(f"✕ {msg}")
        QMessageBox.critical(self, "Evaluation Error", msg)

    # ── Inference ─────────────────────────────────────────────────────────────

    def _pick_infer_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick Image for Inference", str(ORIG_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if path:
            self._infer_image_path = Path(path)
            self._infer_path_lbl.setText(self._infer_image_path.name)
            self._run_infer_btn.setEnabled(True)
            # Show raw preview
            bgr = cv2.imread(path)
            if bgr is not None:
                pm = ndarray_to_qpixmap(bgr)
                pm = pm.scaled(290, 200, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                self._infer_preview.setPixmap(pm)

    def _run_inference(self):
        if not self._infer_image_path or not self._infer_image_path.exists():
            QMessageBox.warning(self, "No Image", "Please pick an image first.")
            return
        if not _TORCH_AVAILABLE:
            QMessageBox.critical(self, "PyTorch Not Installed", "PyTorch required for inference.")
            return
        if not MODEL_PATH.exists():
            QMessageBox.warning(self, "No Model", "Train a model first.")
            return

        self._run_infer_btn.setEnabled(False)
        self._infer_result_lbl.setText("Running…")

        self._infer_worker = InferWorker(self._infer_image_path)
        self._infer_thread = QThread()
        self._infer_worker.moveToThread(self._infer_thread)
        self._infer_thread.started.connect(self._infer_worker.run)
        self._infer_worker.finished.connect(self._on_infer_finished)
        self._infer_worker.error.connect(self._on_infer_error)
        self._infer_thread.start()

    def _on_infer_finished(self, result: dict):
        self._run_infer_btn.setEnabled(True)
        p1 = result["p1"]
        p2 = result["p2"]
        d  = result["pixel_distance"]
        pm = result["preview"]
        pm = pm.scaled(290, 200, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        self._infer_preview.setPixmap(pm)
        self._infer_result_lbl.setText(
            f"P1: ({p1[0]}, {p1[1]})  |  P2: ({p2[0]}, {p2[1]})\n"
            f"Pixel Distance: {d} px"
        )

    def _on_infer_error(self, msg: str):
        self._run_infer_btn.setEnabled(True)
        self._infer_result_lbl.setText(f"✕ {msg}")

    # ── Test (640x480 strict validation) ──────────────────────────────────────

    def _pick_test_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick Test Image (must be 640×480)", str(ORIG_DIR),
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff)")
        if path:
            self._test_image_path = Path(path)
            self._test_path_lbl.setText(self._test_image_path.name)
            self._run_test_btn.setEnabled(True)
            # Show preview
            bgr = cv2.imread(path)
            if bgr is not None:
                h, w = bgr.shape[:2]
                size_text = f"{w}×{h}"
                pm = ndarray_to_qpixmap(bgr)
                pm = pm.scaled(290, 200, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                self._test_preview.setPixmap(pm)
                self._test_result_lbl.setText(f"Image size: {size_text}")

    def _run_test(self):
        if not self._test_image_path or not self._test_image_path.exists():
            QMessageBox.warning(self, "No Image", "Please pick an image first.")
            return
        if not _TORCH_AVAILABLE:
            QMessageBox.critical(self, "PyTorch Not Installed", "PyTorch required for testing.")
            return
        if not MODEL_PATH.exists():
            QMessageBox.warning(self, "No Model", "Train a model first.")
            return

        self._run_test_btn.setEnabled(False)
        self._test_result_lbl.setText("Testing…")

        self._test_worker = TestImageWorker(self._test_image_path)
        self._test_thread = QThread()
        self._test_worker.moveToThread(self._test_thread)
        self._test_thread.started.connect(self._test_worker.run)
        self._test_worker.finished.connect(self._on_test_finished)
        self._test_worker.error.connect(self._on_test_error)
        self._test_thread.start()

    def _on_test_finished(self, result: dict):
        self._run_test_btn.setEnabled(True)
        p1 = result["p1"]
        p2 = result["p2"]
        d  = result["pixel_distance"]
        pm = result["preview"]
        blur_score = result["blur_score"]
        pm = pm.scaled(290, 200, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        self._test_preview.setPixmap(pm)
        self._test_result_lbl.setText(
            f"✓ Clear image (blur: {blur_score})\n"
            f"P1: ({p1[0]}, {p1[1]})  P2: ({p2[0]}, {p2[1]})\n"
            f"Distance: {d} px"
        )
        self._test_result_lbl.setStyleSheet(f"color:{C['green']}; font-size:10px;")
        if self.toast:
            self.toast.show_message(f"Test passed! Distance: {d} px")

    def _on_test_error(self, msg: str):
        self._run_test_btn.setEnabled(True)
        self._test_result_lbl.setText(f"✕ {msg}")
        self._test_result_lbl.setStyleSheet(f"color:{C['red']}; font-size:10px;")

    # ── Visibility ────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_dataset_info()
        self._refresh_model_info()
        self._loss_chart.load_from_file()