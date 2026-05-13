# Bellmounth Inspection System - Premium Dark Pro UI for Yazaki
# Professional measurement application with enterprise-grade interface

import cv2
import tkinter as tk
import json
import time
import math
import sys
import os
import uuid
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageTk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model_bellmounth_mesure"))
from utils import apply_threshold

from camera_setup import get_camera
from pixelmeasure import PixelMeasure
from cable_detector import detect_cable
import cable_detector

try:
    import tensorflow as tf
    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False

# ==================== COLORS (Dark Pro Palette) ====================
BG      = "#0C0C12"
PANEL   = "#101018"
CARD    = "#15151E"
BORDER  = "#20202E"
BTN     = "#0D47A1"
ACCENT  = "#00BFFF"
GREEN   = "#00E676"
RED     = "#FF2D55"
AMBER   = "#FFB300"
TEXT    = "#E8E8F0"
TEXT2   = "#5C5C7A"
SEP     = "#1C1C28"

# ==================== CONFIG ====================
CONFIG_FILE = Path(__file__).parent / "config.json"
DATASET_DIR = Path(__file__).parent / "model_bellmounth_mesure" / "dataset"
ORIG_DIR = DATASET_DIR / "original"
THRESH_DIR = DATASET_DIR / "thresholded"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
MODEL_PATH = Path(__file__).parent / "model_bellmounth_mesure" / "model" / "CNN_BELMOUNTH_MODEL_V1.h5"

for d in [ORIG_DIR, THRESH_DIR]:
    d.mkdir(parents=True, exist_ok=True)
if not ANNOTATIONS_FILE.exists():
    ANNOTATIONS_FILE.write_text("[]")

# ==================== LOGIN WINDOW ====================
class LoginWindow:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Bellmounth Inspection System")
        self.window.geometry("480x560")
        self.window.configure(bg=BG)
        self.window.resizable(False, False)

        self.config = self._load_config()
        self.result = None

        self._build_ui()
        self.window.transient()
        self.window.grab_set()

    def _load_config(self):
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
        return {"machine_name": "LAB-01", "password": "bellmounth"}

    def _build_ui(self):
        tk.Frame(self.window, bg=BG, height=40).pack()

        tk.Label(self.window, text="YAZAKI", bg=BG, fg=TEXT,
                font=("Arial", 12, "bold")).pack()
        tk.Label(self.window, text="BELLMOUNTH INSPECTION SYSTEM", bg=BG, fg=ACCENT,
                font=("Arial", 22, "bold")).pack(pady=(4, 20))

        sep = tk.Frame(self.window, bg=SEP, height=1)
        sep.pack(fill=tk.X, padx=60, pady=(0, 30))

        card_outer = tk.Frame(self.window, bg=BORDER)
        card_outer.pack(padx=40, pady=0, fill=tk.BOTH, expand=True)

        card = tk.Frame(card_outer, bg=CARD)
        card.pack(fill=tk.BOTH, padx=1, pady=1)

        tk.Label(card, text="MACHINE NAME", bg=CARD, fg=TEXT2,
                font=("Arial", 8, "bold")).pack(anchor=tk.W, padx=24, pady=(24, 6))
        self.machine_entry = tk.Entry(card, font=("Consolas", 12),
                                     bg=PANEL, fg=TEXT, insertbackground=TEXT,
                                     relief=tk.FLAT, bd=0, highlightthickness=1,
                                     highlightbackground=BORDER, highlightcolor=ACCENT)
        self.machine_entry.insert(0, self.config.get("machine_name", "LAB-01"))
        self.machine_entry.pack(padx=24, pady=(0, 16), fill=tk.X)

        tk.Label(card, text="PASSWORD", bg=CARD, fg=TEXT2,
                font=("Arial", 8, "bold")).pack(anchor=tk.W, padx=24, pady=(0, 6))
        self.password_entry = tk.Entry(card, font=("Consolas", 12), show="●",
                                      bg=PANEL, fg=TEXT, insertbackground=TEXT,
                                      relief=tk.FLAT, bd=0, highlightthickness=1,
                                      highlightbackground=BORDER, highlightcolor=ACCENT)
        self.password_entry.pack(padx=24, pady=(0, 20), fill=tk.X)

        self.error_label = tk.Label(card, text="", bg=CARD, fg=RED,
                                   font=("Arial", 9))
        self.error_label.pack(pady=(0, 12))

        tk.Button(card, text="SIGN IN", command=self._login,
                 bg=BTN, fg=TEXT, font=("Arial", 11, "bold"),
                 relief=tk.FLAT, bd=0, pady=12, activebackground="#0D47A1",
                 activeforeground=TEXT).pack(padx=24, pady=(0, 28), fill=tk.X)

        self.password_entry.bind("<Return>", lambda e: self._login())

    def _login(self):
        machine = self.machine_entry.get().strip()
        password = self.password_entry.get()

        if password == self.config.get("password", "bellmounth"):
            self.result = machine
            self.window.destroy()
        else:
            self.error_label.config(text="⚠ Incorrect password")
            self.password_entry.delete(0, tk.END)

    def show(self):
        self.window.mainloop()
        return self.result

