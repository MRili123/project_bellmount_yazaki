# app.py
import cv2
from pixelmeasure import PixelMeasure
import tkinter as tk
from PIL import Image, ImageTk
from datetime import datetime
import os
import time
import math
import sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model_bellmounth_mesure"))
from utils import apply_threshold

from camera_setup import get_camera
import interaction_setup as inter
import cable_detector
from cable_detector import detect_cable
from handle_screenshot import save_screenshot

try:
    import tensorflow as tf
    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False

# Initialize camera
cap = get_camera()
if cap is None:
    raise RuntimeError("No camera detected!")

# Get camera resolution
ret, test_frame = cap.read()
camera_width = test_frame.shape[1] if ret else 1920
camera_height = test_frame.shape[0] if ret else 1440

# Initialize SDK with actual camera width
pixel_measure = PixelMeasure(camera_width=camera_width)

current_frame = None
match_score = 0
camera_status = "Camera not loaded"

# --------- Auto-capture + inference state ---------
_tf_model = None
_cable_in_start = None
_auto_triggered = False
_result_overlay = None
_result_window = None
CABLE_IN_REQUIRED = 5.0
OVERLAY_DURATION = 8.0
MODEL_PATH = os.path.join(os.path.dirname(__file__),
    "model_bellmounth_mesure", "model", "CNN_BELMOUNTH_MODEL_V1.h5")

def load_model_once():
    global _tf_model
    if _tf_model is None and _TF_AVAILABLE:
        try:
            _tf_model = tf.keras.models.load_model(MODEL_PATH, compile=False)
        except Exception as e:
            print(f"Model load error: {e}")
    return _tf_model

def run_inference(frame):
    model = load_model_once()
    if model is None:
        return None

    h, w = frame.shape[:2]

    try:
        # Preprocess: threshold -> resize -> normalize -> add channel dim
        thresh = apply_threshold(frame)
        resized = cv2.resize(thresh, (640, 480))
        normalized = resized.astype(np.float32) / 255.0
        inp = normalized[..., np.newaxis][np.newaxis, ...]  # (1, 480, 640, 1)

        pred = model.predict(inp, verbose=0)[0]

        # Denormalize to pixel coords
        p1 = (int(pred[0] * w), int(pred[1] * h))
        p2 = (int(pred[2] * w), int(pred[3] * h))
        pixel_dist = math.dist(p1, p2)

        # Get real distance from SDK
        pixel_measure.update()
        _, mm_pp = pixel_measure.get_values()
        dist_mm = pixel_dist * mm_pp if mm_pp else None

        return p1, p2, dist_mm
    except Exception as e:
        print(f"Inference error: {e}")
        return None

