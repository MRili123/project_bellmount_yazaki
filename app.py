# Bellmounth Inspection System - Premium Dark Pro UI for Yazaki
# Professional measurement application with enterprise-grade interface

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
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "model_bellmounth_mesure"))
from utils import apply_threshold

from camera_setup import get_camera
from pixelmeasure import PixelMeasure
from cable_detector import detect_cable
import cable_detector
from api_client import APIClient, check_internet_connection

try:
    import tensorflow as tf
    _TF_AVAILABLE = True
except ImportError:
    _TF_AVAILABLE = False

# ==================== COLORS (Light Pro Palette) ====================
BG      = "#FFFFFF"
PANEL   = "#F5F5F5"
CARD    = "#FFFFFF"
BORDER  = "#E0E0E0"
BTN     = "#AF151D"
ACCENT  = "#AF151D"
GREEN   = "#4CAF50"
RED     = "#AF151D"
AMBER   = "#FF9800"
TEXT    = "#1A1A1A"
TEXT2   = "#666666"
SEP     = "#E8E8E8"

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

# ==================== ERROR DIALOG ====================
class ErrorDialog:
    def __init__(self, parent, error_type, message, details="", on_retry=None, on_change_url=None, on_exit=None):
        self.window = tk.Toplevel(parent)
        self.window.title("Connection Error")
        self.window.geometry("500x400")
        self.window.configure(bg="#FFFFFF")
        self.window.resizable(False, False)
        self.on_retry = on_retry
        self.on_change_url = on_change_url
        self.on_exit = on_exit
        self.result = None

        # Color scheme based on error type
        error_colors = {
            "no_internet": ("#FF9800", "NO INTERNET"),
            "server_down": ("#F44336", "SERVER UNREACHABLE"),
            "server_error": ("#FF5722", "SERVER ERROR"),
            "auth_error": ("#F44336", "AUTHENTICATION FAILED"),
            "unknown": ("#FF9800", "ERROR")
        }
        color, title_text = error_colors.get(error_type, ("#FF9800", "ERROR"))

        main = tk.Frame(self.window, bg="#FFFFFF")
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Icon and title
        icon_frame = tk.Frame(main, bg="#FFFFFF")
        icon_frame.pack(fill=tk.X, pady=(0, 20))
        tk.Label(icon_frame, text="⚠", font=("Arial", 32), fg=color, bg="#FFFFFF").pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(icon_frame, text=title_text, font=("Arial", 16, "bold"), fg=color, bg="#FFFFFF").pack(side=tk.LEFT)

        # Message
        tk.Label(main, text=message, font=("Arial", 11), fg="#333333", bg="#FFFFFF", wraplength=400, justify=tk.LEFT).pack(fill=tk.X, pady=(0, 20))

        # Details section
        self.details_frame = tk.Frame(main, bg="#F5F5F5", relief=tk.SUNKEN, bd=1)
        self.details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        self.details_frame.pack_propagate(False)

        details_text = tk.Text(self.details_frame, font=("Consolas", 8), bg="#F5F5F5", fg="#666666", height=8, width=50, relief=tk.FLAT, bd=0)
        details_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        details_text.insert(tk.END, details)
        details_text.config(state=tk.DISABLED)

        # Buttons
        btn_frame = tk.Frame(main, bg="#FFFFFF")
        btn_frame.pack(fill=tk.X, pady=(0, 0))

        if on_retry:
            retry_btn = tk.Button(btn_frame, text="RETRY", command=self._on_retry,
                                 bg="#4CAF50", fg="#FFFFFF", font=("Arial", 10, "bold"),
                                 relief=tk.FLAT, bd=0, padx=16, pady=8)
            retry_btn.pack(side=tk.LEFT, padx=(0, 8))
            add_hover_effect(retry_btn, "#4CAF50", "#45A049", "#FFFFFF")

        if on_change_url:
            url_btn = tk.Button(btn_frame, text="CHANGE URL", command=self._on_change_url,
                               bg="#2196F3", fg="#FFFFFF", font=("Arial", 10, "bold"),
                               relief=tk.FLAT, bd=0, padx=16, pady=8)
            url_btn.pack(side=tk.LEFT, padx=(0, 8))
            add_hover_effect(url_btn, "#2196F3", "#1976D2", "#FFFFFF")

        exit_btn = tk.Button(btn_frame, text="EXIT", command=self._on_exit,
                            bg="#F44336", fg="#FFFFFF", font=("Arial", 10, "bold"),
                            relief=tk.FLAT, bd=0, padx=16, pady=8)
        exit_btn.pack(side=tk.RIGHT)
        add_hover_effect(exit_btn, "#F44336", "#D32F2F", "#FFFFFF")

    def _on_retry(self):
        self.result = "retry"
        if self.on_retry:
            self.on_retry()
        try:
            if self.window.winfo_exists():
                self.window.quit()
        except:
            pass

    def _on_change_url(self):
        self.result = "change_url"
        if self.on_change_url:
            self.on_change_url()
        try:
            if self.window.winfo_exists():
                self.window.quit()
        except:
            pass

    def _on_exit(self):
        self.result = "exit"
        if self.on_exit:
            self.on_exit()
        try:
            if self.window.winfo_exists():
                self.window.quit()
        except:
            pass

    def show(self):
        self.window.transient()
        self.window.grab_set()
        self.window.mainloop()
        return self.result

