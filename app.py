# app.py
import cv2
from pixelmeasure import PixelMeasure
import tkinter as tk
from PIL import Image, ImageTk
from datetime import datetime
import os

from camera_setup import get_camera
import interaction_setup as inter
from cable_detector import detect_cable
from handle_screenshot import save_screenshot

# Initialize Dino-Lite SDK (used only on screenshot)
pixel_measure = PixelMeasure(r"C:\Program Files\DNX64\DNX64.dll")

# Initialize camera
cap = get_camera()
if cap is None:
    raise RuntimeError("No camera detected!")

current_frame = None
match_score = 0
camera_status = "Camera not loaded"

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
    global current_frame, match_score

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

        # ---------------- Display ----------------
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        imgtk = ImageTk.PhotoImage(image=img)

        label.imgtk = imgtk
        label.configure(image=imgtk)

    label.after(10, update_frame)

# ---------------- Start loop ----------------
update_frame()
root.mainloop()
cap.release()