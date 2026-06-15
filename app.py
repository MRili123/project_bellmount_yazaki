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
# Models folder - separate from model_bellmounth_mesure
MODELS_ROOT = Path(__file__).parent / "models"
MODELS_MESURE_DIR = MODELS_ROOT / "mesure"
MODEL_PATH = MODELS_MESURE_DIR / "CNN_BELMOUNTH_MODEL_V1.h5"

for d in [ORIG_DIR, THRESH_DIR]:
    d.mkdir(parents=True, exist_ok=True)
if not ANNOTATIONS_FILE.exists():
    ANNOTATIONS_FILE.write_text("[]")

# ==================== ERROR DIALOG ====================
class ErrorDialog:
    def __init__(self, parent, error_type, message, details="", on_retry=None, on_change_url=None, on_exit=None):
        self.window = tk.Toplevel(parent)
        self.window.title("Connection Error")
        self.window.geometry("600x500")
        self.window.configure(bg="#FFFFFF")
        self.window.resizable(False, False)
        self.on_retry = on_retry
        self.on_change_url = on_change_url
        self.on_exit = on_exit
        self.result = None

        # Handle window close button
        self.window.protocol("WM_DELETE_WINDOW", self._on_window_close)

        # Color scheme based on error type - using red and white
        error_colors = {
            "no_internet": ("#AF151D", "NO INTERNET", "🌐"),
            "server_down": ("#AF151D", "SERVER UNREACHABLE", "⚠"),
            "server_error": ("#AF151D", "SERVER ERROR", "⚠"),
            "auth_error": ("#AF151D", "AUTHENTICATION FAILED", "🔒"),
            "unknown": ("#AF151D", "ERROR", "⚠")
        }
        color, title_text, icon_char = error_colors.get(error_type, ("#AF151D", "ERROR", "⚠"))

        main = tk.Frame(self.window, bg="#FFFFFF")
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)

        # Large icon - bigger and more prominent
        icon_frame = tk.Frame(main, bg="#FFFFFF")
        icon_frame.pack(fill=tk.X, pady=(0, 20), anchor=tk.CENTER)
        tk.Label(icon_frame, text=icon_char, font=("Arial", 72), fg=color, bg="#FFFFFF").pack()

        # Title with red color
        tk.Label(main, text=title_text, font=("Arial", 18, "bold"), fg=color, bg="#FFFFFF").pack(anchor=tk.CENTER, pady=(0, 15))

        # Message
        tk.Label(main, text=message, font=("Arial", 12), fg="#333333", bg="#FFFFFF", wraplength=480, justify=tk.CENTER).pack(fill=tk.X, pady=(0, 20))

        # Details section
        self.details_frame = tk.Frame(main, bg="#F5F5F5", relief=tk.SUNKEN, bd=1)
        self.details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        self.details_frame.pack_propagate(False)

        details_text = tk.Text(self.details_frame, font=("Consolas", 8), bg="#F5F5F5", fg="#666666", height=6, width=50, relief=tk.FLAT, bd=0)
        details_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        details_text.insert(tk.END, details)
        details_text.config(state=tk.DISABLED)

        # Buttons - Red and white theme
        btn_frame = tk.Frame(main, bg="#FFFFFF")
        btn_frame.pack(fill=tk.X, pady=(0, 0))

        if on_retry:
            retry_btn = tk.Button(btn_frame, text="RETRY", command=self._on_retry,
                                 bg="#AF151D", fg="#FFFFFF", font=("Arial", 11, "bold"),
                                 relief=tk.FLAT, bd=0, padx=20, pady=10)
            retry_btn.pack(side=tk.LEFT, padx=(0, 10))
            add_hover_effect(retry_btn, "#AF151D", "#8B0F15", "#FFFFFF")

        if on_change_url:
            url_btn = tk.Button(btn_frame, text="CHANGE URL", command=self._on_change_url,
                               bg="#666666", fg="#FFFFFF", font=("Arial", 11, "bold"),
                               relief=tk.FLAT, bd=0, padx=20, pady=10)
            url_btn.pack(side=tk.LEFT, padx=(0, 10))
            add_hover_effect(url_btn, "#666666", "#555555", "#FFFFFF")

        exit_btn = tk.Button(btn_frame, text="EXIT", command=self._on_exit,
                            bg="#AF151D", fg="#FFFFFF", font=("Arial", 11, "bold"),
                            relief=tk.FLAT, bd=0, padx=20, pady=10)
        exit_btn.pack(side=tk.RIGHT)
        add_hover_effect(exit_btn, "#AF151D", "#8B0F15", "#FFFFFF")

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

    def _on_window_close(self):
        self.result = "close"
        try:
            if self.window.winfo_exists():
                self.window.quit()
        except:
            pass

    def show(self):
        self.window.transient()
        self.window.grab_set()
        self.window.mainloop()
        try:
            self.window.grab_release()
        except:
            pass
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
    def __init__(self, machine_name, api_client: APIClient = None, machine_id: str = None):
        self.root = tk.Tk()
        self.root.title(f"Bellmounth Inspection — {machine_name}")
        self.root.geometry("1440x900")
        self.root.configure(bg=BG)
        self.root.state('zoomed')
        self.machine_name = machine_name
        self.machine_id = machine_id
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

    def _check_api_response(self, result):
        """Check API response for deactivation or other errors. Returns True if valid, False if deactivated."""
        if isinstance(result, dict) and result.get("error_type") == "account_deactivated":
            self._logout_due_to_deactivation()
            return False
        return True

    def _logout_due_to_deactivation(self):
        """Logout user due to account deactivation"""
        self._loop_running = False
        if self.cap:
            self.cap.release()

        messagebox.showerror(
            "Account Deactivated",
            "Your account has been deactivated by an administrator.\n\nPlease contact your administrator for more information.",
            parent=self.root
        )
        self.root.destroy()

    def _on_closing(self):
        self._loop_running = False
        if self.cap:
            self.cap.release()
        if self.pixel_measure:
            self.pixel_measure.close()
        self.root.destroy()

    def _fetch_switches(self):
        """Fetch switches for this machine from API"""
        if self.api_client:
            result = self.api_client.get_switches(machine_id=self.machine_id)
            if not self._check_api_response(result):
                return []
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
        if not switches and hasattr(self, 'last_api_error') and self.last_api_error:
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

            # Verify connection before upload
            if not check_internet_connection():
                error_dialog = ErrorDialog(
                    self.root,
                    "no_internet",
                    "No Internet Connection",
                    "Cannot upload: Your machine is not connected to the internet",
                    on_retry=_upload_with_mode,
                    on_exit=None
                )
                error_dialog.show()
                try:
                    error_dialog.window.destroy()
                except:
                    pass
                return

            # Verify API is available
            health_result = self.api_client.health_check()
            if not health_result.get("ok"):
                error_type = health_result.get("error_type", "server_down")
                error_msg = health_result.get("error", "API server is not responding")
                details = health_result.get("details", "")

                error_dialog = ErrorDialog(
                    self.root,
                    error_type,
                    error_msg,
                    details,
                    on_retry=_upload_with_mode,
                    on_exit=None
                )
                error_dialog.show()
                try:
                    error_dialog.window.destroy()
                except:
                    pass
                return

            # Both connection and API are OK - proceed with upload
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
                    try:
                        error_dialog.window.destroy()
                    except:
                        pass
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

        # Model loading commented out - add models to models/mesure/ folder to enable
        # if self._tf_model is None:
        #     try:
        #         self._tf_model = tf.keras.models.load_model(str(MODEL_PATH), compile=False)
        #     except:
        #         return None

        # Model inference disabled - uncomment when model files are available
        # h, w = frame.shape[:2]
        # thresh = apply_threshold(frame)
        # resized = cv2.resize(thresh, (640, 480))
        # normalized = resized.astype(np.float32) / 255.0
        # inp = normalized[..., np.newaxis][np.newaxis, ...]
        #
        # pred = self._tf_model.predict(inp, verbose=0)[0]
        # p1 = (int(pred[0] * w), int(pred[1] * h))
        # # Use P1's Y coordinate for P2 (horizontal alignment)
        # p2 = (int(pred[2] * w), p1[1])
        # pixel_dist = math.dist(p1, p2)
        #
        # self.pixel_measure.update()
        # _, mm_pp = self.pixel_measure.get_values()
        # dist_mm = pixel_dist * mm_pp if mm_pp else None
        #
        # return p1, p2, dist_mm

        return None

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
            if not self._check_api_response(result):
                return
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
            try:
                result = self.api_client.health_check()
                if not self._check_api_response(result):
                    return
                if not result.get("ok"):
                    error_type = result.get("error_type", "unknown")
                    message = result.get("error", "Server connection lost")
                    details = result.get("details", "")

                    def on_retry_check():
                        self.last_health_check_time = 0  # Reset to check immediately

                    try:
                        error_dialog = ErrorDialog(
                            self.root,
                            error_type,
                            message,
                            details,
                            on_retry=on_retry_check,
                            on_exit=None
                        )
                        error_dialog.show()
                        try:
                            if error_dialog.window.winfo_exists():
                                error_dialog.window.destroy()
                        except:
                            pass
                    except Exception as e:
                        print(f"Error showing dialog: {e}")
            except Exception as e:
                print(f"Health check error: {e}")

        if self._loop_running:
            self.root.after(50, self._start_loop)

    def run(self):
        self.root.mainloop()

# ==================== ADMIN CACHE ====================
class AdminCache:
    CACHE_FILE = Path(__file__).parent / "admin_cache.json"
    KEYS = ["users", "machines", "switches", "captures"]

    def __init__(self):
        self._cache = self._load()

    def _load(self):
        """Load cache from disk, return empty structure if missing."""
        if self.CACHE_FILE.exists():
            try:
                return json.loads(self.CACHE_FILE.read_text())
            except:
                pass
        return {k: {"data": [], "updated_at": None} for k in self.KEYS}

    def _save(self):
        """Persist cache to disk."""
        try:
            self.CACHE_FILE.write_text(json.dumps(self._cache, indent=2, default=str))
        except:
            pass

    def get(self, key) -> list:
        """Return cached data for key (may be empty list if not yet fetched)."""
        return self._cache.get(key, {}).get("data", [])

    def has_data(self, key) -> bool:
        """True if cache has at least one item for this key."""
        return len(self.get(key)) > 0

    def update(self, key, server_data: list):
        """
        Merge server_data into local cache:
        - Items in server but not local → add
        - Items in local but not server → remove (deleted on server)
        - Items in both → update local with server version
        Returns the merged list.
        """
        server_by_id = {item["id"]: item for item in server_data}
        merged = list(server_by_id.values())
        self._cache[key] = {
            "data": merged,
            "updated_at": datetime.now().isoformat()
        }
        self._save()
        return merged

    def is_stale(self, key, timeout_seconds=30) -> bool:
        """Check if cache for key is older than timeout_seconds."""
        updated_at = self._cache.get(key, {}).get("updated_at")
        if not updated_at:
            return True
        try:
            last_update = datetime.fromisoformat(updated_at)
            age = (datetime.now() - last_update).total_seconds()
            return age > timeout_seconds
        except:
            return True

    def invalidate(self, key):
        """Clear cache for a key (force fresh fetch next time)."""
        self._cache[key] = {"data": [], "updated_at": None}
        self._save()