# ==================== SETUP WINDOW (First-Time Configuration) ====================
class SetupWindow:
    SETUP_BG = "#FFFFFF"
    SETUP_CARD = "#FFFFFF"
    SETUP_PANEL = "#F5F5F5"
    SETUP_BORDER = "#E0E0E0"
    SETUP_TEXT = "#1A1A1A"
    SETUP_TEXT2 = "#666666"
    SETUP_RED = "#AF151D"
    SETUP_GREEN = "#4CAF50"

    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Bellmounth Setup")
        self.window.geometry("600x500")
        self.window.configure(bg=self.SETUP_BG)
        self.window.resizable(False, False)
        self.result = None
        self.api_client = None
        self._build_ui()
        self.window.transient()
        self.window.grab_set()

    def _build_ui(self):
        main = tk.Frame(self.window, bg=self.SETUP_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        # Title
        tk.Label(main, text="BELLMOUNTH SETUP", bg=self.SETUP_BG, fg=self.SETUP_TEXT,
                font=("Arial", 18, "bold")).pack(anchor=tk.W, pady=(0, 10))

        tk.Label(main, text="Configure API connection for first launch", bg=self.SETUP_BG,
                fg=self.SETUP_TEXT2, font=("Arial", 10)).pack(anchor=tk.W, pady=(0, 30))

        # API URL field
        tk.Label(main, text="API URL", bg=self.SETUP_BG, fg=self.SETUP_TEXT2,
                font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 8))

        url_frame = tk.Frame(main, bg=self.SETUP_BG)
        url_frame.pack(fill=tk.X, pady=(0, 20))

        self.api_url_entry = tk.Entry(url_frame, font=("Consolas", 10),
                                     bg=self.SETUP_PANEL, fg=self.SETUP_TEXT,
                                     insertbackground=self.SETUP_RED,
                                     relief=tk.FLAT, bd=0, highlightthickness=2,
                                     highlightbackground=self.SETUP_BORDER,
                                     highlightcolor=self.SETUP_RED)
        self.api_url_entry.insert(0, "http://localhost:8000")
        self.api_url_entry.pack(fill=tk.X, ipady=10)

        # Example label
        tk.Label(main, text="Example: http://localhost:8000  or  https://bellmounth-api.azurewebsites.net",
                bg=self.SETUP_BG, fg=self.SETUP_TEXT2, font=("Arial", 8)).pack(anchor=tk.W, pady=(0, 20))

        # Status label
        self.status_label = tk.Label(main, text="", bg=self.SETUP_BG, fg=self.SETUP_GREEN,
                                    font=("Arial", 10))
        self.status_label.pack(pady=(0, 20))

        # Error label
        self.error_label = tk.Label(main, text="", bg=self.SETUP_BG, fg=self.SETUP_RED,
                                   font=("Arial", 10))
        self.error_label.pack(pady=(0, 20))

        # Button frame
        btn_frame = tk.Frame(main, bg=self.SETUP_BG)
        btn_frame.pack(fill=tk.X, pady=(30, 0))

        test_btn = tk.Button(btn_frame, text="TEST CONNECTION", command=self._test_connection,
                 bg=self.SETUP_PANEL, fg=self.SETUP_TEXT, font=("Arial", 11, "bold"),
                 relief=tk.FLAT, bd=0, padx=16, pady=10,
                 activebackground=self.SETUP_BORDER, activeforeground=self.SETUP_TEXT,
                 cursor="hand2")
        test_btn.pack(side=tk.LEFT, padx=(0, 10))

        save_btn = tk.Button(btn_frame, text="SAVE & CONTINUE", command=self._save_config,
                 bg=self.SETUP_RED, fg="#FFFFFF", font=("Arial", 11, "bold"),
                 relief=tk.FLAT, bd=0, padx=16, pady=10,
                 activebackground="#8B0F15", activeforeground="#FFFFFF",
                 cursor="hand2")
        save_btn.pack(side=tk.LEFT)
        add_hover_effect(save_btn, self.SETUP_RED, self.SETUP_RED, "#FFFFFF")
        add_hover_effect(test_btn, self.SETUP_PANEL, "#E8E8E8", self.SETUP_TEXT)

    def _test_connection(self):
        api_url = self.api_url_entry.get().strip()
        if not api_url:
            self.error_label.config(text="✕ API URL cannot be empty")
            self.status_label.config(text="")
            return

        self.status_label.config(text="Testing connection...")
        self.window.update()

        client = APIClient(api_url)
        result = client.health_check()
        if result.get("ok"):
            self.status_label.config(text="✓ Connection successful!", fg=self.SETUP_GREEN)
            self.error_label.config(text="")
            self.api_client = client
        else:
            error_type = result.get("error_type", "unknown")
            error_msg = result.get("error", "Cannot connect to API")

            error_text_map = {
                "no_internet": "✕ No internet connection",
                "server_down": "✕ Server unreachable",
                "server_error": "✕ Server error",
                "auth_error": "✕ Authentication failed",
                "unknown": f"✕ {error_msg}"
            }

            self.error_label.config(text=error_text_map.get(error_type, f"✕ {error_msg}"))
            self.status_label.config(text="")

    def _save_config(self):
        if not self.api_client:
            self.error_label.config(text="✕ Test connection first before saving")
            return

        api_url = self.api_url_entry.get().strip()
        config = {"api_url": api_url}

        try:
            CONFIG_FILE.write_text(json.dumps(config, indent=2))
            self.result = api_url
            self.window.destroy()
        except Exception as e:
            self.error_label.config(text=f"✕ Error saving config: {str(e)}")

    def show(self):
        self.window.mainloop()
        return self.result