# ==================== MAIN APP ====================
class MainApp:
    def __init__(self, machine_name):
        self.root = tk.Tk()
        self.root.title(f"Bellmounth Inspection — {machine_name}")
        self.root.geometry("1440x900")
        self.root.configure(bg=BG)
        self.root.state('zoomed')
        self.machine_name = machine_name

        self._init_sdk()
        if not self.camera_ok:
            self._show_no_camera()
            return

        self.current_frame = None
        self.mode = "AUTO"
        self.p1 = None
        self.p2 = None
        self.dist_mm = None
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start = None
        self.annotation_count = self._count_annotations()
        self._tf_model = None

        self._build_ui()
        self._update_clock()
        self._start_loop()

    def _init_sdk(self):
        self.camera_ok = False
        self.cap = None
        self.pixel_measure = None

        try:
            self.cap = get_camera()
            if self.cap is None:
                return
            ret, frame = self.cap.read()
            if not ret:
                return
            self.camera_width = frame.shape[1]
            self.camera_height = frame.shape[0]
            self.pixel_measure = PixelMeasure(camera_width=self.camera_width)
            self.camera_ok = True
        except Exception as e:
            print(f"SDK init error: {e}")

    def _show_no_camera(self):
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="✕", font=("Arial", 72, "bold"), fg=RED, bg=BG).pack(pady=20)
        tk.Label(frame, text="NO CAMERA DETECTED", font=("Arial", 18, "bold"),
                fg=TEXT, bg=BG).pack(pady=6)
        tk.Label(frame, text="Connect a Dino-Lite microscope and press Retry.",
                font=("Arial", 11), fg=TEXT2, bg=BG).pack(pady=6)

        btn_row = tk.Frame(frame, bg=BG)
        btn_row.pack(pady=30)

        tk.Button(btn_row, text="RETRY", command=self.root.destroy,
                 bg=BTN, fg=TEXT, font=("Arial", 10, "bold"),
                 relief=tk.FLAT, bd=0, padx=30, pady=10).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="QUIT", command=self.root.quit,
                 bg=SEP, fg=TEXT, font=("Arial", 10, "bold"),
                 relief=tk.FLAT, bd=0, padx=30, pady=10).pack(side=tk.LEFT, padx=6)

    def _card(self, parent, title):
        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill=tk.X, padx=12, pady=5)
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill=tk.BOTH, padx=1, pady=1)
        hrow = tk.Frame(inner, bg=CARD)
        hrow.pack(fill=tk.X, padx=12, pady=(10, 6))
        tk.Label(hrow, text=title, bg=CARD, fg=TEXT2,
                font=("Arial", 8, "bold")).pack(side=tk.LEFT)
        tk.Frame(hrow, bg=SEP, height=1).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(8,0), pady=6)
        body = tk.Frame(inner, bg=CARD)
        body.pack(fill=tk.X, padx=12, pady=(0, 12))
        return body

    def _build_ui(self):
        # Header bar
        top = tk.Frame(self.root, bg=PANEL, height=58)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        tk.Label(top, text="YAZAKI", bg=PANEL, fg=TEXT,
                font=("Arial", 13, "bold"), padx=20).pack(side=tk.LEFT, pady=12)
        tk.Frame(top, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        tk.Label(top, text="BELLMOUNTH INSPECTION SYSTEM", bg=PANEL, fg=ACCENT,
                font=("Arial", 13)).pack(side=tk.LEFT, padx=0)

        tk.Frame(top, bg=PANEL).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(top, text="●", bg=PANEL, fg=RED, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(top, text="LIVE", bg=PANEL, fg=TEXT2, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 20))
        tk.Frame(top, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        tk.Label(top, text=self.machine_name, bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(side=tk.LEFT, padx=12)
        tk.Frame(top, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        self.clock_lbl = tk.Label(top, text="--:--:--", bg=PANEL, fg=TEXT2, font=("Consolas", 10))
        self.clock_lbl.pack(side=tk.LEFT, padx=12)
        tk.Frame(top, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        tk.Button(top, text="QUIT", command=self.root.destroy,
                 bg=RED, fg=TEXT, font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=18, activebackground=RED,
                 activeforeground=TEXT).pack(side=tk.LEFT, padx=20, pady=12)

        # Content area
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill=tk.BOTH, expand=True)

        # Canvas + border
        canvas_outer = tk.Frame(content, bg=BORDER)
        canvas_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.canvas = tk.Canvas(canvas_outer, bg="#080810", relief=tk.FLAT, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Right panel
        right = tk.Frame(content, bg=PANEL, width=330)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=8)
        right.pack_propagate(False)

        # Measurement card
        body = self._card(right, "MEASUREMENT")
        self.dist_lbl = tk.Label(body, text="--", bg=CARD, fg=ACCENT,
                                font=("Consolas", 38, "bold"))
        self.dist_lbl.pack()
        tk.Label(body, text="mm", bg=CARD, fg=TEXT2, font=("Arial", 11)).pack()
        tk.Frame(body, bg=SEP, height=1).pack(fill=tk.X, pady=8)

        grid = tk.Frame(body, bg=CARD)
        grid.pack(fill=tk.X)
        lc = tk.Frame(grid, bg=CARD)
        lc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(lc, text="ZOOM", bg=CARD, fg=TEXT2, font=("Arial", 8, "bold")).pack(anchor=tk.W)
        self.zoom_val = tk.Label(lc, text="--", bg=CARD, fg=TEXT, font=("Consolas", 12))
        self.zoom_val.pack(anchor=tk.W)
        rc = tk.Frame(grid, bg=CARD)
        rc.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(rc, text="MM / PX", bg=CARD, fg=TEXT2, font=("Arial", 8, "bold")).pack(anchor=tk.W)
        self.mpp_val = tk.Label(rc, text="--", bg=CARD, fg=TEXT, font=("Consolas", 12))
        self.mpp_val.pack(anchor=tk.W)

        tk.Frame(body, bg=SEP, height=1).pack(fill=tk.X, pady=8)
        coords = tk.Frame(body, bg=CARD)
        coords.pack(fill=tk.X)
        self.p1_lbl = tk.Label(coords, text="P1  --", bg=CARD, fg=TEXT2, font=("Consolas", 9))
        self.p1_lbl.pack(side=tk.LEFT)
        self.p2_lbl = tk.Label(coords, text="P2  --", bg=CARD, fg=TEXT2, font=("Consolas", 9))
        self.p2_lbl.pack(side=tk.RIGHT)

        # Status card
        body = self._card(right, "STATUS")
        row = tk.Frame(body, bg=CARD)
        row.pack(fill=tk.X)
        self.cable_dot = tk.Label(row, text="●", bg=CARD, fg=TEXT2, font=("Arial", 12))
        self.cable_dot.pack(side=tk.LEFT)
        self.cable_lbl = tk.Label(row, text="CABLE --", bg=CARD, fg=TEXT2,
                                 font=("Arial", 9, "bold"))
        self.cable_lbl.pack(side=tk.LEFT, padx=(4, 20))
        tk.Label(row, text="●", bg=CARD, fg=GREEN, font=("Arial", 12)).pack(side=tk.LEFT)
        tk.Label(row, text="CAMERA OK", bg=CARD, fg=TEXT2, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=4)

        # Mode card
        body = self._card(right, "ANALYSIS MODE")
        row = tk.Frame(body, bg=CARD)
        row.pack(fill=tk.X)
        self.btn_auto = tk.Button(row, text="AUTO CNN", command=lambda: self._set_mode("AUTO"),
                                 bg=BTN, fg=TEXT, font=("Arial", 9, "bold"),
                                 relief=tk.FLAT, bd=0, pady=8, width=12)
        self.btn_auto.pack(side=tk.LEFT, padx=(0, 4))
        self.btn_manual = tk.Button(row, text="MANUAL", command=lambda: self._set_mode("MANUAL"),
                                   bg=SEP, fg=TEXT2, font=("Arial", 9, "bold"),
                                   relief=tk.FLAT, bd=0, pady=8, width=12)
        self.btn_manual.pack(side=tk.LEFT)
        self.mode_btns = {"AUTO": self.btn_auto, "MANUAL": self.btn_manual}

        # Actions card
        body = self._card(right, "ACTIONS")
        self.capture_btn = tk.Button(body, text="CAPTURE", command=self._on_capture,
                                    bg=BTN, fg=TEXT, font=("Arial", 11, "bold"),
                                    relief=tk.FLAT, bd=0, pady=12)
        self.capture_btn.pack(fill=tk.X, pady=(0, 6))
        self.save_btn = tk.Button(body, text="SAVE ANNOTATION", command=self._save_annotation,
                                 bg=AMBER, fg="#1A1000", font=("Arial", 10, "bold"),
                                 relief=tk.FLAT, bd=0, pady=10, state=tk.DISABLED)
        self.save_btn.pack(fill=tk.X)
        self.dataset_lbl = tk.Label(body, text=f"{self.annotation_count} samples",
                                   bg=CARD, fg=TEXT2, font=("Arial", 8))
        self.dataset_lbl.pack(anchor=tk.E, pady=(4, 0))

        # LED card
        body = self._card(right, "ILLUMINATION")
        row = tk.Frame(body, bg=CARD)
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Button(row, text="LED  ON", command=self._led_on,
                 bg=GREEN, fg="#001A00", font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, pady=8).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tk.Button(row, text="LED  OFF", command=self._led_off,
                 bg=SEP, fg=TEXT, font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, pady=8).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(body, text="BRIGHTNESS", bg=CARD, fg=TEXT2, font=("Arial", 8, "bold")).pack(anchor=tk.W)
        self.led_slider = tk.Scale(body, from_=1, to=6, orient=tk.HORIZONTAL,
                                  bg=CARD, fg=TEXT, highlightthickness=0, troughcolor=SEP,
                                  activebackground=BTN, sliderlength=18,
                                  command=self._set_brightness)
        self.led_slider.set(3)
        self.led_slider.pack(fill=tk.X)

        # Bottom status bar
        bottom = tk.Frame(self.root, bg=PANEL, height=30)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        bottom.pack_propagate(False)
        tk.Frame(bottom, bg=SEP, height=1).pack(fill=tk.X)
        tk.Label(bottom, text="YAZAKI INSPECTION SYSTEM  v1.0", bg=PANEL, fg=TEXT2,
                font=("Arial", 8)).pack(side=tk.LEFT, padx=20, pady=7)

    def _set_mode(self, mode):
        self.mode = mode
        self.mode_btns["AUTO"].config(bg=BTN if mode=="AUTO" else SEP,
                                      fg=TEXT if mode=="AUTO" else TEXT2)
        self.mode_btns["MANUAL"].config(bg=BTN if mode=="MANUAL" else SEP,
                                        fg=TEXT if mode=="MANUAL" else TEXT2)
        self.p1 = self.p2 = self.dist_mm = None
        self._update_display()

    def _on_scroll(self, event):
        if event.delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1
        self.zoom = max(1, min(self.zoom, 10))

    def _on_press(self, event):
        if self.mode == "MANUAL" and self.current_frame is not None:
            h, w = self.current_frame.shape[:2]
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()

            if canvas_w > 1 and canvas_h > 1:
                # Simple direct mapping: click position in canvas → frame position
                # accounting for any zoom/pan
                if self.zoom > 1:
                    new_w = int(w / self.zoom)
                    new_h = int(h / self.zoom)
                    cx = w // 2 + self.pan_x
                    cy = h // 2 + self.pan_y
                    x1 = max(0, cx - new_w // 2)
                    y1 = max(0, cy - new_h // 2)
                    x2 = min(w, cx + new_w // 2)
                    y2 = min(h, cy + new_h // 2)

                    # Map canvas click directly to frame coordinates
                    x = int(x1 + (event.x / canvas_w) * (x2 - x1))
                    y = int(y1 + (event.y / canvas_h) * (y2 - y1))
                else:
                    # No zoom: direct proportional mapping
                    x = int(event.x / canvas_w * w)
                    y = int(event.y / canvas_h * h)

                # Clamp to frame bounds
                x = max(0, min(x, w - 1))
                y = max(0, min(y, h - 1))

                if self.p1 is None:
                    self.p1 = (x, y)
                elif self.p2 is None:
                    self.p2 = (x, y)
                    self._compute_distance()
        else:
            self.drag_start = (event.x, event.y)

    def _on_move(self, event):
        if self.drag_start and self.zoom > 1:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.pan_x -= int(dx / self.zoom)
            self.pan_y -= int(dy / self.zoom)
            self.drag_start = (event.x, event.y)

    def _on_release(self, event):
        self.drag_start = None

    def _on_capture(self):
        if self.current_frame is None:
            return

        if self.mode == "AUTO":
            result = self._run_inference(self.current_frame)
            if result:
                self.p1, self.p2, self.dist_mm = result
        else:
            self.p1 = None
            self.p2 = None
            self.dist_mm = None

    def _run_inference(self, frame):
        if not _TF_AVAILABLE:
            return None

        if self._tf_model is None:
            try:
                self._tf_model = tf.keras.models.load_model(str(MODEL_PATH), compile=False)
            except:
                return None

        h, w = frame.shape[:2]
        thresh = apply_threshold(frame)
        resized = cv2.resize(thresh, (640, 480))
        normalized = resized.astype(np.float32) / 255.0
        inp = normalized[..., np.newaxis][np.newaxis, ...]

        pred = self._tf_model.predict(inp, verbose=0)[0]
        p1 = (int(pred[0] * w), int(pred[1] * h))
        p2 = (int(pred[2] * w), int(pred[3] * h))
        pixel_dist = math.dist(p1, p2)

        self.pixel_measure.update()
        _, mm_pp = self.pixel_measure.get_values()
        dist_mm = pixel_dist * mm_pp if mm_pp else None

        return p1, p2, dist_mm

    def _compute_distance(self):
        if self.p1 and self.p2:
            pixel_dist = math.dist(self.p1, self.p2)
            self.pixel_measure.update()
            _, mm_pp = self.pixel_measure.get_values()
            self.dist_mm = pixel_dist * mm_pp if mm_pp else None

    def _save_annotation(self):
        if not (self.p1 and self.p2 and self.current_frame is not None):
            return

        fname = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}.png"
        orig_path = ORIG_DIR / fname
        thresh_path = THRESH_DIR / fname

        cv2.imwrite(str(orig_path), self.current_frame)
        cv2.imwrite(str(thresh_path), apply_threshold(self.current_frame))

        entry = {
            "id": str(uuid.uuid4()),
            "filename": fname,
            "original_path": str(orig_path),
            "thresholded_path": str(thresh_path),
            "width": self.current_frame.shape[1],
            "height": self.current_frame.shape[0],
            "points": [
                {"label": "point_1", "x": self.p1[0], "y": self.p1[1]},
                {"label": "point_2", "x": self.p2[0], "y": self.p2[1]}
            ],
            "pixel_distance": math.dist(self.p1, self.p2),
            "timestamp": datetime.now().isoformat()
        }

        data = json.loads(ANNOTATIONS_FILE.read_text() or "[]")
        data = [d for d in data if d["filename"] != fname]
        data.append(entry)

        tmp = ANNOTATIONS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(ANNOTATIONS_FILE)

        self.annotation_count += 1
        self.dataset_lbl.config(text=f"{self.annotation_count} samples")

    def _led_on(self):
        try:
            self.pixel_measure.dnx.SetLEDState(0, 1)
        except:
            pass

    def _led_off(self):
        try:
            self.pixel_measure.dnx.SetLEDState(0, 0)
        except:
            pass

    def _set_brightness(self, val):
        try:
            self.pixel_measure.dnx.SetFLCLevel(0, int(val))
        except:
            pass

    def _count_annotations(self):
        if ANNOTATIONS_FILE.exists():
            return len(json.loads(ANNOTATIONS_FILE.read_text() or "[]"))
        return 0

    def _update_clock(self):
        self.clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _update_display(self):
        if self.current_frame is None:
            return

        disp = self.current_frame.copy()
        h, w = disp.shape[:2]

        if self.zoom > 1:
            new_w = int(w / self.zoom)
            new_h = int(h / self.zoom)
            cx = w // 2 + self.pan_x
            cy = h // 2 + self.pan_y
            x1 = max(cx - new_w // 2, 0)
            y1 = max(cy - new_h // 2, 0)
            x2 = min(cx + new_w // 2, w)
            y2 = min(cy + new_h // 2, h)
            disp = disp[y1:y2, x1:x2]
            disp = cv2.resize(disp, (w, h))

        # Cable status
        status_color = (0, 255, 0) if cable_detector.stable_status == "Cable IN" else (0, 0, 255)
        cv2.putText(disp, cable_detector.stable_status, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        # Draw points and line
        if self.p1:
            cv2.circle(disp, self.p1, 16, (0, 191, 255), 2)
            cv2.circle(disp, self.p1, 5, (255, 255, 255), -1)
        if self.p2:
            cv2.circle(disp, self.p2, 16, (0, 191, 255), 2)
            cv2.circle(disp, self.p2, 5, (255, 255, 255), -1)
        if self.p1 and self.p2:
            dx, dy = self.p2[0]-self.p1[0], self.p2[1]-self.p1[1]
            dist = int(math.hypot(dx, dy))
            for i in range(0, dist, 16):
                t0 = i/dist if dist > 0 else 0
                t1 = min((i+10)/dist, 1.0) if dist > 0 else 1.0
                s = (int(self.p1[0]+t0*dx), int(self.p1[1]+t0*dy))
                e = (int(self.p1[0]+t1*dx), int(self.p1[1]+t1*dy))
                cv2.line(disp, s, e, (0, 191, 255), 2)

            if self.dist_mm is not None:
                mid = ((self.p1[0]+self.p2[0])//2, (self.p1[1]+self.p2[1])//2)
                txt = f"{self.dist_mm:.2f} mm"
                (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(disp, (mid[0]-tw//2-6, mid[1]-th-8),
                             (mid[0]+tw//2+6, mid[1]+4), (0, 0, 0), -1)
                cv2.putText(disp, txt, (mid[0]-tw//2, mid[1]),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 191, 255), 2)

        # Manual mode hint
        if self.mode == "MANUAL":
            hint = "CLICK TO PLACE P1" if self.p1 is None else ("CLICK TO PLACE P2" if self.p2 is None else "")
            if hint:
                cv2.rectangle(disp, (0, h-36), (len(hint)*9+20, h), (0, 0, 0), -1)
                cv2.putText(disp, hint, (10, h-12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 191, 255), 2)

        # Display on canvas - resize to match canvas dimensions
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w > 1 and canvas_h > 1:
            disp = cv2.resize(disp, (canvas_w, canvas_h))

        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor='nw', image=imgtk)
        self.canvas.image = imgtk

        # Update labels
        if self.p1:
            self.p1_lbl.config(text=f"P1  ({self.p1[0]}, {self.p1[1]})")
        if self.p2:
            self.p2_lbl.config(text=f"P2  ({self.p2[0]}, {self.p2[1]})")
        if self.dist_mm is not None:
            self.dist_lbl.config(text=f"{self.dist_mm:.2f}")
            self.save_btn.config(state=tk.NORMAL, bg=AMBER, fg="#1A1000")
        else:
            self.dist_lbl.config(text="--")
            self.save_btn.config(state=tk.DISABLED, bg=SEP, fg=TEXT2)

    def _start_loop(self):
        if not self.camera_ok:
            return

        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame.copy()
            detect_cable(frame)
            self._update_display()

            self.pixel_measure.update()
            zoom, mpp = self.pixel_measure.get_values()
            if zoom:
                self.zoom_val.config(text=f"{zoom:.2f}x")
            if mpp:
                self.mpp_val.config(text=f"{mpp:.5f}")

            color = GREEN if cable_detector.stable_status == "Cable IN" else RED
            self.cable_dot.config(fg=color)
            self.cable_lbl.config(text=cable_detector.stable_status, fg=color)

        self.root.after(33, self._start_loop)

    def run(self):
        self.root.mainloop()

# ==================== MAIN ====================
if __name__ == "__main__":
    machine = LoginWindow().show()
    if machine:
        app = MainApp(machine)
        app.run()