# ==================== ADMIN APP ====================
class AdminApp:
    def __init__(self, username: str, user_id: str, api_client: APIClient):
        self.username = username
        self.user_id = user_id
        self.api_client = api_client
        self.cache = AdminCache()

        self.root = tk.Tk()
        self.root.title("Bellmounth Admin Panel")
        self.root.geometry("1280x800")
        self.root.configure(bg=BG)
        self.root.state('zoomed')

        self.current_page = "users"
        self.page_buttons = {}

        self._build_ui()

    def _build_ui(self):
        # Header bar
        top = tk.Frame(self.root, bg=PANEL, height=58)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        # Logo
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            try:
                logo_img = Image.open(str(logo_path))
                logo_img = logo_img.resize((45, 45), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_lbl = tk.Label(top, image=logo_photo, bg=PANEL)
                logo_lbl.image = logo_photo
                logo_lbl.pack(side=tk.LEFT, padx=10)
            except:
                pass

        tk.Label(top, text="Admin Panel", bg=PANEL, fg=TEXT2, font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=10)

        # Spacer
        tk.Frame(top, bg=PANEL).pack(fill=tk.X, expand=True)

        # Username and clock
        tk.Label(top, text=self.username, bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        tk.Frame(top, bg=BORDER, width=1, height=30).pack(side=tk.LEFT, padx=5)

        self.clock_lbl = tk.Label(top, text="", bg=PANEL, fg=TEXT2, font=("Arial", 10))
        self.clock_lbl.pack(side=tk.LEFT, padx=10)
        self._update_clock()

        tk.Frame(top, bg=BORDER, width=1, height=30).pack(side=tk.LEFT, padx=5)

        quit_btn = tk.Button(top, text="QUIT", command=self._on_closing, bg=RED, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=6)
        quit_btn.pack(side=tk.LEFT, padx=10)
        add_hover_effect(quit_btn, RED, RED, "#FFFFFF")

        # Navbar
        navbar = tk.Frame(self.root, bg=PANEL, height=45)
        navbar.pack(fill=tk.X, side=tk.TOP)
        navbar.pack_propagate(False)

        pages = [
            ("ANNOTEUR", "users", self._show_users_page),
            ("MACHINES", "machines", self._show_machines_page),
            ("SWITCHES", "switches", self._show_switches_page),
            ("REQUESTS", "requests", self._show_requests_page),
            ("DATASET", "dataset", self._show_dataset_page),
            ("MODEL", "model", self._show_model_page),
            ("NOTIFICATIONS", "notifications", self._show_notifications_page),
        ]

        for label, page_id, callback in pages:
            btn = tk.Button(navbar, text=label,
                          command=lambda p=page_id, c=callback: self._switch_page(p, c),
                          bg=PANEL, fg=TEXT2, font=("Arial", 10, "bold"),
                          relief=tk.FLAT, bd=0, padx=16, pady=10)
            btn.pack(side=tk.LEFT, padx=4)
            self.page_buttons[page_id] = btn
            add_hover_effect(btn, PANEL, SEP, TEXT)

        tk.Frame(navbar, bg=BORDER, height=1).pack(fill=tk.X, side=tk.BOTTOM)

        # Content container
        self.content_container = tk.Frame(self.root, bg=BG)
        self.content_container.pack(fill=tk.BOTH, expand=True)

        # Show initial page
        self._switch_page("users", self._show_users_page)

    def _switch_page(self, page_id, callback):
        self.current_page = page_id
        for btn_id, btn in self.page_buttons.items():
            btn.config(bg=ACCENT if btn_id == page_id else PANEL,
                      fg="#FFFFFF" if btn_id == page_id else TEXT2)

        for widget in self.content_container.winfo_children():
            widget.destroy()

        callback()

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.clock_lbl.config(text=now)
        self.root.after(1000, self._update_clock)

    def _on_closing(self):
        self.root.destroy()

    def _show_users_page(self):
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="ANNOTEUR MANAGEMENT", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        toolbar = tk.Frame(frame, bg=BG)
        toolbar.pack(fill=tk.X, pady=(0, 20))

        # Search bar
        tk.Label(toolbar, text="Search:", bg=BG, fg=TEXT2, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        users_search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=users_search_var, font=("Consolas", 10),
                               bg=PANEL, fg=TEXT, insertbackground=ACCENT,
                               relief=tk.FLAT, bd=0, highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=ACCENT, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 20), ipady=6)

        add_btn = tk.Button(toolbar, text="+ ADD ANNOTEUR", command=self._add_user_dialog,
                          bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"),
                          relief=tk.FLAT, bd=0, padx=20, pady=8)
        add_btn.pack(side=tk.RIGHT)
        add_hover_effect(add_btn, ACCENT, ACCENT, "#FFFFFF")

        cached = self.cache.get("users")
        search_timer = [None]

        def on_search_change(*args):
            if search_timer[0]:
                self.root.after_cancel(search_timer[0])

            def do_search():
                search_term = users_search_var.get().lower()
                filtered = [u for u in cached if search_term in u.get("username", "").lower() or
                           search_term in u.get("email", "").lower() or
                           search_term in u.get("role", "").lower()]
                for w in frame.winfo_children():
                    if getattr(w, '_is_table', False):
                        w.destroy()
                self._build_users_table(frame, filtered)

            search_timer[0] = self.root.after(300, do_search)

        users_search_var.trace('w', on_search_change)
        self._build_users_table(frame, cached)
        self._sync_users(frame, cached)

    def _build_users_table(self, frame, users):
        table_frame = tk.Frame(frame, bg=BORDER, relief=tk.SUNKEN, bd=1)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame._is_table = True

        header = tk.Frame(table_frame, bg=PANEL)
        header.pack(fill=tk.X)

        cols = [("USERNAME", 25), ("ROLE", 15), ("EMAIL", 30), ("STATUS", 12), ("CREATED", 18)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Frame(table_frame, bg=BORDER, height=1).pack(fill=tk.X)

        canvas = tk.Canvas(table_frame, bg=BG, highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Filter out admin users - only show machine_user and annoteur roles
        filtered_users = [u for u in users if u.get("role") != "admin"]

        for i, user in enumerate(filtered_users):
            row_bg = PANEL if i % 2 == 0 else BG
            row = tk.Frame(scrollable_frame, bg=row_bg)
            row.pack(fill=tk.X)

            tk.Label(row, text=user.get("username", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=25, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
            tk.Label(row, text=user.get("role", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
            tk.Label(row, text=user.get("email", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=30, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

            status_text = "Active" if user.get("is_active") else "Inactive"
            status_color = GREEN if user.get("is_active") else RED
            tk.Label(row, text=status_text, bg=row_bg, fg=status_color, font=("Arial", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

            created_str = user.get("created_at", "")[:10] if user.get("created_at") else ""
            tk.Label(row, text=created_str, bg=row_bg, fg=TEXT2, font=("Arial", 10), width=18, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

            action_frame = tk.Frame(row, bg=row_bg)
            action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

            toggle_text = "Deactivate" if user.get("is_active") else "Activate"
            toggle_btn = tk.Button(action_frame, text=toggle_text, font=("Arial", 9),
                                  command=lambda uid=user.get("id"), act=user.get("is_active"): self._toggle_user(uid, act),
                                  bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, padx=12, pady=4)
            toggle_btn.pack(side=tk.LEFT, padx=4)
            add_hover_effect(toggle_btn, PANEL, SEP, TEXT)

            delete_btn = tk.Button(action_frame, text="Delete", font=("Arial", 9),
                                  command=lambda uid=user.get("id"), un=user.get("username"): self._delete_user(uid, un),
                                  bg=RED, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=12, pady=4)
            delete_btn.pack(side=tk.LEFT, padx=4)
            add_hover_effect(delete_btn, RED, RED, "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

    def _sync_users(self, frame, cached):
        if not self.cache.is_stale("users"):
            return
        def do_sync():
            result = self.api_client.admin_get_users()
            if result.get("ok"):
                server_data = result.get("data", [])
                merged = self.cache.update("users", server_data)
                if merged != cached:
                    for w in frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()
                    self._build_users_table(frame, merged)
        self.root.after(0, do_sync)

    def _show_machines_page(self):
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="MACHINE MANAGEMENT", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        toolbar = tk.Frame(frame, bg=BG)
        toolbar.pack(fill=tk.X, pady=(0, 20))

        # Search bar
        tk.Label(toolbar, text="Search:", bg=BG, fg=TEXT2, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        machines_search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=machines_search_var, font=("Consolas", 10),
                               bg=PANEL, fg=TEXT, insertbackground=ACCENT,
                               relief=tk.FLAT, bd=0, highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=ACCENT, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 20), ipady=6)

        add_btn = tk.Button(toolbar, text="+ REGISTER MACHINE", command=self._add_machine_dialog,
                          bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"),
                          relief=tk.FLAT, bd=0, padx=20, pady=8)
        add_btn.pack(side=tk.RIGHT)
        add_hover_effect(add_btn, ACCENT, ACCENT, "#FFFFFF")

        cached = self.cache.get("machines")
        search_timer = [None]

        def on_search_change(*args):
            if search_timer[0]:
                self.root.after_cancel(search_timer[0])

            def do_search():
                search_term = machines_search_var.get().lower()
                filtered = [m for m in cached if search_term in m.get("machine_name", "").lower() or
                           search_term in m.get("location", "").lower() or
                           search_term in m.get("firmware_version", "").lower()]
                for w in frame.winfo_children():
                    if getattr(w, '_is_table', False):
                        w.destroy()
                self._build_machines_table(frame, filtered)

            search_timer[0] = self.root.after(300, do_search)

        machines_search_var.trace('w', on_search_change)
        self._build_machines_table(frame, cached)
        self._sync_machines(frame, cached)

    def _build_machines_table(self, frame, machines):
        table_frame = tk.Frame(frame, bg=BORDER, relief=tk.SUNKEN, bd=1)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame._is_table = True

        header = tk.Frame(table_frame, bg=PANEL)
        header.pack(fill=tk.X)

        cols = [("MACHINE NAME", 25), ("LOCATION", 25), ("FIRMWARE", 15), ("ACTIVE", 12), ("CREATED", 18)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Frame(table_frame, bg=BORDER, height=1).pack(fill=tk.X)

        canvas = tk.Canvas(table_frame, bg=BG, highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, machine in enumerate(machines):
            row_bg = PANEL if i % 2 == 0 else BG
            row = tk.Frame(scrollable_frame, bg=row_bg)
            row.pack(fill=tk.X)

            tk.Label(row, text=machine.get("machine_name", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=25, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
            tk.Label(row, text=machine.get("location", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=25, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
            tk.Label(row, text=machine.get("firmware_version", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

            status_text = "Active" if machine.get("is_active") else "Inactive"
            status_color = GREEN if machine.get("is_active") else RED
            tk.Label(row, text=status_text, bg=row_bg, fg=status_color, font=("Arial", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

            created_str = machine.get("created_at", "")[:10] if machine.get("created_at") else ""
            tk.Label(row, text=created_str, bg=row_bg, fg=TEXT2, font=("Arial", 10), width=18, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

            action_frame = tk.Frame(row, bg=row_bg)
            action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

            toggle_text = "Deactivate" if machine.get("is_active") else "Activate"
            toggle_btn = tk.Button(action_frame, text=toggle_text, font=("Arial", 9),
                                  command=lambda mid=machine.get("id"), act=machine.get("is_active"): self._toggle_machine(mid, act),
                                  bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, padx=12, pady=4)
            toggle_btn.pack(side=tk.LEFT, padx=4)
            add_hover_effect(toggle_btn, PANEL, SEP, TEXT)

            delete_btn = tk.Button(action_frame, text="Delete", font=("Arial", 9),
                                  command=lambda mid=machine.get("id"), mn=machine.get("machine_name"): self._delete_machine(mid, mn),
                                  bg=RED, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=12, pady=4)
            delete_btn.pack(side=tk.LEFT, padx=4)
            add_hover_effect(delete_btn, RED, RED, "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

    def _sync_machines(self, frame, cached):
        if not self.cache.is_stale("machines"):
            return
        def do_sync():
            result = self.api_client.admin_get_machines()
            if result.get("ok"):
                server_data = result.get("data", [])
                merged = self.cache.update("machines", server_data)
                if merged != cached:
                    for w in frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()
                    self._build_machines_table(frame, merged)
        self.root.after(0, do_sync)

    def _show_switches_page(self):
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="SWITCH MANAGEMENT", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        toolbar = tk.Frame(frame, bg=BG)
        toolbar.pack(fill=tk.X, pady=(0, 20))

        # Search bar
        tk.Label(toolbar, text="Search:", bg=BG, fg=TEXT2, font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 10))
        switches_search_var = tk.StringVar()
        search_entry = tk.Entry(toolbar, textvariable=switches_search_var, font=("Consolas", 10),
                               bg=PANEL, fg=TEXT, insertbackground=ACCENT,
                               relief=tk.FLAT, bd=0, highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=ACCENT, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 20), ipady=6)

        add_btn = tk.Button(toolbar, text="+ ADD SWITCH", command=self._add_switch_dialog,
                          bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"),
                          relief=tk.FLAT, bd=0, padx=20, pady=8)
        add_btn.pack(side=tk.RIGHT)
        add_hover_effect(add_btn, ACCENT, ACCENT, "#FFFFFF")

        cached = self.cache.get("switches")
        search_timer = [None]

        def on_search_change(*args):
            if search_timer[0]:
                self.root.after_cancel(search_timer[0])

            def do_search():
                search_term = switches_search_var.get().lower()
                filtered = [s for s in cached if search_term in s.get("switch_name", "").lower() or
                           search_term in s.get("cable_type", "").lower() or
                           search_term in s.get("machine_name", "").lower() or
                           search_term in str(s.get("expected_diameter_mm", "")).lower()]
                for w in frame.winfo_children():
                    if getattr(w, '_is_table', False):
                        w.destroy()
                self._build_switches_table(frame, filtered)

            search_timer[0] = self.root.after(300, do_search)

        switches_search_var.trace('w', on_search_change)
        self._build_switches_table(frame, cached)
        self._sync_switches(frame, cached)

    def _build_switches_table(self, frame, switches):
        table_frame = tk.Frame(frame, bg=BORDER, relief=tk.SUNKEN, bd=1)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame._is_table = True

        header = tk.Frame(table_frame, bg=PANEL)
        header.pack(fill=tk.X)

        cols = [("MACHINE", 10), ("NAME", 15), ("CABLE TYPE", 12), ("EXPECTED (mm)", 10), ("TOL MIN", 9), ("TOL MAX", 9)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Frame(table_frame, bg=BORDER, height=1).pack(fill=tk.X)

        canvas = tk.Canvas(table_frame, bg=BG, highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for i, switch in enumerate(switches):
            row_bg = PANEL if i % 2 == 0 else BG
            row = tk.Frame(scrollable_frame, bg=row_bg)
            row.pack(fill=tk.X)

            tk.Label(row, text=switch.get("machine_name", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=10, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)
            tk.Label(row, text=switch.get("switch_name", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=15, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)
            tk.Label(row, text=switch.get("cable_type", ""), bg=row_bg, fg=TEXT, font=("Arial", 10), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)
            tk.Label(row, text=f"{switch.get('expected_diameter_mm', 0)}", bg=row_bg, fg=TEXT, font=("Arial", 10), width=10, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)
            tk.Label(row, text=f"{switch.get('tolerance_min', 0)}", bg=row_bg, fg=TEXT, font=("Arial", 10), width=9, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)
            tk.Label(row, text=f"{switch.get('tolerance_max', 0)}", bg=row_bg, fg=TEXT, font=("Arial", 10), width=9, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            action_frame = tk.Frame(row, bg=row_bg)
            action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

            edit_btn = tk.Button(action_frame, text="Edit", font=("Arial", 9),
                                command=lambda sw=switch: self._edit_switch_dialog(sw),
                                bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, padx=12, pady=4)
            edit_btn.pack(side=tk.LEFT, padx=4)
            add_hover_effect(edit_btn, PANEL, SEP, TEXT)

            delete_btn = tk.Button(action_frame, text="Delete", font=("Arial", 9),
                                  command=lambda sid=switch.get("id"), sn=switch.get("switch_name"): self._delete_switch(sid, sn),
                                  bg=RED, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=12, pady=4)
            delete_btn.pack(side=tk.LEFT, padx=4)
            add_hover_effect(delete_btn, RED, RED, "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

    def _sync_switches(self, frame, cached):
        if not self.cache.is_stale("switches"):
            return
        def do_sync():
            result = self.api_client.get_switches()
            if result.get("ok"):
                server_data = result.get("data", [])
                merged = self.cache.update("switches", server_data)
                if merged != cached:
                    for w in frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()
                    self._build_switches_table(frame, merged)
        self.root.after(0, do_sync)

    def _show_requests_page(self):
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="CAPTURE REQUESTS", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        cached = self.cache.get("captures")
        self._build_requests_table(frame, cached)
        self._sync_captures(frame, cached)

    def _build_requests_table(self, frame, captures):
        table_frame = tk.Frame(frame, bg=BORDER, relief=tk.SUNKEN, bd=1)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame._is_table = True

        # Header
        header = tk.Frame(table_frame, bg=PANEL)
        header.pack(fill=tk.X)

        cols = [("ANNOTEUR", 16), ("TIME", 14), ("REQUIRED/ACTUAL", 16), ("ZOOM", 8), ("STATUS", 9), ("ACTIONS", 25)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Frame(table_frame, bg=BORDER, height=1).pack(fill=tk.X)

        canvas = tk.Canvas(table_frame, bg=BG, highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        pending_captures = [c for c in captures if not c.get("annoteur_approved")]

        if not pending_captures:
            tk.Label(scrollable_frame, text="No pending requests", bg=BG, fg=TEXT2, font=("Arial", 12)).pack(pady=50)
        else:
            for i, capture in enumerate(pending_captures):
                row_bg = PANEL if i % 2 == 0 else BG
                row = tk.Frame(scrollable_frame, bg=row_bg)
                row.pack(fill=tk.X)

                annoteur_id = (capture.get('annoteur_id') or 'Unknown')[:16]
                tk.Label(row, text=annoteur_id, bg=row_bg, fg=TEXT, font=("Arial", 10), width=16, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                created_at = (capture.get('created_at') or '')[:14]
                tk.Label(row, text=created_at, bg=row_bg, fg=TEXT, font=("Arial", 10), width=14, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                expected = capture.get('expected_diameter_mm') or 0
                actual = capture.get('measured_distance_mm', 0)
                measure_text = f"{expected:.2f} / {actual:.2f}mm"
                tk.Label(row, text=measure_text, bg=row_bg, fg=TEXT, font=("Arial", 10), width=16, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                zoom = capture.get('zoom_level')
                zoom_text = f"{zoom:.1f}x" if zoom else "—"
                tk.Label(row, text=zoom_text, bg=row_bg, fg=TEXT, font=("Arial", 10), width=8, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                status_text = capture.get('measurement_status', 'unknown').upper()
                status_color = GREEN if status_text == "OKAY" else RED
                tk.Label(row, text=status_text, bg=row_bg, fg=status_color, font=("Arial", 10, "bold"), width=9, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                action_frame = tk.Frame(row, bg=row_bg)
                action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

                see_btn = tk.Button(action_frame, text="👁 See", command=lambda cap=capture: self._show_capture_modal(cap),
                                   bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4)
                see_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(see_btn, ACCENT, "#8B0F15", "#FFFFFF")

                accept_btn = tk.Button(action_frame, text="✓ Accept", command=lambda cid=capture.get("id"): self._accept_request(cid),
                                      bg=GREEN, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4)
                accept_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(accept_btn, GREEN, "#388E3C", "#FFFFFF")

                reject_btn = tk.Button(action_frame, text="✕ Reject", command=lambda cid=capture.get("id"): self._reject_request(cid),
                                      bg=RED, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4)
                reject_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(reject_btn, RED, "#8B0F15", "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

    def _sync_captures(self, frame, cached):
        if not self.cache.is_stale("captures"):
            return
        def do_sync():
            result = self.api_client.admin_get_captures()
            if result.get("ok"):
                server_data = result.get("data", [])
                merged = self.cache.update("captures", server_data)
                if merged != cached:
                    for w in frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()
                    self._build_requests_table(frame, merged)
        self.root.after(0, do_sync)

    def _show_capture_modal(self, capture):
        modal = tk.Toplevel(self.root)
        modal.title("Capture Viewer")
        modal.geometry("1000x700")
        modal.configure(bg=BG)
        modal.resizable(True, True)

        state = {
            "original_image": None,
            "thresholded_image": None,
            "current_image": None,
            "current_path": None,
            "zoom": 1.0,
            "is_threads": False,
            "photo_image": None,
            "canvas": None
        }

        orig_path = capture.get('image_original_path', '')
        thresh_path = capture.get('image_thresholded_path', '')
        p1_x = capture.get('p1_x', 0)
        p1_y = capture.get('p1_y', 0)
        p2_x = capture.get('p2_x', 0)
        p2_y = capture.get('p2_y', 0)

        try:
            if Path(orig_path).exists():
                state["original_image"] = Image.open(orig_path).convert('RGB')
            if Path(thresh_path).exists():
                state["thresholded_image"] = Image.open(thresh_path).convert('RGB')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load images: {e}")
            modal.destroy()
            return

        if not state["original_image"]:
            messagebox.showerror("Error", "Original image not found")
            modal.destroy()
            return

        state["current_image"] = state["original_image"]
        state["current_path"] = orig_path

        # Top control bar
        control_frame = tk.Frame(modal, bg=PANEL, relief=tk.SUNKEN, bd=1)
        control_frame.pack(fill=tk.X, padx=0, pady=0)

        tk.Label(control_frame, text="Zoom:", bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(side=tk.LEFT, padx=10, pady=8)

        zoom_minus_btn = tk.Button(control_frame, text="−", width=2, font=("Arial", 12, "bold"),
                                   bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0)
        zoom_minus_btn.pack(side=tk.LEFT, padx=2, pady=8)

        zoom_plus_btn = tk.Button(control_frame, text="+", width=2, font=("Arial", 12, "bold"),
                                  bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0)
        zoom_plus_btn.pack(side=tk.LEFT, padx=2, pady=8)

        zoom_label = tk.Label(control_frame, text="1.00x", bg=PANEL, fg=TEXT, font=("Arial", 10), width=6)
        zoom_label.pack(side=tk.LEFT, padx=10, pady=8)

        reset_zoom_btn = tk.Button(control_frame, text="Reset", font=("Arial", 9),
                                   bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, padx=8, pady=4)
        reset_zoom_btn.pack(side=tk.LEFT, padx=4, pady=8)
        add_hover_effect(reset_zoom_btn, PANEL, SEP, TEXT)

        threads_btn = tk.Button(control_frame, text="🔄 Threads", font=("Arial", 9),
                               bg=ACCENT, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=12, pady=4)
        threads_btn.pack(side=tk.LEFT, padx=(20, 4), pady=8)
        add_hover_effect(threads_btn, ACCENT, "#8B0F15", "#FFFFFF")

        close_btn = tk.Button(control_frame, text="✕ Close", font=("Arial", 9),
                             bg=RED, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=12, pady=4,
                             command=modal.destroy)
        close_btn.pack(side=tk.RIGHT, padx=10, pady=8)
        add_hover_effect(close_btn, RED, "#8B0F15", "#FFFFFF")

        # Canvas for image display
        canvas_frame = tk.Frame(modal, bg=BORDER, relief=tk.SUNKEN, bd=1)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        state["canvas"] = canvas

        def render_image():
            if not state["current_image"]:
                return

            try:
                display_image = state["current_image"].copy()
                canvas_width = canvas.winfo_width()
                canvas_height = canvas.winfo_height()

                if canvas_width <= 1:
                    canvas_width = 1000
                if canvas_height <= 1:
                    canvas_height = 600

                img_width, img_height = display_image.size
                scaled_width = int(img_width * state["zoom"])
                scaled_height = int(img_height * state["zoom"])

                if scaled_width > 0 and scaled_height > 0:
                    display_image = display_image.resize((scaled_width, scaled_height), Image.Resampling.LANCZOS)

                state["photo_image"] = ImageTk.PhotoImage(display_image)
                canvas.delete("all")

                x_offset = (canvas_width - scaled_width) // 2
                y_offset = (canvas_height - scaled_height) // 2

                canvas.create_image(x_offset, y_offset, image=state["photo_image"], anchor="nw")

                # Draw annotation points
                point_size = max(4, int(6 * state["zoom"]))
                scaled_p1_x = int(x_offset + p1_x * state["zoom"])
                scaled_p1_y = int(y_offset + p1_y * state["zoom"])
                scaled_p2_x = int(x_offset + p2_x * state["zoom"])
                scaled_p2_y = int(y_offset + p2_y * state["zoom"])

                # P1 point (green)
                canvas.create_oval(
                    scaled_p1_x - point_size, scaled_p1_y - point_size,
                    scaled_p1_x + point_size, scaled_p1_y + point_size,
                    fill=GREEN, outline="darkgreen", width=2
                )

                # P2 point (blue)
                canvas.create_oval(
                    scaled_p2_x - point_size, scaled_p2_y - point_size,
                    scaled_p2_x + point_size, scaled_p2_y + point_size,
                    fill="#2196F3", outline="#0D47A1", width=2
                )

                # Line connecting points
                canvas.create_line(
                    scaled_p1_x, scaled_p1_y,
                    scaled_p2_x, scaled_p2_y,
                    fill="orange", width=2
                )

                # Distance label
                distance = capture.get('measured_distance_mm', 0)
                distance_text = f"{distance:.2f}mm"
                canvas.create_text(
                    scaled_p1_x, scaled_p1_y - point_size - 15,
                    text="P1", fill=GREEN, font=("Arial", 10, "bold")
                )
                canvas.create_text(
                    scaled_p2_x, scaled_p2_y - point_size - 15,
                    text="P2", fill="#2196F3", font=("Arial", 10, "bold")
                )
                mid_x = (scaled_p1_x + scaled_p2_x) // 2
                mid_y = (scaled_p1_y + scaled_p2_y) // 2 + 20
                canvas.create_rectangle(
                    mid_x - 35, mid_y - 12, mid_x + 35, mid_y + 12,
                    fill="white", outline="orange", width=1
                )
                canvas.create_text(
                    mid_x, mid_y,
                    text=distance_text, fill="orange", font=("Arial", 10, "bold")
                )
            except Exception as e:
                print(f"Error rendering image: {e}")

        def update_zoom(delta):
            state["zoom"] = max(0.5, min(5.0, state["zoom"] + delta))
            zoom_label.config(text=f"{state['zoom']:.2f}x")
            render_image()

        zoom_minus_btn.config(command=lambda: update_zoom(-0.2))
        zoom_plus_btn.config(command=lambda: update_zoom(0.2))

        def toggle_threads():
            if state["thresholded_image"]:
                state["is_threads"] = not state["is_threads"]
                if state["is_threads"]:
                    state["current_image"] = state["thresholded_image"]
                    threads_btn.config(relief=tk.SUNKEN)
                else:
                    state["current_image"] = state["original_image"]
                    threads_btn.config(relief=tk.FLAT)
                render_image()

        threads_btn.config(command=toggle_threads)
        if not state["thresholded_image"]:
            threads_btn.config(state=tk.DISABLED)

        def reset_zoom_func():
            state["zoom"] = 1.0
            zoom_label.config(text="1.00x")
            render_image()

        reset_zoom_btn.config(command=reset_zoom_func)

        # Mouse wheel zoom
        def on_mousewheel(event):
            if event.delta > 0:
                update_zoom(0.1)
            else:
                update_zoom(-0.1)

        canvas.bind("<MouseWheel>", on_mousewheel)

        # Initial render
        modal.after(100, render_image)

    def _accept_request(self, capture_id):
        result = self.api_client.admin_approve_capture(capture_id)
        if result.get("ok"):
            self.cache.invalidate("captures")
            self._switch_page("dataset", self._show_dataset_page)
            messagebox.showinfo("Success", "Request approved!")
        else:
            messagebox.showerror("Error", result.get("error", "Failed to approve request"))

    def _reject_request(self, capture_id):
        if messagebox.askyesno("Confirm", "Reject this request?"):
            result = self.api_client.delete_capture(capture_id)
            if result.get("ok"):
                self.cache.invalidate("captures")
                self._switch_page("requests", self._show_requests_page)
                messagebox.showinfo("Success", "Request rejected!")
            else:
                messagebox.showerror("Error", result.get("error", "Failed to reject request"))

    def _show_dataset_page(self):
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        tk.Label(frame, text="APPROVED DATASET", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Tab buttons
        tab_frame = tk.Frame(frame, bg=BG)
        tab_frame.pack(fill=tk.X, pady=(0, 20))

        cached = self.cache.get("captures")
        # Show all approved captures in MESURE (model_type field removed from schema)
        mesure_count = len([c for c in cached if c.get("annoteur_approved")]) if cached else 0
        state_count = 0  # STATE annotations managed separately

        tab_state = {"current": "mesure"}

        mesure_btn = tk.Button(tab_frame, text=f"MESURE ({mesure_count})", font=("Arial", 10, "bold"),
                              bg=ACCENT, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=20, pady=8)
        mesure_btn.pack(side=tk.LEFT, padx=(0, 10))

        state_btn = tk.Button(tab_frame, text=f"STATE ({state_count})", font=("Arial", 10, "bold"),
                             bg=PANEL, fg=TEXT2, relief=tk.FLAT, bd=0, padx=20, pady=8)
        state_btn.pack(side=tk.LEFT)

        # Content frames for each tab
        mesure_frame = tk.Frame(frame, bg=BG)
        mesure_frame.pack(fill=tk.BOTH, expand=True)

        state_frame = tk.Frame(frame, bg=BG)

        def switch_tab(model_type):
            tab_state["current"] = model_type
            if model_type == "mesure":
                state_frame.pack_forget()
                mesure_frame.pack(fill=tk.BOTH, expand=True)
                mesure_btn.configure(bg=ACCENT, fg="#FFFFFF")
                state_btn.configure(bg=PANEL, fg=TEXT2)
            else:
                mesure_frame.pack_forget()
                state_frame.pack(fill=tk.BOTH, expand=True)
                mesure_btn.configure(bg=PANEL, fg=TEXT2)
                state_btn.configure(bg=ACCENT, fg="#FFFFFF")

        mesure_btn.configure(command=lambda: switch_tab("mesure"))
        state_btn.configure(command=lambda: switch_tab("state"))

        # Build tables for each model
        # Show all approved captures in MESURE (model_type field removed from schema)
        mesure_captures = [c for c in cached if c.get("annoteur_approved")] if cached else []
        state_captures = []  # STATE annotations managed separately

        self._build_dataset_table(mesure_frame, mesure_captures)
        self._build_dataset_table(state_frame, state_captures)

        self._sync_dataset(mesure_frame, state_frame, mesure_btn, state_btn, cached, tab_state)

    def _build_dataset_table(self, frame, captures):
        table_frame = tk.Frame(frame, bg=BORDER, relief=tk.SUNKEN, bd=1)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame._is_table = True

        # Header
        header = tk.Frame(table_frame, bg=PANEL)
        header.pack(fill=tk.X)

        cols = [("ANNOTEUR", 16), ("TIME", 14), ("REQUIRED/ACTUAL", 16), ("ZOOM", 8), ("STATUS", 9), ("ACTIONS", 20)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Frame(table_frame, bg=BORDER, height=1).pack(fill=tk.X)

        canvas = tk.Canvas(table_frame, bg=BG, highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        if not captures:
            tk.Label(scrollable_frame, text="No approved captures in dataset", bg=BG, fg=TEXT2, font=("Arial", 12)).pack(pady=50)
        else:
            for i, capture in enumerate(captures):
                row_bg = PANEL if i % 2 == 0 else BG
                row = tk.Frame(scrollable_frame, bg=row_bg)
                row._capture_id = capture.get("id")  # Store ID for deletion
                row.pack(fill=tk.X)

                annoteur_id = (capture.get('annoteur_id') or 'Unknown')[:16]
                tk.Label(row, text=annoteur_id, bg=row_bg, fg=TEXT, font=("Arial", 10), width=16, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                created_at = (capture.get('created_at') or '')[:14]
                tk.Label(row, text=created_at, bg=row_bg, fg=TEXT, font=("Arial", 10), width=14, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
                expected = capture.get('expected_diameter_mm') or 0
                actual = capture.get('measured_distance_mm', 0)
                measure_text = f"{expected:.2f} / {actual:.2f}mm"
                tk.Label(row, text=measure_text, bg=row_bg, fg=TEXT, font=("Arial", 10), width=16, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                zoom = capture.get('zoom_level')
                zoom_text = f"{zoom:.1f}x" if zoom else "—"
                tk.Label(row, text=zoom_text, bg=row_bg, fg=TEXT, font=("Arial", 10), width=8, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                status_text = capture.get('measurement_status', 'unknown').upper()
                status_color = GREEN if status_text == "OKAY" else RED
                tk.Label(row, text=status_text, bg=row_bg, fg=status_color, font=("Arial", 10, "bold"), width=9, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                action_frame = tk.Frame(row, bg=row_bg)
                action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

                view_btn = tk.Button(action_frame, text="👁 View", command=lambda cap=capture: self._show_capture_modal(cap),
                                    bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4)
                view_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(view_btn, ACCENT, "#8B0F15", "#FFFFFF")

                delete_btn = tk.Button(action_frame, text="🗑 Delete", command=lambda cid=capture.get("id"): self._delete_dataset_capture(cid),
                                      bg=RED, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4)
                delete_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(delete_btn, RED, "#8B0F15", "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

    def _sync_dataset(self, mesure_frame, state_frame, mesure_btn, state_btn, cached, tab_state):
        if not self.cache.is_stale("captures"):
            return
        def do_sync():
            result = self.api_client.admin_get_captures()
            if result.get("ok"):
                server_data = result.get("data", [])
                merged = self.cache.update("captures", server_data)
                if merged != cached:
                    # Clear and rebuild both frames
                    for w in mesure_frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()
                    for w in state_frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()

                    # Show all approved captures in MESURE (model_type field removed from schema)
                    mesure_captures = [c for c in merged if c.get("annoteur_approved")]
                    state_captures = []  # STATE annotations managed separately

                    # Update button counts
                    mesure_count = len(mesure_captures)
                    state_count = len(state_captures)
                    mesure_btn.configure(text=f"MESURE ({mesure_count})")
                    state_btn.configure(text=f"STATE ({state_count})")

                    self._build_dataset_table(mesure_frame, mesure_captures)
                    self._build_dataset_table(state_frame, state_captures)
        self.root.after(0, do_sync)

    def _delete_dataset_capture(self, capture_id):
        if messagebox.askyesno("Confirm", "Delete this capture from dataset?"):
            def do_delete():
                result = self.api_client.delete_capture(capture_id)
                self.root.after(0, lambda: self._handle_delete_result(capture_id, result))

            # Run delete in background thread
            import threading
            thread = threading.Thread(target=do_delete, daemon=True)
            thread.start()

    def _handle_delete_result(self, capture_id, result):
        """Handle delete result - update cache and UI without full page reload"""
        if result.get("ok"):
            # Update cache: remove deleted capture
            cached = self.cache.get("captures")
            if cached:
                updated = [c for c in cached if c.get("id") != capture_id]
                self.cache.update("captures", updated)

            # Find and remove the row from current display
            # Look for a table widget with this capture's data
            for widget in self.content_container.winfo_children():
                for child in widget.winfo_children():
                    if hasattr(child, 'winfo_children'):
                        for row in child.winfo_children():
                            if hasattr(row, '_capture_id') and row._capture_id == capture_id:
                                row.destroy()
                                messagebox.showinfo("Success", "Capture deleted!")
                                return

            # If row not found in display, just show success
            messagebox.showinfo("Success", "Capture deleted!")
        else:
            messagebox.showerror("Error", result.get("error", "Failed to delete capture"))

    def _show_notifications_page(self):
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="NOTIFICATIONS", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        cached = self.cache.get("notifications")
        self._build_notifications_table(frame, cached)
        self._sync_notifications(frame, cached)

    def _build_notifications_table(self, frame, notifications):
        if not notifications:
            notifications = []

        table_frame = tk.Frame(frame, bg=BORDER, relief=tk.SUNKEN, bd=1)
        table_frame.pack(fill=tk.BOTH, expand=True)
        table_frame._is_table = True

        # Header
        header = tk.Frame(table_frame, bg=PANEL)
        header.pack(fill=tk.X)

        cols = [("TYPE", 10), ("ANNOTEUR", 15), ("TITLE", 18), ("DATE", 14), ("STATUS", 9), ("ACTIONS", 12)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        tk.Frame(table_frame, bg=BORDER, height=1).pack(fill=tk.X)

        canvas = tk.Canvas(table_frame, bg=BG, highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        if not notifications:
            tk.Label(scrollable_frame, text="No notifications", bg=BG, fg=TEXT2, font=("Arial", 12)).pack(pady=50)
        else:
            for i, notif in enumerate(notifications):
                row_bg = PANEL if i % 2 == 0 else BG
                row = tk.Frame(scrollable_frame, bg=row_bg)
                row.pack(fill=tk.X)

                ntype = ((notif.get('notification_type') or 'info')[:10]).upper()
                type_color = {"INFO": TEXT, "WARNING": AMBER, "ALERT": RED, "SUCCESS": GREEN}.get(ntype, TEXT)
                tk.Label(row, text=ntype, bg=row_bg, fg=type_color, font=("Arial", 9, "bold"), width=10, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                username = (notif.get('username') or 'Unknown')[:15]
                tk.Label(row, text=username, bg=row_bg, fg=TEXT, font=("Arial", 10), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                title = (notif.get('title') or '')[:18]
                tk.Label(row, text=title, bg=row_bg, fg=TEXT, font=("Arial", 10), width=18, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                date = (notif.get('created_at') or '')[:14]
                tk.Label(row, text=date, bg=row_bg, fg=TEXT, font=("Arial", 10), width=14, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                read_status = "READ" if notif.get('read') else "NEW"
                read_color = TEXT if notif.get('read') else GREEN
                tk.Label(row, text=read_status, bg=row_bg, fg=read_color, font=("Arial", 9, "bold"), width=9, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                action_frame = tk.Frame(row, bg=row_bg)
                action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

                view_btn = tk.Button(action_frame, text="👁 View", command=lambda notif_data=notif: self._show_notification_modal(notif_data),
                                    bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=10, pady=4)
                view_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(view_btn, ACCENT, "#8B0F15", "#FFFFFF")

                reply_btn = tk.Button(action_frame, text="↩ Reply", command=lambda notif_title=notif.get('title'): self._show_reply_dialog(notif_title),
                                     bg=GREEN, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=10, pady=4)
                reply_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(reply_btn, GREEN, "#388E3C", "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

    def _sync_notifications(self, frame, cached):
        if not self.cache.is_stale("notifications"):
            return
        def do_sync():
            result = self.api_client.get_notifications()
            if result and result.get("ok"):
                server_data = result.get("data", [])
                merged = self.cache.update("notifications", server_data)
                if merged != cached:
                    for w in frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()
                    self._build_notifications_table(frame, merged)
        self.root.after(0, do_sync)

    def _show_notification_modal(self, notification):
        modal = tk.Toplevel(self.root)
        modal.title("Notification Details")
        modal.geometry("600x450")
        modal.configure(bg=BG)
        modal.resizable(True, True)
        modal.grab_set()

        frame = tk.Frame(modal, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title section
        title_frame = tk.Frame(frame, bg=BG)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ntype = notification.get('notification_type', 'info').upper()
        type_color = {"INFO": TEXT, "WARNING": AMBER, "ALERT": RED, "SUCCESS": GREEN}.get(ntype, TEXT)
        tk.Label(title_frame, text=ntype, bg=BG, fg=type_color, font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(title_frame, text=notification.get('title', ''), bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Metadata section
        meta_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        meta_frame.pack(fill=tk.X, pady=(0, 15))

        created_at_str = (notification.get('created_at') or '')[:19]
        meta_text = f"From: {notification.get('username', 'Unknown')}  |  Date: {created_at_str}"
        tk.Label(meta_frame, text=meta_text, bg=PANEL, fg=TEXT2, font=("Arial", 9)).pack(anchor=tk.W, padx=10, pady=8)

        # Message section
        tk.Label(frame, text="Message:", bg=BG, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))

        msg_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        msg_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        msg_text = tk.Text(msg_frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, wrap=tk.WORD)
        msg_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        msg_text.insert(tk.END, notification.get('body', ''))
        msg_text.config(state=tk.DISABLED)

        # Reply section
        reply_frame = tk.Frame(frame, bg=BG)
        reply_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tk.Label(reply_frame, text="Your Reply:", bg=BG, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 8))

        reply_box = tk.Frame(reply_frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        reply_box.pack(fill=tk.BOTH, expand=True)

        reply_text = tk.Text(reply_box, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, height=4, wrap=tk.WORD, insertbackground=ACCENT)
        reply_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        reply_text.focus()

        # Buttons
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        close_btn = tk.Button(btn_frame, text="CLOSE", command=modal.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        close_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(close_btn, PANEL, SEP, TEXT)

        def submit_reply():
            reply_content = reply_text.get("1.0", tk.END).strip()
            if not reply_content:
                messagebox.showwarning("Empty", "Please enter a reply")
                return
            messagebox.showinfo("Success", "Reply sent!")
            modal.destroy()

        reply_btn = tk.Button(btn_frame, text="↩ REPLY", command=submit_reply, bg=GREEN, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        reply_btn.pack(side=tk.LEFT)
        add_hover_effect(reply_btn, GREEN, "#388E3C", "#FFFFFF")

    def _show_reply_dialog(self, notification_title):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Reply to: {notification_title}")
        dialog.geometry("500x400")
        dialog.configure(bg=BG)
        dialog.resizable(True, True)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="Write your reply:", bg=BG, fg=TEXT, font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

        reply_box = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1, height=150)
        reply_box.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        reply_box.pack_propagate(False)

        reply_text = tk.Text(reply_box, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, wrap=tk.WORD, insertbackground=ACCENT, height=8)
        reply_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        reply_text.focus()

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def submit_reply():
            reply_content = reply_text.get("1.0", tk.END).strip()
            if not reply_content:
                messagebox.showwarning("Empty", "Please enter a reply")
                return

            # Send reply to API (owner will receive notification)
            try:
                # Create a notification for the message owner
                import requests
                response = requests.post(
                    f"{self.api_client.api_url}/notifications/reply",
                    json={
                        "notification_title": notification_title,
                        "reply_content": reply_content,
                        "replied_by": self.api_client.user_id or "Admin"
                    },
                    headers={"Authorization": f"Bearer {self.api_client.access_token}"},
                    timeout=5
                )

                if response.status_code == 200:
                    messagebox.showinfo("Success", "Reply sent to message owner!")
                    dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send reply. Please try again.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send reply: {str(e)}")
                dialog.destroy()

        send_btn = tk.Button(btn_frame, text="SEND", command=submit_reply, bg=GREEN, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        send_btn.pack(side=tk.LEFT)
        add_hover_effect(send_btn, GREEN, "#388E3C", "#FFFFFF")

    def _add_user_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Annoteur")
        dialog.geometry("400x350")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="Add New User", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text="Username", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        username_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        username_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Password", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        password_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, show="●", relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        password_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Email", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        email_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        email_entry.pack(fill=tk.X, pady=(0, 20))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X)

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def submit():
            result = self.api_client.admin_create_user(
                username_entry.get(),
                password_entry.get(),
                email_entry.get(),
                "annoteur"
            )
            if result.get("ok"):
                self.cache.invalidate("users")
                dialog.destroy()
                self._switch_page("users", self._show_users_page)
            else:
                messagebox.showerror("Error", result.get("error", "Failed to create user"))

        submit_btn = tk.Button(btn_frame, text="SUBMIT", command=submit, bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        submit_btn.pack(side=tk.LEFT)
        add_hover_effect(submit_btn, ACCENT, ACCENT, "#FFFFFF")

    def _add_machine_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Register Machine")
        dialog.geometry("400x420")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="Register Machine", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text="Machine Name", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        name_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        name_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Password", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        password_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, show="●", relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        password_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Location", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        location_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        location_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Firmware Version", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        firmware_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        firmware_entry.pack(fill=tk.X, pady=(0, 20))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X)

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def submit():
            result = self.api_client.admin_create_machine(
                name_entry.get(),
                password_entry.get(),
                location_entry.get(),
                firmware_entry.get()
            )
            if result.get("ok"):
                self.cache.invalidate("machines")
                dialog.destroy()
                self._switch_page("machines", self._show_machines_page)
            else:
                messagebox.showerror("Error", result.get("error", "Failed to create machine"))

        submit_btn = tk.Button(btn_frame, text="SUBMIT", command=submit, bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        submit_btn.pack(side=tk.LEFT)
        add_hover_effect(submit_btn, ACCENT, ACCENT, "#FFFFFF")

    def _add_switch_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Switch")
        dialog.geometry("400x500")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="Add Switch", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        machines = self.cache.get("machines")
        machine_names = [m.get("machine_name", "") for m in machines] if machines else []
        machine_ids = {m.get("machine_name", ""): m.get("id", "") for m in machines} if machines else {}

        tk.Label(frame, text="Machine", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        machine_var = tk.StringVar(value=machine_names[0] if machine_names else "")
        machine_dropdown = tk.OptionMenu(frame, machine_var, *machine_names)
        machine_dropdown.configure(bg=PANEL, fg=TEXT, font=("Consolas", 10), relief=tk.FLAT, bd=0, highlightthickness=0)
        machine_dropdown.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Switch Name", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        name_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        name_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Cable Type", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        type_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        type_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Expected Diameter (mm)", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        expected_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        expected_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Tolerance Min (mm)", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        min_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        min_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Tolerance Max (mm)", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        max_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        max_entry.pack(fill=tk.X, pady=(0, 20))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X)

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def submit():
            try:
                selected_machine = machine_var.get()
                if not selected_machine:
                    messagebox.showerror("Error", "Please select a machine")
                    return
                machine_id = machine_ids.get(selected_machine, "")
                result = self.api_client.admin_create_switch(
                    machine_id,
                    name_entry.get(),
                    float(expected_entry.get()),
                    float(min_entry.get()),
                    float(max_entry.get()),
                    type_entry.get()
                )
                if result.get("ok"):
                    self.cache.invalidate("switches")
                    dialog.destroy()
                    self._switch_page("switches", self._show_switches_page)
                else:
                    messagebox.showerror("Error", result.get("error", "Failed to create switch"))
            except ValueError:
                messagebox.showerror("Error", "Invalid number format")

        submit_btn = tk.Button(btn_frame, text="SUBMIT", command=submit, bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        submit_btn.pack(side=tk.LEFT)
        add_hover_effect(submit_btn, ACCENT, ACCENT, "#FFFFFF")

    def _edit_switch_dialog(self, switch_data):
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Switch")
        dialog.geometry("400x380")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="Edit Switch", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text="Switch Name", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        name_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        name_entry.insert(0, switch_data.get("switch_name", ""))
        name_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Cable Type", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        type_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        type_entry.insert(0, switch_data.get("cable_type", ""))
        type_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Expected Diameter (mm)", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        expected_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        expected_entry.insert(0, str(switch_data.get("expected_diameter_mm", "")))
        expected_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Tolerance Min (mm)", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        min_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        min_entry.insert(0, str(switch_data.get("tolerance_min", "")))
        min_entry.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Tolerance Max (mm)", bg=BG, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        max_entry = tk.Entry(frame, font=("Consolas", 10), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        max_entry.insert(0, str(switch_data.get("tolerance_max", "")))
        max_entry.pack(fill=tk.X, pady=(0, 20))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X)

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def submit():
            try:
                result = self.api_client.admin_update_switch(
                    switch_data.get("id"),
                    switch_name=name_entry.get(),
                    cable_type=type_entry.get(),
                    expected_diameter_mm=float(expected_entry.get()),
                    tolerance_min=float(min_entry.get()),
                    tolerance_max=float(max_entry.get())
                )
                if result.get("ok"):
                    self.cache.invalidate("switches")
                    dialog.destroy()
                    self._switch_page("switches", self._show_switches_page)
                else:
                    messagebox.showerror("Error", result.get("error", "Failed to update switch"))
            except ValueError:
                messagebox.showerror("Error", "Invalid number format")

        submit_btn = tk.Button(btn_frame, text="UPDATE", command=submit, bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        submit_btn.pack(side=tk.LEFT)
        add_hover_effect(submit_btn, ACCENT, ACCENT, "#FFFFFF")

    def _toggle_user(self, user_id, current_active):
        result = self.api_client.admin_update_user(user_id, is_active=not current_active)
        if result.get("ok"):
            self.cache.invalidate("users")
            self._switch_page("users", self._show_users_page)
        else:
            messagebox.showerror("Error", result.get("error", "Failed to toggle user"))

    def _toggle_machine(self, machine_id, current_active):
        result = self.api_client.admin_update_machine(machine_id, is_active=not current_active)
        if result.get("ok"):
            self.cache.invalidate("machines")
            self._switch_page("machines", self._show_machines_page)
        else:
            messagebox.showerror("Error", result.get("error", "Failed to toggle machine"))

    def _delete_user(self, user_id, username):
        if messagebox.askyesno("Confirm", f"Delete user '{username}'?"):
            result = self.api_client.admin_delete_user(user_id)
            if result.get("ok"):
                self.cache.invalidate("users")
                self._switch_page("users", self._show_users_page)
            else:
                messagebox.showerror("Error", result.get("error", "Failed to delete user"))

    def _delete_machine(self, machine_id, machine_name):
        if messagebox.askyesno("Confirm", f"Delete machine '{machine_name}'?"):
            result = self.api_client.admin_delete_machine(machine_id)
            if result.get("ok"):
                self.cache.invalidate("machines")
                self._switch_page("machines", self._show_machines_page)
            else:
                messagebox.showerror("Error", result.get("error", "Failed to delete machine"))

    def _delete_switch(self, switch_id, switch_name):
        if messagebox.askyesno("Confirm", f"Delete switch '{switch_name}'?"):
            result = self.api_client.admin_delete_switch(switch_id)
            if result.get("ok"):
                self.cache.invalidate("switches")
                self._switch_page("switches", self._show_switches_page)
            else:
                messagebox.showerror("Error", result.get("error", "Failed to delete switch"))

    def _load_model_metadata(self, model_type="mesure"):
        """Load model metadata from JSON file, return default if not found"""
        metadata_path = MODELS_MESURE_DIR / f"{model_type}_metadata.json"

        if metadata_path.exists():
            try:
                import json
                return json.loads(metadata_path.read_text())
            except Exception as e:
                print(f"Error loading metadata: {e}")

        # Return default metadata if file doesn't exist
        if model_type == "mesure":
            return {
                "model_name": "CNN_BELMOUNTH_MESURE_V1",
                "type": "mesure",
                "status": "untrained",
                "accuracy_10px": 0,
                "accuracy_20px": 0,
                "test_loss": 0,
                "test_mae": 0,
                "mean_pixel_error": 0,
                "epochs_trained": 0,
                "training_samples": 0,
                "test_samples": 0
            }
        else:  # state
            return {
                "model_name": "CNN_BELMOUNTH_STATE_V1",
                "type": "state",
                "status": "untrained",
                "overall_accuracy": 0,
                "test_loss": 0,
                "precision": 0,
                "recall": 0,
                "f1_score": 0,
                "epochs_trained": 0,
                "training_samples": 0,
                "test_samples": 0
            }

    def _show_model_page(self):
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        tk.Label(frame, text="ML MODEL MANAGEMENT", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 15))

        # Get dataset count and approved captures
        dataset_captures = self.cache.get("captures")
        if not dataset_captures:
            self.cache.update("captures", self.api_client.admin_get_captures().get("data", []))
            dataset_captures = self.cache.get("captures")

        mesure_dataset = len([c for c in dataset_captures if c.get("annoteur_approved") and c.get("model_type") == "mesure"]) if dataset_captures else 0
        state_dataset = len([c for c in dataset_captures if c.get("annoteur_approved") and c.get("model_type") == "state"]) if dataset_captures else 0

        # Check for actual model files and track versions
        model_dir = MODELS_MESURE_DIR

        # MESURE model versions
        mesure_model_v1 = model_dir / "CNN_BELMOUNTH_MODEL_V1.h5"
        mesure_model_v2 = model_dir / "CNN_BELMOUNTH_MESURE_V2.h5"
        mesure_v1_exists = mesure_model_v1.exists()
        mesure_v2_exists = mesure_model_v2.exists()
        mesure_latest_version = 2 if mesure_v2_exists else (1 if mesure_v1_exists else 0)
        mesure_exists = mesure_latest_version > 0

        # STATE model versions
        state_model_v1 = model_dir / "CNN_BELMOUNTH_STATE_V1.h5"
        state_model_v2 = model_dir / "CNN_BELMOUNTH_STATE_V2.h5"
        state_v1_exists = state_model_v1.exists()
        state_v2_exists = state_model_v2.exists()
        state_latest_version = 2 if state_v2_exists else (1 if state_v1_exists else 0)
        state_exists = state_latest_version > 0

        # Load metadata for latest version
        mesure_metadata = self._load_model_metadata("mesure") if mesure_exists else {"model_name": f"CNN_BELMOUNTH_MESURE_V{mesure_latest_version}"}
        state_metadata = self._load_model_metadata("state") if state_exists else {"model_name": f"CNN_BELMOUNTH_STATE_V{state_latest_version}"}

        # Create table
        table_frame = tk.Frame(frame, bg=BORDER, relief=tk.SUNKEN, bd=1)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Header row
        header = tk.Frame(table_frame, bg=PANEL)
        header.pack(fill=tk.X)

        cols = [("MODEL", 12), ("TYPE", 12), ("STATUS", 12), ("VERSION", 10), ("DATASET", 12), ("ACTIONS", 20)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=5, pady=10)

        tk.Frame(table_frame, bg=BORDER, height=1).pack(fill=tk.X)

        canvas = tk.Canvas(table_frame, bg=BG, highlightthickness=0, height=300)
        scrollbar = tk.Scrollbar(table_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Models data
        models_data = [
            ("MESURE", "Keypoint Detection", "TRAINED" if mesure_exists else "NOT TRAINED",
             f"V{mesure_latest_version}" if mesure_exists else "—", f"{mesure_dataset}/499", "mesure", mesure_latest_version, mesure_exists, mesure_v1_exists, mesure_v2_exists),
            ("STATE", "Cable Classification", "TRAINED" if state_exists else "NOT TRAINED",
             f"V{state_latest_version}" if state_exists else "—", f"{state_dataset}/500", "state", state_latest_version, state_exists, state_v1_exists, state_v2_exists),
        ]

        for i, (model_name, model_type, status, version, dataset, model_id, latest_ver, exists, v1_ex, v2_ex) in enumerate(models_data):
            row_bg = PANEL if i % 2 == 0 else BG
            row = tk.Frame(scrollable_frame, bg=row_bg)
            row.pack(fill=tk.X)

            # Model name
            tk.Label(row, text=model_name, bg=row_bg, fg=TEXT, font=("Arial", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Type
            tk.Label(row, text=model_type, bg=row_bg, fg=TEXT2, font=("Arial", 9), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Status
            status_color = GREEN if "TRAINED" in status else AMBER
            tk.Label(row, text=status, bg=row_bg, fg=status_color, font=("Arial", 9, "bold"), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Version
            tk.Label(row, text=version, bg=row_bg, fg=TEXT, font=("Arial", 9), width=10, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Dataset
            limit = 499 if model_id == "mesure" else 500
            dataset_color = GREEN if "/" in dataset and int(dataset.split("/")[0]) >= limit else TEXT
            tk.Label(row, text=dataset, bg=row_bg, fg=dataset_color, font=("Arial", 9), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Actions
            action_frame = tk.Frame(row, bg=row_bg)
            action_frame.pack(side=tk.LEFT, padx=5, pady=8)

            if exists:
                upgrade_btn = tk.Button(action_frame, text=f"🔄 Upgrade", font=("Arial", 8, "bold"),
                                       command=lambda m=model_id, d=(mesure_dataset if model_id == "mesure" else state_dataset), v=latest_ver: self._upgrade_model_dialog(m, d, v),
                                       bg=GREEN, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=8, pady=3)
                upgrade_btn.pack(side=tk.LEFT, padx=2)
                add_hover_effect(upgrade_btn, GREEN, "#388E3C", "#FFFFFF")

                if v1_ex and v2_ex:
                    delete_btn = tk.Button(action_frame, text="🗑 V1", font=("Arial", 8, "bold"),
                                          command=lambda m=model_id: self._delete_model_version(m, 1),
                                          bg=RED, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=8, pady=3)
                    delete_btn.pack(side=tk.LEFT, padx=2)
                    add_hover_effect(delete_btn, RED, "#8B0F15", "#FFFFFF")
            else:
                dataset_val = mesure_dataset if model_id == "mesure" else state_dataset
                limit = 499 if model_id == "mesure" else 500
                if dataset_val < limit:
                    tk.Label(action_frame, text=f"⚠ Need {limit - dataset_val}", fg=RED, bg=row_bg, font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
                else:
                    create_btn = tk.Button(action_frame, text="✚ Create", font=("Arial", 8, "bold"),
                                          command=lambda m=model_id, d=dataset_val: self._create_model_dialog(m, d),
                                          bg=GREEN, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=8, pady=3)
                    create_btn.pack(side=tk.LEFT, padx=2)
                    add_hover_effect(create_btn, GREEN, "#388E3C", "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        # Send button
        button_frame = tk.Frame(frame, bg=BG)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        send_btn = tk.Button(button_frame, text="🚀 SEND MODELS TO MACHINES",
                            command=lambda: self._deploy_models_dialog(mesure_exists, state_exists, mesure_latest_version, state_latest_version),
                            bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        send_btn.pack(side=tk.LEFT)
        add_hover_effect(send_btn, ACCENT, "#8B0F15", "#FFFFFF")

    def _create_model_dialog(self, model_type, dataset_count):
        """Dialog to create a new model"""
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Create {model_type.upper()} Model")
        dialog.geometry("500x380")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text=f"Create {model_type.upper()} Model", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text=f"Dataset samples available: {dataset_count}", bg=BG, fg=TEXT, font=("Arial", 11)).pack(anchor=tk.W, pady=(0, 5))
        tk.Label(frame, text="This will use all approved captures from the dataset section.", bg=BG, fg=TEXT2, font=("Arial", 9)).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text="⚙ Model will be trained using:", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

        info_text = f"""• All {dataset_count} approved captures from DATASET section
• 80% training data ({int(dataset_count * 0.8)} samples)
• 20% test data ({int(dataset_count * 0.2)} samples)
• Type: {model_type}
• Model will be saved as {model_type}_model_v1.h5"""

        tk.Label(frame, text=info_text, bg=BG, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 20))

        # Buttons
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=10)

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 11, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=15)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def confirm_create():
            messagebox.showinfo("Model Training", f"Training {model_type} model with {dataset_count} samples...\n\nThis may take several minutes.")
            dialog.destroy()
            # TODO: Call backend to start training
            messagebox.showinfo("Success", f"Model training started! Check the TRAINING section for progress.")

        create_btn = tk.Button(btn_frame, text="CREATE & TRAIN", command=confirm_create, bg=GREEN, fg="#FFFFFF", font=("Arial", 11, "bold"), relief=tk.FLAT, bd=0, padx=30, pady=15)
        create_btn.pack(side=tk.LEFT)
        add_hover_effect(create_btn, GREEN, "#388E3C", "#FFFFFF")

    def _upgrade_model_dialog(self, model_type, dataset_count, current_version):
        """Dialog to upgrade an existing model to next version"""
        next_version = current_version + 1
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Upgrade {model_type.upper()} Model")
        dialog.geometry("500x350")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text=f"Upgrade {model_type.upper()} Model", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text=f"Current available dataset: {dataset_count} samples", bg=BG, fg=TEXT, font=("Arial", 11)).pack(anchor=tk.W, pady=(0, 5))
        tk.Label(frame, text=f"Current version: V{current_version} → New version: V{next_version}", bg=BG, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 15))

        limit = 499 if model_type == "mesure" else 500
        if dataset_count < limit:
            shortage = limit - dataset_count
            tk.Label(frame, text=f"❌ Not enough new data! Need {shortage} more samples.", bg=BG, fg=RED, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 20))
            tk.Label(frame, text=f"Please collect and approve at least {limit} new captures before upgrading.", bg=BG, fg=TEXT2, font=("Arial", 9)).pack(anchor=tk.W, pady=(0, 20))

            close_btn = tk.Button(frame, text="CLOSE", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
            close_btn.pack(anchor=tk.W)
        else:
            tk.Label(frame, text=f"✓ Ready to upgrade with {dataset_count} samples", bg=BG, fg=GREEN, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 20))

            tk.Label(frame, text="⚙ Upgrade will:", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

            info_text = f"""• Use all {dataset_count} approved captures
• Create new model version (V{current_version} → V{next_version})
• Keep V{current_version} for comparison/rollback
• Training: {int(dataset_count * 0.8)} samples
• Testing: {int(dataset_count * 0.2)} samples
• Optional: Delete old version after V{next_version} is verified"""

            tk.Label(frame, text=info_text, bg=BG, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 20))

            # Buttons
            btn_frame = tk.Frame(frame, bg=BG)
            btn_frame.pack(fill=tk.X)

            cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
            cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
            add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

            def confirm_upgrade():
                messagebox.showinfo("Model Upgrade", f"Upgrading {model_type} model to V{next_version}...\n\nThis may take several minutes.")
                dialog.destroy()
                # TODO: Call backend to start upgrade training
                messagebox.showinfo("Success", f"Model upgrade started!\nV{next_version} will be created while keeping V{current_version}.\nYou can delete the old version once verified.")

            upgrade_btn = tk.Button(btn_frame, text=f"🔄 UPGRADE TO V{next_version}", command=confirm_upgrade, bg=GREEN, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
            upgrade_btn.pack(side=tk.LEFT)
            add_hover_effect(upgrade_btn, GREEN, "#388E3C", "#FFFFFF")

    def _delete_model_version(self, model_type, version):
        """Delete an old model version"""
        if not messagebox.askyesno("Confirm Delete", f"Delete {model_type.upper()} Model V{version}?\n\nThis will free up disk space but cannot be undone."):
            return

        try:
            model_dir = MODELS_MESURE_DIR

            if model_type == "mesure":
                if version == 1:
                    model_file = model_dir / "CNN_BELMOUNTH_MODEL_V1.h5"
                else:
                    model_file = model_dir / "CNN_BELMOUNTH_MESURE_V2.h5"
            else:  # state
                if version == 1:
                    model_file = model_dir / "CNN_BELMOUNTH_STATE_V1.h5"
                else:
                    model_file = model_dir / "CNN_BELMOUNTH_STATE_V2.h5"

            if model_file.exists():
                model_file.unlink()
                messagebox.showinfo("Success", f"✓ {model_type.upper()} Model V{version} deleted successfully!\n\nFreed up {model_file.stat().st_size / (1024**3):.2f} GB")
                # Refresh the page
                self._switch_page("model", self._show_model_page)
            else:
                messagebox.showerror("Error", f"Model file not found: {model_file.name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete model: {str(e)}")

    def _deploy_models_dialog(self, mesure_exists, state_exists, mesure_latest_version, state_latest_version):
        """Dialog to deploy models to machines with version selection"""
        # Check available versions
        models_state_dir = MODELS_ROOT / "state"
        mesure_v1 = MODELS_MESURE_DIR / "CNN_BELMOUNTH_MODEL_V1.h5"
        mesure_v2 = MODELS_MESURE_DIR / "CNN_BELMOUNTH_MESURE_V2.h5"
        state_v1 = models_state_dir / "CNN_BELMOUNTH_STATE_V1.h5"
        state_v2 = models_state_dir / "CNN_BELMOUNTH_STATE_V2.h5"

        mesure_versions = []
        if mesure_v1.exists():
            mesure_versions.append(1)
        if mesure_v2.exists():
            mesure_versions.append(2)

        state_versions = []
        if state_v1.exists():
            state_versions.append(1)
        if state_v2.exists():
            state_versions.append(2)

        dialog = tk.Toplevel(self.root)
        dialog.title("Send Models to Machines")
        dialog.geometry("500x350")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="Send Models to All Machines", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 30))

        # MESURE Model Selection
        tk.Label(frame, text="📐 MESURE Model", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        mesure_var = tk.StringVar(value=f"V{max(mesure_versions)}" if mesure_versions else "None")

        if mesure_versions:
            mesure_options = [f"V{v}" for v in sorted(mesure_versions, reverse=True)]
            mesure_dropdown = tk.OptionMenu(frame, mesure_var, *mesure_options)
            mesure_dropdown.configure(bg=PANEL, fg=TEXT, font=("Consolas", 10), relief=tk.FLAT, bd=0, highlightthickness=0)
            mesure_dropdown.pack(fill=tk.X, pady=(0, 20))
        else:
            mesure_var = tk.StringVar(value="None")
            tk.Label(frame, text="⚠ No MESURE model available", bg=BG, fg=AMBER, font=("Arial", 9)).pack(anchor=tk.W, pady=(0, 20))

        # STATE Model Selection
        tk.Label(frame, text="🔍 STATE Model", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        state_var = tk.StringVar(value=f"V{max(state_versions)}" if state_versions else "None")

        if state_versions:
            state_options = [f"V{v}" for v in sorted(state_versions, reverse=True)]
            state_dropdown = tk.OptionMenu(frame, state_var, *state_options)
            state_dropdown.configure(bg=PANEL, fg=TEXT, font=("Consolas", 10), relief=tk.FLAT, bd=0, highlightthickness=0)
            state_dropdown.pack(fill=tk.X, pady=(0, 20))
        else:
            tk.Label(frame, text="⚠ No STATE model available", bg=BG, fg=AMBER, font=("Arial", 9)).pack(anchor=tk.W, pady=(0, 20))

        # Buttons
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def confirm_deploy():
            models_to_deploy = []
            deploy_info = []

            if mesure_var.get() != "None":
                models_to_deploy.append(f"MESURE {mesure_var.get()}")
                deploy_info.append(f"  • MESURE Model {mesure_var.get()}")

            if state_var.get() != "None":
                models_to_deploy.append(f"STATE {state_var.get()}")
                deploy_info.append(f"  • STATE Model {state_var.get()}")

            if not models_to_deploy:
                messagebox.showwarning("Selection", "Please select at least one model to deploy")
                return

            # Confirmation
            confirm_msg = "Ready to send model updates:\n\n" + "\n".join(deploy_info) + "\n\nProceed?"
            if not messagebox.askyesno("Confirm Deployment", confirm_msg):
                return

            messagebox.showinfo("Deployment", f"Sending {' + '.join(models_to_deploy)} update notification to all machines...")
            dialog.destroy()
            # TODO: Call backend to send notifications with version info
            messagebox.showinfo("Success", f"✓ Notification sent to all machines!\n\nMachine users will see:\n{chr(10).join(deploy_info)}\n\nThey can click 'Update Model' to install.")

        deploy_btn = tk.Button(btn_frame, text="🚀 SEND TO MACHINES", command=confirm_deploy, bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
        deploy_btn.pack(side=tk.LEFT)
        add_hover_effect(deploy_btn, ACCENT, "#8B0F15", "#FFFFFF")

    def _open_model_training(self):
        try:
            model_app_path = Path(__file__).parent / "model_bellmounth_mesure" / "model_app.py"
            if model_app_path.exists():
                import subprocess
                subprocess.Popen([sys.executable, str(model_app_path)])
                messagebox.showinfo("Success", "Model training UI launched in new window")
            else:
                messagebox.showerror("Error", f"Model app not found at:\n{model_app_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch model training:\n{str(e)}")

    def run(self):
        self.root.mainloop()

# ==================== ANNOTEUR APP (Interactive Point Editing) ====================
class AnnoteurApp:
    def __init__(self, username: str, user_id: str, api_client: APIClient):
        self.username = username
        self.user_id = user_id
        self.api_client = api_client
        self.captures = []
        self.current_capture_idx = 0

        self.root = tk.Tk()
        self.root.title("Bellmounth Annotation Interface")
        self.root.geometry("1280x900")
        self.root.configure(bg=BG)
        self.root.state('zoomed')

        self._build_ui()
        self._load_captures()

    def _build_ui(self):
        # Header bar
        top = tk.Frame(self.root, bg=PANEL, height=58)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        tk.Label(top, text="Annotation Interface", bg=PANEL, fg=TEXT2, font=("Arial", 11, "bold")).pack(side=tk.LEFT, padx=10)

        tk.Frame(top, bg=PANEL).pack(fill=tk.X, expand=True)

        tk.Label(top, text=self.username, bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        tk.Frame(top, bg=BORDER, width=1, height=30).pack(side=tk.LEFT, padx=5)

        self.clock_lbl = tk.Label(top, text="", bg=PANEL, fg=TEXT2, font=("Arial", 10))
        self.clock_lbl.pack(side=tk.LEFT, padx=10)
        self._update_clock()

        tk.Frame(top, bg=BORDER, width=1, height=30).pack(side=tk.LEFT, padx=5)

        quit_btn = tk.Button(top, text="LOGOUT", command=self._on_closing, bg=RED, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=6)
        quit_btn.pack(side=tk.LEFT, padx=10)
        add_hover_effect(quit_btn, RED, RED, "#FFFFFF")

        # Main content
        main_content = tk.Frame(self.root, bg=BG)
        main_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        tk.Label(main_content, text="Cable State Annotation", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Toolbar
        toolbar = tk.Frame(main_content, bg=BG)
        toolbar.pack(fill=tk.X, pady=(0, 20))

        self.status_lbl = tk.Label(toolbar, text="Loading captures...", bg=BG, fg=TEXT2, font=("Arial", 10))
        self.status_lbl.pack(side=tk.LEFT)

        tk.Frame(toolbar, bg=BG).pack(fill=tk.X, expand=True)

        refresh_btn = tk.Button(toolbar, text="🔄 REFRESH", command=self._load_captures,
                               bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"),
                               relief=tk.FLAT, bd=0, padx=15, pady=8)
        refresh_btn.pack(side=tk.RIGHT)
        add_hover_effect(refresh_btn, ACCENT, ACCENT, "#FFFFFF")

        # Content frame
        self.content_frame = tk.Frame(main_content, bg=BG)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

    def _update_clock(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.clock_lbl.config(text=now)
        self.root.after(1000, self._update_clock)

    def _load_captures(self):
        try:
            response = self.api_client.get("/admin/captures?status=pending")
            if response:
                self.captures = response if isinstance(response, list) else []
                self.current_capture_idx = 0
                self._show_current_capture()
                self._update_status()
            else:
                self.captures = []
                self._show_no_captures()
                self._update_status()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load captures: {str(e)}")
            self._show_no_captures()

    def _update_status(self):
        total = len(self.captures)
        current = self.current_capture_idx + 1 if self.captures else 0
        self.status_lbl.config(text=f"Capture {current} of {total}")

    def _show_no_captures(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        frame = tk.Frame(self.content_frame, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        tk.Label(frame, text="✓", bg=BG, fg=GREEN, font=("Arial", 72)).pack(pady=(40, 20))
        tk.Label(frame, text="All Caught Up!", bg=BG, fg=TEXT, font=("Arial", 20, "bold")).pack(pady=(0, 10))
        tk.Label(frame, text="There are no pending captures to annotate", bg=BG, fg=TEXT2, font=("Arial", 12)).pack()

    def _show_current_capture(self):
        if not self.captures:
            self._show_no_captures()
            return

        capture = self.captures[self.current_capture_idx]

        for widget in self.content_frame.winfo_children():
            widget.destroy()

        # Layout: left side image, right side annotation panel
        left_panel = tk.Frame(self.content_frame, bg=BG)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        right_panel = tk.Frame(self.content_frame, bg=PANEL, width=350)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=0)
        right_panel.pack_propagate(False)

        # Image display
        image_frame = tk.Frame(left_panel, bg=BORDER, highlightbackground=BORDER, highlightthickness=1)
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        image_path = capture.get("image_original_path", "")
        if image_path and Path(image_path).exists():
            try:
                import cv2

                # Load image with OpenCV
                img_cv = cv2.imread(image_path)
                if img_cv is not None:
                    # Get original dimensions
                    orig_h, orig_w = img_cv.shape[:2]

                    # Get keypoints
                    p1_x = capture.get('p1_x', 0)
                    p1_y = capture.get('p1_y', 0)
                    p2_x = capture.get('p2_x', 0)
                    p2_y = capture.get('p2_y', 0)

                    # Draw circles at keypoints (green)
                    cv2.circle(img_cv, (int(p1_x), int(p1_y)), 8, (0, 255, 0), -1)  # Filled green circle
                    cv2.circle(img_cv, (int(p2_x), int(p2_y)), 8, (0, 255, 0), -1)

                    # Draw line connecting keypoints (yellow)
                    cv2.line(img_cv, (int(p1_x), int(p1_y)), (int(p2_x), int(p2_y)), (0, 255, 255), 2)

                    # Calculate pixel distance
                    px_dist = ((p2_x - p1_x)**2 + (p2_y - p1_y)**2)**0.5

                    # Add distance label (red text)
                    mm_dist = capture.get('measured_distance_mm', 0)
                    label = f"{mm_dist:.2f} mm ({px_dist:.0f} px)"
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.6
                    thickness = 2
                    color = (0, 0, 255)  # Red in BGR

                    # Get text size to add background
                    text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]
                    label_x = int((p1_x + p2_x) / 2) - text_size[0] // 2
                    label_y = int((p1_y + p2_y) / 2) - 15

                    # Add white background for text
                    cv2.rectangle(img_cv,
                                 (label_x - 5, label_y - text_size[1] - 5),
                                 (label_x + text_size[0] + 5, label_y + 5),
                                 (255, 255, 255), -1)

                    # Add text
                    cv2.putText(img_cv, label, (label_x, label_y), font, font_scale, color, thickness)

                    # Convert to PIL and resize
                    img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(img_rgb)
                    img.thumbnail((700, 600), Image.Resampling.LANCZOS)

                    photo = ImageTk.PhotoImage(img)
                    img_lbl = tk.Label(image_frame, image=photo, bg=BORDER)
                    img_lbl.image = photo
                    img_lbl.pack(fill=tk.BOTH, expand=True)
                else:
                    tk.Label(image_frame, text="Failed to load image", bg=BORDER, fg=TEXT2).pack(fill=tk.BOTH, expand=True)
            except Exception as e:
                print(f"Image display error: {e}")
                tk.Label(image_frame, text="Failed to load image", bg=BORDER, fg=TEXT2).pack(fill=tk.BOTH, expand=True)
        else:
            tk.Label(image_frame, text="No image available", bg=BORDER, fg=TEXT2, font=("Arial", 12)).pack(fill=tk.BOTH, expand=True)

        # Measurement info
        info_frame = tk.Frame(left_panel, bg=PANEL)
        info_frame.pack(fill=tk.X, pady=10)

        p1_x = capture.get('p1_x', 0)
        p1_y = capture.get('p1_y', 0)
        p2_x = capture.get('p2_x', 0)
        p2_y = capture.get('p2_y', 0)
        px_dist = ((p2_x - p1_x)**2 + (p2_y - p1_y)**2)**0.5

        machine_id = ((capture.get('machine_id') or 'N/A')[:8]) if capture.get('machine_id') else 'N/A'
        switch_id = ((capture.get('switch_id') or 'N/A')[:8]) if capture.get('switch_id') else 'N/A'
        info_text = f"""Machine: {machine_id}...
Switch: {switch_id}...
Measured: {capture.get('measured_distance_mm', 'N/A')} mm
Status: {capture.get('measurement_status', 'N/A')}

P1 (Start): ({int(p1_x)}, {int(p1_y)})
P2 (End):   ({int(p2_x)}, {int(p2_y)})
Distance:   {px_dist:.1f} pixels"""

        tk.Label(info_frame, text=info_text, bg=PANEL, fg=TEXT2, font=("Consolas", 9), justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=10)

        # Right panel: approval controls
        tk.Label(right_panel, text="APPROVE CAPTURE", bg=PANEL, fg=TEXT, font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 20))

        # Measurement details
        details = f"""Measured: {capture.get('measured_distance_mm', 'N/A')} mm
Status: {capture.get('measurement_status', 'N/A')}
Method: {capture.get('capture_method', 'N/A')}
Quality: {capture.get('quality_score', 'N/A')}"""

        tk.Label(right_panel, text=details, bg=PANEL, fg=TEXT2, font=("Consolas", 9), justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=(0, 20))

        # Navigation buttons
        tk.Frame(right_panel, bg=BORDER, height=1).pack(fill=tk.X, pady=15, padx=15)

        button_frame = tk.Frame(right_panel, bg=PANEL)
        button_frame.pack(fill=tk.X, padx=15, pady=(15, 20))

        def on_approve():
            try:
                result = self.api_client.put(f"/admin/captures/{capture.get('id')}/approve", {})
                if result:
                    messagebox.showinfo("Success", "Capture approved!")
                    self._load_captures()
                else:
                    messagebox.showerror("Error", "Failed to approve capture")
            except Exception as e:
                messagebox.showerror("Error", f"Approval failed: {str(e)}")

        approve_btn = tk.Button(button_frame, text="✓ APPROVE", command=on_approve,
                               bg=GREEN, fg="#FFFFFF", font=("Arial", 11, "bold"),
                               relief=tk.FLAT, bd=0, padx=20, pady=12, width=30)
        approve_btn.pack(fill=tk.X, pady=(0, 10))
        add_hover_effect(approve_btn, GREEN, GREEN, "#FFFFFF")

        def on_skip():
            self._next_capture()

        skip_btn = tk.Button(button_frame, text="SKIP", command=on_skip,
                            bg=AMBER, fg="#FFFFFF", font=("Arial", 11, "bold"),
                            relief=tk.FLAT, bd=0, padx=20, pady=12, width=30)
        skip_btn.pack(fill=tk.X)
        add_hover_effect(skip_btn, AMBER, AMBER, "#FFFFFF")

        # Navigation controls at bottom
        nav_frame = tk.Frame(right_panel, bg=PANEL)
        nav_frame.pack(fill=tk.X, padx=15, pady=15)

        prev_btn = tk.Button(nav_frame, text="◀ PREV", command=self._prev_capture,
                            bg=TEXT2, fg="#FFFFFF", font=("Arial", 9, "bold"),
                            relief=tk.FLAT, bd=0, padx=10, pady=8)
        prev_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(prev_btn, TEXT2, TEXT2, "#FFFFFF")

        tk.Label(nav_frame, text="", bg=PANEL).pack(fill=tk.X, expand=True)

        next_btn = tk.Button(nav_frame, text="NEXT ▶", command=self._next_capture,
                            bg=TEXT2, fg="#FFFFFF", font=("Arial", 9, "bold"),
                            relief=tk.FLAT, bd=0, padx=10, pady=8)
        next_btn.pack(side=tk.RIGHT)
        add_hover_effect(next_btn, TEXT2, TEXT2, "#FFFFFF")

    def _next_capture(self):
        if self.current_capture_idx < len(self.captures) - 1:
            self.current_capture_idx += 1
            self._show_current_capture()
            self._update_status()

    def _prev_capture(self):
        if self.current_capture_idx > 0:
            self.current_capture_idx -= 1
            self._show_current_capture()
            self._update_status()

    def _on_closing(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


# ==================== CAPTURE EDITOR MODAL ====================
class CaptureEditorModal:
    """Modal window for editing capture annotations"""
    def __init__(self, parent, capture, api_client, on_save_callback):
        self.parent = parent
        self.capture = capture
        self.api_client = api_client
        self.on_save_callback = on_save_callback
        self.edited_p1 = (capture.get('p1_x', 0), capture.get('p1_y', 0))
        self.edited_p2 = (capture.get('p2_x', 0), capture.get('p2_y', 0))
        self.original_p1 = (capture.get('p1_x', 0), capture.get('p1_y', 0))
        self.original_p2 = (capture.get('p2_x', 0), capture.get('p2_y', 0))
        self.dragging_point = None
        self.thread_mode = False
        self.current_image_pil = None
        self.current_photo = None
        self.thresholded_image_pil = None
        self.thresholded_photo = None
        self.cable_state = tk.StringVar()

        # Zoom state
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.max_zoom = 5.0
        self.min_zoom = 0.5
        self.last_drag_x = 0
        self.last_drag_y = 0
        self.panning = False

        self.modal = tk.Toplevel(parent)
        self.modal.title("Edit Capture Annotation")
        self.modal.geometry("1200x800")
        self.modal.configure(bg=BG)
        self.modal.resizable(False, False)

        self._build_ui()
        self._load_image()

    def _build_ui(self):
        # Header with close button
        header = tk.Frame(self.modal, bg=PANEL, height=50)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        tk.Label(header, text=f"Edit: {self.capture.get('machine_name', 'Unknown')}", bg=PANEL, fg=TEXT, font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=15, pady=10)
        tk.Frame(header, bg=PANEL).pack(fill=tk.X, expand=True)

        close_btn = tk.Button(header, text="✕", command=self.modal.destroy,
                             bg=RED, fg="#FFFFFF", font=("Arial", 14, "bold"),
                             relief=tk.FLAT, bd=0, padx=10, pady=5)
        close_btn.pack(side=tk.RIGHT, padx=10)
        add_hover_effect(close_btn, RED, "#8B0F15", "#FFFFFF")

        # Main content
        main = tk.Frame(self.modal, bg=BG)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Canvas
        left = tk.Frame(main, bg=BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Canvas toolbar
        toolbar = tk.Frame(left, bg=BG)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        tk.Label(toolbar, text="Click & Drag points to edit | Scroll to Zoom", bg=BG, fg=TEXT2, font=("Arial", 9)).pack(side=tk.LEFT)

        # Zoom controls
        zoom_frame = tk.Frame(toolbar, bg=BG)
        zoom_frame.pack(side=tk.RIGHT)

        tk.Button(zoom_frame, text="🔍−", command=self._zoom_out, bg=PANEL, fg=TEXT, font=("Arial", 9), relief=tk.FLAT, bd=0, padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        self.zoom_lbl = tk.Label(zoom_frame, text="1.0x", bg=PANEL, fg=TEXT, font=("Arial", 9), width=6)
        self.zoom_lbl.pack(side=tk.LEFT, padx=5)

        tk.Button(zoom_frame, text="🔍+", command=self._zoom_in, bg=PANEL, fg=TEXT, font=("Arial", 9), relief=tk.FLAT, bd=0, padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        tk.Button(zoom_frame, text="⟲ Reset", command=self._zoom_reset, bg=PANEL, fg=TEXT, font=("Arial", 9), relief=tk.FLAT, bd=0, padx=8, pady=4).pack(side=tk.LEFT, padx=2)

        # Thread mode toggle
        self.thread_btn = tk.Button(zoom_frame, text="🔀 THREAD", command=self._toggle_thread_mode,
                                   bg=PANEL, fg=TEXT, font=("Arial", 9, "bold"),
                                   relief=tk.FLAT, bd=0, padx=12, pady=4)
        self.thread_btn.pack(side=tk.LEFT, padx=(10, 0))
        add_hover_effect(self.thread_btn, PANEL, "#E8E8E8", TEXT)

        self.canvas = tk.Canvas(left, bg=BORDER, width=600, height=700, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<MouseWheel>", self._on_canvas_scroll)
        self.canvas.bind("<Button-4>", self._on_canvas_scroll)  # Linux scroll up
        self.canvas.bind("<Button-5>", self._on_canvas_scroll)  # Linux scroll down

        # Right: Edit panel
        right = tk.Frame(main, bg=PANEL, width=350)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, padx=10)
        right.pack_propagate(False)

        tk.Label(right, text="EDIT ANNOTATION", bg=PANEL, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 10))

        # Original points
        tk.Label(right, text="ORIGINAL POINTS", bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 5))
        self.orig_lbl = tk.Label(right, text="P1: (0, 0)\nP2: (0, 0)", bg=PANEL, fg=TEXT2, font=("Consolas", 8), justify=tk.LEFT)
        self.orig_lbl.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Edited points
        tk.Label(right, text="EDITED POINTS", bg=PANEL, fg=ACCENT, font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 5))
        self.edit_lbl = tk.Label(right, text="P1: (0, 0)\nP2: (0, 0)\nDistance: 0 px", bg=PANEL, fg=ACCENT, font=("Consolas", 8), justify=tk.LEFT)
        self.edit_lbl.pack(anchor=tk.W, padx=20, pady=(0, 15))

        tk.Frame(right, bg=BORDER, height=1).pack(fill=tk.X, pady=10, padx=15)

        # Cable state
        tk.Label(right, text="CABLE STATE", bg=PANEL, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 10))

        states = [("🔴 No Cable", "no_cable"), ("🟠 Male End", "cable_male"), ("🟢 Good Cable", "cable_good")]
        for label, value in states:
            tk.Radiobutton(right, text=label, variable=self.cable_state, value=value,
                          bg=PANEL, fg=TEXT, font=("Arial", 9),
                          selectcolor=ACCENT, activebackground=PANEL, activeforeground=ACCENT).pack(anchor=tk.W, padx=25, pady=2)

        tk.Frame(right, bg=BORDER, height=1).pack(fill=tk.X, pady=10, padx=15)

        # Save button
        self.save_btn = tk.Button(right, text="✓ SAVE", command=self._save_changes,
                                 bg=GREEN, fg="#FFFFFF", font=("Arial", 10, "bold"),
                                 relief=tk.FLAT, bd=0, padx=20, pady=12, state=tk.DISABLED)
        self.save_btn.pack(fill=tk.X, padx=15, pady=(0, 8))
        add_hover_effect(self.save_btn, GREEN, "#3E7C3F", "#FFFFFF")

        # Cancel button
        cancel_btn = tk.Button(right, text="✕ CANCEL", command=self.modal.destroy,
                              bg=TEXT2, fg="#FFFFFF", font=("Arial", 10, "bold"),
                              relief=tk.FLAT, bd=0, padx=20, pady=12)
        cancel_btn.pack(fill=tk.X, padx=15)
        add_hover_effect(cancel_btn, TEXT2, "#555555", "#FFFFFF")

    def _load_image(self):
        """Load the capture images (original and thresholded)"""
        # Load original image
        image_path = self.capture.get('image_original_path', '')
        if image_path and Path(image_path).exists():
            try:
                self.current_image_pil = Image.open(image_path).convert('RGB')
                print(f"✓ Loaded original image: {image_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load original image: {str(e)}")
                return
        else:
            messagebox.showerror("Error", "Image file not found")
            return

        # ALWAYS generate thresholded image from original (don't rely on API paths)
        print("⚙ Generating thresholded image from original...")
        self._generate_thresholded_image()

        self._redraw_canvas()

    def _generate_thresholded_image(self):
        """Generate thresholded image from original using apply_threshold"""
        try:
            if self.current_image_pil is None:
                print("✗ No original image loaded")
                self.thresholded_image_pil = None
                return

            # Convert PIL to numpy array (RGB)
            img_np = np.array(self.current_image_pil)

            # Convert RGB to BGR for OpenCV
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

            # Apply threshold using the standard config from utils.py
            thresholded = apply_threshold(img_bgr)

            # thresholded is now a binary (grayscale) image
            # Convert to PIL Image
            thresh_pil = Image.fromarray(thresholded)

            # Convert to RGB for consistent handling (will display as grayscale since all channels are same)
            self.thresholded_image_pil = thresh_pil.convert('RGB')

            print(f"✓ Thresholded image generated: {self.thresholded_image_pil.size}")
        except Exception as e:
            import traceback
            print(f"✗ Failed to generate thresholded image: {str(e)}")
            traceback.print_exc()
            self.thresholded_image_pil = None

    def _redraw_canvas(self):
        """Redraw canvas with image and points (with zoom and pan support)"""
        self.canvas.delete("all")

        # Choose which image to display
        source_image = self.thresholded_image_pil if self.thread_mode else self.current_image_pil

        if source_image:
            # Resize image based on zoom level
            if self.zoom_level != 1.0:
                new_width = int(source_image.width * self.zoom_level)
                new_height = int(source_image.height * self.zoom_level)
                zoomed_img = source_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                zoomed_img = source_image

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(zoomed_img)

            # Display on canvas with pan offset
            self.canvas.create_image(self.pan_x, self.pan_y, image=photo, anchor=tk.NW)
            # Store reference to prevent garbage collection
            self.canvas.image = photo

        # Draw points with zoom and pan
        if self.edited_p1 and self.edited_p2:
            p1_x, p1_y = self.edited_p1
            p2_x, p2_y = self.edited_p2

            # Apply zoom and pan to point coordinates
            p1_x_z = int(p1_x * self.zoom_level + self.pan_x)
            p1_y_z = int(p1_y * self.zoom_level + self.pan_y)
            p2_x_z = int(p2_x * self.zoom_level + self.pan_x)
            p2_y_z = int(p2_y * self.zoom_level + self.pan_y)

            # Draw circles (green) - scale with zoom
            r = max(5, int(8 * self.zoom_level))
            self.canvas.create_oval(p1_x_z-r, p1_y_z-r, p1_x_z+r, p1_y_z+r, fill=GREEN, outline=GREEN, width=2)
            self.canvas.create_oval(p2_x_z-r, p2_y_z-r, p2_x_z+r, p2_y_z+r, fill=GREEN, outline=GREEN, width=2)

            # Draw line (yellow)
            self.canvas.create_line(p1_x_z, p1_y_z, p2_x_z, p2_y_z, fill=AMBER, width=2)

            # Draw labels
            self.canvas.create_text(p1_x_z-15, p1_y_z-15, text="P1", fill=GREEN, font=("Arial", 10, "bold"))
            self.canvas.create_text(p2_x_z+15, p2_y_z+15, text="P2", fill=GREEN, font=("Arial", 10, "bold"))

        self._update_display()

    def _apply_zoom(self, x, y):
        """Apply zoom transformation"""
        return (int(x * self.zoom_level + self.zoom_pan_x), int(y * self.zoom_level + self.zoom_pan_y))

    def _reverse_zoom(self, x, y):
        """Reverse zoom transformation from canvas to image coordinates"""
        return (int((x - self.zoom_pan_x) / self.zoom_level), int((y - self.zoom_pan_y) / self.zoom_level))

    def _on_canvas_press(self, event):
        """Detect if user clicked on P1/P2 (for point drag) or empty area (for pan)"""
        self.last_drag_x = event.x
        self.last_drag_y = event.y

        if not self.edited_p1 or not self.edited_p2:
            self.panning = True
            return

        p1_x, p1_y = self.edited_p1
        p2_x, p2_y = self.edited_p2

        # Convert click to image coordinates (reverse zoom and pan)
        click_x = int((event.x - self.pan_x) / self.zoom_level) if self.zoom_level > 0 else event.x
        click_y = int((event.y - self.pan_y) / self.zoom_level) if self.zoom_level > 0 else event.y

        # Check distance with tolerance scaled by zoom
        tolerance = 15 / self.zoom_level if self.zoom_level > 0 else 15
        dist_p1 = ((click_x - p1_x)**2 + (click_y - p1_y)**2)**0.5
        dist_p2 = ((click_x - p2_x)**2 + (click_y - p2_y)**2)**0.5

        if dist_p1 < tolerance:
            self.dragging_point = "p1"
            self.panning = False
        elif dist_p2 < tolerance:
            self.dragging_point = "p2"
            self.panning = False
        else:
            # Clicked on empty area - allow panning
            self.panning = True

    def _on_canvas_drag(self, event):
        """Handle point dragging or image panning"""
        if self.panning:
            # Pan the image
            delta_x = event.x - self.last_drag_x
            delta_y = event.y - self.last_drag_y
            self.pan_x += delta_x
            self.pan_y += delta_y
        else:
            # Drag point
            if self.dragging_point == "p1":
                img_x = int((event.x - self.pan_x) / self.zoom_level) if self.zoom_level > 0 else event.x
                img_y = int((event.y - self.pan_y) / self.zoom_level) if self.zoom_level > 0 else event.y
                self.edited_p1 = (img_x, img_y)
                self._enable_save_button()
            elif self.dragging_point == "p2":
                img_x = int((event.x - self.pan_x) / self.zoom_level) if self.zoom_level > 0 else event.x
                img_y = int((event.y - self.pan_y) / self.zoom_level) if self.zoom_level > 0 else event.y
                self.edited_p2 = (img_x, img_y)
                self._enable_save_button()

        self.last_drag_x = event.x
        self.last_drag_y = event.y
        self._redraw_canvas()

    def _on_canvas_release(self, event):
        """Stop dragging point or panning"""
        self.dragging_point = None
        self.panning = False

    def _on_canvas_scroll(self, event):
        """Handle mouse wheel zoom"""
        if event.delta > 0 or event.num == 4:
            self._zoom_in()
        else:
            self._zoom_out()

    def _zoom_in(self):
        """Increase zoom level"""
        if self.zoom_level < self.max_zoom:
            self.zoom_level = min(self.zoom_level + 0.2, self.max_zoom)
            self.zoom_lbl.config(text=f"{self.zoom_level:.1f}x")
            self._redraw_canvas()

    def _zoom_out(self):
        """Decrease zoom level"""
        if self.zoom_level > self.min_zoom:
            self.zoom_level = max(self.zoom_level - 0.2, self.min_zoom)
            self.zoom_lbl.config(text=f"{self.zoom_level:.1f}x")
            self._redraw_canvas()

    def _zoom_reset(self):
        """Reset zoom to 1.0x and reset pan"""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.zoom_lbl.config(text="1.0x")
        self._redraw_canvas()

    def _toggle_thread_mode(self):
        """Toggle thread mode for verification"""
        print(f"[DEBUG] Toggling thread mode - current: {self.thread_mode}, has thresholded: {self.thresholded_image_pil is not None}")

        if not self.thresholded_image_pil:
            print("[DEBUG] Thresholded image is None, trying to generate...")
            # Show status
            self.thread_btn.config(text="🔄 GENERATING...", state=tk.DISABLED)
            self.modal.update()

            self._generate_thresholded_image()

            # Restore button
            self.thread_btn.config(text="🔀 THREAD", state=tk.NORMAL)

            if not self.thresholded_image_pil:
                messagebox.showwarning("Thread Mode", "Thresholded image could not be generated.\nMake sure opencv-python is installed.")
                return

        self.thread_mode = not self.thread_mode
        print(f"[DEBUG] Thread mode is now: {self.thread_mode}")

        if self.thread_mode:
            self.thread_btn.config(bg=ACCENT, fg="#FFFFFF", text="🔀 ORIGINAL")
        else:
            self.thread_btn.config(bg=PANEL, fg=TEXT, text="🔀 THREAD")

        self._redraw_canvas()

    def _update_display(self):
        """Update info labels"""
        self.orig_lbl.config(text=f"P1: {self.original_p1}\nP2: {self.original_p2}")

        if self.edited_p1 and self.edited_p2:
            dist = ((self.edited_p2[0]-self.edited_p1[0])**2 + (self.edited_p2[1]-self.edited_p1[1])**2)**0.5
            self.edit_lbl.config(text=f"P1: {self.edited_p1}\nP2: {self.edited_p2}\nDistance: {dist:.0f} px")

    def _enable_save_button(self):
        """Enable save button if changes detected"""
        if self.edited_p1 != self.original_p1 or self.edited_p2 != self.original_p2:
            self.save_btn.config(state=tk.NORMAL)

    def _save_changes(self):
        """Save edited annotation"""
        try:
            payload = {
                "p1_x": int(self.edited_p1[0]),
                "p1_y": int(self.edited_p1[1]),
                "p2_x": int(self.edited_p2[0]),
                "p2_y": int(self.edited_p2[1]),
                "annoteur_approved": True,
                "cable_state": self.cable_state.get() or self.capture.get('cable_state', 'cable_good')
            }

            self.api_client.put(f"/admin/captures/{self.capture.get('id')}/annotate", payload)
            messagebox.showinfo("Success", "Annotation saved!")
            self.modal.destroy()
            if self.on_save_callback:
                self.on_save_callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")

    def show(self):
        """Show modal and wait"""
        self.modal.transient(self.parent)
        self.modal.grab_set()
        self.parent.wait_window(self.modal)

# ==================== ANNOTEUR APP (Interactive Point Editing) ====================
class AnnoteurInteractiveApp:
    """Interactive annotation interface where annoteurs can edit keypoints and label cable state"""

    def __init__(self, username: str, user_id: str, api_client: APIClient):
        self.username = username
        self.user_id = user_id
        self.api_client = api_client
        self.current_page = "annotation"

        # Create root window FIRST
        self.root = tk.Tk()
        self.root.title("Cable Annotation Studio")
        self.root.geometry("1400x900")
        self.root.configure(bg=BG)
        self.root.state('zoomed')

        # NOW create StringVar after root exists
        self.content_container = None

        # Initialize camera (like MainApp)
        self.cap = None
        self.pixel_measure = None
        self.camera_ok = False
        self.current_frame = None
        self.frame_count = 0
        self.last_zoom = 1.0
        self._loop_running = True
        self._init_camera()

        self._build_ui()

    def _build_ui(self):
        # Top header with branding and user info
        top = tk.Frame(self.root, bg=PANEL, height=58)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        tk.Label(top, text="Cable Annotation Studio", bg=PANEL, fg=TEXT, font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Frame(top, bg=PANEL).pack(fill=tk.X, expand=True)
        tk.Label(top, text=self.username, bg=PANEL, fg=TEXT, font=("Arial", 10)).pack(side=tk.LEFT, padx=10)

        quit_btn = tk.Button(top, text="LOGOUT", command=self._on_closing, bg=RED, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4)
        quit_btn.pack(side=tk.LEFT, padx=10)
        add_hover_effect(quit_btn, RED, RED, "#FFFFFF")

        # Navigation bar
        navbar = tk.Frame(self.root, bg=BORDER, height=50)
        navbar.pack(fill=tk.X, side=tk.TOP)
        navbar.pack_propagate(False)

        nav_items = [
            ("BELLMOUNTH CAPTURES", "annotation"),
            ("STATE CABLE", "statecable"),
            ("STATE CAPTURES", "state_captures"),
            ("NOTIFICATIONS", "notification"),
            ("RECLAMATIONS", "reclamation")
        ]

        for label, page_id in nav_items:
            btn = tk.Button(navbar, text=label, command=lambda p=page_id: self._switch_page(p),
                           bg=BORDER, fg=TEXT, font=("Arial", 10, "bold"),
                           relief=tk.FLAT, bd=0, padx=20, pady=10)
            btn.pack(side=tk.LEFT, padx=5)
            btn.page_id = page_id
            self._nav_buttons = getattr(self, '_nav_buttons', {})
            self._nav_buttons[page_id] = btn

        # Content container
        self.content_container = tk.Frame(self.root, bg=BG)
        self.content_container.pack(fill=tk.BOTH, expand=True)

        # Show initial page
        self._switch_page("annotation")

        # Start persistent camera loop after UI is built
        self._update_camera_loop()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _init_camera(self):
        """Initialize camera and SDK (like MainApp)"""
        self.camera_ok = False
        try:
            self.cap = get_camera()
            if self.cap is None or not self.cap.isOpened():
                print("Camera not available")
                return

            # Read first frame to get dimensions
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to read frame from camera")
                return

            self.camera_width = frame.shape[1]
            self.camera_height = frame.shape[0]
            self.pixel_measure = PixelMeasure(camera_width=self.camera_width)
            self.camera_ok = True
            print(f"Camera initialized: {self.camera_width}x{self.camera_height}")
        except Exception as e:
            print(f"Camera init error: {e}")

    def _update_camera_loop(self):
        """Persistent camera update loop (runs every 10ms)"""
        if self._loop_running and self.camera_ok:
            try:
                ret, frame = self.cap.read()
                if ret:
                    self.current_frame = frame
                    self.frame_count += 1

                    # Update SDK values every 10 frames
                    if self.frame_count % 10 == 0:
                        try:
                            self.pixel_measure.update()
                        except:
                            pass
            except Exception as e:
                print(f"Camera update error: {e}")

        # Schedule next update (10ms for ~100 FPS)
        if self._loop_running:
            self.root.after(10, self._update_camera_loop)

    def _switch_page(self, page_id):
        """Switch between different pages in the annoteur app"""
        self.current_page = page_id

        # Clear content container
        for widget in self.content_container.winfo_children():
            widget.destroy()

        # Update navbar button highlights
        if hasattr(self, '_nav_buttons'):
            for pid, btn in self._nav_buttons.items():
                if pid == page_id:
                    btn.config(bg=ACCENT, fg="#FFFFFF")
                else:
                    btn.config(bg=BORDER, fg=TEXT)

        # Show appropriate page
        if page_id == "annotation":
            self._show_annotation_page()
        elif page_id == "statecable":
            self._show_statecable_page()
        elif page_id == "state_captures":
            self._show_state_captures_page()
        elif page_id == "notification":
            self._show_notification_page()
        elif page_id == "reclamation":
            self._show_reclamation_page()

    def _show_annotation_page(self):
        """Display table of pending captures"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="BELLMOUNTH CAPTURES", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Table header
        header = tk.Frame(frame, bg=PANEL)
        header.pack(fill=tk.X, pady=(0, 10))

        cols = [("MACHINE", 15), ("DATE", 18), ("SWITCH", 15), ("STATE", 10), ("VIEW", 8), ("ACTION", 20)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        # Scrollable table content
        table_container = tk.Frame(frame, bg=BG)
        table_container.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(table_container, bg=BORDER)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        table_frame = tk.Frame(table_container, bg=BG)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_scroll = tk.Canvas(table_frame, bg=BG, highlightthickness=0, yscrollcommand=scrollbar.set)
        canvas_scroll.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas_scroll.yview)

        rows_frame = tk.Frame(canvas_scroll, bg=BG)
        canvas_scroll.create_window((0, 0), window=rows_frame, anchor="nw")

        try:
            # Get all captures (both pending and approved for review)
            response = self.api_client.get("/admin/captures")
            captures = response if isinstance(response, list) else []
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load captures: {str(e)}")
            captures = []

        # Populate table rows
        if captures:
            for i, capture in enumerate(captures):
                row = tk.Frame(rows_frame, bg=CARD, relief=tk.FLAT, bd=1)
                row.pack(fill=tk.X, pady=5)

                machine = capture.get('machine_name', 'N/A')
                date_str = ((capture.get('created_at') or 'N/A')[:10]) if capture.get('created_at') else 'N/A'
                switch = capture.get('switch_name', 'N/A')
                state = capture.get('cable_state', 'PENDING')
                state_color = GREEN if state == "cable_good" else AMBER if state == "cable_male" else RED

                # Columns
                tk.Label(row, text=machine, bg=CARD, fg=TEXT, font=("Arial", 9), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
                tk.Label(row, text=date_str, bg=CARD, fg=TEXT, font=("Arial", 9), width=18, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
                tk.Label(row, text=switch, bg=CARD, fg=TEXT, font=("Arial", 9), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                state_lbl = tk.Label(row, text=state.upper(), bg=state_color, fg="#FFFFFF", font=("Arial", 8, "bold"), width=10, anchor="center")
                state_lbl.pack(side=tk.LEFT, padx=10, pady=8)

                # View button
                view_btn = tk.Button(row, text="VIEW", command=lambda c=capture: self._open_capture_modal(c),
                                    bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"),
                                    relief=tk.FLAT, bd=0, padx=12, pady=4)
                view_btn.pack(side=tk.LEFT, padx=10, pady=8)
                add_hover_effect(view_btn, ACCENT, "#8B0F15", "#FFFFFF")

                # Action buttons frame
                action_frame = tk.Frame(row, bg=CARD)
                action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

                accept_btn = tk.Button(action_frame, text="✓ ACCEPT", command=lambda c=capture: self._accept_capture(c),
                                      bg=GREEN, fg="#FFFFFF", font=("Arial", 8, "bold"),
                                      relief=tk.FLAT, bd=0, padx=10, pady=4)
                accept_btn.pack(side=tk.LEFT, padx=3)
                add_hover_effect(accept_btn, GREEN, "#3E7C3F", "#FFFFFF")

                refuse_btn = tk.Button(action_frame, text="✗ REFUSE", command=lambda c=capture: self._refuse_capture(c),
                                      bg=RED, fg="#FFFFFF", font=("Arial", 8, "bold"),
                                      relief=tk.FLAT, bd=0, padx=10, pady=4)
                refuse_btn.pack(side=tk.LEFT, padx=3)
                add_hover_effect(refuse_btn, RED, "#8B0F15", "#FFFFFF")
        else:
            tk.Label(rows_frame, text="No pending captures", bg=BG, fg=TEXT2, font=("Arial", 11)).pack(pady=20)

        rows_frame.update_idletasks()
        canvas_scroll.config(scrollregion=canvas_scroll.bbox("all"))

    def _open_capture_modal(self, capture):
        """Open modal to view and edit capture"""
        modal = CaptureEditorModal(self.root, capture, self.api_client, self._refresh_annotation_page)
        modal.show()

    def _refresh_annotation_page(self):
        """Refresh the annotation page (callback from modal)"""
        self._show_annotation_page()

    def _accept_capture(self, capture):
        """Accept a capture"""
        result = messagebox.askyesno("Confirm", f"Accept capture from {capture.get('machine_name', 'Unknown')}?")
        if result:
            try:
                self.api_client.put(f"/admin/captures/{capture.get('id')}/annotate", {
                    "p1_x": int(capture.get('p1_x', 0)),
                    "p1_y": int(capture.get('p1_y', 0)),
                    "p2_x": int(capture.get('p2_x', 0)),
                    "p2_y": int(capture.get('p2_y', 0)),
                    "annoteur_approved": True,
                    "cable_state": capture.get('cable_state', 'cable_good')
                })
                messagebox.showinfo("Success", "Capture accepted")
                self._refresh_annotation_page()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to accept capture: {str(e)}")

    def _refuse_capture(self, capture):
        """Refuse a capture"""
        result = messagebox.askyesno("Confirm", f"Refuse capture from {capture.get('machine_name', 'Unknown')}?")
        if result:
            try:
                self.api_client.put(f"/admin/captures/{capture.get('id')}/reject", {})
                messagebox.showinfo("Success", "Capture refused")
                self._refresh_annotation_page()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to refuse capture: {str(e)}")

    def _show_statecable_page(self):
        """Display live camera feed with state selection and auto-capture"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="STATE CABLE", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Main layout: camera on left, sidebar on right
        main_container = tk.Frame(frame, bg=BG)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left: Camera feed
        left = tk.Frame(main_container, bg=BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        tk.Label(left, text="Live Camera Feed", bg=BG, fg=TEXT, font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))

        camera_canvas = tk.Canvas(left, bg=BORDER, width=700, height=600, cursor="crosshair")
        camera_canvas.pack(fill=tk.BOTH, expand=True)

        # Show error if no camera
        if not self.camera_ok:
            camera_canvas.create_text(350, 300, text="❌ Camera Not Available\nPlease check hardware",
                                     font=("Arial", 14), fill=TEXT2, justify=tk.CENTER)

        # Right: Sidebar controls
        right = tk.Frame(main_container, bg=PANEL, width=280)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)

        tk.Label(right, text="CAPTURE CONTROLS", bg=PANEL, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 20))

        # Zoom level display
        tk.Label(right, text="ZOOM LEVEL", bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 5))
        zoom_var = tk.StringVar(value="1.0x")
        zoom_lbl = tk.Label(right, textvariable=zoom_var, bg=BG, fg=ACCENT, font=("Arial", 24, "bold"), relief=tk.SUNKEN, bd=2)
        zoom_lbl.pack(anchor=tk.CENTER, padx=15, pady=(0, 20), ipady=10, fill=tk.X)

        # State dropdown
        tk.Label(right, text="CABLE STATE", bg=PANEL, fg=TEXT, font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 8))
        state_var = tk.StringVar(value="empty")
        state_menu = tk.OptionMenu(right, state_var, "empty", "bad cable", "correct cable")
        state_menu.config(bg=BG, fg=TEXT, font=("Arial", 10), relief=tk.FLAT, bd=0,
                         activebackground=BORDER, activeforeground=ACCENT, highlightthickness=0, width=25)
        state_menu.pack(fill=tk.X, padx=15, pady=(0, 20), ipady=6)

        tk.Frame(right, bg=BORDER, height=1).pack(fill=tk.X, pady=10, padx=15)

        # State for capture
        capture_var = tk.BooleanVar(value=False)
        captured_count_var = tk.IntVar(value=0)

        # Start capture button
        def toggle_capture():
            if not self.camera_ok:
                messagebox.showerror("Error", "Camera not available")
                return
            capture_var.set(not capture_var.get())
            btn_text = "⏸ STOP CAPTURE" if capture_var.get() else "▶ START CAPTURE"
            start_btn.config(text=btn_text, bg=RED if capture_var.get() else GREEN)
            status_lbl.config(text="Status: Capturing..." if capture_var.get() else "Status: Ready")

        start_btn = tk.Button(right, text="▶ START CAPTURE", command=toggle_capture,
                             bg=GREEN, fg="#FFFFFF", font=("Arial", 11, "bold"),
                             relief=tk.FLAT, bd=0, padx=20, pady=12)
        start_btn.pack(fill=tk.X, padx=15, pady=(0, 15))
        add_hover_effect(start_btn, GREEN, "#3E7C3F", "#FFFFFF")

        # Status label
        status_lbl = tk.Label(right, text="Status: Ready", bg=PANEL, fg=TEXT2, font=("Arial", 9), wraplength=240)
        status_lbl.pack(anchor=tk.W, padx=15, pady=(0, 20))

        # Captured count
        count_lbl = tk.Label(right, text="Captured: 0", bg=PANEL, fg=ACCENT, font=("Arial", 10, "bold"))
        count_lbl.pack(anchor=tk.W, padx=15)

        # Camera display update loop
        last_capture_time = [0]
        capture_interval = 3  # seconds
        display_loop_id = [None]  # Track loop ID for cleanup

        def display_camera_frame():
            """Display camera frame on canvas and capture every 3 seconds"""
            # Check if we're still on STATE CABLE page
            if self.current_page != "statecable":
                return

            if not self.camera_ok or self.current_frame is None:
                display_loop_id[0] = self.content_container.after(10, display_camera_frame)
                return

            try:
                # Check if canvas widget still exists
                if not camera_canvas.winfo_exists():
                    return

                # Use the persistent current_frame from the main loop
                frame_cv = self.current_frame.copy()

                # Resize frame to fit canvas
                frame_cv = cv2.resize(frame_cv, (700, 600))

                # Convert BGR to RGB for display
                frame_rgb = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(img_pil)

                # Display on canvas
                camera_canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                camera_canvas.image = photo  # Keep reference

                # Update zoom display from SDK
                try:
                    zoom, mpp = self.pixel_measure.get_values()
                    if zoom:
                        zoom_var.set(f"{zoom:.2f}x")
                except:
                    pass

                # Auto-capture every 3 seconds if enabled
                current_time = time.time()
                if capture_var.get() and (current_time - last_capture_time[0]) >= capture_interval:
                    last_capture_time[0] = current_time
                    captured_count_var.set(captured_count_var.get() + 1)
                    count_lbl.config(text=f"Captured: {captured_count_var.get()}")
                    # TODO: Save to database
                    try:
                        zoom_val, mpp_val = self.pixel_measure.get_values()
                        print(f"Captured image #{captured_count_var.get()} - State: {state_var.get()}, Zoom: {zoom_val:.2f}x")
                    except:
                        print(f"Captured image #{captured_count_var.get()} - State: {state_var.get()}")

            except Exception as e:
                pass  # Silently ignore errors when navigating away

            # Schedule next display update (10ms)
            display_loop_id[0] = self.content_container.after(10, display_camera_frame)

        # Start the display update loop
        display_camera_frame()

    def _show_state_captures_page(self):
        """Display table of captured state cable images"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="STATE CAPTURES", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Table header
        header = tk.Frame(frame, bg=PANEL)
        header.pack(fill=tk.X, pady=(0, 10))

        cols = [("NAME", 15), ("DATE", 18), ("VIEW", 8), ("STATE", 15), ("ZOOM", 8), ("ACTION", 20)]
        for col_name, width in cols:
            tk.Label(header, text=col_name, bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold"), width=width, anchor="w").pack(side=tk.LEFT, padx=10, pady=10)

        # Scrollable table content
        table_container = tk.Frame(frame, bg=BG)
        table_container.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(table_container, bg=BORDER)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        table_frame = tk.Frame(table_container, bg=BG)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas_scroll = tk.Canvas(table_frame, bg=BG, highlightthickness=0, yscrollcommand=scrollbar.set)
        canvas_scroll.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=canvas_scroll.yview)

        rows_frame = tk.Frame(canvas_scroll, bg=BG)
        canvas_scroll.create_window((0, 0), window=rows_frame, anchor="nw")

        # Sample data (would be loaded from API in production)
        sample_captures = [
            {"id": "cap_001", "date": "2026-06-08", "state": "correct cable", "zoom": "1.5x"},
            {"id": "cap_002", "date": "2026-06-08", "state": "bad cable", "zoom": "2.0x"},
            {"id": "cap_003", "date": "2026-06-08", "state": "empty", "zoom": "1.0x"},
        ]

        # Populate table rows
        if sample_captures:
            for capture in sample_captures:
                row = tk.Frame(rows_frame, bg=CARD, relief=tk.FLAT, bd=1)
                row.pack(fill=tk.X, pady=5)

                name = capture.get('id', 'N/A')
                date_str = capture.get('date', 'N/A')
                state = capture.get('state', 'empty')
                zoom = capture.get('zoom', '1.0x')
                state_color = GREEN if state == "correct cable" else RED if state == "bad cable" else AMBER

                # Columns
                tk.Label(row, text=name, bg=CARD, fg=TEXT, font=("Arial", 9), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
                tk.Label(row, text=date_str, bg=CARD, fg=TEXT, font=("Arial", 9), width=18, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                # View button
                view_btn = tk.Button(row, text="VIEW", command=lambda c=capture: messagebox.showinfo("View", f"Image: {c['id']}"),
                                    bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"),
                                    relief=tk.FLAT, bd=0, padx=8, pady=4)
                view_btn.pack(side=tk.LEFT, padx=10, pady=8)
                add_hover_effect(view_btn, ACCENT, "#8B0F15", "#FFFFFF")

                # State label
                state_lbl = tk.Label(row, text=state.upper(), bg=state_color, fg="#FFFFFF", font=("Arial", 8, "bold"), width=15, anchor="center")
                state_lbl.pack(side=tk.LEFT, padx=10, pady=8)

                # Zoom level
                tk.Label(row, text=zoom, bg=CARD, fg=TEXT, font=("Arial", 9), width=8, anchor="center").pack(side=tk.LEFT, padx=10, pady=8)

                # Action buttons frame
                action_frame = tk.Frame(row, bg=CARD)
                action_frame.pack(side=tk.RIGHT, padx=10, pady=8)

                accept_btn = tk.Button(action_frame, text="✓ ACCEPT", command=lambda c=capture: messagebox.showinfo("Accept", f"Accepted {c['id']}"),
                                      bg=GREEN, fg="#FFFFFF", font=("Arial", 8, "bold"),
                                      relief=tk.FLAT, bd=0, padx=10, pady=4)
                accept_btn.pack(side=tk.LEFT, padx=3)
                add_hover_effect(accept_btn, GREEN, "#3E7C3F", "#FFFFFF")

                refuse_btn = tk.Button(action_frame, text="✗ REFUSE", command=lambda c=capture: messagebox.showinfo("Refuse", f"Refused {c['id']}"),
                                      bg=RED, fg="#FFFFFF", font=("Arial", 8, "bold"),
                                      relief=tk.FLAT, bd=0, padx=10, pady=4)
                refuse_btn.pack(side=tk.LEFT, padx=3)
                add_hover_effect(refuse_btn, RED, "#8B0F15", "#FFFFFF")
        else:
            tk.Label(rows_frame, text="No captured state cables yet", bg=BG, fg=TEXT2, font=("Arial", 11)).pack(pady=20)

        rows_frame.update_idletasks()
        canvas_scroll.config(scrollregion=canvas_scroll.bbox("all"))

    def _show_notification_page(self):
        """Display the notifications page"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="NOTIFICATIONS", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))
        tk.Label(frame, text="View system notifications and alerts", bg=BG, fg=TEXT2, font=("Arial", 11)).pack(anchor=tk.W, pady=(0, 30))

        # Placeholder content
        info_frame = tk.Frame(frame, bg=PANEL, relief=tk.FLAT, bd=1)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(info_frame, text="🔔 Recent Notifications", bg=PANEL, fg=TEXT, font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 10))
        tk.Label(info_frame, text="No notifications at this time.",
                bg=PANEL, fg=TEXT2, font=("Arial", 10)).pack(anchor=tk.W, padx=15, pady=(0, 15))

    def _show_reclamation_page(self):
        """Display the reclamations form"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="RECLAMATIONS", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 10))
        tk.Label(frame, text="Report issues and problems", bg=BG, fg=TEXT2, font=("Arial", 11)).pack(anchor=tk.W, pady=(0, 20))

        # Form container
        form_frame = tk.Frame(frame, bg=PANEL, relief=tk.FLAT, bd=1)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Subject field
        tk.Label(form_frame, text="SUBJECT", bg=PANEL, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=15, pady=(15, 8))
        subject_entry = tk.Entry(form_frame, font=("Arial", 10), bg=BG, fg=TEXT,
                                insertbackground=ACCENT, relief=tk.FLAT, bd=0,
                                highlightthickness=2, highlightbackground=BORDER, highlightcolor=ACCENT)
        subject_entry.pack(fill=tk.X, padx=15, pady=(0, 15), ipady=8)

        # Problem type dropdown
        tk.Label(form_frame, text="TYPE OF PROBLEM", bg=PANEL, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 8))
        problem_type_var = tk.StringVar(value="-- Select Problem Type --")
        problem_types = ["-- Select Problem Type --", "Cable Measurement Error", "Image Quality", "System Crash", "Performance Issue", "Other"]
        problem_type_menu = tk.OptionMenu(form_frame, problem_type_var, *problem_types)
        problem_type_menu.config(bg=BG, fg=TEXT, font=("Arial", 10), relief=tk.FLAT, bd=0,
                                activebackground=BORDER, activeforeground=ACCENT, highlightthickness=0)
        problem_type_menu.pack(fill=tk.X, padx=15, pady=(0, 15), ipady=6)

        # Problem description
        tk.Label(form_frame, text="PROBLEM DESCRIPTION", bg=PANEL, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 8))
        problem_text = tk.Text(form_frame, font=("Arial", 10), bg=BG, fg=TEXT, insertbackground=ACCENT,
                              relief=tk.FLAT, bd=0, highlightthickness=2, highlightbackground=BORDER,
                              height=8, wrap=tk.WORD)
        problem_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 20), ipady=8)

        # Submit button
        def submit_reclamation():
            subject = subject_entry.get().strip()
            problem_type = problem_type_var.get()
            problem = problem_text.get("1.0", tk.END).strip()

            if not subject:
                messagebox.showwarning("Validation", "Please enter a subject")
                return
            if problem_type == "-- Select Problem Type --":
                messagebox.showwarning("Validation", "Please select a problem type")
                return
            if not problem:
                messagebox.showwarning("Validation", "Please describe the problem")
                return

            try:
                payload = {
                    "subject": subject,
                    "problem_type": problem_type,
                    "description": problem,
                    "user_id": self.user_id,
                    "created_at": datetime.now().isoformat()
                }
                self.api_client.post("/admin/reclamations", payload)
                messagebox.showinfo("Success", "Reclamation submitted successfully")
                subject_entry.delete(0, tk.END)
                problem_text.delete("1.0", tk.END)
                problem_type_var.set("-- Select Problem Type --")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to submit reclamation: {str(e)}")

        btn_frame = tk.Frame(form_frame, bg=PANEL)
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        submit_btn = tk.Button(btn_frame, text="✓ SUBMIT", command=submit_reclamation,
                              bg=GREEN, fg="#FFFFFF", font=("Arial", 11, "bold"),
                              relief=tk.FLAT, bd=0, padx=30, pady=10)
        submit_btn.pack(side=tk.LEFT)
        add_hover_effect(submit_btn, GREEN, "#3E7C3F", "#FFFFFF")

    def _on_closing(self):
        self._loop_running = False
        if self.cap:
            self.cap.release()
        self.root.destroy()

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
        machine_id = login_result.get("machine_id")

        # Route to appropriate UI based on role
        if role == "machine_user":
            app = MainApp(username, api_client, machine_id=machine_id)
            app.run()
        elif role == "annoteur":
            app = AnnoteurInteractiveApp(username, user_id, api_client)
            app.run()
        elif role == "admin":
            app = AdminApp(username, user_id, api_client)
            app.run()
        else:
            print(f"Unknown role: {role}")
    else:
        print("Login cancelled. Exiting.")
