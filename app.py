# Bellmounth Mesure - Professional Measurement System
# Complete rewrite with login, modern UI, auto/manual modes, annotation saving

import cv2
import tkinter as tk
from tkinter import messagebox
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

# ==================== COLORS ====================
BG = "#0D0F14"
SURFACE = "#141720"
CARD = "#1A1E2A"
BORDER = "#252A38"
ACCENT = "#4F8EF7"
GREEN = "#3DDB7E"
RED = "#F75F5F"
YELLOW = "#F7C948"
TEXT = "#E8ECF5"
MUTED = "#6B7394"

# ==================== CONFIG ====================
CONFIG_FILE = Path(__file__).parent / "config.json"
DATASET_DIR = Path(__file__).parent / "model_bellmounth_mesure" / "dataset"
ORIG_DIR = DATASET_DIR / "original"
THRESH_DIR = DATASET_DIR / "thresholded"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
MODEL_PATH = Path(__file__).parent / "model_bellmounth_mesure" / "model" / "CNN_BELMOUNTH_MODEL_V1.h5"

# Create directories
for d in [ORIG_DIR, THRESH_DIR]:
    d.mkdir(parents=True, exist_ok=True)
if not ANNOTATIONS_FILE.exists():
    ANNOTATIONS_FILE.write_text("[]")

# ==================== LOGIN WINDOW ====================
class LoginWindow:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Bellmounth Mesure - Login")
        self.window.geometry("400x300")
        self.window.configure(bg=BG)
        self.window.resizable(False, False)

        # Load config
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
        # Title
        title = tk.Label(self.window, text="◈ BELLMOUNTH MESURE",
                        bg=BG, fg=ACCENT, font=("Arial", 18, "bold"))
        title.pack(pady=30)

        # Card frame
        card = tk.Frame(self.window, bg=CARD, relief=tk.FLAT, bd=0)
        card.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        # Machine name
        tk.Label(card, text="Machine Name:", bg=CARD, fg=TEXT,
                font=("Arial", 10)).pack(anchor=tk.W, padx=15, pady=(15, 5))
        self.machine_entry = tk.Entry(card, font=("Arial", 11),
                                      width=25, bg=SURFACE, fg=TEXT,
                                      insertbackground=TEXT, bd=0)
        self.machine_entry.insert(0, self.config.get("machine_name", "LAB-01"))
        self.machine_entry.pack(padx=15, pady=(0, 10), fill=tk.X)

        # Password
        tk.Label(card, text="Password:", bg=CARD, fg=TEXT,
                font=("Arial", 10)).pack(anchor=tk.W, padx=15, pady=(10, 5))
        self.password_entry = tk.Entry(card, font=("Arial", 11),
                                       width=25, bg=SURFACE, fg=TEXT,
                                       insertbackground=TEXT, show="•", bd=0)
        self.password_entry.pack(padx=15, pady=(0, 15), fill=tk.X)

        # Error label
        self.error_label = tk.Label(card, text="", bg=CARD, fg=RED,
                                   font=("Arial", 9))
        self.error_label.pack()

        # Login button
        btn = tk.Button(card, text="LOGIN", command=self._login,
                       bg=ACCENT, fg="white", font=("Arial", 11, "bold"),
                       relief=tk.FLAT, bd=0, pady=8)
        btn.pack(pady=15, fill=tk.X, padx=15)

        self.password_entry.bind("<Return>", lambda e: self._login())

    def _login(self):
        machine = self.machine_entry.get().strip()
        password = self.password_entry.get()

        if password == self.config.get("password", "bellmounth"):
            self.result = machine
            self.window.destroy()
        else:
            self.error_label.config(text="❌ Incorrect password")
            self.password_entry.delete(0, tk.END)

    def show(self):
        self.window.mainloop()
        return self.result