# ==================== LOGIN WINDOW ====================
class LoginWindow:
    # Light theme colors for login
    LOGIN_BG = "#FFFFFF"
    LOGIN_CARD = "#FFFFFF"
    LOGIN_PANEL = "#F5F5F5"
    LOGIN_BORDER = "#E0E0E0"
    LOGIN_TEXT = "#1A1A1A"
    LOGIN_TEXT2 = "#666666"
    LOGIN_RED = "#AF151D"

    def __init__(self, api_client: APIClient):
        self.window = tk.Tk()
        self.window.title("Bellmounth Inspection System")
        self.window.geometry("500x650")
        self.window.configure(bg=self.LOGIN_BG)
        self.window.resizable(False, False)

        self.api_client = api_client
        self.result = None

        self._build_ui()
        self.window.transient()
        self.window.grab_set()

    def _load_config(self):
        if CONFIG_FILE.exists():
            return json.loads(CONFIG_FILE.read_text())
        return {"machine_name": "LAB-01", "password": "bellmounth"}

    def _build_ui(self):
        main = tk.Frame(self.window, bg=self.LOGIN_BG)
        main.pack(fill=tk.BOTH, expand=True)

        # Top spacer
        tk.Frame(main, bg=self.LOGIN_BG, height=40).pack()

        # Logo section - Display logo image
        logo_frame = tk.Frame(main, bg=self.LOGIN_BG)
        logo_frame.pack(fill=tk.X, pady=(0, 30))

        # Load and display logo image
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            try:
                logo_img = Image.open(str(logo_path))
                logo_img = logo_img.resize((250, 90), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = tk.Label(logo_frame, image=logo_photo, bg=self.LOGIN_BG)
                logo_label.image = logo_photo
                logo_label.pack()
            except Exception as e:
                tk.Label(logo_frame, text="YAZAKI BELLMOUNTH", bg=self.LOGIN_BG, fg=self.LOGIN_TEXT,
                        font=("Arial", 24, "bold")).pack()
        else:
            tk.Label(logo_frame, text="YAZAKI BELLMOUNTH", bg=self.LOGIN_BG, fg=self.LOGIN_TEXT,
                    font=("Arial", 24, "bold")).pack()

        # Form card
        card = tk.Frame(main, bg=self.LOGIN_CARD)
        card.pack(padx=40, fill=tk.BOTH, expand=True)

        # Username field
        tk.Label(card, text="USERNAME", bg=self.LOGIN_CARD, fg=self.LOGIN_TEXT2,
                font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=28, pady=(24, 8))
        self.username_entry = tk.Entry(card, font=("Consolas", 11),
                                     bg=self.LOGIN_PANEL, fg=self.LOGIN_TEXT, insertbackground=self.LOGIN_RED,
                                     relief=tk.FLAT, bd=0, highlightthickness=2,
                                     highlightbackground=self.LOGIN_BORDER, highlightcolor=self.LOGIN_RED)
        self.username_entry.insert(0, "")
        self.username_entry.pack(padx=28, pady=(0, 20), fill=tk.X, ipady=10)

        # Password field
        tk.Label(card, text="PASSWORD", bg=self.LOGIN_CARD, fg=self.LOGIN_TEXT2,
                font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=28, pady=(0, 8))
        self.password_entry = tk.Entry(card, font=("Consolas", 11), show="●",
                                      bg=self.LOGIN_PANEL, fg=self.LOGIN_TEXT, insertbackground=self.LOGIN_RED,
                                      relief=tk.FLAT, bd=0, highlightthickness=2,
                                      highlightbackground=self.LOGIN_BORDER, highlightcolor=self.LOGIN_RED)
        self.password_entry.pack(padx=28, pady=(0, 20), fill=tk.X, ipady=10)

        # Error message
        self.error_label = tk.Label(card, text="", bg=self.LOGIN_CARD, fg=self.LOGIN_RED,
                                   font=("Arial", 10))
        self.error_label.pack(pady=(0, 16))

        # Sign in button - Yazaki red
        sign_in_btn = tk.Button(card, text="SIGN IN", command=self._login,
                 bg=self.LOGIN_RED, fg="#FFFFFF", font=("Arial", 12, "bold"),
                 relief=tk.FLAT, bd=0, padx=24, pady=12,
                 activebackground="#8B0F15", activeforeground="#FFFFFF",
                 cursor="hand2")
        sign_in_btn.pack(padx=28, pady=(0, 28), fill=tk.X)
        add_hover_effect(sign_in_btn, self.LOGIN_RED, self.LOGIN_RED, "#FFFFFF")

        # Footer
        tk.Label(card, text="Press Enter to sign in", bg=self.LOGIN_CARD, fg=self.LOGIN_TEXT2,
                font=("Arial", 9)).pack(pady=(0, 20))

        self.password_entry.bind("<Return>", lambda e: self._login())
        self.username_entry.focus()

    def _login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            self.error_label.config(text="✕ Username and password required")
            return

        # Call API to authenticate
        result = self.api_client.login(username, password)

        if "error" in result:
            error_type = result.get("error_type", "unknown")
            error_msg = result.get("error", "Login failed")
            details = result.get("details", "")

            # Show ErrorDialog for connection errors
            if error_type in ["no_internet", "server_down", "server_error"]:
                error_dialog = ErrorDialog(
                    self.window,
                    error_type,
                    error_msg,
                    details,
                    on_retry=self._login,
                    on_exit=lambda: self.window.destroy()
                )
                error_dialog.show()
            else:
                self.error_label.config(text=f"✕ {error_msg}")
                self.password_entry.delete(0, tk.END)
                self.password_entry.focus()
        else:
            # Login successful - store result and close
            self.result = result
            self.window.destroy()

    def show(self):
        self.window.mainloop()
        return self.result

# ==================== BUTTON HOVER ANIMATION ====================
def add_hover_effect(button, normal_color, hover_color, text_color=TEXT):
    normal_state = {"bg": normal_color, "fg": text_color, "relief": tk.FLAT, "bd": 0}
    hover_state = {"bg": hover_color, "fg": text_color, "relief": tk.RAISED, "bd": 2}

    # Set active colors for when button is clicked/hovered
    button.config(activebackground=hover_color, activeforeground=text_color)

    def on_enter(event):
        if button.cget("state") == tk.NORMAL:
            button.config(**hover_state)
    def on_leave(event):
        if button.cget("state") == tk.NORMAL:
            button.config(**normal_state)

    button.bind("<Enter>", on_enter)
    button.bind("<Leave>", on_leave)

# ==================== MAIN APP ====================
class MainApp:
    def __init__(self, machine_name, api_client: APIClient = None):
        self.root = tk.Tk()
        self.root.title(f"Bellmounth Inspection — {machine_name}")
        self.root.geometry("1440x900")
        self.root.configure(bg=BG)
        self.root.state('zoomed')
        self.machine_name = machine_name
        self.api_client = api_client
        self.selected_switch = None

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
        self.cached_canvas_size = (0, 0)
        self.frame_count = 0
        self.drag_start = None
        self.last_zoom = 1.0
        self.sdk_call_count = 0
        self.annotation_count = self._count_annotations()
        self._tf_model = None
        self._loop_running = True
        self.cable_status = "No cable"
        self.measurement_started = False
        self.cable_state = "no cable detected"
        self.last_api_error = None
        self.last_upload_result = None
        self.last_health_check_time = 0
        self.health_check_interval = 10  # seconds - more responsive

        self._build_ui()
        self._update_clock()
        self._start_loop()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

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

    def _on_closing(self):
        self._loop_running = False
        if self.cap:
            self.cap.release()
        if self.pixel_measure:
            self.pixel_measure.close()
        self.root.destroy()

    def _fetch_switches(self):
        """Fetch available switches from API"""
        if self.api_client:
            result = self.api_client.get_switches()
            if result.get("ok"):
                return result.get("data", [])
            else:
                # Store error for UI to handle
                self.last_api_error = result
                return []
        return []

    def _switch_page(self, page_id, callback):
        """Switch to a different page"""
        self.current_page = page_id

        # Update button styles
        for btn_id, btn in self.page_buttons.items():
            if btn_id == page_id:
                btn.config(bg=ACCENT, fg="#FFFFFF")
            else:
                btn.config(bg=PANEL, fg=TEXT2)

        # Clear measure page specific widget references only
        measure_attrs = ['canvas', 'mode_btns', 'capture_btn', 'save_btn_auto', 'save_btn_manual',
                        'p1_lbl', 'p2_lbl', 'dist_lbl', 'cable_ok_dot', 'cable_ok_lbl',
                        'cable_not_ok_dot', 'cable_not_ok_lbl', 'manual_input_card',
                        'zoom_val', 'mpp_val', 'p1x_entry', 'p1y_entry', 'p2x_entry', 'p2y_entry']
        for attr in measure_attrs:
            if hasattr(self, attr):
                try:
                    delattr(self, attr)
                except:
                    pass

        # Clear content container
        for widget in self.content_container.winfo_children():
            widget.destroy()

        # Update window
        self.root.update_idletasks()

        # Build the page
        callback()

    def _show_switches_page(self):
        """Display switches selection page"""
        switches = self._fetch_switches()

        # Check if there was an API error
        if not switches and hasattr(self, 'last_api_error'):
            error = self.last_api_error
            error_type = error.get("error_type", "unknown")
            message = error.get("error", "Failed to load switches")
            details = error.get("details", "")

            frame = tk.Frame(self.content_container, bg=BG)
            frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            tk.Label(frame, text="SELECT SWITCH TO MEASURE", bg=BG, fg=TEXT,
                    font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

            error_dialog = ErrorDialog(
                self.root,
                error_type,
                message,
                details,
                on_retry=lambda: self._switch_page("switches", self._show_switches_page),
                on_exit=self._on_closing
            )
            error_dialog.show()
            return

        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="SELECT SWITCH TO MEASURE", bg=BG, fg=TEXT,
                font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Search bar
        search_frame = tk.Frame(frame, bg=BG)
        search_frame.pack(fill=tk.X, pady=(0, 16))

        tk.Label(search_frame, text="Search:", bg=BG, fg=TEXT2,
                font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 8))

        search_var = tk.StringVar()
        search_entry = tk.Entry(search_frame, font=("Consolas", 11),
                               bg=PANEL, fg=TEXT, insertbackground=ACCENT,
                               relief=tk.FLAT, bd=0, highlightthickness=2,
                               highlightbackground=BORDER, highlightcolor=ACCENT,
                               width=30)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        if not switches:
            tk.Label(frame, text="No switches available", bg=BG, fg=TEXT2,
                    font=("Arial", 12)).pack(pady=40)
            return

        # Scrollable container
        switches_container = tk.Frame(frame, bg=BG)
        switches_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(switches_container, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(switches_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def update_switches(*args):
            for widget in scrollable_frame.winfo_children():
                widget.destroy()

            search_text = search_var.get().lower()
            filtered = [s for s in switches if search_text in s.get("switch_name", "").lower()]

            if not filtered:
                tk.Label(scrollable_frame, text="No switches found", bg=BG, fg=TEXT2,
                        font=("Arial", 12)).pack(pady=20)
                return

            for switch in filtered:
                card = tk.Frame(scrollable_frame, bg=CARD, relief=tk.RAISED, bd=1)
                card.pack(fill=tk.X, pady=8)

                def select_and_measure(sw=switch):
                    self.selected_switch = sw
                    self._switch_page("measure", self._show_measure_page)

                inner = tk.Frame(card, bg=CARD)
                inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

                left = tk.Frame(inner, bg=CARD)
                left.pack(side=tk.LEFT, fill=tk.X, expand=True)

                tk.Label(left, text=switch.get("switch_name", "Unknown"), bg=CARD, fg=TEXT,
                        font=("Arial", 13, "bold")).pack(anchor=tk.W)
                tk.Label(left, text=f"Expected: {switch.get('expected_diameter_mm')}mm  |  Range: {switch.get('tolerance_min')}-{switch.get('tolerance_max')}mm",
                        bg=CARD, fg=TEXT2, font=("Arial", 10)).pack(anchor=tk.W, pady=(4, 0))
                tk.Label(left, text=f"Type: {switch.get('cable_type', 'N/A')}", bg=CARD, fg=TEXT2,
                        font=("Arial", 9)).pack(anchor=tk.W)

                btn = tk.Button(inner, text="SELECT", command=select_and_measure,
                               bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"),
                               relief=tk.FLAT, bd=0, padx=20, pady=8)
                btn.pack(side=tk.RIGHT, padx=(20, 0))
                add_hover_effect(btn, ACCENT, ACCENT, "#FFFFFF")

        search_var.trace("w", update_switches)
        update_switches()

    def _show_measure_page(self):
        """Display measurement page - builds the camera and measurement UI"""
        main_frame = tk.Frame(self.content_container, bg=BG)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Switch info at top
        if self.selected_switch:
            info = tk.Label(main_frame, text=f"Switch: {self.selected_switch.get('switch_name')} | Expected: {self.selected_switch.get('expected_diameter_mm')}mm",
                           bg=BG, fg=TEXT, font=("Arial", 11, "bold"))
            info.pack(fill=tk.X, padx=10, pady=8)

        # Create a horizontal layout: canvas on left, controls on right
        content_frame = tk.Frame(main_frame, bg=BG)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Configure grid weights for proper layout
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=0)

        # Canvas (left side)
        left_frame = tk.Frame(content_frame, bg=BG)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Camera canvas
        self.canvas = tk.Canvas(left_frame, bg="#000000", highlightthickness=0, highlightbackground=BORDER)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # Controls (right side) - scrollable sidebar
        right_container = tk.Frame(content_frame, bg=BG)
        right_container.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        right_scrollbar = tk.Scrollbar(right_container, orient=tk.VERTICAL)
        right_canvas = tk.Canvas(right_container, bg=BG, highlightthickness=0, yscrollcommand=right_scrollbar.set, width=300)
        right_scrollbar.config(command=right_canvas.yview)

        right_frame = tk.Frame(right_canvas, bg=BG)
        right_frame_id = right_canvas.create_window((0, 0), window=right_frame, anchor="nw")

        def on_frame_configure(event=None):
            right_canvas.configure(scrollregion=right_canvas.bbox("all"))

        right_frame.bind("<Configure>", on_frame_configure)

        right_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Mousewheel scrolling
        def _on_right_scroll(event):
            try:
                right_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass
        right_frame.bind_all("<MouseWheel>", _on_right_scroll)

        # Mode selection
        mode_card = self._card(right_frame, "MEASUREMENT MODE")
        self.mode_btns = {}
        for mode in ["AUTO", "MANUAL"]:
            btn = tk.Button(mode_card, text=mode, command=lambda m=mode: self._set_mode(m),
                           bg=SEP, fg=TEXT, font=("Arial", 10, "bold"),
                           relief=tk.FLAT, bd=0, padx=12, pady=8)
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self.mode_btns[mode] = btn
            add_hover_effect(btn, SEP, BORDER, TEXT)
        self._set_mode("AUTO")

        # Measurement display
        measure_card = self._card(right_frame, "MEASUREMENT")
        tk.Label(measure_card, text="P1", bg=CARD, fg=TEXT2, font=("Arial", 8, "bold")).pack(anchor=tk.W)
        self.p1_lbl = tk.Label(measure_card, text="(---, ---)", bg=CARD, fg=TEXT, font=("Consolas", 9))
        self.p1_lbl.pack(anchor=tk.W, pady=(0, 6))

        tk.Label(measure_card, text="P2", bg=CARD, fg=TEXT2, font=("Arial", 8, "bold")).pack(anchor=tk.W)
        self.p2_lbl = tk.Label(measure_card, text="(---, ---)", bg=CARD, fg=TEXT, font=("Consolas", 9))
        self.p2_lbl.pack(anchor=tk.W, pady=(0, 10))

        tk.Label(measure_card, text="Distance", bg=CARD, fg=TEXT2, font=("Arial", 8, "bold")).pack(anchor=tk.W)
        dist_frame = tk.Frame(measure_card, bg=CARD)
        dist_frame.pack(anchor=tk.W, pady=(0, 10))
        self.dist_lbl = tk.Label(dist_frame, text="--", bg=CARD, fg=TEXT, font=("Consolas", 14, "bold"))
        self.dist_lbl.pack(side=tk.LEFT)
        tk.Label(dist_frame, text="mm", bg=CARD, fg=TEXT2, font=("Arial", 9)).pack(side=tk.LEFT, padx=(4, 0))

        # Cable status indicator
        status_card = self._card(right_frame, "CABLE STATUS")
        self.cable_ok_dot = tk.Label(status_card, text="●", bg=CARD, fg=TEXT2, font=("Arial", 10))
        self.cable_ok_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.cable_ok_lbl = tk.Label(status_card, text="CABLE OK", bg=CARD, fg=TEXT2, font=("Arial", 10, "bold"))
        self.cable_ok_lbl.pack(side=tk.LEFT)

        status_card2 = self._card(right_frame, "")
        self.cable_not_ok_dot = tk.Label(status_card2, text="●", bg=CARD, fg=TEXT2, font=("Arial", 10))
        self.cable_not_ok_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.cable_not_ok_lbl = tk.Label(status_card2, text="NOT OK", bg=CARD, fg=TEXT2, font=("Arial", 10, "bold"))
        self.cable_not_ok_lbl.pack(side=tk.LEFT)

        # Manual input (shown when MANUAL mode active)
        self.manual_input_card = self._card(right_frame, "COORDINATES")

        coords_row1 = tk.Frame(self.manual_input_card, bg=CARD)
        coords_row1.pack(fill=tk.X, pady=(0, 8))
        tk.Label(coords_row1, text="P1 X:", bg=CARD, fg=TEXT, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.p1x_entry = tk.Entry(coords_row1, font=("Consolas", 9), bg=PANEL, fg=TEXT,
                                 relief=tk.FLAT, bd=0, width=8, highlightthickness=1,
                                 highlightbackground=BORDER, highlightcolor=ACCENT)
        self.p1x_entry.pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(coords_row1, text="P1 Y:", bg=CARD, fg=TEXT, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.p1y_entry = tk.Entry(coords_row1, font=("Consolas", 9), bg=PANEL, fg=TEXT,
                                 relief=tk.FLAT, bd=0, width=8, highlightthickness=1,
                                 highlightbackground=BORDER, highlightcolor=ACCENT)
        self.p1y_entry.pack(side=tk.LEFT)

        coords_row2 = tk.Frame(self.manual_input_card, bg=CARD)
        coords_row2.pack(fill=tk.X, pady=(0, 12))
        tk.Label(coords_row2, text="P2 X:", bg=CARD, fg=TEXT, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.p2x_entry = tk.Entry(coords_row2, font=("Consolas", 9), bg=PANEL, fg=TEXT,
                                 relief=tk.FLAT, bd=0, width=8, highlightthickness=1,
                                 highlightbackground=BORDER, highlightcolor=ACCENT)
        self.p2x_entry.pack(side=tk.LEFT, padx=(0, 12))
        tk.Label(coords_row2, text="P2 Y:", bg=CARD, fg=TEXT, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.p2y_entry = tk.Entry(coords_row2, font=("Consolas", 9), bg=PANEL, fg=TEXT,
                                 relief=tk.FLAT, bd=0, width=8, highlightthickness=1,
                                 highlightbackground=BORDER, highlightcolor=ACCENT)
        self.p2y_entry.pack(side=tk.LEFT)

        apply_btn = tk.Button(self.manual_input_card, text="APPLY", command=self._apply_manual_coords,
                             bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"),
                             relief=tk.FLAT, bd=0, padx=12, pady=6)
        apply_btn.pack(fill=tk.X)
        add_hover_effect(apply_btn, ACCENT, ACCENT, "#FFFFFF")

        # SDK values
        sdk_card = self._card(right_frame, "SDK VALUES")
        zoom_row = tk.Frame(sdk_card, bg=CARD)
        zoom_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(zoom_row, text="Zoom:", bg=CARD, fg=TEXT2, font=("Arial", 8)).pack(side=tk.LEFT)
        self.zoom_val = tk.Label(zoom_row, text="1.00x", bg=CARD, fg=TEXT, font=("Consolas", 9, "bold"))
        self.zoom_val.pack(side=tk.LEFT, padx=(4, 0))

        mpp_row = tk.Frame(sdk_card, bg=CARD)
        mpp_row.pack(fill=tk.X)
        tk.Label(mpp_row, text="mm/px:", bg=CARD, fg=TEXT2, font=("Arial", 8)).pack(side=tk.LEFT)
        self.mpp_val = tk.Label(mpp_row, text="0.0165", bg=CARD, fg=TEXT, font=("Consolas", 9, "bold"))
        self.mpp_val.pack(side=tk.LEFT, padx=(4, 0))

        # Action buttons
        action_card = self._card(right_frame, "ACTIONS")
        self.capture_btn = tk.Button(action_card, text="CAPTURE", command=self._on_capture,
                                   bg=BTN, fg="#FFFFFF", font=("Arial", 10, "bold"),
                                   relief=tk.FLAT, bd=0, padx=16, pady=8)
        self.capture_btn.pack(fill=tk.X, pady=(0, 6))
        add_hover_effect(self.capture_btn, BTN, ACCENT, "#FFFFFF")

        def _upload_with_mode():
            mode_text = "AUTO mode" if self.mode == "AUTO" else "MANUAL mode"
            self._save_annotation()

            # Check upload result
            if hasattr(self, 'last_upload_result') and self.last_upload_result:
                result = self.last_upload_result
                if result.get("ok"):
                    messagebox.showinfo("Success", f"✓ Image uploaded ({mode_text})")
                else:
                    error_type = result.get("error_type", "unknown")
                    error_msg = result.get("error", "Upload failed")
                    details = result.get("details", "")

                    error_dialog = ErrorDialog(
                        self.root,
                        error_type,
                        error_msg,
                        details,
                        on_retry=_upload_with_mode,
                        on_exit=None
                    )
                    error_dialog.show()
            else:
                messagebox.showinfo("Success", f"✓ Image saved locally ({mode_text})")

        upload_btn = tk.Button(action_card, text="UPLOAD TO SERVER", command=_upload_with_mode,
                              bg=GREEN, fg="#FFFFFF", font=("Arial", 10, "bold"),
                              relief=tk.FLAT, bd=0, padx=16, pady=8)
        upload_btn.pack(fill=tk.X)
        add_hover_effect(upload_btn, GREEN, "#45A049", "#FFFFFF")

        # Trigger initial display
        self._update_display()

    def _show_notifications_page(self):
        """Display notifications page"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="NOTIFICATIONS", bg=BG, fg=TEXT,
                font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text="No new notifications", bg=BG, fg=TEXT2,
                font=("Arial", 12)).pack(pady=40)

    def _show_reclamations_page(self):
        """Display reclamations (issues) report page"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="REPORT AN ISSUE", bg=BG, fg=TEXT,
                font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        card = tk.Frame(frame, bg=CARD, relief=tk.FLAT, bd=1)
        card.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        tk.Label(inner, text="Title:", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        title_entry = tk.Entry(inner, font=("Consolas", 10), bg=PANEL, fg=TEXT,
                              relief=tk.FLAT, bd=0, highlightthickness=2,
                              highlightbackground=BORDER, highlightcolor=ACCENT)
        title_entry.pack(fill=tk.X, pady=(0, 12), ipady=8)

        tk.Label(inner, text="Description:", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        desc_text = tk.Text(inner, font=("Consolas", 10), bg=PANEL, fg=TEXT,
                           relief=tk.FLAT, bd=0, height=6, highlightthickness=2,
                           highlightbackground=BORDER, highlightcolor=ACCENT)
        desc_text.pack(fill=tk.BOTH, expand=True, pady=(0, 12), ipady=8)

        tk.Label(inner, text="Category:", bg=CARD, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        category_var = tk.StringVar(value="bug")
        category_menu = tk.OptionMenu(inner, category_var, "bug", "slow", "incorrect", "other")
        category_menu.config(bg=PANEL, fg=TEXT, font=("Arial", 10), relief=tk.FLAT, bd=0, highlightthickness=0)
        category_menu.pack(fill=tk.X, pady=(0, 12))

        btn = tk.Button(inner, text="SUBMIT REPORT", command=lambda: print("Report submitted"),
                       bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"),
                       relief=tk.FLAT, bd=0, padx=20, pady=10)
        btn.pack(fill=tk.X)
        add_hover_effect(btn, ACCENT, ACCENT, "#FFFFFF")


    def _build_ui(self):
        # Header bar
        top = tk.Frame(self.root, bg=PANEL, height=58)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        # Load and display logo in header
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            try:
                logo_img = Image.open(str(logo_path))
                logo_img = logo_img.resize((135, 48), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = tk.Label(top, image=logo_photo, bg=PANEL)
                logo_label.image = logo_photo
                logo_label.pack(side=tk.LEFT, padx=12, pady=9)
            except:
                tk.Label(top, text="YAZAKI BELLMOUNTH", bg=PANEL, fg=TEXT,
                        font=("Arial", 13, "bold"), padx=20).pack(side=tk.LEFT, pady=12)
        else:
            tk.Label(top, text="YAZAKI BELLMOUNTH", bg=PANEL, fg=TEXT,
                    font=("Arial", 13, "bold"), padx=20).pack(side=tk.LEFT, pady=12)

        # Selected switch display
        if self.selected_switch:
            tk.Label(top, text=f"SWITCH: {self.selected_switch.get('switch_name', 'Unknown')}", bg=PANEL, fg=TEXT,
                    font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=12)

        tk.Frame(top, bg=PANEL).pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(top, text="●", bg=PANEL, fg=RED, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 4))
        tk.Label(top, text="LIVE", bg=PANEL, fg=TEXT2, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 12))

        # Illumination controls
        tk.Label(top, text="LED", bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 6))
        led_on_btn = tk.Button(top, text="ON", command=self._led_on,
                 bg=GREEN, fg="#001A00", font=("Arial", 8, "bold"),
                 relief=tk.FLAT, bd=0, padx=8, pady=4)
        led_on_btn.pack(side=tk.LEFT, padx=(0, 2))
        add_hover_effect(led_on_btn, GREEN, "#45A049", "#001A00")

        led_off_btn = tk.Button(top, text="OFF", command=self._led_off,
                 bg=SEP, fg=TEXT, font=("Arial", 8, "bold"),
                 relief=tk.FLAT, bd=0, padx=6, pady=4)
        led_off_btn.pack(side=tk.LEFT, padx=(0, 20))
        add_hover_effect(led_off_btn, SEP, "#D3D3D3")

        tk.Frame(top, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        tk.Label(top, text=self.machine_name, bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(side=tk.LEFT, padx=12)
        tk.Frame(top, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        self.clock_lbl = tk.Label(top, text="--:--:--", bg=PANEL, fg=TEXT2, font=("Consolas", 10))
        self.clock_lbl.pack(side=tk.LEFT, padx=12)
        tk.Frame(top, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        quit_btn = tk.Button(top, text="QUIT", command=self._on_closing,
                 bg=RED, fg=TEXT, font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=18, activebackground=RED,
                 activeforeground=TEXT)
        quit_btn.pack(side=tk.LEFT, padx=20, pady=12)
        add_hover_effect(quit_btn, RED, RED, TEXT)

        # Navigation bar
        navbar = tk.Frame(self.root, bg=PANEL, height=45)
        navbar.pack(fill=tk.X, side=tk.TOP)
        navbar.pack_propagate(False)

        self.current_page = "switches"
        self.page_buttons = {}

        pages = [
            ("SWITCHES", "switches", self._show_switches_page),
            ("MEASURE", "measure", self._show_measure_page),
            ("NOTIFICATIONS", "notifications", self._show_notifications_page),
            ("RECLAMATIONS", "reclamations", self._show_reclamations_page),
        ]

        for label, page_id, callback in pages:
            btn = tk.Button(navbar, text=label, command=lambda p=page_id, c=callback: self._switch_page(p, c),
                           bg=PANEL, fg=TEXT2, font=("Arial", 10, "bold"),
                           relief=tk.FLAT, bd=0, padx=16, pady=10,
                           activebackground=PANEL, activeforeground=TEXT)
            btn.pack(side=tk.LEFT, padx=4)
            self.page_buttons[page_id] = btn
            add_hover_effect(btn, PANEL, SEP, TEXT)

        tk.Frame(navbar, bg=BORDER, height=1).pack(fill=tk.X, side=tk.BOTTOM)

        # Content container
        self.content_container = tk.Frame(self.root, bg=BG)
        self.content_container.pack(fill=tk.BOTH, expand=True)

        # Initialize pages - start with switches
        self._switch_page("switches", self._show_switches_page)

    def _set_mode(self, mode):
        if not hasattr(self, 'mode_btns') or not hasattr(self, 'manual_input_card'):
            return

        self.mode = mode
        self.mode_btns["AUTO"].config(bg=BTN if mode=="AUTO" else SEP,
                                      fg=TEXT if mode=="AUTO" else TEXT2)
        self.mode_btns["MANUAL"].config(bg=BTN if mode=="MANUAL" else SEP,
                                        fg=TEXT if mode=="MANUAL" else TEXT2)
        self.p1 = self.p2 = self.dist_mm = None
        self.measurement_started = False
        self._reset_status_leds()
        # Reset zoom and pan when switching modes
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0

        # Show/hide controls based on mode
        if mode == "MANUAL":
            self.manual_input_card.pack(fill=tk.X, padx=12, pady=5)
            self.capture_btn.pack_forget()  # Hide CAPTURE in MANUAL
        else:
            self.manual_input_card.pack_forget()
            self.capture_btn.pack(fill=tk.X, pady=(0, 6))  # Show CAPTURE in AUTO

        if hasattr(self, 'canvas'):
            self._update_display()

    def _on_scroll(self, event):
        if event.delta > 0:
            self.zoom *= 1.1
        else:
            self.zoom /= 1.1
        self.zoom = max(1, min(self.zoom, 10))
        # Reset pan when zooming to center view
        self.pan_x = 0
        self.pan_y = 0
        # Recalculate distance when zoom changes (SDK FOVx changes with zoom)
        self._compute_distance()
        self._update_display()

    def _on_press(self, event):
        try:
            # In MANUAL mode, only place points if both aren't placed yet; otherwise allow pan
            if self.mode == "MANUAL" and self.current_frame is not None and (self.p1 is None or self.p2 is None):
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
                        self.measurement_started = True
                        # Update input fields
                        if hasattr(self, 'p1x_entry'):
                            self.p1x_entry.delete(0, tk.END)
                            self.p1x_entry.insert(0, str(x))
                        if hasattr(self, 'p1y_entry'):
                            self.p1y_entry.delete(0, tk.END)
                            self.p1y_entry.insert(0, str(y))
                    elif self.p2 is None:
                        # Use P1's Y coordinate for P2 (horizontal alignment)
                        self.p2 = (x, self.p1[1])
                        # Update input fields
                        if hasattr(self, 'p2x_entry'):
                            self.p2x_entry.delete(0, tk.END)
                            self.p2x_entry.insert(0, str(x))
                        if hasattr(self, 'p2y_entry'):
                            self.p2y_entry.delete(0, tk.END)
                            self.p2y_entry.insert(0, str(self.p1[1]))
                        self._compute_distance()
            # If both points placed in MANUAL, or in AUTO mode, allow panning
            self.drag_start = (event.x, event.y)
        except:
            pass

    def _on_move(self, event):
        if self.drag_start and self.zoom > 1:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.pan_x -= int(dx / self.zoom)
            self.pan_y -= int(dy / self.zoom)

            # Clamp pan to prevent stretching at edges
            if self.current_frame is not None:
                h, w = self.current_frame.shape[:2]
                new_w = int(w / self.zoom)
                new_h = int(h / self.zoom)
                max_pan_x = (w - new_w) // 2
                max_pan_y = (h - new_h) // 2
                self.pan_x = max(-max_pan_x, min(self.pan_x, max_pan_x))
                self.pan_y = max(-max_pan_y, min(self.pan_y, max_pan_y))

            self.drag_start = (event.x, event.y)

    def _on_release(self, event):
        self.drag_start = None

    def _on_capture(self):
        if self.current_frame is None:
            return

        if self.mode == "AUTO":
            self.measurement_started = True
            result = self._run_inference(self.current_frame)
            if result:
                self.p1, self.p2, self.dist_mm = result

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
        # Use P1's Y coordinate for P2 (horizontal alignment)
        p2 = (int(pred[2] * w), p1[1])
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

        # Save images locally
        cv2.imwrite(str(orig_path), self.current_frame)
        cv2.imwrite(str(thresh_path), apply_threshold(self.current_frame))

        # Calculate measurement values
        pixel_distance = math.dist(self.p1, self.p2)
        measured_mm = pixel_distance * 0.0165  # using default mm_per_pixel

        # Determine measurement status (assume OKAY unless we have switch tolerance info)
        measurement_status = "okay"
        delta_mm = 0.0
        if self.selected_switch:
            expected = self.selected_switch.get("expected_diameter_mm", measured_mm)
            tolerance_min = self.selected_switch.get("tolerance_min", expected - 0.5)
            tolerance_max = self.selected_switch.get("tolerance_max", expected + 0.5)
            delta_mm = measured_mm - expected
            measurement_status = "okay" if (tolerance_min <= measured_mm <= tolerance_max) else "not_okay"

        # Save to local annotations.json
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
            "pixel_distance": pixel_distance,
            "timestamp": datetime.now().isoformat()
        }

        data = json.loads(ANNOTATIONS_FILE.read_text() or "[]")
        data = [d for d in data if d["filename"] != fname]
        data.append(entry)

        tmp = ANNOTATIONS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(ANNOTATIONS_FILE)

        # Try to upload to API if available
        self.last_upload_result = None
        if self.api_client:
            result = self.api_client.upload_capture(
                machine_id=self.machine_name,
                switch_id=self.selected_switch.get("id", "") if self.selected_switch else "",
                measured_value_mm=measured_mm,
                p1_x=self.p1[0],
                p1_y=self.p1[1],
                p2_x=self.p2[0],
                p2_y=self.p2[1],
                capture_method=self.mode.lower(),
                measurement_status=measurement_status,
                delta_mm=delta_mm,
                image_original_path=str(orig_path),
                image_thresholded_path=str(thresh_path)
            )
            self.last_upload_result = result

        self.annotation_count += 1
        if hasattr(self, 'dataset_lbl'):
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

    def _apply_manual_coords(self):
        try:
            p1x = int(self.p1x_entry.get().strip())
            p1y = int(self.p1y_entry.get().strip())
            p2x = int(self.p2x_entry.get().strip())
            # Ignore P2 Y, use P1 Y for horizontal alignment
            self.p1 = (p1x, p1y)
            self.p2 = (p2x, p1y)
            # Update P2 Y field to match P1 Y
            self.p2y_entry.delete(0, tk.END)
            self.p2y_entry.insert(0, str(p1y))
            self._compute_distance()
            self._update_display()
        except ValueError:
            pass

    def _count_annotations(self):
        if ANNOTATIONS_FILE.exists():
            return len(json.loads(ANNOTATIONS_FILE.read_text() or "[]"))
        return 0

    def _update_clock(self):
        self.clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._update_clock)

    def _set_cable_ok(self, is_ok):
        """Set LED status: True = CABLE OK (green), False = CABLE NOT OK (red)"""
        if not hasattr(self, 'cable_ok_dot'):
            return
        if is_ok:
            self.cable_ok_dot.config(fg=GREEN)
            self.cable_ok_lbl.config(fg=GREEN)
            self.cable_not_ok_dot.config(fg=TEXT2)
            self.cable_not_ok_lbl.config(fg=TEXT2)
        else:
            self.cable_ok_dot.config(fg=TEXT2)
            self.cable_ok_lbl.config(fg=TEXT2)
            self.cable_not_ok_dot.config(fg=RED)
            self.cable_not_ok_lbl.config(fg=RED)

    def _reset_status_leds(self):
        """Reset both LEDs to OFF (gray)"""
        try:
            if hasattr(self, 'cable_ok_dot'):
                self.cable_ok_dot.config(fg=TEXT2)
            if hasattr(self, 'cable_ok_lbl'):
                self.cable_ok_lbl.config(fg=TEXT2)
            if hasattr(self, 'cable_not_ok_dot'):
                self.cable_not_ok_dot.config(fg=TEXT2)
            if hasattr(self, 'cable_not_ok_lbl'):
                self.cable_not_ok_lbl.config(fg=TEXT2)
        except:
            pass

    def set_cable_state(self, state):
        """Update cable state display (no cable detected / cable male placed / cable good placed)"""
        self.cable_state = state

    def _update_display(self):
        if self.current_frame is None or not hasattr(self, 'canvas'):
            return

        disp = self.current_frame.copy()
        h, w = disp.shape[:2]

        # Apply zoom by cropping and resizing back
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
            # Resize back to original size for correct coordinate mapping
            disp = cv2.resize(disp, (w, h), interpolation=cv2.INTER_LINEAR)

        # Scale drawing elements based on zoom
        point_radius = max(2, int(5 * min(self.zoom, 1.2)))
        line_thickness = max(1, int(2 * min(self.zoom, 2)))
        dash_segment = max(8, int(16 * min(self.zoom, 1.5)))
        text_size = 0.6 * min(self.zoom, 2)

        # Calculate crop region for zoom+pan
        crop_x1, crop_y1, crop_x2, crop_y2 = 0, 0, w, h
        if self.zoom > 1:
            new_w = int(w / self.zoom)
            new_h = int(h / self.zoom)
            cx = w // 2 + self.pan_x
            cy = h // 2 + self.pan_y
            crop_x1 = max(cx - new_w // 2, 0)
            crop_y1 = max(cy - new_h // 2, 0)
            crop_x2 = min(cx + new_w // 2, w)
            crop_y2 = min(cy + new_h // 2, h)

        # Transform points to account for zoom and pan
        def scale_point(pt, zoom, crop_x1, crop_y1, crop_x2, crop_y2):
            if pt is None:
                return None
            crop_w = crop_x2 - crop_x1
            crop_h = crop_y2 - crop_y1
            # Map point from original frame to cropped region
            # Then scale it to fill the display
            rel_x = (pt[0] - crop_x1) / crop_w if crop_w > 0 else 0
            rel_y = (pt[1] - crop_y1) / crop_h if crop_h > 0 else 0
            display_x = int(rel_x * w)
            display_y = int(rel_y * h)
            return (display_x, display_y)

        p1_scaled = scale_point(self.p1, self.zoom, crop_x1, crop_y1, crop_x2, crop_y2)
        p2_scaled = scale_point(self.p2, self.zoom, crop_x1, crop_y1, crop_x2, crop_y2)

        # Draw points and line with scaled positions
        if p1_scaled:
            cv2.circle(disp, p1_scaled, point_radius, (0, 255, 0), -1)  # Green filled dot for P1
        if p2_scaled:
            cv2.circle(disp, p2_scaled, point_radius, (255, 0, 0), -1)  # Blue filled dot for P2
        if p1_scaled and p2_scaled:
            dx, dy = p2_scaled[0]-p1_scaled[0], p2_scaled[1]-p1_scaled[1]
            dist = int(math.hypot(dx, dy))
            if dist > 20:  # Only draw dashed line if distance is meaningful
                step = max(10, dash_segment)
                for i in range(0, dist, step):
                    t0 = i/dist
                    t1 = min((i+step*0.6)/dist, 1.0)
                    s = (int(p1_scaled[0]+t0*dx), int(p1_scaled[1]+t0*dy))
                    e = (int(p1_scaled[0]+t1*dx), int(p1_scaled[1]+t1*dy))
                    cv2.line(disp, s, e, (0, 191, 255), line_thickness)

            if self.dist_mm is not None:
                mid = ((p1_scaled[0]+p2_scaled[0])//2, (p1_scaled[1]+p2_scaled[1])//2)
                txt = f"{self.dist_mm:.2f} mm"
                cv2.putText(disp, txt, (mid[0], mid[1]),
                           cv2.FONT_HERSHEY_SIMPLEX, text_size, (0, 0, 255), int(line_thickness))

        # Draw state indicator in top left corner
        state_text = f"STATE: {self.cable_state.upper()}"
        state_font_size = 0.7
        cv2.rectangle(disp, (10, 10), (350, 45), (0, 0, 0), -1)  # Black background
        cv2.putText(disp, state_text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX,
                   state_font_size, (0, 191, 255), 2)  # Cyan text

        # Display on canvas - only resize if needed
        try:
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
        except:
            return

        if canvas_w > 1 and canvas_h > 1:
            if (canvas_w, canvas_h) != self.cached_canvas_size:
                # Canvas size changed - resize with INTER_LINEAR (faster than default)
                disp = cv2.resize(disp, (canvas_w, canvas_h), interpolation=cv2.INTER_LINEAR)
                self.cached_canvas_size = (canvas_w, canvas_h)
            elif disp.shape != (canvas_h, canvas_w, 3):
                # Size mismatch (e.g., after crop) - resize
                disp = cv2.resize(disp, (canvas_w, canvas_h), interpolation=cv2.INTER_LINEAR)
            # Otherwise skip resize - display is already correct size

        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        imgtk = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor='nw', image=imgtk)
        self.canvas.image = imgtk

        # Update labels
        try:
            if hasattr(self, 'p1_lbl') and self.p1:
                self.p1_lbl.config(text=f"P1  ({self.p1[0]}, {self.p1[1]})")
            if hasattr(self, 'p2_lbl') and self.p2:
                self.p2_lbl.config(text=f"P2  ({self.p2[0]}, {self.p2[1]})")
            if hasattr(self, 'dist_lbl') and self.dist_mm is not None:
                self.dist_lbl.config(text=f"{self.dist_mm:.2f}")
                # Enable both save buttons
                if hasattr(self, 'save_btn_auto'):
                    self.save_btn_auto.config(state=tk.NORMAL, bg=AMBER, fg="#FFFFFF")
                if hasattr(self, 'save_btn_manual'):
                    self.save_btn_manual.config(state=tk.NORMAL, bg=AMBER, fg="#FFFFFF")
            elif hasattr(self, 'dist_lbl'):
                self.dist_lbl.config(text="--")
                # Disable both save buttons
                if hasattr(self, 'save_btn_auto'):
                    self.save_btn_auto.config(state=tk.DISABLED, bg=SEP, fg=TEXT2)
                if hasattr(self, 'save_btn_manual'):
                    self.save_btn_manual.config(state=tk.DISABLED, bg=SEP, fg=TEXT2)
        except:
            pass

    def _start_loop(self):
        if not self._loop_running or not self.camera_ok:
            return

        ret, frame = self.cap.read()
        if ret:
            # Reduce frame size for faster processing (but keep original for calculations)
            if frame.shape[1] > 1280:
                frame = cv2.resize(frame, (1280, int(frame.shape[0] * 1280 / frame.shape[1])))
            self.current_frame = frame

            # Only update display every 2 frames (10 FPS display, but 20 FPS camera reads)
            if self.frame_count % 2 == 0:
                self._update_display()

            # Skip SDK calls if zoom is changing (avoid freeze during zoom)
            zoom_changed = abs(self.zoom - self.last_zoom) > 0.01
            self.last_zoom = self.zoom

            # Update SDK values only every 10 frames AND only if zoom is stable
            if self.frame_count % 10 == 0 and not zoom_changed:
                try:
                    self.pixel_measure.update()
                    zoom, mpp = self.pixel_measure.get_values()
                    if zoom:
                        self.zoom_val.config(text=f"{zoom:.2f}x")
                    if mpp:
                        self.mpp_val.config(text=f"{mpp:.5f}")
                except:
                    pass

            self.frame_count += 1

        # Health check every 30 seconds
        current_time = time.time()
        if current_time - self.last_health_check_time >= self.health_check_interval and self.api_client:
            self.last_health_check_time = current_time
            result = self.api_client.health_check()
            if not result.get("ok"):
                error_type = result.get("error_type", "unknown")
                message = result.get("error", "Server connection lost")
                details = result.get("details", "")

                error_dialog = ErrorDialog(
                    self.root,
                    error_type,
                    message,
                    details,
                    on_retry=lambda: self._start_loop(),
                    on_exit=self._on_closing
                )
                error_dialog.show()

        if self._loop_running:
            self.root.after(50, self._start_loop)

    def run(self):
        self.root.mainloop()

# ==================== MAIN ====================
if __name__ == "__main__":
    # Check if API URL is configured
    api_url = None
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
            api_url = config.get("api_url")
        except:
            pass

    # If no API URL configured, show setup window
    if not api_url:
        setup = SetupWindow()
        api_url = setup.show()
        if not api_url:
            print("Setup cancelled. Exiting.")
            sys.exit(0)

    # Create API client and check connection before showing login
    api_client = APIClient(api_url)

    # Loop for connection retry logic
    while True:
        # First check if machine has internet connection
        if not check_internet_connection():
            error_root = tk.Tk()
            error_root.withdraw()

            user_action = [None]

            def on_retry():
                user_action[0] = "retry"

            def on_exit():
                user_action[0] = "exit"

            error_dialog = ErrorDialog(
                error_root,
                "no_internet",
                "No Internet Connection",
                "Your machine is not connected to the internet",
                on_retry=on_retry,
                on_exit=on_exit
            )
            error_dialog.show()
            try:
                error_root.destroy()
            except:
                pass

            if user_action[0] == "exit":
                sys.exit(0)
            else:
                # user_action[0] == "retry" - continue loop to retry
                continue

        # Check API connection
        health_result = api_client.health_check()
        if health_result.get("ok"):
            # Both internet and API are OK - break loop and proceed to login
            break

        # Connection failed - show error dialog
        error_type = health_result.get("error_type", "unknown")
        error_msg = health_result.get("error", "Cannot connect to API")
        details = health_result.get("details", "")

        # Create a window for the error dialog
        error_root = tk.Tk()
        error_root.withdraw()

        user_action = [None]  # Use list to capture choice in closure

        def on_retry():
            user_action[0] = "retry"

        def on_change_url():
            user_action[0] = "change_url"

        def on_exit():
            user_action[0] = "exit"

        error_dialog = ErrorDialog(
            error_root,
            error_type,
            error_msg,
            details,
            on_retry=on_retry,
            on_change_url=on_change_url,
            on_exit=on_exit
        )
        error_dialog.show()
        try:
            error_root.destroy()
        except:
            pass

        # Handle user's choice
        if user_action[0] == "retry":
            continue  # Retry connection check
        elif user_action[0] == "change_url":
            setup = SetupWindow()
            new_url = setup.show()
            if new_url:
                api_url = new_url
                api_client = APIClient(new_url)
                continue  # Try connection with new URL
            else:
                sys.exit(0)
        else:  # exit
            sys.exit(0)

    # Connection OK, show login
    login_window = LoginWindow(api_client)
    login_result = login_window.show()

    if login_result:
        role = login_result.get("role")
        username = login_result.get("username")
        user_id = login_result.get("user_id")

        # Route to appropriate UI based on role
        if role == "machine_user":
            app = MainApp(username, api_client)
            app.run()
        elif role == "annoteur":
            print(f"Annoteur UI not yet implemented. Logged in as {username}")
        elif role == "admin":
            print(f"Admin UI not yet implemented. Logged in as {username}")
        else:
            print(f"Unknown role: {role}")
    else:
        print("Login cancelled. Exiting.")