def show_result_window(frame, p1, p2, dist_mm):
    global _result_window

    # Close previous window if exists
    try:
        if _result_window and _result_window.winfo_exists():
            _result_window.destroy()
    except:
        pass

    # Create new window
    _result_window = tk.Toplevel(root)
    _result_window.title("Cable Measurement Result - Scroll to zoom, Click & drag to pan")
    _result_window.geometry("900x700")
    _result_window.configure(bg="#2b2b2b")

    # Store result data for interaction
    original_frame = frame.copy()
    result_data = {
        'frame': original_frame,
        'p1': p1,
        'p2': p2,
        'dist_mm': dist_mm,
        'zoom': 1.0,
        'pan_x': 0,
        'pan_y': 0,
        'drag_start': None,
        'h': original_frame.shape[0],
        'w': original_frame.shape[1]
    }

    # Create canvas for image display
    canvas = tk.Canvas(_result_window, bg="black", cursor="cross")
    canvas.pack(fill=tk.BOTH, expand=True)

    def update_display():
        """Redraw image with zoom and pan applied"""
        disp_frame = result_data['frame'].copy()

        # Apply zoom and pan
        h, w = disp_frame.shape[:2]
        if result_data['zoom'] > 1:
            new_w = int(w / result_data['zoom'])
            new_h = int(h / result_data['zoom'])
            center_x = w // 2 + result_data['pan_x']
            center_y = h // 2 + result_data['pan_y']
            x1 = max(center_x - new_w // 2, 0)
            y1 = max(center_y - new_h // 2, 0)
            x2 = min(center_x + new_w // 2, w)
            y2 = min(center_y + new_h // 2, h)
            disp_frame = disp_frame[y1:y2, x1:x2]
            disp_frame = cv2.resize(disp_frame, (w, h))

        # Draw overlay
        cv2.circle(disp_frame, result_data['p1'], 8, (0, 255, 0), -1)
        cv2.circle(disp_frame, result_data['p2'], 8, (0, 255, 0), -1)
        cv2.line(disp_frame, result_data['p1'], result_data['p2'], (0, 255, 255), 2)
        label_text = f"{result_data['dist_mm']:.2f} mm" if result_data['dist_mm'] else "SDK unavailable"
        mid = ((result_data['p1'][0] + result_data['p2'][0]) // 2,
               (result_data['p1'][1] + result_data['p2'][1]) // 2 - 15)
        cv2.putText(disp_frame, label_text, mid, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # Add zoom indicator
        zoom_text = f"Zoom: {result_data['zoom']:.1f}x" if result_data['zoom'] > 1 else ""
        if zoom_text:
            cv2.putText(disp_frame, zoom_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # Convert to Tkinter
        frame_rgb = cv2.cvtColor(disp_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)

        canvas.create_image(0, 0, anchor='nw', image=imgtk)
        canvas.image = imgtk

    def on_scroll(event):
        """Handle mouse wheel zoom"""
        if event.delta > 0:
            result_data['zoom'] *= 1.1
        else:
            result_data['zoom'] /= 1.1
        result_data['zoom'] = max(1, min(result_data['zoom'], 10))
        update_display()

    def on_press(event):
        """Handle mouse press for pan"""
        result_data['drag_start'] = (event.x, event.y)

    def on_move(event):
        """Handle mouse move for pan"""
        if result_data['drag_start'] is not None and result_data['zoom'] > 1:
            dx = event.x - result_data['drag_start'][0]
            dy = event.y - result_data['drag_start'][1]
            result_data['pan_x'] -= int(dx / result_data['zoom'])
            result_data['pan_y'] -= int(dy / result_data['zoom'])
            result_data['drag_start'] = (event.x, event.y)
            update_display()

    def on_release(event):
        """Handle mouse release"""
        result_data['drag_start'] = None

    # Bind events
    canvas.bind("<MouseWheel>", on_scroll)
    canvas.bind("<Button-1>", on_press)
    canvas.bind("<B1-Motion>", on_move)
    canvas.bind("<ButtonRelease-1>", on_release)

    # Add info label
    info_text = f"Distance: {dist_mm:.2f} mm" if dist_mm else "SDK data unavailable"
    info_label = tk.Label(_result_window, text=info_text, bg="#2b2b2b", fg="#3DDB7E",
                         font=("Arial", 12, "bold"))
    info_label.pack(pady=10)

    # Display initial image
    update_display()

    # Make window closable and on top
    _result_window.focus()
    _result_window.attributes('-topmost', True)

# ---------------- GUI setup ----------------
root = tk.Tk()
root.title("Cable Camera Controller")
root.geometry("900x700")
root.configure(bg="#2b2b2b")

label = tk.Label(root, bg="black")
label.pack(pady=10)

label.bind("<Button-1>", inter.mouse_down)
label.bind("<B1-Motion>", inter.mouse_move)
label.bind("<ButtonRelease-1>", inter.mouse_up)
label.bind("<MouseWheel>", inter.mouse_scroll)

# ---------------- Screenshot button ----------------
def take_screenshot():
    global current_frame

    if current_frame is None:
        return

    # Only update zoom / mm when taking screenshot
    pixel_measure.update()
    zoom, mm_per_pixel = pixel_measure.get_values()

    save_screenshot(current_frame, zoom, mm_per_pixel)

btn_screenshot = tk.Button(
    root,
    text="Take Screenshot",
    command=take_screenshot,
    bg="#FF5722",
    fg="white",
    font=("Arial", 11, "bold"),
    padx=10,
    pady=5
)
btn_screenshot.pack(pady=5)

# ---------------- Update Frame Function ----------------
def update_frame():
    global current_frame, match_score, _cable_in_start, _auto_triggered, _result_window

    ret, frame = cap.read()
    if ret:
        current_frame = frame.copy()
        h, w = frame.shape[:2]

        # ---------------- Zoom & Pan ----------------
        new_w = int(w / inter.zoom)
        new_h = int(h / inter.zoom)

        center_x = w // 2 + inter.pan_x
        center_y = h // 2 + inter.pan_y

        x1 = max(center_x - new_w // 2, 0)
        y1 = max(center_y - new_h // 2, 0)
        x2 = min(center_x + new_w // 2, w)
        y2 = min(center_y + new_h // 2, h)

        frame = frame[y1:y2, x1:x2]
        frame = cv2.resize(frame, (w, h))

        # ---------------- Cable detection ----------------
        frame = detect_cable(frame)

        # -------- 5-second auto-trigger for inference --------
        if cable_detector.stable_status == "Cable IN":
            if _cable_in_start is None:
                _cable_in_start = time.time()
            elif not _auto_triggered and (time.time() - _cable_in_start) >= CABLE_IN_REQUIRED:
                _auto_triggered = True
                result = run_inference(current_frame)
                if result:
                    p1, p2, dist_mm = result
                    show_result_window(current_frame, p1, p2, dist_mm)
        else:
            _cable_in_start = None
            _auto_triggered = False

        # ---------------- Display ----------------
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)

        label.imgtk = imgtk
        label.configure(image=imgtk)

    label.after(10, update_frame)

# ---------------- Start loop ----------------
if __name__ == "__main__":
    update_frame()
    root.mainloop()
    cap.release()