# ==================== MAIN APP ====================
class MainApp:
    def __init__(self, machine_name):
        self.root = tk.Tk()
        self.root.title(f"Bellmounth Mesure - {machine_name}")
        self.root.geometry("1400x900")
        self.root.configure(bg=BG)
        self.machine_name = machine_name

        # Initialize SDK
        self._init_sdk()

        if not self.camera_ok:
            self._show_no_camera()
            return

        # State
        self.current_frame = None
        self.mode = "AUTO"  # AUTO or MANUAL
        self.p1 = None
        self.p2 = None
        self.dist_mm = None
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.drag_start = None
        self.annotation_count = self._count_annotations()

        # TF model
        self._tf_model = None

        self._build_ui()
        self._start_loop()

    def _init_sdk(self):
        """Initialize Dino-Lite camera and SDK"""
        self.camera_ok = False
        self.cap = None
        self.dnx = None
        self.pixel_measure = None

        try:
            self.cap = get_camera()
            if self.cap is None:
                print("Camera not found")
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
        """Show error screen when no Dino-Lite detected"""
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="⚠️", font=("Arial", 80), fg=RED, bg=BG).pack(pady=30)
        tk.Label(frame, text="No Dino-Lite Camera Detected", font=("Arial", 18),
                fg=TEXT, bg=BG).pack(pady=10)
        tk.Label(frame, text="Please connect a Dino-Lite microscope and restart.",
                font=("Arial", 12), fg=MUTED, bg=BG).pack(pady=10)

        def retry():
            self.root.destroy()
            LoginWindow().show()

        tk.Button(frame, text="Retry", command=retry, bg=ACCENT, fg="white",
                 font=("Arial", 11, "bold"), padx=20, pady=10).pack(pady=20)

    def _build_ui(self):
        """Build main UI layout"""
        # Top bar
        top = tk.Frame(self.root, bg=SURFACE, height=50)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        tk.Label(top, text="◈ BELLMOUNTH MESURE", bg=SURFACE, fg=ACCENT,
                font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=20, pady=12)
        tk.Label(top, text=f"Machine: {self.machine_name}", bg=SURFACE, fg=TEXT,
                font=("Arial", 10)).pack(side=tk.LEFT, padx=10, pady=12)

        tk.Button(top, text="⏻ QUIT", command=self.root.destroy,
                 bg=RED, fg="white", font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=15, pady=5).pack(side=tk.RIGHT, padx=20, pady=12)

        # Main content
        content = tk.Frame(self.root, bg=BG)
        content.pack(fill=tk.BOTH, expand=True)

        # Left: Camera
        self.canvas = tk.Canvas(content, bg="black", width=900, height=600)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Right: Controls
        right = tk.Frame(content, bg=SURFACE, width=350)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10, pady=10)
        right.pack_propagate(False)

        self._build_right_panel(right)

        # Bottom: Status bar
        bottom = tk.Frame(self.root, bg=SURFACE, height=40)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        bottom.pack_propagate(False)

        self.zoom_lbl = tk.Label(bottom, text="Zoom: --x", bg=SURFACE, fg=TEXT, font=("Arial", 9))
        self.zoom_lbl.pack(side=tk.LEFT, padx=20, pady=10)

        self.mpp_lbl = tk.Label(bottom, text="-- mm/px", bg=SURFACE, fg=TEXT, font=("Arial", 9))
        self.mpp_lbl.pack(side=tk.LEFT, padx=20, pady=10)

        self.cable_lbl = tk.Label(bottom, text="●Cable: --", bg=SURFACE, fg=MUTED, font=("Arial", 9))
        self.cable_lbl.pack(side=tk.LEFT, padx=20, pady=10)

    def _build_right_panel(self, parent):
        """Build right control panel"""
        # Mode selector
        mode_frm = tk.LabelFrame(parent, text="MODE", bg=CARD, fg=TEXT,
                                font=("Arial", 9, "bold"), padx=10, pady=10)
        mode_frm.pack(fill=tk.X, padx=10, pady=10)

        btn_frame = tk.Frame(mode_frm, bg=CARD)
        btn_frame.pack(fill=tk.X)

        tk.Button(btn_frame, text="AUTO CNN", command=lambda: self._set_mode("AUTO"),
                 bg=ACCENT, fg="white", font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=15, pady=6,
                 width=12).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frame, text="MANUAL", command=lambda: self._set_mode("MANUAL"),
                 bg=MUTED, fg="white", font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=15, pady=6,
                 width=12).pack(side=tk.LEFT, padx=3)

        self.mode_btns = {"AUTO": btn_frame.winfo_children()[0],
                         "MANUAL": btn_frame.winfo_children()[1]}

        # Measurement display
        meas_frm = tk.LabelFrame(parent, text="MEASUREMENT", bg=CARD, fg=TEXT,
                               font=("Arial", 9, "bold"), padx=10, pady=10)
        meas_frm.pack(fill=tk.X, padx=10, pady=10)

        self.dist_lbl = tk.Label(meas_frm, text="-- mm", bg=CARD, fg=GREEN,
                                font=("Arial", 32, "bold"))
        self.dist_lbl.pack()

        coords_frm = tk.Frame(meas_frm, bg=CARD)
        coords_frm.pack(fill=tk.X, pady=5)
        self.p1_lbl = tk.Label(coords_frm, text="P1: --", bg=CARD, fg=TEXT, font=("Arial", 8))
        self.p1_lbl.pack(side=tk.LEFT, padx=5)
        self.p2_lbl = tk.Label(coords_frm, text="P2: --", bg=CARD, fg=TEXT, font=("Arial", 8))
        self.p2_lbl.pack(side=tk.LEFT, padx=5)

        # Capture button
        self.capture_btn = tk.Button(parent, text="📸 CAPTURE",
                                    command=self._on_capture,
                                    bg=ACCENT, fg="white", font=("Arial", 11, "bold"),
                                    relief=tk.FLAT, bd=0, padx=20, pady=10)
        self.capture_btn.pack(fill=tk.X, padx=10, pady=10)

        # Save annotation
        save_frm = tk.LabelFrame(parent, text="SAVE", bg=CARD, fg=TEXT,
                               font=("Arial", 9, "bold"), padx=10, pady=10)
        save_frm.pack(fill=tk.X, padx=10, pady=10)

        self.save_btn = tk.Button(save_frm, text="💾 Save Annotation",
                                 command=self._save_annotation,
                                 bg=YELLOW, fg="black", font=("Arial", 9, "bold"),
                                 relief=tk.FLAT, bd=0, padx=15, pady=8, state=tk.DISABLED)
        self.save_btn.pack(fill=tk.X)

        self.dataset_lbl = tk.Label(save_frm, text=f"Dataset: {self.annotation_count} items",
                                   bg=CARD, fg=TEXT, font=("Arial", 8))
        self.dataset_lbl.pack(pady=5)

        # LED Control
        led_frm = tk.LabelFrame(parent, text="LED CONTROL", bg=CARD, fg=TEXT,
                              font=("Arial", 9, "bold"), padx=10, pady=10)
        led_frm.pack(fill=tk.X, padx=10, pady=10)

        btn_frm = tk.Frame(led_frm, bg=CARD)
        btn_frm.pack(fill=tk.X)
        tk.Button(btn_frm, text="ON", command=self._led_on,
                 bg=GREEN, fg="black", font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=15, pady=6, width=8).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_frm, text="OFF", command=self._led_off,
                 bg=RED, fg="white", font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=15, pady=6, width=8).pack(side=tk.LEFT, padx=3)

        tk.Label(led_frm, text="Brightness:", bg=CARD, fg=TEXT, font=("Arial", 8)).pack(anchor=tk.W, pady=(10, 5))
        self.led_slider = tk.Scale(led_frm, from_=1, to=6, orient=tk.HORIZONTAL,
                                  bg=SURFACE, fg=TEXT, highlightthickness=0,
                                  troughcolor=CARD, command=self._set_brightness)
        self.led_slider.set(3)
        self.led_slider.pack(fill=tk.X)

    def _set_mode(self, mode):
        self.mode = mode
        for m, btn in self.mode_btns.items():
            btn.config(bg=ACCENT if m == mode else MUTED)

        self.p1 = None
        self.p2 = None
        self.dist_mm = None
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
            x = int(event.x * w / self.canvas.winfo_width())
            y = int(event.y * h / self.canvas.winfo_height())

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
        self.dataset_lbl.config(text=f"Dataset: {self.annotation_count} items")

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

    def _update_display(self):
        if self.current_frame is None:
            return

        disp = self.current_frame.copy()
        h, w = disp.shape[:2]

        # Apply zoom/pan
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

        # Draw cable detection
        if cable_detector.stable_status == "Cable IN":
            cv2.putText(disp, cable_detector.stable_status, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(disp, cable_detector.stable_status, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Draw points
        if self.p1:
            cv2.circle(disp, self.p1, 8, (0, 255, 0), -1)
        if self.p2:
            cv2.circle(disp, self.p2, 8, (0, 255, 0), -1)
        if self.p1 and self.p2:
            cv2.line(disp, self.p1, self.p2, (0, 255, 255), 2)

        # Convert & display
        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor='nw', image=imgtk)
        self.canvas.image = imgtk

        # Update labels
        if self.p1:
            self.p1_lbl.config(text=f"P1: {self.p1}")
        if self.p2:
            self.p2_lbl.config(text=f"P2: {self.p2}")
        if self.dist_mm is not None:
            self.dist_lbl.config(text=f"{self.dist_mm:.2f} mm")
            self.save_btn.config(state=tk.NORMAL)
        else:
            self.dist_lbl.config(text="-- mm")
            self.save_btn.config(state=tk.DISABLED)

    def _start_loop(self):
        if not self.camera_ok:
            return

        ret, frame = self.cap.read()
        if ret:
            self.current_frame = frame.copy()
            frame = detect_cable(frame)
            self._update_display()

            # Update status bar
            self.pixel_measure.update()
            zoom, mpp = self.pixel_measure.get_values()
            if zoom:
                self.zoom_lbl.config(text=f"Zoom: {zoom:.2f}x")
            if mpp:
                self.mpp_lbl.config(text=f"{mpp:.4f} mm/px")

            color = GREEN if cable_detector.stable_status == "Cable IN" else MUTED
            self.cable_lbl.config(text=f"●{cable_detector.stable_status}", fg=color)

        self.root.after(10, self._start_loop)

    def run(self):
        self.root.mainloop()

# ==================== MAIN ====================
if __name__ == "__main__":
    machine = LoginWindow().show()
    if machine:
        app = MainApp(machine)
        app.run()
