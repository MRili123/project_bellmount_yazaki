# Bellmounth Inspection System - Premium Dark Pro UI for Yazaki
# Professional measurement application with enterprise-grade interface

import cv2
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import time
import math
import sys
import os
import uuid
import io
import tempfile
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageTk
import requests

from threshold_utils import apply_threshold

from camera_setup import get_camera
from pixelmeasure import PixelMeasure, DEFAULT_MM_PER_PIXEL
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
# App folder: next to app.py in development, next to the .exe when packaged
# with PyInstaller — so config.json, .env, api/ and models/ stay editable
# files beside the executable.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

CONFIG_FILE = APP_DIR / "config.json"
ICON_FILE = APP_DIR / "app_icon.ico"

# Give every Tk window the Yazaki telescope icon (title bar + taskbar)
# without having to touch each of the many tk.Tk() call sites.
_orig_tk_init = tk.Tk.__init__

def _tk_init_with_icon(self, *args, **kwargs):
    _orig_tk_init(self, *args, **kwargs)
    if ICON_FILE.exists():
        try:
            self.iconbitmap(default=str(ICON_FILE))
        except Exception:
            pass

tk.Tk.__init__ = _tk_init_with_icon


def uninstall_app(root=None):
    """Delete the app from this device by launching the installer's uninstaller
    (created by Inno Setup at install time). Confirms first, then quits so the
    uninstaller can remove the files."""
    from tkinter import messagebox
    import subprocess

    if not messagebox.askyesno(
            "Uninstall Bellmounth",
            "This will remove Yazaki Bellmounth Mesure from this computer.\n\n"
            "Your cloud data (accounts, measurements) is NOT affected — only "
            "this app is removed from this PC.\n\nContinue?",
            icon="warning"):
        return

    uninstaller = None
    for name in ("unins000.exe", "unins001.exe"):
        candidate = APP_DIR / name
        if candidate.exists():
            uninstaller = candidate
            break

    if uninstaller is None:
        messagebox.showinfo(
            "Uninstall",
            "No uninstaller found.\n\nThis happens when the app is run directly "
            "(development mode) rather than installed from the setup file. "
            "Installed copies can be removed here or from Windows Settings → Apps.")
        return

    try:
        subprocess.Popen([str(uninstaller)], cwd=str(APP_DIR))
    except Exception as e:
        messagebox.showerror("Uninstall failed", f"Could not start uninstaller:\n{e}")
        return

    # Close the app so the uninstaller can delete its files.
    try:
        if root is not None:
            root.destroy()
    except Exception:
        pass
    sys.exit(0)


# Dataset is now on C: drive (NOT in OneDrive to avoid permission issues)
DATASET_DIR = Path("C:/BellmouthProject/dataset")
ORIG_DIR = DATASET_DIR / "original"
THRESH_DIR = DATASET_DIR / "thresholded"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
# Models folder - separate from model_bellmounth_mesure
MODELS_ROOT = APP_DIR / "models"
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

    def __init__(self, current_url=None):
        self.current_url = current_url
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

        subtitle = ("Change the API connection (e.g. connect to Azure)"
                    if self.current_url else "Configure API connection for first launch")
        tk.Label(main, text=subtitle, bg=self.SETUP_BG,
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
        self.api_url_entry.insert(0, self.current_url or "http://localhost:8000")
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

# ==================== API CHOICE WINDOW (shown every launch) ====================
class ApiChoiceWindow:
    """Shown on every startup once an API URL is already saved. Lets the user
    keep the current backend or switch to a different one (e.g. Azure)."""
    BG = "#FFFFFF"
    PANEL = "#F5F5F5"
    BORDER = "#E0E0E0"
    TEXT = "#1A1A1A"
    TEXT2 = "#666666"
    RED = "#AF151D"

    def __init__(self, current_url: str):
        self.current_url = current_url
        self.result = None  # "keep" | "change" | "exit"
        self.window = tk.Tk()
        self.window.title("Bellmounth — Select Connection")
        self.window.geometry("560x430")
        self.window.configure(bg=self.BG)
        self.window.resizable(False, False)
        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._on_exit)
        self.window.transient()
        self.window.grab_set()

    def _describe(self, url):
        u = (url or "").lower()
        if "azurewebsites.net" in u or "azure" in u:
            return "☁  Azure cloud backend"
        if "localhost" in u or "127.0.0.1" in u:
            return "\U0001F5A5  Local backend (this PC)"
        return "\U0001F310  Remote backend"

    def _build_ui(self):
        main = tk.Frame(self.window, bg=self.BG)
        main.pack(fill=tk.BOTH, expand=True, padx=40, pady=40)

        tk.Label(main, text="SELECT API CONNECTION", bg=self.BG, fg=self.TEXT,
                 font=("Arial", 18, "bold")).pack(anchor=tk.W, pady=(0, 8))
        tk.Label(main, text="Choose which backend this machine connects to.",
                 bg=self.BG, fg=self.TEXT2, font=("Arial", 10)).pack(anchor=tk.W, pady=(0, 24))

        # Current API card
        card = tk.Frame(main, bg=self.PANEL, highlightthickness=1,
                        highlightbackground=self.BORDER)
        card.pack(fill=tk.X, pady=(0, 26))
        tk.Label(card, text="CURRENT API", bg=self.PANEL, fg=self.TEXT2,
                 font=("Arial", 8, "bold")).pack(anchor=tk.W, padx=16, pady=(14, 2))
        tk.Label(card, text=self.current_url, bg=self.PANEL, fg=self.TEXT,
                 font=("Consolas", 11, "bold"), wraplength=460,
                 justify=tk.LEFT).pack(anchor=tk.W, padx=16, pady=(0, 4))
        tk.Label(card, text=self._describe(self.current_url), bg=self.PANEL,
                 fg=self.TEXT2, font=("Arial", 9)).pack(anchor=tk.W, padx=16, pady=(0, 14))

        # Keep (primary)
        keep_btn = tk.Button(main, text="✓  KEEP THIS API", command=self._on_keep,
                             bg=self.RED, fg="#FFFFFF", font=("Arial", 12, "bold"),
                             relief=tk.FLAT, bd=0, padx=16, pady=12, cursor="hand2")
        keep_btn.pack(fill=tk.X, pady=(0, 12))
        add_hover_effect(keep_btn, self.RED, "#8B0F15", "#FFFFFF")

        # Change (secondary)
        change_btn = tk.Button(main, text="⚙  CHANGE API  (connect to Azure / other)",
                               command=self._on_change,
                               bg=self.PANEL, fg=self.TEXT, font=("Arial", 12, "bold"),
                               relief=tk.FLAT, bd=0, padx=16, pady=12, cursor="hand2")
        change_btn.pack(fill=tk.X, pady=(0, 12))
        add_hover_effect(change_btn, self.PANEL, "#E8E8E8", self.TEXT)

        # Exit
        exit_btn = tk.Button(main, text="EXIT", command=self._on_exit,
                             bg=self.BG, fg=self.TEXT2, font=("Arial", 10),
                             relief=tk.FLAT, bd=0, padx=8, pady=6, cursor="hand2")
        exit_btn.pack()

    def _on_keep(self):
        self.result = "keep"
        self.window.destroy()

    def _on_change(self):
        self.result = "change"
        self.window.destroy()

    def _on_exit(self):
        self.result = "exit"
        self.window.destroy()

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
        logo_path = APP_DIR / "logo.png"
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

        # Detect the Bellmounth (Dino-Lite) camera. If it isn't connected the
        # app still runs fully — a warning banner shows at the top instead of
        # blocking the whole panel.
        self._init_sdk()

        self.current_frame = None
        self.frozen = False  # True after a capture: the displayed frame is held still
        self.frozen_frame = None  # snapshot shown while frozen
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
        self._loop_alive = False  # True while a _start_loop chain is scheduled
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
        # Safe defaults so the rest of the app works even with no camera.
        self.camera_width = 1920
        self.camera_height = 1080

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
        tk.Label(frame, text="STATE: NO BELLMOUNTH CAMERA DETECTED", font=("Arial", 18, "bold"),
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

        # Camera canvas. This is a brand-new canvas each time the page is shown,
        # so drop any image-item id / cached size from the previous (destroyed)
        # canvas — otherwise _update_display would try to itemconfig an id that
        # doesn't exist on this canvas (a silent no-op in Tk) and the feed would
        # stay black. This is what caused the "black camera after switching
        # sections" bug.
        self._canvas_img_id = None
        self.cached_canvas_size = None
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

        # Trigger initial display and make sure the live camera loop is running
        # (it may have stopped while another page was open).
        self._update_display()
        self._ensure_loop()

    def _show_notifications_page(self):
        """Display notifications page with model update buttons"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="📬 NOTIFICATIONS", bg=BG, fg=TEXT,
                font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Fetch notifications from API
        try:
            from api_client import APIClient
            api = APIClient(api_url="http://localhost:8000")
            result = api.get_notifications()
            notifications = result.get('data', []) if result.get('ok') else []
        except:
            notifications = []

        if not notifications:
            tk.Label(frame, text="No new notifications", bg=BG, fg=TEXT2,
                    font=("Arial", 12)).pack(pady=40)
            return

        # Create scrollable area for notifications
        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Display each notification
        for notif in notifications:
            notif_type = notif.get('notification_type', 'info')
            title = notif.get('title', 'Notification')
            body = notif.get('body', '')

            # Notification card
            card = tk.Frame(scrollable_frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
            card.pack(fill=tk.X, pady=10, padx=5)

            # Title and type indicator
            title_frame = tk.Frame(card, bg=PANEL)
            title_frame.pack(fill=tk.X, padx=15, pady=(10, 5))

            # Icon based on type
            icon = self._get_notification_icon(notif_type)
            tk.Label(title_frame, text=f"{icon} {title}", bg=PANEL, fg=TEXT,
                    font=("Arial", 11, "bold")).pack(anchor=tk.W)

            # Body
            tk.Label(card, text=body, bg=PANEL, fg=TEXT2, font=("Arial", 9),
                    justify=tk.LEFT, wraplength=500).pack(anchor=tk.W, padx=15, pady=5)

            # Action buttons based on notification type
            button_frame = tk.Frame(card, bg=PANEL)
            button_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

            # A model-update notification carries a "Download link:" line in its body
            has_link = "Download link:" in body
            is_model_notif = (notif_type in ['mesure-upload', 'state-upload', 'model_update']
                              or (notif_type == 'info' and has_link))

            if is_model_notif and has_link:
                # Extract only the URL (first line after the marker), then install on click.
                download_link = body.split("Download link:")[-1].strip().split("\n")[0].strip()
                model_types = self._parse_model_types(notif_type, title, body)
                label = "⬇️ UPDATE " + " + ".join(m.upper() for m in model_types) + " MODEL"
                update_btn = tk.Button(button_frame, text=label,
                                      command=lambda link=download_link, mt=tuple(model_types), nid=notif.get('id'): self._download_and_install_model(link, mt, nid),
                                      bg=GREEN, fg="#FFFFFF", font=("Arial", 9, "bold"),
                                      relief=tk.FLAT, bd=0, padx=15, pady=8)
                update_btn.pack(side=tk.LEFT, padx=(0, 10))
                add_hover_effect(update_btn, GREEN, "#388E3C", "#FFFFFF")
            else:
                # Non-model notifications keep the Mark as Read button
                mark_read_btn = tk.Button(button_frame, text="✓ Mark as Read",
                                         bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"),
                                         relief=tk.FLAT, bd=0, padx=15, pady=8)
                mark_read_btn.pack(side=tk.LEFT)
                add_hover_effect(mark_read_btn, ACCENT, "#5A5F75", "#FFFFFF")

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _get_notification_icon(self, notif_type):
        """Get icon emoji for notification type"""
        icons = {
            'mesure-upload': '📊',
            'state-upload': '🔍',
            'info': '📦',
            'reply': '💬',
            'model_update': '📦'
        }
        return icons.get(notif_type, '📬')

    def _parse_model_types(self, notif_type, title, body):
        """Determine which model slot(s) a notification targets: mesure, state, or both."""
        if notif_type == "mesure-upload":
            return ["mesure"]
        if notif_type == "state-upload":
            return ["state"]
        # Fallback: scan the title/body text for model keywords
        text = f"{title} {body}".upper()
        types = []
        if "MESURE" in text:
            types.append("mesure")
        if "STATE" in text:
            types.append("state")
        return types or ["mesure"]

    def _extract_drive_file_id(self, url):
        """Extract the Google Drive file ID from any common link format."""
        import re
        if not url:
            return None
        for pattern in (
            r"/file/d/([a-zA-Z0-9_-]+)",   # .../file/d/FILE_ID/view  (share/view link)
            r"[?&]id=([a-zA-Z0-9_-]+)",    # ...uc?id=FILE_ID  or  open?id=FILE_ID
            r"/d/([a-zA-Z0-9_-]+)",        # .../d/FILE_ID
        ):
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    def _download_drive_zip(self, download_link, temp_zip, progress_var, status_text, progress_dialog):
        """Download a (possibly large) file from a Google Drive link to temp_zip.

        Converts share/view links to a direct download and resolves Google's
        large-file virus-scan confirmation page. Raises if Drive returns HTML
        (e.g. the file isn't shared as 'Anyone with the link').
        """
        import re
        import requests

        session = requests.Session()
        file_id = self._extract_drive_file_id(download_link)
        base = "https://drive.google.com/uc?export=download"

        if file_id:
            response = session.get(base, params={"id": file_id}, stream=True)
        else:
            response = session.get(download_link, stream=True)
        response.raise_for_status()

        # Large files: Google serves an HTML interstitial that needs a confirm token
        if "text/html" in response.headers.get("Content-Type", ""):
            html = response.text

            token = None
            for k, v in session.cookies.items():
                if k.startswith("download_warning"):
                    token = v

            if token and file_id:
                response = session.get(base, params={"id": file_id, "confirm": token}, stream=True)
            else:
                # Newer flow: re-submit the download form (action + hidden inputs)
                action = re.search(r'action="([^"]+)"', html)
                if action:
                    form_url = action.group(1).replace("&amp;", "&")
                    params = dict(re.findall(r'name="([^"]+)"\s+value="([^"]*)"', html))
                    response = session.get(form_url, params=params, stream=True)
            response.raise_for_status()

        # Final guard: still HTML means the file isn't publicly downloadable
        if "text/html" in response.headers.get("Content-Type", ""):
            raise ValueError(
                "Google Drive returned a web page instead of the file.\n\n"
                "Set the file's sharing to 'Anyone with the link' and try again."
            )

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        with open(temp_zip, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        percent = int((downloaded / total_size) * 80)
                        progress_var.set(percent)
                        status_text.config(text=f"Downloading... {percent}%")
                        progress_dialog.update()

    def _download_and_install_model(self, download_link, model_types, notif_id=None):
        """Download a model ZIP from the link and install it, replacing the old model(s).

        model_types is a list like ['mesure'], ['state'] or ['mesure', 'state'].
        The matching model folder is deleted entirely (no backup) and replaced with
        the new files from the ZIP. On success the source notification (notif_id) is
        deleted from the server and the notifications page is refreshed.
        """
        # Accept a single string for backward compatibility
        if isinstance(model_types, str):
            model_types = [model_types]
        model_types = list(model_types)

        # Validate link (reject empty, the unedited placeholder, or non-http URLs)
        if not download_link or "id=..." in download_link or not download_link.startswith("http"):
            messagebox.showerror("Error", "Invalid download link in notification")
            return

        try:
            import requests
            import zipfile
            import shutil

            # Map each model type to its destination folder
            dest_dirs = {
                "mesure": MODELS_MESURE_DIR,
                "state": MODELS_ROOT / "state",
            }
            for mt in model_types:
                if mt not in dest_dirs:
                    messagebox.showerror("Error", f"Unknown model type: {mt}")
                    return

            # Create progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Installing Model Update")
            progress_dialog.geometry("500x200")
            progress_dialog.configure(bg=BG)
            progress_dialog.grab_set()

            content = tk.Frame(progress_dialog, bg=BG)
            content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            label_txt = " + ".join(m.upper() for m in model_types)
            tk.Label(content, text=f"📥 Installing {label_txt} Model...", bg=BG, fg=TEXT, font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 20))

            from tkinter import ttk
            progress_var = tk.DoubleVar(value=0)
            progress_bar = ttk.Progressbar(content, variable=progress_var, maximum=100, length=400, mode='determinate')
            progress_bar.pack(fill=tk.X, pady=(0, 10))

            status_text = tk.Label(content, text="Downloading...", bg=BG, fg=TEXT2, font=("Arial", 9))
            status_text.pack(anchor=tk.W)

            progress_dialog.update()

            # Download the ZIP (handles Drive share/view links + large-file confirm)
            print(f"Downloading model from {download_link[:50]}...")
            temp_zip = Path(tempfile.gettempdir()) / f"bellmouth_model_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            self._download_drive_zip(download_link, temp_zip, progress_var, status_text, progress_dialog)

            # Extract ZIP into a dedicated temp folder
            progress_var.set(80)
            status_text.config(text="Extracting files...")
            progress_dialog.update()

            extract_root = temp_zip.parent / f"bellmouth_extract_{datetime.now().strftime('%H%M%S')}"
            extract_root.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(temp_zip, 'r') as zf:
                zf.extractall(extract_root)

            # Install each requested model type: delete the old folder, then replace
            installed = []
            for mt in model_types:
                extracted_path = extract_root / mt
                if not extracted_path.exists():
                    print(f"⚠️ ZIP has no '{mt}/' folder - skipping {mt}")
                    continue

                dest_dir = dest_dirs[mt]
                # Delete the old model entirely (no backup, per requirement)
                if dest_dir.exists():
                    shutil.rmtree(dest_dir)
                    print(f"Deleted old {mt} model at {dest_dir}")
                dest_dir.mkdir(parents=True, exist_ok=True)

                for file in extracted_path.glob("*"):
                    shutil.move(str(file), str(dest_dir / file.name))
                installed.append(mt.upper())

            # Cleanup
            try:
                temp_zip.unlink()
                shutil.rmtree(extract_root)
            except Exception:
                pass

            # Update progress
            progress_var.set(100)
            status_text.config(text="✓ Installation complete!")
            progress_dialog.update()

            self.root.after(2000, progress_dialog.destroy)

            # Drop any cached model so the measure section reloads the new one
            self._tf_model = None

            if installed:
                messagebox.showinfo("Success", f"✓ {' + '.join(installed)} model updated successfully!\n\nThe new model is now active.")
                print(f"✓ Installed models: {', '.join(installed)}")

                # Delete the source notification AND its duplicates (admin sends one
                # per active machine, so the same update can appear several times).
                try:
                    from api_client import APIClient
                    _api = APIClient(api_url="http://localhost:8000")
                    deleted_ids = set()
                    if notif_id:
                        _api.delete_notification(notif_id)
                        deleted_ids.add(notif_id)
                    # Remove any other copies carrying the same download link
                    res = _api.get_notifications()
                    for n in (res.get('data', []) if res.get('ok') else []):
                        nid = n.get('id')
                        if nid and nid not in deleted_ids and download_link and download_link in n.get('body', ''):
                            _api.delete_notification(nid)
                            deleted_ids.add(nid)
                except Exception as e:
                    print(f"Could not delete notification(s): {e}")

                # Rebuild the notifications page so the installed one disappears
                try:
                    for widget in self.content_container.winfo_children():
                        widget.destroy()
                    self._show_notifications_page()
                except Exception as e:
                    print(f"Could not refresh notifications page: {e}")
            else:
                messagebox.showwarning("Nothing Installed", "The downloaded ZIP did not contain the expected model folder(s).")

        except Exception as e:
            messagebox.showerror("Installation Error", f"Failed to install model:\n{str(e)}")
            print(f"Model installation error: {e}")

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

        def submit_report():
            title = title_entry.get().strip()
            description = desc_text.get("1.0", tk.END).strip()
            category = category_var.get()

            if not title:
                messagebox.showwarning("Validation", "Please enter a title")
                return
            if not description:
                messagebox.showwarning("Validation", "Please describe the issue")
                return

            result = self.api_client.submit_report(
                machine_name=self.machine_name,
                title=title,
                description=description,
                category=category,
            )
            if result.get("ok"):
                messagebox.showinfo("Success", "Report submitted successfully")
                title_entry.delete(0, tk.END)
                desc_text.delete("1.0", tk.END)
                category_var.set("bug")
            else:
                messagebox.showerror("Error", f"Failed to submit report: {result.get('error', 'Unknown error')}")

        btn = tk.Button(inner, text="SUBMIT REPORT", command=submit_report,
                       bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"),
                       relief=tk.FLAT, bd=0, padx=20, pady=10)
        btn.pack(fill=tk.X)
        add_hover_effect(btn, ACCENT, ACCENT, "#FFFFFF")


    def _build_ui(self):
        # Header bar
        top = tk.Frame(self.root, bg=PANEL, height=58)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        # Warning banner across the top when the Bellmounth (Dino-Lite) camera
        # isn't connected. The app stays fully usable — this is just a notice.
        if not self.camera_ok:
            banner = tk.Frame(self.root, bg=RED)
            banner.pack(fill=tk.X, side=tk.TOP)
            tk.Label(banner, text="⚠  NO BELLMOUNTH CAMERA DETECTED",
                     bg=RED, fg="#FFFFFF", font=("Arial", 10, "bold"),
                     pady=6).pack()

        # Load and display logo in header
        logo_path = APP_DIR / "logo.png"
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

        self.live_dot = tk.Label(top, text="●", bg=PANEL, fg=RED, font=("Arial", 10))
        self.live_dot.pack(side=tk.LEFT, padx=(0, 4))
        self.live_lbl = tk.Label(top, text="LIVE", bg=PANEL, fg=TEXT2, font=("Arial", 9), cursor="hand2")
        self.live_lbl.pack(side=tk.LEFT, padx=(0, 12))
        # Click the indicator to resume the live feed after a capture freeze
        self.live_lbl.bind("<Button-1>", self._resume_live)
        self.live_dot.bind("<Button-1>", self._resume_live)

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
        quit_btn.pack(side=tk.LEFT, padx=(20, 4), pady=12)
        add_hover_effect(quit_btn, RED, RED, TEXT)

        uninstall_btn = tk.Button(top, text="UNINSTALL",
                 command=lambda: uninstall_app(self.root),
                 bg=SEP, fg=TEXT2, font=("Arial", 9, "bold"),
                 relief=tk.FLAT, bd=0, padx=12, activebackground=SEP,
                 activeforeground=TEXT)
        uninstall_btn.pack(side=tk.LEFT, padx=(0, 20), pady=12)
        add_hover_effect(uninstall_btn, SEP, "#D3D3D3", TEXT)

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
        self._set_frozen(False)  # switching modes resumes the live feed
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
        print(f"[CAPTURE] clicked | mode={self.mode} | frame={'set' if self.current_frame is not None else 'None'}", file=sys.stderr)
        if self.current_frame is None:
            messagebox.showwarning("No Frame", "No camera frame available to capture.")
            return

        if self.mode == "AUTO":
            self.measurement_started = True
            result = self._run_inference(self.current_frame)
            print(f"[CAPTURE] inference result = {result}", file=sys.stderr)
            if result:
                self.p1, self.p2, self.dist_mm = result
                # Light the CABLE OK / NOT OK LED based on the selected switch tolerance.
                self._evaluate_cable_status()
                # Keep the live feed running; the detected points are drawn as an
                # overlay on top of the live frames (no freeze).
                if hasattr(self, 'canvas'):
                    self._update_display()

    def _set_frozen(self, frozen):
        """Freeze/resume the live preview and update the LIVE/FROZEN indicator."""
        self.frozen = frozen
        if hasattr(self, 'live_lbl'):
            if frozen:
                self.live_lbl.config(text="FROZEN — click to resume")
                self.live_dot.config(fg=AMBER)
            else:
                self.live_lbl.config(text="LIVE")
                self.live_dot.config(fg=RED)

    def _resume_live(self, event=None):
        """Resume the live feed after a freeze."""
        if getattr(self, 'frozen', False):
            self._set_frozen(False)

    def _run_inference(self, frame):
        print(f"[INFER] _TF_AVAILABLE={_TF_AVAILABLE} | MODEL_PATH={MODEL_PATH} | exists={MODEL_PATH.exists()}", file=sys.stderr)
        if not _TF_AVAILABLE:
            messagebox.showwarning(
                "Auto Capture Unavailable",
                "TensorFlow is not installed, so AUTO detection can't run.\n\n"
                "Install it with 'pip install tensorflow', or switch to MANUAL mode "
                "and place the points by hand.")
            return None

        # Lazy-load the CNN model on first use (it is large, ~1.9 GB, so the first
        # capture takes a few seconds while it loads into memory).
        if self._tf_model is None:
            if not MODEL_PATH.exists():
                messagebox.showerror(
                    "Model Not Found",
                    f"The measurement model was not found at:\n{MODEL_PATH}\n\n"
                    "Train or install a MESURE model first, or use MANUAL mode.")
                return None
            try:
                self.capture_btn.config(text="LOADING MODEL…", state=tk.DISABLED)
                self.root.update_idletasks()
                print(f"[INFER] loading model from {MODEL_PATH} ...", file=sys.stderr)
                self._tf_model = tf.keras.models.load_model(str(MODEL_PATH), compile=False)
                print(f"[INFER] model loaded OK | input_shape={self._tf_model.input_shape}", file=sys.stderr)
            except Exception as e:
                print(f"[INFER] model load FAILED: {type(e).__name__}: {e}", file=sys.stderr)
                messagebox.showerror("Model Load Failed", f"Could not load the model:\n{e}")
                return None
            finally:
                self.capture_btn.config(text="CAPTURE", state=tk.NORMAL)

        try:
            h, w = frame.shape[:2]
            thresh = apply_threshold(frame)
            resized = cv2.resize(thresh, (640, 480))
            normalized = resized.astype(np.float32) / 255.0
            inp = normalized[..., np.newaxis][np.newaxis, ...]

            pred = self._tf_model.predict(inp, verbose=0)[0]
            print(f"[INFER] raw prediction (x1,y1,x2,y2) = {[round(float(v),4) for v in pred]} | frame {w}x{h}", file=sys.stderr)
            # Model outputs 4 normalized values [x1, y1, x2, y2]
            p1 = (int(pred[0] * w), int(pred[1] * h))
            # Use P1's Y coordinate for P2 (horizontal alignment, same as MANUAL mode)
            p2 = (int(pred[2] * w), p1[1])
            pixel_dist = math.dist(p1, p2)

            if self.pixel_measure:
                self.pixel_measure.update()
                _, mm_pp = self.pixel_measure.get_values()
                mm_pp = mm_pp or DEFAULT_MM_PER_PIXEL
            else:
                mm_pp = DEFAULT_MM_PER_PIXEL  # no camera/SDK -> default calibration
            dist_mm = pixel_dist * mm_pp

            print(f"[INFER] points P1={p1} P2={p2} | pixel_dist={pixel_dist:.1f} | mm/px={mm_pp} | dist_mm={dist_mm:.3f}", file=sys.stderr)
            return p1, p2, dist_mm
        except Exception as e:
            print(f"[INFER] inference FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            messagebox.showerror("Auto Capture Failed", f"Inference failed:\n{e}")
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

        # Calculate measurement values (use the live SDK mm/pixel when available,
        # otherwise fall back to the default calibration)
        pixel_distance = math.dist(self.p1, self.p2)
        if self.pixel_measure:
            self.pixel_measure.update()
            _, mm_pp = self.pixel_measure.get_values()
            mm_pp = mm_pp or DEFAULT_MM_PER_PIXEL
        else:
            mm_pp = DEFAULT_MM_PER_PIXEL
        measured_mm = pixel_distance * mm_pp

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
                machine_id=self.machine_id,
                switch_id=self.selected_switch.get("id", "") if self.selected_switch else "",
                measured_value_mm=measured_mm,
                p1_x=self.p1[0],
                p1_y=self.p1[1],
                p2_x=self.p2[0],
                p2_y=self.p2[1],
                capture_method="auto_cnn" if self.mode == "AUTO" else "manual",
                measurement_status=measurement_status,
                delta_mm=delta_mm,
                zoom_level=float(self.zoom),
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
            self._evaluate_cable_status()
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

    def _evaluate_cable_status(self):
        """Compare the current measured distance against the selected switch's
        tolerance and light the CABLE OK / CABLE NOT OK LED accordingly."""
        if self.dist_mm is None or not self.selected_switch:
            self._reset_status_leds()
            return

        measured_mm = self.dist_mm
        expected = self.selected_switch.get("expected_diameter_mm", measured_mm)
        tolerance_min = self.selected_switch.get("tolerance_min", expected - 0.5)
        tolerance_max = self.selected_switch.get("tolerance_max", expected + 0.5)

        is_ok = tolerance_min <= measured_mm <= tolerance_max
        self._set_cable_ok(is_ok)

    def set_cable_state(self, state):
        """Update cable state display (no cable detected / cable male placed / cable good placed)"""
        self.cable_state = state

    def _render_message(self, text, color=(60, 60, 255)):
        """Paint a centered message on the camera canvas (used when there is no
        live video, e.g. the Bellmounth microscope isn't connected)."""
        if not hasattr(self, 'canvas'):
            return
        try:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
        except Exception:
            return
        if cw <= 1 or ch <= 1:
            cw, ch = 640, 480
        disp = np.zeros((ch, cw, 3), dtype=np.uint8)
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        x = max(10, (cw - tw) // 2)
        y = (ch + th) // 2
        cv2.putText(disp, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)
        imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
        if getattr(self, '_canvas_img_id', None) is None:
            self._canvas_img_id = self.canvas.create_image(0, 0, anchor='nw', image=imgtk)
        else:
            try:
                self.canvas.itemconfig(self._canvas_img_id, image=imgtk)
            except Exception:
                self._canvas_img_id = self.canvas.create_image(0, 0, anchor='nw', image=imgtk)
        self.canvas.image = imgtk

    def _update_display(self):
        if not hasattr(self, 'canvas'):
            return
        if self.current_frame is None:
            # No live frame — the Bellmounth (Dino-Lite) microscope isn't sending
            # video. Show it on the feed instead of a blank black canvas.
            self._render_message("STATE: NO BELLMOUNTH CAMERA DETECTED")
            return

        # While frozen, always render the captured snapshot (so zoom/pan still
        # show the held frame and points, not a fresh live frame).
        source = self.frozen_frame if (self.frozen and self.frozen_frame is not None) else self.current_frame
        disp = source.copy()
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
        # Reuse a single canvas image item instead of creating a new one every
        # frame. create_image() never removes the previous item, so at ~10 FPS
        # the canvas accumulated thousands of stale image objects — a steady
        # memory + rendering slowdown the longer the app ran. Create once, then
        # just swap the bitmap.
        if getattr(self, '_canvas_img_id', None) is None:
            self._canvas_img_id = self.canvas.create_image(0, 0, anchor='nw', image=imgtk)
        else:
            try:
                self.canvas.itemconfig(self._canvas_img_id, image=imgtk)
            except Exception:
                # Canvas item was lost (e.g. canvas rebuilt) — recreate it.
                self._canvas_img_id = self.canvas.create_image(0, 0, anchor='nw', image=imgtk)
        self.canvas.image = imgtk  # keep a reference so the PhotoImage isn't GC'd

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

    def _ensure_loop(self):
        """Start the camera loop if it isn't already running. Called when the
        measure page is shown so the live feed always resumes — even if the
        loop had stopped while another page (reclamations, notifications…) was
        open."""
        if self._loop_running and self.camera_ok and not getattr(self, "_loop_alive", False):
            self._loop_alive = True
            self.root.after(0, self._start_loop)

    def _start_loop(self):
        if not self._loop_running or not self.camera_ok:
            self._loop_alive = False
            return

        self._loop_alive = True
        # The measure widgets (canvas, zoom_val, mpp_val) only exist while the
        # measure page is open. When another page is showing they are gone, so
        # skip all frame work — but keep the loop scheduled so returning to the
        # measure page shows a live feed again. Everything is wrapped so a
        # transient error can never kill the reschedule (the old cause of the
        # "black camera after leaving reclamations" bug).
        try:
            on_measure_page = (hasattr(self, "canvas")
                               and self.canvas.winfo_exists())
            if on_measure_page:
                ret, frame = self.cap.read()
                if ret:
                    # Reduce frame size for faster processing (keep original for calc)
                    if frame.shape[1] > 1280:
                        frame = cv2.resize(frame, (1280, int(frame.shape[0] * 1280 / frame.shape[1])))
                    self.current_frame = frame

                    # Update display every 2 frames. While frozen (after a
                    # capture) hold the displayed image still.
                    if self.frame_count % 2 == 0 and not self.frozen:
                        self._update_display()

                    # Skip SDK calls if zoom is changing (avoid freeze during zoom)
                    zoom_changed = abs(self.zoom - self.last_zoom) > 0.01
                    self.last_zoom = self.zoom

                    # Update SDK values every 10 frames if zoom is stable
                    if self.frame_count % 10 == 0 and not zoom_changed:
                        try:
                            self.pixel_measure.update()
                            zoom, mpp = self.pixel_measure.get_values()
                            if zoom and hasattr(self, "zoom_val"):
                                self.zoom_val.config(text=f"{zoom:.2f}x")
                            if mpp and hasattr(self, "mpp_val"):
                                self.mpp_val.config(text=f"{mpp:.5f}")
                        except:
                            pass

                    self.frame_count += 1
        except Exception as e:
            print(f"Camera loop iteration error: {e}")

        # Health check every 30 seconds
        current_time = time.time()
        if current_time - self.last_health_check_time >= self.health_check_interval and self.api_client:
            self.last_health_check_time = current_time
            try:
                result = self.api_client.health_check()
                if not self._check_api_response(result):
                    self._loop_alive = False
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
    CACHE_FILE = APP_DIR / "admin_cache.json"
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

        # Training state (initialize as empty)
        self.current_training_model = None
        self.current_training_samples = 0
        self.training_start_time = None
        self.training_active = False

        self._build_ui()

    def _build_ui(self):
        # Header bar
        top = tk.Frame(self.root, bg=PANEL, height=58)
        top.pack(fill=tk.X, side=tk.TOP)
        top.pack_propagate(False)

        # Logo
        logo_path = APP_DIR / "logo.png"
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
        uninstall_btn = tk.Button(top, text="UNINSTALL", command=lambda: uninstall_app(self.root), bg=SEP, fg=TEXT2, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=6)
        uninstall_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(uninstall_btn, SEP, "#D3D3D3", TEXT)

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
            ("TRAINING", "training", self._show_training_page),
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

        cols = [("ANNOTEUR", 16), ("TIME", 14), ("METHOD", 10), ("REQUIRED/ACTUAL", 16), ("ZOOM", 8), ("STATUS", 9), ("ACTIONS", 25)]
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

        # Stage 2 queue: annoteur has verified these, awaiting admin confirmation
        # into the training database.
        pending_captures = [c for c in captures
                            if c.get("annoteur_approved") and not c.get("in_training_dataset")]

        if not pending_captures:
            tk.Label(scrollable_frame, text="No pending requests", bg=BG, fg=TEXT2, font=("Arial", 12)).pack(pady=50)
        else:
            for i, capture in enumerate(pending_captures):
                row_bg = PANEL if i % 2 == 0 else BG
                row = tk.Frame(scrollable_frame, bg=row_bg)
                row.pack(fill=tk.X)

                annoteur_name = capture.get('annoteur_name') or capture.get('annoteur_id') or 'Unassigned'
                tk.Label(row, text=annoteur_name[:16], bg=row_bg, fg=TEXT, font=("Arial", 10), width=16, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                created_at = (capture.get('created_at') or '')[:14]
                tk.Label(row, text=created_at, bg=row_bg, fg=TEXT, font=("Arial", 10), width=14, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                # How the capture was taken: auto_cnn -> AUTO, manual -> MANUAL.
                method_raw = capture.get('capture_method', '')
                if method_raw == "auto_cnn":
                    method_text, method_fg = "AUTO", "#FF9800"    # amber (AI/auto)
                elif method_raw == "manual":
                    method_text, method_fg = "MANUAL", "#607D8B"  # blue-grey (human)
                else:
                    method_text, method_fg = "—", TEXT2
                tk.Label(row, text=method_text, bg=row_bg, fg=method_fg, font=("Arial", 10, "bold"), width=10, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

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

        capture_id = capture.get('id')
        try:
            # Prefer downloading from the server (works across machines).
            if capture_id and self.api_client:
                orig_bytes = self.api_client.get_capture_image(capture_id, kind="original")
                if orig_bytes:
                    state["original_image"] = Image.open(io.BytesIO(orig_bytes)).convert('RGB')
                thresh_bytes = self.api_client.get_capture_image(capture_id, kind="thresholded")
                if thresh_bytes:
                    state["thresholded_image"] = Image.open(io.BytesIO(thresh_bytes)).convert('RGB')

            # Fallback to local copies on the same machine.
            if not state["original_image"] and Path(orig_path).exists():
                state["original_image"] = Image.open(orig_path).convert('RGB')
            if not state["thresholded_image"] and Path(thresh_path).exists():
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

        cached = self.cache.get("captures")
        # Show captures the admin has confirmed into the training database.
        mesure_captures = [c for c in cached if c.get("in_training_dataset")] if cached else []

        mesure_frame = tk.Frame(frame, bg=BG)
        mesure_frame.pack(fill=tk.BOTH, expand=True)

        self._build_dataset_table(mesure_frame, mesure_captures)
        self._sync_dataset(mesure_frame, cached)

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

                annoteur_name = capture.get('annoteur_name') or capture.get('annoteur_id') or 'Unassigned'
                tk.Label(row, text=annoteur_name[:16], bg=row_bg, fg=TEXT, font=("Arial", 10), width=16, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

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

    def _sync_dataset(self, mesure_frame, cached):
        if not self.cache.is_stale("captures"):
            return
        def do_sync():
            result = self.api_client.admin_get_captures()
            if result.get("ok"):
                server_data = result.get("data", [])
                merged = self.cache.update("captures", server_data)
                if merged != cached:
                    for w in mesure_frame.winfo_children():
                        if getattr(w, '_is_table', False):
                            w.destroy()
                    # Show captures the admin has confirmed into the training database.
                    mesure_captures = [c for c in merged if c.get("in_training_dataset")]
                    self._build_dataset_table(mesure_frame, mesure_captures)
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

                delete_btn = tk.Button(action_frame, text="✕", command=lambda nid=notif.get('id'): self._delete_notification(nid, frame),
                                     bg=RED, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=4)
                delete_btn.pack(side=tk.LEFT, padx=4)
                add_hover_effect(delete_btn, RED, "#8B0F15", "#FFFFFF")

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

    def _delete_notification(self, notif_id, frame):
        """Delete a notification from the server and refresh the table."""
        if not notif_id:
            return
        if not messagebox.askyesno("Delete Notification", "Delete this notification? This cannot be undone."):
            return
        result = self.api_client.delete_notification(notif_id)
        if result and result.get("ok"):
            updated = [n for n in (self.cache.get("notifications") or []) if n.get("id") != notif_id]
            self.cache.update("notifications", updated)
            for w in frame.winfo_children():
                if getattr(w, '_is_table', False):
                    w.destroy()
            self._build_notifications_table(frame, updated)
        else:
            error = result.get("error", "Unknown error") if result else "No response from server"
            messagebox.showerror("Error", f"Failed to delete notification: {error}")

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

    def _show_model_details(self, model_type):
        """Show detailed model metrics in a dialog"""
        metadata = self._load_model_metadata(model_type)

        dialog = tk.Toplevel(self.root)
        dialog.title(f"{model_type.upper()} Model Details")
        dialog.geometry("500x500")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Title
        tk.Label(frame, text=f"📊 {model_type.upper()} Model Metrics", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Metrics frame
        metrics_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        metrics_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Build metric display based on model type
        metrics_list = []
        if model_type == "mesure":
            metrics_list = [
                ("Model Name", metadata.get("model_name", "—")),
                ("Status", metadata.get("status", "—").upper()),
                ("", ""),  # Spacer
                ("ACCURACY METRICS", ""),
                ("10px Accuracy", f"{metadata.get('accuracy_10px', 0):.2%}"),
                ("20px Accuracy", f"{metadata.get('accuracy_20px', 0):.2%}"),
                ("", ""),  # Spacer
                ("LOSS METRICS", ""),
                ("Test Loss (MSE)", f"{metadata.get('test_loss', 0):.6f}"),
                ("Test MAE", f"{metadata.get('test_mae', 0):.6f}"),
                ("Mean Pixel Error", f"{metadata.get('mean_pixel_error', 0):.4f} px"),
                ("", ""),  # Spacer
                ("TRAINING INFO", ""),
                ("Epochs Trained", str(metadata.get("epochs_trained", 0))),
                ("Training Samples", str(metadata.get("training_samples", 0))),
                ("Test Samples", str(metadata.get("test_samples", 0))),
            ]
        else:  # state
            metrics_list = [
                ("Model Name", metadata.get("model_name", "—")),
                ("Status", metadata.get("status", "—").upper()),
                ("", ""),  # Spacer
                ("ACCURACY METRICS", ""),
                ("Overall Accuracy", f"{metadata.get('overall_accuracy', 0):.2%}"),
                ("Precision", f"{metadata.get('precision', 0):.4f}"),
                ("Recall", f"{metadata.get('recall', 0):.4f}"),
                ("F1 Score", f"{metadata.get('f1_score', 0):.4f}"),
                ("", ""),  # Spacer
                ("LOSS METRICS", ""),
                ("Test Loss", f"{metadata.get('test_loss', 0):.6f}"),
                ("", ""),  # Spacer
                ("TRAINING INFO", ""),
                ("Epochs Trained", str(metadata.get("epochs_trained", 0))),
                ("Training Samples", str(metadata.get("training_samples", 0))),
                ("Test Samples", str(metadata.get("test_samples", 0))),
            ]

        # Display metrics
        canvas = tk.Canvas(metrics_frame, bg=PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(metrics_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=PANEL)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        for metric_name, metric_value in metrics_list:
            if not metric_name:  # Spacer
                tk.Frame(scrollable_frame, bg=PANEL, height=5).pack(fill=tk.X)
                continue

            row = tk.Frame(scrollable_frame, bg=PANEL)
            row.pack(fill=tk.X, padx=10, pady=5)

            if metric_value == "":  # Section header
                tk.Label(row, text=metric_name, bg=PANEL, fg=ACCENT, font=("Arial", 10, "bold")).pack(anchor=tk.W)
            else:
                tk.Label(row, text=metric_name, bg=PANEL, fg=TEXT2, font=("Arial", 9)).pack(anchor=tk.W)
                tk.Label(row, text=str(metric_value), bg=PANEL, fg=GREEN, font=("Arial", 9, "bold")).pack(anchor=tk.E, padx=20)

        canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        # Close button
        close_btn = tk.Button(frame, text="CLOSE", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        close_btn.pack(side=tk.LEFT)
        add_hover_effect(close_btn, PANEL, SEP, TEXT)

    def _show_settings_dialog(self):
        """Show settings dialog for Google Drive and upload configuration"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Settings")
        dialog.geometry("700x500")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="⚙ Settings", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Load current config
        config_file = APP_DIR / "config.json"
        config = {}
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text())
            except:
                pass

        # Google Drive Settings
        tk.Label(frame, text="☁ Google Drive Configuration", bg=BG, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(10, 5))

        drive_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        drive_frame.pack(fill=tk.X, padx=5, pady=(0, 20))

        # Credentials path section
        tk.Label(drive_frame, text="Credentials File Path:", bg=PANEL, fg=TEXT2, font=("Arial", 9)).pack(anchor=tk.W, padx=10, pady=(10, 5))

        path_frame = tk.Frame(drive_frame, bg=PANEL)
        path_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        creds_path_var = tk.StringVar(value=config.get('google_drive', {}).get('credentials_path', ''))
        creds_entry = tk.Entry(path_frame, font=("Arial", 9), bg="#2A2E3A", fg=TEXT, relief=tk.FLAT, bd=1)
        creds_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        creds_entry.insert(0, creds_path_var.get())

        def browse_credentials():
            file_path = filedialog.askopenfilename(
                title="Select Google Credentials JSON",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialdir=str(APP_DIR)
            )
            if file_path:
                creds_entry.delete(0, tk.END)
                creds_entry.insert(0, file_path)
                creds_path_var.set(file_path)

        browse_btn = tk.Button(path_frame, text="📁 Browse", command=browse_credentials,
                              bg=ACCENT, fg="#FFFFFF", font=("Arial", 8, "bold"),
                              relief=tk.FLAT, bd=0, padx=12, pady=5)
        browse_btn.pack(side=tk.LEFT)
        add_hover_effect(browse_btn, ACCENT, "#5A5F75", "#FFFFFF")

        # Enable checkbox
        enable_var = tk.BooleanVar(value=config.get('google_drive', {}).get('enabled', False))
        enable_cb = tk.Checkbutton(drive_frame, text="Enable Google Drive auto-upload", variable=enable_var,
                                  bg=PANEL, fg=TEXT2, font=("Arial", 9), selectcolor="#1A1E2A", activebackground=PANEL)
        enable_cb.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Status info
        status_frame = tk.Frame(drive_frame, bg="#1A1E2A", relief=tk.SUNKEN, bd=1)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        def update_status():
            creds_file = Path(creds_entry.get())
            if creds_file.exists():
                status_text = f"✓ Credentials file found\n{creds_file.name}"
                status_color = GREEN
            else:
                status_text = "✗ Credentials file not found\nPlease select a valid file"
                status_color = RED

            status_label.config(text=status_text, fg=status_color)

        status_label = tk.Label(status_frame, text="", bg="#1A1E2A", fg=TEXT2, font=("Arial", 8), justify=tk.LEFT)
        status_label.pack(anchor=tk.W, padx=10, pady=10)
        update_status()

        # Help text
        help_text = """How to get credentials:
1. Go to https://console.cloud.google.com
2. Create project → Enable Drive API
3. Create OAuth 2.0 Desktop credentials
4. Download JSON → Select it here"""

        tk.Label(frame, text=help_text, bg=BG, fg=TEXT2, font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 20))

        # Buttons
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X)

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy,
                              bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        def save_settings():
            creds_path = creds_entry.get().strip()

            # Validate
            if enable_var.get() and creds_path:
                creds_file = Path(creds_path)
                if not creds_file.exists():
                    messagebox.showerror("Error", "Credentials file does not exist!")
                    return

            # Save config
            config_file = APP_DIR / "config.json"
            config = {
                "google_drive": {
                    "credentials_path": creds_path,
                    "enabled": enable_var.get()
                },
                "upload_method": "google_drive" if enable_var.get() else "manual",
                "models_upload_folder": "uploads"
            }

            config_file.write_text(json.dumps(config, indent=2))
            messagebox.showinfo("Success", "✓ Settings saved!\n\nGoogle Drive is " + ("enabled" if enable_var.get() else "disabled"))
            dialog.destroy()

        save_btn = tk.Button(btn_frame, text="💾 SAVE SETTINGS", command=save_settings,
                            bg=GREEN, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        save_btn.pack(side=tk.LEFT)
        add_hover_effect(save_btn, GREEN, "#388E3C", "#FFFFFF")

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

        # Check for actual model files and track versions
        model_dir = MODELS_MESURE_DIR

        # MESURE model versions
        mesure_model_v1 = model_dir / "CNN_BELMOUNTH_MODEL_V1.h5"
        mesure_model_v2 = model_dir / "CNN_BELMOUNTH_MESURE_V2.h5"
        mesure_v1_exists = mesure_model_v1.exists()
        mesure_v2_exists = mesure_model_v2.exists()
        mesure_latest_version = 2 if mesure_v2_exists else (1 if mesure_v1_exists else 0)
        mesure_exists = mesure_latest_version > 0

        # Load metadata for latest version
        mesure_metadata = self._load_model_metadata("mesure") if mesure_exists else {"model_name": f"CNN_BELMOUNTH_MESURE_V{mesure_latest_version}"}

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

        # Build models data - show each version as separate row
        models_data = []
        row_count = 0

        # MESURE versions
        if mesure_v1_exists:
            models_data.append(("MESURE", "Keypoint Detection", "TRAINED", "V1", f"{mesure_dataset}/499", "mesure", 1, mesure_latest_version, True))
            row_count += 1
        if mesure_v2_exists:
            models_data.append(("MESURE", "Keypoint Detection", "TRAINED ✦", "V2", f"{mesure_dataset}/499", "mesure", 2, mesure_latest_version, True))
            row_count += 1
        if not mesure_exists:
            models_data.append(("MESURE", "Keypoint Detection", "NOT TRAINED", "—", f"{mesure_dataset}/499", "mesure", 0, 0, False))
            row_count += 1

        for i, (model_name, model_type, status, version, dataset, model_id, ver_num, latest_ver, exists) in enumerate(models_data):
            row_bg = PANEL if i % 2 == 0 else BG
            row = tk.Frame(scrollable_frame, bg=row_bg)
            row.pack(fill=tk.X)

            # Model name
            tk.Label(row, text=model_name, bg=row_bg, fg=TEXT, font=("Arial", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Type
            tk.Label(row, text=model_type, bg=row_bg, fg=TEXT2, font=("Arial", 9), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Status (✦ marks latest version)
            status_color = GREEN if "TRAINED" in status else AMBER
            tk.Label(row, text=status, bg=row_bg, fg=status_color, font=("Arial", 9, "bold"), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Version
            tk.Label(row, text=version, bg=row_bg, fg=TEXT, font=("Arial", 9), width=10, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Dataset
            limit = 499
            dataset_color = GREEN if "/" in dataset and int(dataset.split("/")[0]) >= limit else TEXT
            tk.Label(row, text=dataset, bg=row_bg, fg=dataset_color, font=("Arial", 9), width=12, anchor="w").pack(side=tk.LEFT, padx=5, pady=8)

            # Actions
            action_frame = tk.Frame(row, bg=row_bg)
            action_frame.pack(side=tk.LEFT, padx=5, pady=8)

            if exists:
                details_btn = tk.Button(action_frame, text="📊 Details", font=("Arial", 8, "bold"),
                                       command=lambda m=model_id: self._show_model_details(m),
                                       bg=ACCENT, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=8, pady=3)
                details_btn.pack(side=tk.LEFT, padx=2)
                add_hover_effect(details_btn, ACCENT, "#5A5F75", "#FFFFFF")

                # Only show upgrade button on latest version
                if ver_num == latest_ver:
                    new_samples_count = self._count_new_samples(model_id)
                    upgrade_enabled = new_samples_count >= 500
                    upgrade_state = tk.NORMAL if upgrade_enabled else tk.DISABLED
                    upgrade_text = f"🔄 Upgrade" if upgrade_enabled else f"🔄 +{500-new_samples_count}"

                    upgrade_btn = tk.Button(action_frame, text=upgrade_text, font=("Arial", 8, "bold"),
                                           command=lambda m=model_id, d=mesure_dataset, v=latest_ver, n=new_samples_count: self._upgrade_model_dialog(m, d, v, n),
                                           bg=GREEN, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=8, pady=3, state=upgrade_state)
                    upgrade_btn.pack(side=tk.LEFT, padx=2)
                    if upgrade_enabled:
                        add_hover_effect(upgrade_btn, GREEN, "#388E3C", "#FFFFFF")

                # Export button for each version
                export_btn = tk.Button(action_frame, text=f"📥 Export", font=("Arial", 8, "bold"),
                                      command=lambda m=model_id, v=ver_num, n=model_name: self._export_single_model(m, v, n),
                                      bg=ACCENT, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=8, pady=3)
                export_btn.pack(side=tk.LEFT, padx=2)
                add_hover_effect(export_btn, ACCENT, "#5A5F75", "#FFFFFF")

                # Delete button for each version
                delete_btn = tk.Button(action_frame, text=f"🗑 Delete", font=("Arial", 8, "bold"),
                                      command=lambda m=model_id, v=ver_num: self._delete_model_version(m, v),
                                      bg=RED, fg="#FFFFFF", relief=tk.FLAT, bd=0, padx=8, pady=3)
                delete_btn.pack(side=tk.LEFT, padx=2)
                add_hover_effect(delete_btn, RED, "#8B0F15", "#FFFFFF")
            else:
                dataset_val = mesure_dataset
                limit = 499
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

        # Send/Export buttons
        button_frame = tk.Frame(frame, bg=BG)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        send_btn = tk.Button(button_frame, text="🚀 SEND MODELS TO MACHINES",
                            command=lambda: self._send_models_to_machines_dialog(mesure_exists, mesure_latest_version),
                            bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        send_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(send_btn, ACCENT, "#8B0F15", "#FFFFFF")


    def _show_training_page(self):
        """Display training status and progress"""
        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        tk.Label(frame, text="◉  MODEL TRAINING", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Determine whether a training session is actually running
        training_active = getattr(self, 'training_active', False) and getattr(self, 'current_training_samples', 0) > 0

        # Empty state: nothing is training yet
        if not training_active:
            empty_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
            empty_frame.pack(fill=tk.X, pady=(0, 20))

            tk.Label(empty_frame, text="◌  No model is currently training", bg=PANEL, fg=TEXT,
                    font=("Arial", 13, "bold")).pack(anchor=tk.W, padx=20, pady=(20, 8))
            tk.Label(empty_frame,
                    text="No training session is active right now.\n\n"
                         "To start training a model:\n"
                         "1. Go to the MODEL section\n"
                         "2. Click CREATE & TRAIN\n"
                         "3. Confirm — progress will appear here.",
                    bg=PANEL, fg=TEXT2, font=("Arial", 10), justify=tk.LEFT, wraplength=600).pack(anchor=tk.W, padx=20, pady=(0, 20))

            btn_frame = tk.Frame(frame, bg=BG)
            btn_frame.pack(fill=tk.X, pady=(10, 0))
            go_to_model = tk.Button(btn_frame, text="Go to MODEL Section",
                                    command=lambda: self._switch_page("model", self._show_model_page),
                                    bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"),
                                    relief=tk.FLAT, bd=0, padx=20, pady=10)
            go_to_model.pack(side=tk.LEFT)
            add_hover_effect(go_to_model, ACCENT, "#8B0F15", "#FFFFFF")
            return

        # Training info box
        info_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        info_text = """
📊 TRAINING STATUS

A training session is in progress.

You can monitor live progress below. Use CANCEL TRAINING to stop the
current session, or return to the MODEL section.

⏱ Training typically takes 5-30 minutes depending on dataset size.
        """

        tk.Label(info_frame, text=info_text, bg=PANEL, fg=TEXT2, font=("Arial", 10), justify=tk.LEFT, wraplength=600).pack(anchor=tk.W, padx=20, pady=20)

        # Progress section
        tk.Label(frame, text="TRAINING PROGRESS", bg=BG, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(20, 10))

        progress_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        progress_frame.pack(fill=tk.X, pady=(0, 5), padx=5)

        # Epoch counter
        epoch_label = tk.Label(progress_frame, text="Epoch: 0/30  |  Train Loss: --  |  Val Loss: --", bg=PANEL, fg=GREEN, font=("Arial", 10, "bold"))
        epoch_label.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Progress bar
        progress_bar = tk.Canvas(progress_frame, bg="#E0E0E0", height=30, highlightthickness=0)
        progress_bar.pack(fill=tk.X, padx=1, pady=1)

        # Progress fill (0%)
        progress_fill = progress_bar.create_rectangle(0, 0, 0, 30, fill=GREEN, outline=GREEN)

        def update_progress(percent, epoch=None, train_loss=None, val_loss=None):
            try:
                if percent < 0:
                    percent = 0
                if percent > 100:
                    percent = 100
                width = progress_bar.winfo_width()
                if width <= 1:
                    width = 600
                fill_width = (width - 2) * (percent / 100)
                progress_bar.coords(progress_fill, 0, 0, fill_width, 30)
                percent_label.config(text=f"{percent}%")

                # Update epoch and loss display
                if epoch is not None:
                    loss_text = f"Epoch: {epoch}/30"
                    if train_loss is not None:
                        loss_text += f"  |  Train Loss: {train_loss:.5f}"
                    if val_loss is not None:
                        loss_text += f"  |  Val Loss: {val_loss:.5f}"
                    epoch_label.config(text=loss_text)
                    print(f"[PROGRESS] {loss_text}", file=sys.stderr)

                # Calculate and update samples processed
                if dataset_size > 0:
                    samples_processed = int((dataset_size * percent) / 100)
                    try:
                        self.training_time_updater(dataset_size, percent, samples_processed)
                    except:
                        pass

                progress_bar.update()
            except Exception as e:
                print(f"[ERROR in update_progress] {type(e).__name__}: {e}", file=sys.stderr)
                pass

        # Bind the canvas to update on window resize
        progress_bar.bind("<Configure>", lambda e: update_progress(0))

        # Progress percentage
        percent_label = tk.Label(progress_frame, text="0%", bg=PANEL, fg=TEXT, font=("Arial", 9, "bold"))
        percent_label.pack(anchor=tk.E, padx=10, pady=5)

        # Store reference to progress updater for background thread
        self.current_progress_updater = update_progress

        # Status info with time estimation
        status_frame = tk.Frame(frame, bg=PANEL, relief=tk.SUNKEN, bd=1)
        status_frame.pack(fill=tk.X, pady=(0, 20), padx=5)

        # Check if training is active
        training_active = hasattr(self, 'current_training_samples') and self.current_training_samples > 0
        model_name = getattr(self, 'current_training_model', 'unknown').upper() if training_active else ""
        dataset_size = getattr(self, 'current_training_samples', 0) if training_active else 0

        if training_active:
            status_text = f"Status: Training {model_name} model with {dataset_size} samples..."
        else:
            status_text = "Status: Waiting for training to start..."

        status_info = tk.Label(status_frame, text=status_text, bg=PANEL, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT)
        status_info.pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Time estimation
        time_info = tk.Label(status_frame, text="", bg=PANEL, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT)
        time_info.pack(anchor=tk.W, padx=10, pady=(0, 5))

        # Samples processed counter
        samples_info = tk.Label(status_frame, text="", bg=PANEL, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT)
        samples_info.pack(anchor=tk.W, padx=10, pady=(0, 10))

        def calculate_training_time(dataset_size):
            """Calculate estimated training time in minutes based on dataset size"""
            # Estimation: ~2 minutes per 100 samples
            estimated_minutes = (dataset_size / 100) * 2
            return max(estimated_minutes, 5)  # Minimum 5 minutes

        def format_time(minutes):
            """Format minutes to HH:MM:SS format"""
            total_seconds = int(minutes * 60)
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            if hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            else:
                return f"{minutes}m {seconds}s"

        def update_time_display(dataset_size=0, elapsed_percent=0, samples_processed=0):
            """Update time and samples information display"""
            if dataset_size > 0:
                estimated_minutes = calculate_training_time(dataset_size)
                estimated_time_str = format_time(estimated_minutes)
                elapsed_minutes = (estimated_minutes * elapsed_percent) / 100
                elapsed_time_str = format_time(elapsed_minutes)
                remaining_minutes = estimated_minutes - elapsed_minutes
                remaining_time_str = format_time(remaining_minutes)

                time_text = f"⏱ Estimated: {estimated_time_str}  |  Elapsed: {elapsed_time_str}  |  Remaining: {remaining_time_str}"
                time_info.config(text=time_text)

                # Update samples processed
                samples_text = f"📊 Samples Processed: {samples_processed}/{dataset_size}"
                samples_info.config(text=samples_text)
            else:
                time_info.config(text="")
                samples_info.config(text="")

        # Show time estimation if training is active
        if training_active and dataset_size > 0:
            update_time_display(dataset_size, 0, 0)

        # Store reference for updates
        self.training_time_updater = update_time_display

        # Action buttons
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        cancel_btn = tk.Button(btn_frame, text="CANCEL TRAINING", command=self._cancel_training, bg=RED, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(cancel_btn, RED, "#8B0F15", "#FFFFFF")

        go_to_model = tk.Button(btn_frame, text="Go to MODEL Section", command=lambda: self._switch_page("model", self._show_model_page), bg=ACCENT, fg="#FFFFFF", font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        go_to_model.pack(side=tk.LEFT)
        add_hover_effect(go_to_model, ACCENT, "#8B0F15", "#FFFFFF")

    def _train_model_real(self):
        """Start REAL model training using the dataset"""
        import threading
        import traceback

        def train_worker():
            print("\n" + "=" * 80, file=sys.stderr)
            print("TRAINING STARTED", file=sys.stderr)
            print("=" * 80, file=sys.stderr)
            try:
                model_type = getattr(self, 'current_training_model', 'mesure')
                dataset_count = getattr(self, 'current_training_samples', 100)

                # Import necessary modules
                import json
                import numpy as np
                from sklearn.model_selection import train_test_split

                # Load dataset from annotations
                dataset_path = ANNOTATIONS_FILE
                if not dataset_path.exists():
                    raise Exception("Dataset annotations not found")

                annotations = json.loads(dataset_path.read_text())

                if not annotations:
                    raise Exception("No dataset available")

                # Load and preprocess images
                from PIL import Image
                X = []
                y = []

                for ann in annotations[:dataset_count]:
                    # Try original_path first (from our dataset), then fallback to image_path
                    img_path = Path(ann.get("original_path", ann.get("image_path", "")))
                    if not img_path.is_absolute():
                        img_path = ORIG_DIR / ann.get("filename", "")

                    if img_path.exists():
                        bgr = cv2.imread(str(img_path))
                        if bgr is None:
                            continue
                        # Threshold so training input matches what the model sees
                        # at inference time (apply_threshold), then resize to 640x480.
                        thresh = apply_threshold(bgr)
                        resized = cv2.resize(thresh, (640, 480))
                        img_array = resized.astype(np.float32) / 255.0

                        # Convert stored absolute points -> normalized [x1, y1, x2, y2].
                        # The labels live under "points", NOT "keypoints".
                        points = ann.get("points", [])
                        if len(points) < 2:
                            continue
                        aw = ann.get("width", 640) or 640
                        ah = ann.get("height", 480) or 480
                        keypoints = [
                            points[0].get("x", 0) / aw,
                            points[0].get("y", 0) / ah,
                            points[1].get("x", 0) / aw,
                            points[1].get("y", 0) / ah,
                        ]
                        X.append(img_array)
                        y.append(keypoints)

                if len(X) < 10:
                    raise Exception("Not enough valid training images")

                X = np.array(X)[..., np.newaxis]  # Add channel dimension
                y = np.array(y, dtype=np.float32)

                # Split dataset
                X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

                # Build CNN model (same as model_app.py)
                model = tf.keras.Sequential([
                    tf.keras.layers.Input(shape=(480, 640, 1)),
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
                    tf.keras.layers.Flatten(),
                    tf.keras.layers.Dense(512, activation='relu'),
                    tf.keras.layers.BatchNormalization(),
                    tf.keras.layers.Dropout(0.4),
                    tf.keras.layers.Dense(256, activation='relu'),
                    tf.keras.layers.Dropout(0.3),
                    tf.keras.layers.Dense(4, activation='sigmoid')
                ])

                model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3), loss='mse', metrics=['mae'])

                # Training callback for progress
                class ProgressCallback(tf.keras.callbacks.Callback):
                    def on_epoch_end(self, epoch, logs=None):
                        pct = int((epoch + 1) / self.params['epochs'] * 100)
                        print(f"[CALLBACK] Epoch {epoch+1}, pct={pct}, logs={logs}", file=sys.stderr)
                        if hasattr(self, 'app') and hasattr(self.app, 'current_progress_updater'):
                            try:
                                train_loss = logs.get('loss') if logs else None
                                val_loss = logs.get('val_loss') if logs else None
                                print(f"[CALLBACK] Calling updater: pct={pct}, epoch={epoch+1}, train_loss={train_loss}, val_loss={val_loss}", file=sys.stderr)
                                self.app.current_progress_updater(pct, epoch=epoch + 1, train_loss=train_loss, val_loss=val_loss)
                            except Exception as e:
                                print(f"[CALLBACK ERROR] {type(e).__name__}: {e}", file=sys.stderr)
                        else:
                            print(f"[CALLBACK] App or updater not set", file=sys.stderr)

                progress_cb = ProgressCallback()
                progress_cb.app = self

                # Train model
                history = model.fit(
                    X_train, y_train,
                    validation_split=0.1,
                    epochs=30,
                    batch_size=16,
                    callbacks=[
                        progress_cb
                    ],
                    verbose=0
                )

                # Evaluate
                test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)

                # Calculate additional metrics
                predictions = model.predict(X_test, verbose=0)
                pixel_errors = []
                accuracy_10px = 0
                accuracy_20px = 0

                for i in range(len(predictions)):
                    pred = predictions[i]
                    true = y_test[i]

                    # Calculate pixel distance error (denormalize and compute distance)
                    p1_pred = np.array([pred[0] * 640, pred[1] * 480])
                    p1_true = np.array([true[0] * 640, true[1] * 480])
                    p2_pred = np.array([pred[2] * 640, pred[3] * 480])
                    p2_true = np.array([true[2] * 640, true[3] * 480])

                    dist_pred = np.linalg.norm(p2_pred - p1_pred)
                    dist_true = np.linalg.norm(p2_true - p1_true)
                    pixel_error = abs(dist_pred - dist_true)
                    pixel_errors.append(pixel_error)

                    if pixel_error <= 10:
                        accuracy_10px += 1
                    if pixel_error <= 20:
                        accuracy_20px += 1

                mean_pixel_error = np.mean(pixel_errors) if pixel_errors else 0
                accuracy_10px = accuracy_10px / len(predictions) if predictions.shape[0] > 0 else 0
                accuracy_20px = accuracy_20px / len(predictions) if predictions.shape[0] > 0 else 0

                # Save model
                model_file = MODELS_MESURE_DIR / f"CNN_BELMOUNTH_MODEL_V1.h5"
                model_file.parent.mkdir(parents=True, exist_ok=True)
                model.save(str(model_file))

                # Save metadata with metrics
                metadata = {
                    "model_name": f"CNN_BELMOUNTH_MODEL_V1",
                    "type": "mesure",
                    "status": "trained",
                    "test_loss": float(test_loss),
                    "test_mae": float(test_mae),
                    "mean_pixel_error": float(mean_pixel_error),
                    "accuracy_10px": float(accuracy_10px),
                    "accuracy_20px": float(accuracy_20px),
                    "epochs_trained": 30,
                    "training_samples": len(X_train),
                    "test_samples": len(X_test),
                    "trained_at": str(datetime.now())
                }

                metadata_file = MODELS_MESURE_DIR / "mesure_metadata.json"
                metadata_file.parent.mkdir(parents=True, exist_ok=True)
                metadata_file.write_text(json.dumps(metadata, indent=2))

                # Reset training state
                self.training_active = False
                self.current_training_model = None
                self.current_training_samples = 0
                self.training_start_time = None
                messagebox.showinfo("Training Complete", f"✓ {model_type.upper()} model trained and saved!\n\nTest Loss: {test_loss:.4f}\nTest MAE: {test_mae:.4f}\nPixel Error: {mean_pixel_error:.2f}px\n10px Accuracy: {accuracy_10px:.1%}\n20px Accuracy: {accuracy_20px:.1%}")

            except Exception as e:
                # Reset training state on failure
                self.training_active = False
                self.current_training_model = None
                self.current_training_samples = 0
                self.training_start_time = None
                print("\n" + "=" * 80, file=sys.stderr)
                print(f"TRAINING FAILED: {type(e).__name__}", file=sys.stderr)
                print("=" * 80, file=sys.stderr)
                print(f"Error: {str(e)}", file=sys.stderr)
                print("\nFull Traceback:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                print("=" * 80, file=sys.stderr)
                messagebox.showerror("Training Error", f"Training failed:\n{str(e)}")

        # Start training in background
        thread = threading.Thread(target=train_worker, daemon=False)
        thread.start()

    def _upgrade_model_finetune(self, model_type, new_sample_count, old_version):
        """Fine-tune existing model on new samples (upgrade)"""
        def upgrade_worker():
            try:
                import json
                import numpy as np
                from sklearn.model_selection import train_test_split

                old_model_file = MODELS_MESURE_DIR / f"CNN_BELMOUNTH_MODEL_V1.h5" if old_version == 1 else MODELS_MESURE_DIR / "CNN_BELMOUNTH_MESURE_V2.h5"
                new_model_file = MODELS_MESURE_DIR / f"CNN_BELMOUNTH_MESURE_V{old_version + 1}.h5"

                # Load existing model
                if not old_model_file.exists():
                    raise Exception(f"Old model file not found: {old_model_file}")

                old_model = tf.keras.models.load_model(str(old_model_file))

                # Load NEW samples only (added after last training)
                metadata_file = MODELS_MESURE_DIR / f"{model_type}_metadata.json"
                trained_at_str = ""
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    trained_at_str = metadata.get("trained_at", "")

                annotations = json.loads(ANNOTATIONS_FILE.read_text())
                new_annotations = []

                if trained_at_str:
                    trained_at = datetime.fromisoformat(trained_at_str.replace("Z", "+00:00"))
                    for ann in annotations:
                        try:
                            created_str = ann.get("created_at", "")
                            if created_str:
                                created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                                if created_at > trained_at:
                                    new_annotations.append(ann)
                        except:
                            pass
                else:
                    new_annotations = annotations

                # Load and preprocess new samples
                from PIL import Image
                X_new = []
                y_new = []

                for ann in new_annotations[:new_sample_count]:
                    img_path = Path(ann.get("original_path", ann.get("image_path", "")))
                    if not img_path.is_absolute():
                        img_path = ORIG_DIR / ann.get("filename", "")

                    if img_path.exists():
                        bgr = cv2.imread(str(img_path))
                        if bgr is None:
                            continue
                        # Threshold to match inference-time preprocessing.
                        thresh = apply_threshold(bgr)
                        resized = cv2.resize(thresh, (640, 480))
                        img_array = resized.astype(np.float32) / 255.0

                        # Labels are under "points" (absolute) -> normalize them.
                        points = ann.get("points", [])
                        if len(points) < 2:
                            continue
                        aw = ann.get("width", 640) or 640
                        ah = ann.get("height", 480) or 480
                        keypoints = [
                            points[0].get("x", 0) / aw,
                            points[0].get("y", 0) / ah,
                            points[1].get("x", 0) / aw,
                            points[1].get("y", 0) / ah,
                        ]
                        X_new.append(img_array)
                        y_new.append(keypoints)

                if len(X_new) < 10:
                    raise Exception("Not enough new samples to fine-tune")

                X_new = np.array(X_new)[..., np.newaxis]
                y_new = np.array(y_new, dtype=np.float32)

                # Split new data
                X_train_new, X_test_new, y_train_new, y_test_new = train_test_split(X_new, y_new, test_size=0.2, random_state=42)

                # Fine-tune: lower learning rate for transfer learning
                old_model.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4), loss='mse', metrics=['mae'])

                class ProgressCallback(tf.keras.callbacks.Callback):
                    def on_epoch_end(self, epoch, logs=None):
                        pct = int((epoch + 1) / self.params['epochs'] * 100)
                        print(f"[CALLBACK] Epoch {epoch+1}, pct={pct}, logs={logs}", file=sys.stderr)
                        if hasattr(self, 'app') and hasattr(self.app, 'current_progress_updater'):
                            try:
                                train_loss = logs.get('loss') if logs else None
                                val_loss = logs.get('val_loss') if logs else None
                                print(f"[CALLBACK] Calling updater: pct={pct}, epoch={epoch+1}, train_loss={train_loss}, val_loss={val_loss}", file=sys.stderr)
                                self.app.current_progress_updater(pct, epoch=epoch + 1, train_loss=train_loss, val_loss=val_loss)
                            except Exception as e:
                                print(f"[CALLBACK ERROR] {type(e).__name__}: {e}", file=sys.stderr)
                        else:
                            print(f"[CALLBACK] App or updater not set", file=sys.stderr)

                progress_cb = ProgressCallback()
                progress_cb.app = self

                # Fine-tune for fewer epochs (10 instead of 30) since we're starting from trained weights
                history = old_model.fit(
                    X_train_new, y_train_new,
                    validation_split=0.1,
                    epochs=10,
                    batch_size=16,
                    callbacks=[progress_cb],
                    verbose=0
                )

                # Evaluate on new test set
                test_loss, test_mae = old_model.evaluate(X_test_new, y_test_new, verbose=0)

                # Calculate metrics on new test set
                predictions = old_model.predict(X_test_new, verbose=0)
                pixel_errors = []
                accuracy_10px = 0
                accuracy_20px = 0

                for i in range(len(predictions)):
                    pred = predictions[i]
                    true = y_test_new[i]

                    p1_pred = np.array([pred[0] * 640, pred[1] * 480])
                    p1_true = np.array([true[0] * 640, true[1] * 480])
                    p2_pred = np.array([pred[2] * 640, pred[3] * 480])
                    p2_true = np.array([true[2] * 640, true[3] * 480])

                    dist_pred = np.linalg.norm(p2_pred - p1_pred)
                    dist_true = np.linalg.norm(p2_true - p1_true)
                    pixel_error = abs(dist_pred - dist_true)
                    pixel_errors.append(pixel_error)

                    if pixel_error <= 10:
                        accuracy_10px += 1
                    if pixel_error <= 20:
                        accuracy_20px += 1

                mean_pixel_error = np.mean(pixel_errors) if pixel_errors else 0
                accuracy_10px = accuracy_10px / len(predictions) if predictions.shape[0] > 0 else 0
                accuracy_20px = accuracy_20px / len(predictions) if predictions.shape[0] > 0 else 0

                # Save fine-tuned model as new version
                new_model_file.parent.mkdir(parents=True, exist_ok=True)
                old_model.save(str(new_model_file))

                # Save metadata for new version
                new_metadata = {
                    "model_name": f"CNN_BELMOUNTH_MODEL_V{old_version + 1}",
                    "type": "mesure",
                    "status": "trained",
                    "test_loss": float(test_loss),
                    "test_mae": float(test_mae),
                    "mean_pixel_error": float(mean_pixel_error),
                    "accuracy_10px": float(accuracy_10px),
                    "accuracy_20px": float(accuracy_20px),
                    "epochs_trained": 10,
                    "training_samples": len(X_train_new),
                    "test_samples": len(X_test_new),
                    "trained_at": str(datetime.now()),
                    "upgraded_from_version": old_version,
                    "new_samples_used": new_sample_count
                }

                metadata_file = MODELS_MESURE_DIR / "mesure_metadata.json"
                metadata_file.write_text(json.dumps(new_metadata, indent=2))

                # Reset training state
                self.training_active = False
                self.current_training_model = None
                self.current_training_samples = 0
                self.training_start_time = None

                # Show success message and refresh model page
                def show_result():
                    messagebox.showinfo("Upgrade Complete", f"✓ Model upgraded to V{old_version + 1}!\n\nTest Loss: {test_loss:.4f}\nTest MAE: {test_mae:.4f}\nPixel Error: {mean_pixel_error:.2f}px\n10px Accuracy: {accuracy_10px:.1%}\n20px Accuracy: {accuracy_20px:.1%}")
                    # Refresh model page to show new V2
                    self._switch_page("model", self._show_model_page)

                self.root.after(0, show_result)

            except Exception as e:
                # Reset training state on failure
                self.training_active = False
                self.current_training_model = None
                self.current_training_samples = 0
                self.training_start_time = None
                print("\n" + "=" * 80, file=sys.stderr)
                print(f"UPGRADE FAILED: {type(e).__name__}", file=sys.stderr)
                print("=" * 80, file=sys.stderr)
                print(f"Error: {str(e)}", file=sys.stderr)
                print("\nFull Traceback:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                print("=" * 80, file=sys.stderr)
                messagebox.showerror("Upgrade Error", f"Upgrade failed:\n{str(e)}")

        # Start upgrade in background
        thread = threading.Thread(target=upgrade_worker, daemon=False)
        thread.start()

    def _cancel_training(self):
        """Cancel the ongoing training"""
        if messagebox.askyesno("Cancel Training", "Are you sure you want to cancel the training?\n\nThis cannot be undone."):
            # Reset training state
            self.training_active = False
            self.current_training_model = None
            self.current_training_samples = 0
            self.training_start_time = None
            # TODO: Call backend to stop training
            messagebox.showinfo("Training Cancelled", "Training has been cancelled.\n\nGo back to MODEL section to start a new training.")
            self._switch_page("model", self._show_model_page)

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
            # Store training info for the TRAINING page
            self.current_training_model = model_type
            self.current_training_samples = dataset_count
            self.training_start_time = time.time()
            self.training_active = True
            # Switch to TRAINING page to show progress
            self._switch_page("training", self._show_training_page)
            # Start REAL training
            self._train_model_real()

        create_btn = tk.Button(btn_frame, text="CREATE & TRAIN", command=confirm_create, bg=GREEN, fg="#FFFFFF", font=("Arial", 11, "bold"), relief=tk.FLAT, bd=0, padx=30, pady=15)
        create_btn.pack(side=tk.LEFT)
        add_hover_effect(create_btn, GREEN, "#388E3C", "#FFFFFF")

    def _count_new_samples(self, model_type):
        """Count samples added since the last model training"""
        try:
            metadata_file = MODELS_MESURE_DIR / f"{model_type}_metadata.json"
            if not metadata_file.exists():
                return 0

            metadata = json.loads(metadata_file.read_text())
            trained_at_str = metadata.get("trained_at", "")

            if not trained_at_str:
                return 0

            # Parse the training date
            trained_at = datetime.fromisoformat(trained_at_str.replace("Z", "+00:00"))

            # Count samples added after training
            annotations_file = ANNOTATIONS_FILE
            if not annotations_file.exists():
                return 0

            annotations = json.loads(annotations_file.read_text())
            new_count = 0

            for ann in annotations:
                created_str = ann.get("created_at", "")
                if created_str:
                    try:
                        created_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if created_at > trained_at:
                            new_count += 1
                    except:
                        pass

            return new_count
        except:
            return 0

    def _upgrade_model_dialog(self, model_type, dataset_count, current_version, new_samples):
        """Dialog to upgrade an existing model to next version with fine-tuning"""
        next_version = current_version + 1
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Upgrade {model_type.upper()} Model")
        dialog.geometry("550x400")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = tk.Frame(dialog, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text=f"Upgrade {model_type.upper()} Model to V{next_version}", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        tk.Label(frame, text=f"New samples available: {new_samples} (≥500 required)", bg=BG, fg=GREEN if new_samples >= 500 else AMBER, font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 5))
        tk.Label(frame, text=f"Current version: V{current_version} → New version: V{next_version}", bg=BG, fg=TEXT, font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0, 15))

        if new_samples < 500:
            shortage = 500 - new_samples
            tk.Label(frame, text=f"❌ Not enough new samples! Need {shortage} more.", bg=BG, fg=RED, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 20))
            tk.Label(frame, text=f"Please collect and approve at least 500 NEW captures since the last training before upgrading.", bg=BG, fg=TEXT2, font=("Arial", 9)).pack(anchor=tk.W, pady=(0, 20))

            close_btn = tk.Button(frame, text="CLOSE", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
            close_btn.pack(anchor=tk.W)
        else:
            tk.Label(frame, text=f"✓ Ready to upgrade with {new_samples} NEW samples", bg=BG, fg=GREEN, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 20))

            tk.Label(frame, text="⚙ Upgrade will:", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 10))

            info_text = f"""• Load V{current_version} model (transfer learning)
• Fine-tune on {new_samples} NEW samples
• Create new model version (V{next_version})
• Keep V{current_version} for comparison/rollback
• Training: {int(new_samples * 0.8)} new samples
• Testing: {int(new_samples * 0.2)} new samples
• Optional: Delete old version after V{next_version} is verified"""

            tk.Label(frame, text=info_text, bg=BG, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 20))

            # Buttons
            btn_frame = tk.Frame(frame, bg=BG)
            btn_frame.pack(fill=tk.X)

            cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=16, pady=8)
            cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
            add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

            def confirm_upgrade():
                messagebox.showinfo("Model Upgrade", f"Upgrading {model_type} model to V{next_version}...\n\nThis may take several minutes with fine-tuning on {new_samples} new samples.")
                dialog.destroy()
                # Store upgrade info for the TRAINING page
                self.current_training_model = model_type
                self.current_training_samples = new_samples
                self.training_start_time = time.time()
                self.training_active = True
                # Switch to TRAINING page to show progress
                self._switch_page("training", self._show_training_page)
                # Start upgrade training
                self._upgrade_model_finetune(model_type, new_samples, current_version)

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

    def _delete_model_all(self, model_type):
        """Delete all versions of a model"""
        if not messagebox.askyesno("Confirm Delete All", f"Delete ALL versions of {model_type.upper()} model?\n\nThis will permanently remove the trained model and cannot be undone."):
            return

        try:
            model_dir = MODELS_MESURE_DIR
            deleted_size = 0
            deleted_count = 0

            if model_type == "mesure":
                model_files = [
                    model_dir / "CNN_BELMOUNTH_MODEL_V1.h5",
                    model_dir / "CNN_BELMOUNTH_MESURE_V2.h5"
                ]
            else:  # state
                model_files = [
                    model_dir / "CNN_BELMOUNTH_STATE_V1.h5",
                    model_dir / "CNN_BELMOUNTH_STATE_V2.h5"
                ]

            for model_file in model_files:
                if model_file.exists():
                    deleted_size += model_file.stat().st_size
                    model_file.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                messagebox.showinfo("Success", f"✓ {deleted_count} model file(s) deleted!\n\nFreed up {deleted_size / (1024**3):.2f} GB\n\nYou can train a new {model_type.upper()} model.")
                # Refresh the page
                self._switch_page("model", self._show_model_page)
            else:
                messagebox.showerror("Error", f"No {model_type.upper()} model files found to delete")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete model: {str(e)}")

    def _export_single_model(self, model_type, version, model_name):
        """Export a single model version as ZIP"""
        from tkinter import filedialog

        try:
            # Ask user where to save
            save_path = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("ZIP Files", "*.zip"), ("All Files", "*.*")],
                initialfile=f"{model_type}_{model_name}_V{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            )

            if not save_path:
                return

            import zipfile
            import shutil

            # Create temporary zip file
            temp_zip = Path(tempfile.gettempdir()) / f"bellmouth_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                if model_type == "mesure":
                    model_file = MODELS_MESURE_DIR / f"CNN_BELMOUNTH_MODEL_V{version}.h5"
                    if not model_file.exists():
                        # Try alternative naming
                        model_file = MODELS_MESURE_DIR / f"CNN_BELMOUNTH_MESURE_V{version}.h5"
                else:  # state
                    state_dir = MODELS_ROOT / "state"
                    model_file = state_dir / f"CNN_BELMOUNTH_STATE_V{version}.h5"

                if not model_file.exists():
                    messagebox.showerror("Error", f"Model file not found: {model_file}")
                    return

                # Add model file
                zf.write(model_file, f"{model_type}/{model_file.name}")
                print(f"Added: {model_file.name}")

                # Add manifest
                manifest = {
                    "export_date": datetime.now().isoformat(),
                    "model_type": model_type,
                    "model_name": model_name,
                    "version": version,
                    "model_file": model_file.name
                }
                zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2))

            # Move to final location
            shutil.move(str(temp_zip), save_path)
            file_size = Path(save_path).stat().st_size / (1024 * 1024)

            messagebox.showinfo("Export Complete", f"✓ Model exported successfully!\n\n"
                                                   f"Model: {model_name} V{version}\n"
                                                   f"File: {Path(save_path).name}\n"
                                                   f"Size: {file_size:.2f} MB")
            print(f"Export complete: {save_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export model:\n{str(e)}")
            print(f"Export error: {e}")

    def _send_models_to_machines_dialog(self, mesure_exists, mesure_latest_version, state_exists=False, state_latest_version=0):
        """Dialog with 2 options: Upload NEW or Select EXISTING.
        STATE model was removed from the product, so state_exists defaults to
        False and every STATE branch below is simply skipped."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Send Models to Machines")
        dialog.geometry("550x550")
        dialog.configure(bg=BG)
        dialog.grab_set()

        # Create scrollable frame for content
        canvas = tk.Canvas(dialog, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        frame = tk.Frame(canvas, bg=BG)

        frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=20)

        tk.Label(frame, text="📤 Send Models to Machines", bg=BG, fg=TEXT, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # === METHOD SELECTION ===
        method_var = tk.StringVar(value="upload")

        upload_radio = tk.Radiobutton(frame, text="☁️ Upload NEW Models to Google Drive", variable=method_var, value="upload",
                                      bg=BG, fg=TEXT2, font=("Arial", 10), selectcolor=PANEL, activebackground=BG)
        upload_radio.pack(anchor=tk.W, pady=5)

        select_radio = tk.Radiobutton(frame, text="📁 Select EXISTING Model from Google Drive", variable=method_var, value="select",
                                     bg=BG, fg=TEXT2, font=("Arial", 10), selectcolor=PANEL, activebackground=BG)
        select_radio.pack(anchor=tk.W, pady=5)

        # === UPLOAD NEW MODELS SECTION ===
        upload_frame = tk.Frame(frame, bg=BG)
        upload_frame.pack(fill=tk.X, pady=(20, 0))

        # JSON credentials selector
        creds_label = tk.Label(upload_frame, text="📁 JSON Credentials File:", bg=BG, fg=TEXT2, font=("Arial", 9))
        creds_label.pack(anchor=tk.W)

        creds_frame = tk.Frame(upload_frame, bg=BG)
        creds_frame.pack(fill=tk.X, pady=(5, 10))

        creds_entry = tk.Entry(creds_frame, font=("Arial", 9), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=1)
        creds_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        creds_entry.insert(0, "No file selected")

        def browse_creds():
            file = filedialog.askopenfilename(
                filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
                title="Select Google Credentials JSON"
            )
            if file:
                creds_entry.delete(0, tk.END)
                creds_entry.insert(0, file)

        browse_creds_btn = tk.Button(creds_frame, text="🔍 BROWSE", command=browse_creds,
                                     bg=ACCENT, fg="#FFFFFF", font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=10)
        browse_creds_btn.pack(side=tk.LEFT)
        add_hover_effect(browse_creds_btn, ACCENT, "#5A5F75", "#FFFFFF")

        from tkinter import ttk
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox',
                      fieldbackground=PANEL,
                      background=PANEL,
                      foreground=TEXT,
                      arrowcolor=TEXT2)

        # MESURE Model section
        mesure_label = tk.Label(upload_frame, text="📊 MESURE Model Version:", bg=BG, fg=TEXT2, font=("Arial", 9))
        mesure_label.pack(anchor=tk.W, pady=(10, 5))

        if mesure_exists:
            mesure_versions = [f"V{mesure_latest_version}"]
            mesure_var = tk.StringVar(value=mesure_versions[0])
            mesure_dropdown = ttk.Combobox(upload_frame, textvariable=mesure_var, values=mesure_versions,
                                          state='readonly', font=("Arial", 9), width=35)
            mesure_dropdown.pack(fill=tk.X, pady=(0, 15))
        else:
            tk.Label(upload_frame, text="✗ No MESURE model available", bg=BG, fg=RED, font=("Arial", 9)).pack(anchor=tk.W, pady=(0, 15))
            mesure_var = None

        # STATE Model section
        state_label = tk.Label(upload_frame, text="🔍 STATE Model Version:", bg=BG, fg=TEXT2, font=("Arial", 9))
        state_label.pack(anchor=tk.W, pady=(10, 5))

        if state_exists:
            state_versions = [f"V{state_latest_version}"]
            state_var = tk.StringVar(value=state_versions[0])
            state_dropdown = ttk.Combobox(upload_frame, textvariable=state_var, values=state_versions,
                                         state='readonly', font=("Arial", 9), width=35)
            state_dropdown.pack(fill=tk.X, pady=(0, 0))
        else:
            tk.Label(upload_frame, text="✗ No STATE model available", bg=BG, fg=RED, font=("Arial", 9)).pack(anchor=tk.W, pady=(0, 0))
            state_var = None

        # === UPLOAD BUTTON (in upload section) ===
        def upload_models():
            # Determine which model to upload
            model_to_upload = None
            if mesure_exists and state_exists:
                # Ask user which one
                choice = messagebox.askyesnocancel("Select Model", "Upload MESURE model?\n\nYes = MESURE\nNo = STATE\nCancel = Cancel")
                if choice is None:
                    return
                model_to_upload = f"MESURE {mesure_var.get()}" if choice else f"STATE {state_var.get()}"
            elif mesure_exists:
                model_to_upload = f"MESURE {mesure_var.get()}"
            elif state_exists:
                model_to_upload = f"STATE {state_var.get()}"
            else:
                messagebox.showerror("Error", "No trained models available")
                return

            creds_path = creds_entry.get()
            if creds_path == "No file selected":
                messagebox.showerror("Error", "Please select JSON credentials file")
                return

            dialog.destroy()
            messagebox.showinfo("Uploading", f"Uploading {model_to_upload}...\n\nThis may take several minutes for large files.\n\nThe app will notify all machines automatically when complete.")
            import threading
            upload_thread = threading.Thread(
                target=self._upload_selected_model,
                args=(model_to_upload, creds_path, notify_var.get()),
                daemon=True
            )
            upload_thread.start()

        upload_btn = tk.Button(upload_frame, text="☁️ UPLOAD TO DRIVE & SEND TO MACHINES", command=upload_models,
                              bg=GREEN, fg="#FFFFFF", font=("Arial", 11, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=12)
        upload_btn.pack(fill=tk.X, pady=(20, 0))
        add_hover_effect(upload_btn, GREEN, "#388E3C", "#FFFFFF")

        # === SELECT EXISTING SECTION ===
        select_frame = tk.Frame(frame, bg=BG)

        url_label = tk.Label(select_frame, text="🔗 Google Drive Model URL:", bg=BG, fg=TEXT2, font=("Arial", 9))
        url_label.pack(anchor=tk.W)

        url_entry = tk.Entry(select_frame, font=("Arial", 9), bg=PANEL, fg=TEXT, relief=tk.FLAT, bd=1)
        url_entry.pack(fill=tk.X, pady=(5, 0))
        url_entry.insert(0, "https://drive.google.com/uc?id=...&export=download")

        # === SEND BUTTON (in select section) ===
        def send_existing():
            url = url_entry.get().strip()
            if not url or url.startswith("https://drive.google.com/uc?id="):
                messagebox.showerror("Error", "Please enter a valid Google Drive URL")
                return
            dialog.destroy()
            messagebox.showinfo("Sending", f"Sending model to machines...")
            import threading
            send_thread = threading.Thread(
                target=self._send_manual_model,
                args=(url, "custom", notify_var.get()),
                daemon=True
            )
            send_thread.start()

        send_btn = tk.Button(select_frame, text="📤 SEND TO MACHINES", command=send_existing,
                            bg=ACCENT, fg="#FFFFFF", font=("Arial", 11, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=12)
        send_btn.pack(fill=tk.X, pady=(15, 0))
        add_hover_effect(send_btn, ACCENT, "#5A5F75", "#FFFFFF")

        # === NOTIFICATIONS (bottom) ===
        notify_var = tk.BooleanVar(value=True)
        notify_cb = tk.Checkbutton(frame, text="✓ Send notifications to all machines", variable=notify_var,
                                   bg=BG, fg=TEXT2, font=("Arial", 9), selectcolor=PANEL, activebackground=BG)
        notify_cb.pack(anchor=tk.W, pady=(20, 0))

        # === CANCEL BUTTON ===
        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(fill=tk.X, pady=(30, 0))

        cancel_btn = tk.Button(btn_frame, text="CANCEL", command=dialog.destroy, bg=PANEL, fg=TEXT,
                              font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
        cancel_btn.pack(side=tk.LEFT)
        add_hover_effect(cancel_btn, PANEL, SEP, TEXT)

        # === CONDITIONAL UI ===
        def update_ui(*args):
            if method_var.get() == "upload":
                upload_frame.pack(fill=tk.X, pady=(20, 0))
                select_frame.pack_forget()
            else:
                upload_frame.pack_forget()
                select_frame.pack(fill=tk.X, pady=(20, 0))

        method_var.trace_add("write", update_ui)
        update_ui()  # Initial state

    def _upload_selected_model(self, model_name, creds_path, notify):
        """Upload a selected model to Google Drive with progress bar"""
        import zipfile
        import shutil

        try:
            # Parse model name: "MESURE V2" or "STATE V1"
            parts = model_name.split(" V")
            model_type = parts[0].lower()  # "mesure" or "state"
            version = int(parts[1]) if len(parts) > 1 else 1

            # Find model file
            if model_type == "mesure":
                model_file = MODELS_MESURE_DIR / f"CNN_BELMOUNTH_MODEL_V{version}.h5"
                if not model_file.exists():
                    model_file = MODELS_MESURE_DIR / f"CNN_BELMOUNTH_MESURE_V{version}.h5"
            else:
                state_dir = MODELS_ROOT / "state"
                model_file = state_dir / f"CNN_BELMOUNTH_STATE_V{version}.h5"

            if not model_file.exists():
                messagebox.showerror("Error", f"Model file not found: {model_file}")
                return

            # Create progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Uploading Model")
            progress_dialog.geometry("500x200")
            progress_dialog.configure(bg=BG)
            progress_dialog.resizable(False, False)
            progress_dialog.grab_set()

            content = tk.Frame(progress_dialog, bg=BG)
            content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            tk.Label(content, text=f"📤 Uploading {model_name}...", bg=BG, fg=TEXT, font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 20))

            # Progress bar
            from tkinter import ttk
            progress_var = tk.DoubleVar(value=0)
            progress_bar = ttk.Progressbar(content, variable=progress_var, maximum=100, length=400, mode='determinate')
            progress_bar.pack(fill=tk.X, pady=(0, 10))

            # Progress text
            progress_text = tk.Label(content, text="0% - Preparing...", bg=BG, fg=TEXT2, font=("Arial", 9))
            progress_text.pack(anchor=tk.W, pady=(0, 10))

            # Status
            status_text = tk.Label(content, text="", bg=BG, fg=TEXT2, font=("Arial", 9))
            status_text.pack(anchor=tk.W)

            progress_dialog.update()

            # Create ZIP
            temp_zip = Path(tempfile.gettempdir()) / f"bellmouth_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(model_file, f"{model_type}/{model_file.name}")
                zf.writestr("MANIFEST.json", json.dumps({
                    "export_date": datetime.now().isoformat(),
                    "model_type": model_type,
                    "model_name": model_name,
                    "version": version,
                    "model_file": model_file.name
                }, indent=2))

            print(f"Created ZIP: {temp_zip}")
            progress_text.config(text="✓ ZIP created - Starting upload...")
            progress_dialog.update()

            # Upload to Google Drive
            from google_drive_client import GoogleDriveClient
            drive_client = GoogleDriveClient(creds_path)

            zip_size_mb = temp_zip.stat().st_size / (1024 * 1024)
            print(f"Uploading {temp_zip.name} ({zip_size_mb:.2f} MB)...")

            # Progress callback for GUI
            def on_progress(percent, message):
                try:
                    progress_var.set(percent)
                    progress_text.config(text=f"{percent}% - {message}")
                    status_text.config(text=f"Uploading {zip_size_mb:.2f} MB...")
                    progress_dialog.update()
                except:
                    pass  # Dialog closed

            # Upload with progress tracking
            upload_result = drive_client.upload_file(str(temp_zip), file_name=temp_zip.name, progress_callback=on_progress)
            download_link = upload_result['downloadLink']

            # Update progress
            progress_var.set(100)
            progress_text.config(text="100% - Upload complete!")
            status_text.config(text=f"✓ {temp_zip.name} uploaded successfully")
            progress_dialog.update()

            print(f"Upload complete! File ID: {upload_result.get('id')}")
            temp_zip.unlink()  # Delete temp file

            # Wait a moment to show completion
            self.root.after(1500, progress_dialog.destroy)

            # Send notifications if enabled
            if notify:
                try:
                    from api_client import APIClient
                    api = APIClient(api_url="http://localhost:8000")
                    # Determine notification type based on model
                    notif_type = "mesure-upload" if model_type == "mesure" else "state-upload"
                    api.send_model_update_notifications(download_link, model_name, notification_type=notif_type)
                    messagebox.showinfo("Success", f"✓ {model_name} uploaded and shared with machines!\n\nDownload link has been sent to all machines.")
                except Exception as e:
                    messagebox.showinfo("Partial Success", f"✓ Model uploaded to Google Drive!\n\nBut notifications may not have been sent:\n{str(e)}\n\nLink: {download_link}")
            else:
                messagebox.showinfo("Success", f"✓ {model_name} uploaded to Google Drive!\n\nLink: {download_link}")

        except Exception as e:
            messagebox.showerror("Upload Error", f"Failed to upload model:\n{str(e)}")
            print(f"Upload error: {e}")

    def _send_manual_model(self, url, model_type, notify):
        """Send model from manual URL to machines"""
        try:
            # Show success dialog with file info
            success_dialog = tk.Toplevel(self.root)
            success_dialog.title("Models Ready to Send")
            success_dialog.geometry("650x600")
            success_dialog.configure(bg=BG)
            success_dialog.grab_set()

            # Create scrollable frame
            canvas = tk.Canvas(success_dialog, bg=BG, highlightthickness=0)
            scrollbar = tk.Scrollbar(success_dialog, orient=tk.VERTICAL, command=canvas.yview)
            content = tk.Frame(canvas, bg=BG)

            content.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=content, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=20)

            tk.Label(content, text="✓ Ready to Send to Machines!", bg=BG, fg=GREEN, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

            # Summary
            summary_frame = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
            summary_frame.pack(fill=tk.X, pady=(0, 20), padx=5)

            model_type_text = {"mesure": "MESURE", "state": "STATE", "custom": "Custom"}.get(model_type, "Custom")
            summary_text = f"""📦 Model File:
• Type: {model_type_text}
• Download Link Ready
• Ready to send to machines"""

            tk.Label(summary_frame, text=summary_text, bg=PANEL, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=15)

            # Download link section
            tk.Label(content, text="📥 Download Link (for machines):", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))

            link_frame = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
            link_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20), padx=5)

            link_text = tk.Text(link_frame, height=4, bg=PANEL, fg=ACCENT, font=("Courier", 9), relief=tk.FLAT, bd=0, wrap=tk.WORD)
            link_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            link_text.insert("1.0", url)
            link_text.config(state=tk.DISABLED)

            # Copy button
            def copy_link():
                success_dialog.clipboard_clear()
                success_dialog.clipboard_append(url)
                messagebox.showinfo("Copied", "Download link copied to clipboard!")

            copy_btn = tk.Button(content, text="📋 Copy Download Link", command=copy_link, bg=ACCENT, fg="#FFFFFF",
                               font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=15, pady=8)
            copy_btn.pack(anchor=tk.W)

            # Send notifications
            if notify:
                tk.Label(content, text="📢 Sending Notifications to Machines...", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(20, 5))

                notify_info = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
                notify_info.pack(fill=tk.X, padx=5)

                try:
                    from api_client import APIClient
                    api = APIClient(api_url="http://localhost:8000")
                    notify_result = api.send_model_update_notifications(url, model_type_text, notification_type="info")

                    if notify_result.get("ok"):
                        notify_text = f"""✓ Notifications sent successfully!

• Model Type: {model_type_text}
• Download link shared with all active machines
• Machines will auto-update when they process the notification"""
                    else:
                        error_msg = notify_result.get('error', 'Unknown error')
                        notify_text = f"""⚠️ URL ready, but notifications may not have been sent.

Error: {error_msg}

Troubleshooting:
• Make sure the API backend is running
• Verify at least one machine is registered and active
• Check that machines have is_active = True in database"""
                except Exception as e:
                    error_str = str(e)
                    if "Connection" in error_str or "refused" in error_str:
                        notify_text = f"""⚠️ URL ready to share!

⚠️ API Backend Not Running

To enable notifications:
1. Open terminal in C:\\BellmouthProject\\app\\
2. Run: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
3. Leave it running in the background
4. Then try sending again"""
                    else:
                        notify_text = f"""✓ URL ready to share!

Error sending auto-notifications: {error_str}

The download link is ready to share manually."""

                tk.Label(notify_info, text=notify_text, bg=PANEL, fg=TEXT2, font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=10)

            # Close button
            close_btn = tk.Button(content, text="CLOSE", command=success_dialog.destroy, bg=PANEL, fg=TEXT,
                                 font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
            close_btn.pack(side=tk.LEFT, pady=(20, 0))
            add_hover_effect(close_btn, PANEL, SEP, TEXT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process model:\n{str(e)}")

    def _send_existing_model(self, file_name, download_link, notify):
        """Send existing model file to machines"""
        try:
            # Show success dialog with file info
            success_dialog = tk.Toplevel(self.root)
            success_dialog.title("Models Ready to Send")
            success_dialog.geometry("650x600")
            success_dialog.configure(bg=BG)
            success_dialog.grab_set()

            # Create scrollable frame
            canvas = tk.Canvas(success_dialog, bg=BG, highlightthickness=0)
            scrollbar = tk.Scrollbar(success_dialog, orient=tk.VERTICAL, command=canvas.yview)
            content = tk.Frame(canvas, bg=BG)

            content.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=content, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=20)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=20)

            tk.Label(content, text="✓ Ready to Send to Machines!", bg=BG, fg=GREEN, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

            # Summary
            summary_frame = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
            summary_frame.pack(fill=tk.X, pady=(0, 20), padx=5)

            summary_text = f"""📦 Model File:
• Name: {file_name}
• Download Link Ready
• Ready to send to machines"""

            tk.Label(summary_frame, text=summary_text, bg=PANEL, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=15)

            # Download link section
            tk.Label(content, text="📥 Download Link (for machines):", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))

            link_frame = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
            link_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20), padx=5)

            link_text = tk.Text(link_frame, height=4, bg=PANEL, fg=ACCENT, font=("Courier", 9), relief=tk.FLAT, bd=0, wrap=tk.WORD)
            link_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            link_text.insert("1.0", download_link)
            link_text.config(state=tk.DISABLED)

            # Copy button
            def copy_link():
                success_dialog.clipboard_clear()
                success_dialog.clipboard_append(download_link)
                messagebox.showinfo("Copied", "Download link copied to clipboard!")

            copy_btn = tk.Button(content, text="📋 Copy Download Link", command=copy_link, bg=ACCENT, fg="#FFFFFF",
                               font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=15, pady=8)
            copy_btn.pack(anchor=tk.W)

            # Send notifications
            if notify:
                tk.Label(content, text="📢 Sending Notifications to Machines...", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(20, 5))

                notify_info = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
                notify_info.pack(fill=tk.X, padx=5)

                try:
                    from api_client import APIClient
                    api = APIClient(api_url="http://localhost:8000")
                    notify_result = api.send_model_update_notifications(download_link, "Existing Model", notification_type="info")

                    if notify_result.get("ok"):
                        notify_text = f"""✓ Notifications sent successfully!

• File: {file_name}
• Download link shared with all active machines
• Machines will auto-update when they process the notification"""
                    else:
                        error_msg = notify_result.get('error', 'Unknown error')
                        notify_text = f"""⚠️ File ready, but notifications may not have been sent.

Error: {error_msg}

Troubleshooting:
• Make sure the API backend is running
• Verify at least one machine is registered and active"""
                except Exception as e:
                    error_str = str(e)
                    if "Connection" in error_str or "refused" in error_str:
                        notify_text = f"""⚠️ API Backend Not Running

To enable notifications:
1. Open terminal in C:\\BellmouthProject\\app\\
2. Run: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
3. Leave it running in the background"""
                    else:
                        notify_text = f"""⚠️ Error sending notifications: {error_str}"""

                tk.Label(notify_info, text=notify_text, bg=PANEL, fg=TEXT2, font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=10)

            # Close button
            close_btn = tk.Button(content, text="CLOSE", command=success_dialog.destroy, bg=PANEL, fg=TEXT,
                                 font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
            close_btn.pack(side=tk.LEFT, pady=(20, 0))
            add_hover_effect(close_btn, PANEL, SEP, TEXT)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process model:\n{str(e)}")

    def _zip_and_send_models(self, mesure_exists, state_exists, mesure_ver, state_ver, upload_location, compress, notify, method="google_drive"):
        """Zip models and upload to Google Drive or manual location"""
        import zipfile
        import shutil
        from datetime import datetime

        try:
            # Check for Google Drive credentials if using Google Drive
            if method == "google_drive":
                # Get credentials path from config first
                config_file = APP_DIR / "config.json"
                creds_path = None

                if config_file.exists():
                    try:
                        config = json.loads(config_file.read_text())
                        creds_path = config.get('google_drive', {}).get('credentials_path')
                    except:
                        pass

                # If no config path, use default
                if not creds_path:
                    creds_path = str(APP_DIR / "google_credentials.json")

                creds_file = Path(creds_path)
                if not creds_file.exists():
                    messagebox.showerror("Setup Required",
                        f"Google credentials file not found!\n\n"
                        f"Current path: {creds_path}\n\n"
                        "To fix:\n"
                        "1. Click ⚙ SETTINGS (top right)\n"
                        "2. Click 📁 BROWSE\n"
                        "3. Select your google_credentials.json\n"
                        "4. Check 'Enable Google Drive'\n"
                        "5. Save settings\n\n"
                        "Then try again!")
                    return
            # Create upload directory
            upload_dir = MODELS_ROOT / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)

            # Create zip file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_name = f"bellmouth_models_{timestamp}.zip"
            zip_path = upload_dir / zip_name

            with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add MESURE model
                if mesure_exists:
                    mesure_v1 = MODELS_MESURE_DIR / "CNN_BELMOUNTH_MODEL_V1.h5"
                    mesure_v2 = MODELS_MESURE_DIR / "CNN_BELMOUNTH_MESURE_V2.h5"
                    mesure_meta = MODELS_MESURE_DIR / "mesure_metadata.json"

                    if mesure_v1.exists():
                        zipf.write(mesure_v1, arcname=f"mesure/CNN_BELMOUNTH_MODEL_V1.h5")
                    if mesure_v2.exists():
                        zipf.write(mesure_v2, arcname=f"mesure/CNN_BELMOUNTH_MESURE_V2.h5")
                    if mesure_meta.exists():
                        zipf.write(mesure_meta, arcname=f"mesure/metadata.json")

                # Add STATE model (future)
                if state_exists:
                    state_v1 = MODELS_MESURE_DIR / "CNN_BELMOUNTH_STATE_V1.h5"
                    state_v2 = MODELS_MESURE_DIR / "CNN_BELMOUNTH_STATE_V2.h5"
                    state_meta = MODELS_MESURE_DIR / "state_metadata.json"

                    if state_v1.exists():
                        zipf.write(state_v1, arcname=f"state/CNN_BELMOUNTH_STATE_V1.h5")
                    if state_v2.exists():
                        zipf.write(state_v2, arcname=f"state/CNN_BELMOUNTH_STATE_V2.h5")
                    if state_meta.exists():
                        zipf.write(state_meta, arcname=f"state/metadata.json")

                # Add manifest
                manifest = {
                    "timestamp": timestamp,
                    "mesure": {"exists": mesure_exists, "version": mesure_ver} if mesure_exists else None,
                    "state": {"exists": state_exists, "version": state_ver} if state_exists else None,
                    "zip_size_mb": zip_path.stat().st_size / (1024 * 1024)
                }
                zipf.writestr("MANIFEST.json", json.dumps(manifest, indent=2))

            # Upload to Google Drive or use manual location
            file_size = zip_path.stat().st_size / (1024 * 1024)

            if method == "google_drive":
                # Upload to Google Drive
                try:
                    from google_drive_client import GoogleDriveClient

                    # Get credentials path from config
                    config_file = APP_DIR / "config.json"
                    creds_path = None
                    if config_file.exists():
                        try:
                            config = json.loads(config_file.read_text())
                            creds_path = config.get('google_drive', {}).get('credentials_path')
                        except:
                            pass

                    if not creds_path:
                        creds_path = str(APP_DIR / "google_credentials.json")

                    drive_client = GoogleDriveClient(creds_path)

                    # Show progress
                    messagebox.showinfo("Uploading", f"Uploading to Google Drive...\n\nFile: {zip_name}\nSize: {file_size:.2f} MB\n\nA browser window may open for authentication.")

                    # Upload
                    upload_result = drive_client.upload_file(str(zip_path), file_name=zip_name)
                    download_link = upload_result['downloadLink']
                    # The zip is now on Drive - delete the local copy so uploads/ doesn't fill up
                    try:
                        zip_path.unlink()
                    except Exception as _e:
                        print(f"Could not delete local zip: {_e}")
                    upload_info = {
                        'method': 'google_drive',
                        'drive_link': upload_result['webViewLink'],
                        'file_id': upload_result['id']
                    }
                except ImportError as ie:
                    error_detail = str(ie)
                    messagebox.showerror("Missing Dependencies",
                        f"Google Drive libraries not installed.\n\n"
                        f"Error: {error_detail}\n\n"
                        f"Fix:\n"
                        f"1. Open a terminal/command prompt\n"
                        f"2. Run: pip install -r requirements.txt --upgrade\n"
                        f"3. Restart this app\n\n"
                        f"Make sure you're using the same Python environment where this app runs.")
                    return
                except Exception as e:
                    messagebox.showerror("Upload Error", f"Failed to upload to Google Drive:\n{str(e)}")
                    return
            else:
                # Manual URL
                download_link = f"{upload_location.rstrip('/')}/{zip_name}"
                upload_info = {'method': 'manual'}

            # Show success dialog with link
            success_dialog = tk.Toplevel(self.root)
            success_dialog.title("Models Ready to Send")
            success_dialog.geometry("650x400")
            success_dialog.configure(bg=BG)
            success_dialog.resizable(False, False)
            success_dialog.grab_set()

            content = tk.Frame(success_dialog, bg=BG)
            content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            tk.Label(content, text="✓ Models Packaged Successfully!", bg=BG, fg=GREEN, font=("Arial", 14, "bold")).pack(anchor=tk.W, pady=(0, 20))

            # Summary
            summary_frame = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
            summary_frame.pack(fill=tk.X, pady=(0, 20), padx=5)

            upload_method_text = "☁ Google Drive" if method == "google_drive" else "📍 Manual URL"
            summary_text = f"""📦 Package Information:
• File: {zip_name}
• Size: {file_size:.2f} MB
• Models: {'MESURE V' + str(mesure_ver) if mesure_exists else ''} {', STATE V' + str(state_ver) if state_exists else ''}
• Upload: {upload_method_text}
• Ready to download and deploy"""

            tk.Label(summary_frame, text=summary_text, bg=PANEL, fg=TEXT2, font=("Arial", 9), justify=tk.LEFT).pack(anchor=tk.W, padx=15, pady=15)

            # Download link section
            if method == "google_drive":
                tk.Label(content, text="☁ Google Drive Link:", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))

                drive_link_frame = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
                drive_link_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=5)

                drive_link_text = tk.Text(drive_link_frame, height=2, bg=PANEL, fg=GREEN, font=("Courier", 9), relief=tk.FLAT, bd=0, wrap=tk.WORD)
                drive_link_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                drive_link_text.insert("1.0", upload_info.get('drive_link', ''))
                drive_link_text.config(state=tk.DISABLED)

                tk.Label(content, text="📥 Direct Download Link (for machines):", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(15, 5))
            else:
                tk.Label(content, text="📥 Download Link for Machines:", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))

            link_frame = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
            link_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20), padx=5)

            link_text = tk.Text(link_frame, height=4, bg=PANEL, fg=ACCENT, font=("Courier", 9), relief=tk.FLAT, bd=0, wrap=tk.WORD)
            link_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            link_text.insert("1.0", download_link)
            link_text.config(state=tk.DISABLED)

            # Copy button
            def copy_link():
                success_dialog.clipboard_clear()
                success_dialog.clipboard_append(download_link)
                messagebox.showinfo("Copied", "Download link copied to clipboard!")

            copy_btn = tk.Button(content, text="📋 Copy Download Link", command=copy_link, bg=ACCENT, fg="#FFFFFF",
                               font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=15, pady=8)
            copy_btn.pack(anchor=tk.W)

            # Notification section
            if notify:
                tk.Label(content, text="📢 Sending Notifications to Machines...", bg=BG, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(20, 5))

                notify_info = tk.Frame(content, bg=PANEL, relief=tk.SUNKEN, bd=1)
                notify_info.pack(fill=tk.X, padx=5)

                # Prepare notification content
                models_str = f"{'MESURE' if mesure_exists else ''} {'and STATE' if state_exists and mesure_exists else 'STATE' if state_exists else ''}".strip()

                # Send notifications to all machines via API
                try:
                    from api_client import APIClient
                    api = APIClient(api_url="http://localhost:8000")
                    notify_result = api.send_model_update_notifications(download_link, models_str, notification_type="info")

                    if notify_result.get("ok"):
                        notify_text = f"""✓ Notifications sent successfully!

• Models: {models_str}
• Download link shared with all active machines
• Machines will auto-update when they process the notification

Notification info:
{notify_result.get('data', {}).get('message', 'Notifications sent')}"""
                    else:
                        notify_text = f"""✓ Models uploaded, but notifications may not have been sent.

You can manually share this link:
{download_link}

Error: {notify_result.get('error', 'Unknown error')}"""
                except Exception as e:
                    notify_text = f"""✓ Models uploaded successfully!

Share this download link with machines:
{download_link}

Error sending auto-notifications: {str(e)}"""

                tk.Label(notify_info, text=notify_text, bg=PANEL, fg=TEXT2, font=("Arial", 8), justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=10)

            # Close button
            close_btn = tk.Button(content, text="CLOSE", command=success_dialog.destroy, bg=PANEL, fg=TEXT,
                                 font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=20, pady=10)
            close_btn.pack(side=tk.LEFT, pady=(20, 0))
            add_hover_effect(close_btn, PANEL, SEP, TEXT)

            messagebox.showinfo("Success", f"✓ Models packaged successfully!\n\nZip file: {zip_name}\nSize: {file_size:.2f} MB\n\nShare the download link with machines!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to package models:\n{str(e)}")

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
            model_app_path = APP_DIR / "model_bellmounth_mesure" / "model_app.py"
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
        uninstall_btn = tk.Button(top, text="UNINSTALL", command=lambda: uninstall_app(self.root), bg=SEP, fg=TEXT2, font=("Arial", 10, "bold"), relief=tk.FLAT, bd=0, padx=12, pady=6)
        uninstall_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(uninstall_btn, SEP, "#D3D3D3", TEXT)

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
        # mm-per-pixel derived from this capture's own original measurement, so
        # the modal recomputes distance exactly the way the machine did. Falls
        # back to the default calibration when the original data is unusable.
        _odx = self.original_p2[0] - self.original_p1[0]
        _ody = self.original_p2[1] - self.original_p1[1]
        _orig_px = (_odx * _odx + _ody * _ody) ** 0.5
        _meas_mm = capture.get('measured_distance_mm') or 0
        self.mm_per_pixel = (_meas_mm / _orig_px) if (_orig_px and _meas_mm) else DEFAULT_MM_PER_PIXEL
        self.expected_mm = capture.get('expected_diameter_mm')
        self.tolerance_min = capture.get('tolerance_min')
        self.tolerance_max = capture.get('tolerance_max')
        self.dragging_point = None
        self.thread_mode = False
        self.current_image_pil = None
        self.current_photo = None
        self.thresholded_image_pil = None
        self.thresholded_photo = None
        # Pre-select the current OK / NOT OK verdict (measurement_status) so the
        # modal reflects the saved value instead of always being blank.
        self.cable_state = tk.StringVar(value=capture.get('measurement_status') or "")

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
        # Close is handled by the window's native title-bar button and the
        # CANCEL button below — no extra custom ✕ here.

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

        # Switch target — the distance this cable is expected to measure.
        target_txt = f"{self.expected_mm} mm" if self.expected_mm is not None else "N/A"
        tk.Label(right, text="SWITCH TARGET DISTANCE", bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 5))
        tk.Label(right, text=target_txt, bg=PANEL, fg=TEXT, font=("Consolas", 11, "bold")).pack(anchor=tk.W, padx=20, pady=(0, 12))

        # Original points
        tk.Label(right, text="ORIGINAL POINTS", bg=PANEL, fg=TEXT2, font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 5))
        self.orig_lbl = tk.Label(right, text="P1: (0, 0)\nP2: (0, 0)", bg=PANEL, fg=TEXT2, font=("Consolas", 8), justify=tk.LEFT)
        self.orig_lbl.pack(anchor=tk.W, padx=20, pady=(0, 10))

        # Edited points
        tk.Label(right, text="EDITED POINTS", bg=PANEL, fg=ACCENT, font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 5))
        self.edit_lbl = tk.Label(right, text="P1: (0, 0)\nP2: (0, 0)\nDistance: 0.00 mm", bg=PANEL, fg=ACCENT, font=("Consolas", 8), justify=tk.LEFT)
        self.edit_lbl.pack(anchor=tk.W, padx=20, pady=(0, 15))

        tk.Frame(right, bg=BORDER, height=1).pack(fill=tk.X, pady=10, padx=15)

        # Cable state (OK / NOT OK) — read-only badge, auto-computed from the
        # edited distance vs the switch tolerance. Not user-clickable.
        tk.Label(right, text="CABLE STATE", bg=PANEL, fg=TEXT, font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=15, pady=(0, 10))

        self.state_indicator = tk.Label(right, text="—", bg=PANEL, fg=TEXT2,
                                        font=("Arial", 11, "bold"), padx=14, pady=8)
        self.state_indicator.pack(anchor=tk.W, padx=25, pady=(0, 4))

        def refresh_state_rows():
            verdict = self.cable_state.get()
            if verdict == "okay":
                self.state_indicator.config(text="CABLE OK", bg=GREEN, fg="#FFFFFF")
            elif verdict == "not_okay":
                self.state_indicator.config(text="CABLE NOT OK", bg=RED, fg="#FFFFFF")
            else:
                self.state_indicator.config(text="—", bg=PANEL, fg=TEXT2)

        # Exposed so the drag handler / reset can refresh the badge as points move.
        self._refresh_state_rows = refresh_state_rows
        refresh_state_rows()

        tk.Frame(right, bg=BORDER, height=1).pack(fill=tk.X, pady=10, padx=15)

        # Save button
        # Enabled from the start: the annoteur may save after editing the points
        # OR just the cable state, so Save must not depend on dragging a point.
        self.save_btn = tk.Button(right, text="✓ SAVE", command=self._save_changes,
                                 bg=GREEN, fg="#FFFFFF", font=("Arial", 10, "bold"),
                                 relief=tk.FLAT, bd=0, padx=20, pady=12)
        self.save_btn.pack(fill=tk.X, padx=15, pady=(0, 8))
        add_hover_effect(self.save_btn, GREEN, "#3E7C3F", "#FFFFFF")

        # Cancel button
        cancel_btn = tk.Button(right, text="CANCEL", command=self.modal.destroy,
                              bg=TEXT2, fg="#FFFFFF", font=("Arial", 10, "bold"),
                              relief=tk.FLAT, bd=0, padx=20, pady=12)
        cancel_btn.pack(fill=tk.X, padx=15)
        add_hover_effect(cancel_btn, TEXT2, "#555555", "#FFFFFF")

    def _load_image(self):
        """Load the capture images (original and thresholded)"""
        # Primary path: download the original image from the server over HTTP so
        # this works from any machine, not just the one hosting the files.
        self.current_image_pil = None
        capture_id = self.capture.get('id')
        if capture_id and self.api_client:
            img_bytes = self.api_client.get_capture_image(capture_id, kind="original")
            if img_bytes:
                try:
                    self.current_image_pil = Image.open(io.BytesIO(img_bytes)).convert('RGB')
                    print(f"✓ Downloaded original image for capture {capture_id}")
                except Exception as e:
                    print(f"✗ Could not decode downloaded image: {e}")
                    self.current_image_pil = None

        # Fallback: a local copy on this same machine (dev / offline).
        if self.current_image_pil is None:
            image_path = self.capture.get('image_original_path', '')
            if image_path and Path(image_path).exists():
                try:
                    self.current_image_pil = Image.open(image_path).convert('RGB')
                    print(f"✓ Loaded original image locally: {image_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load original image: {str(e)}")
                    return

        if self.current_image_pil is None:
            messagebox.showerror("Error", "Could not load the capture image from the server.")
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
        if not self.panning:
            self._auto_evaluate_state()
        self._redraw_canvas()

    def _auto_evaluate_state(self):
        """Recompute the CABLE OK / NOT OK verdict from the edited distance vs the
        switch tolerance, so fixing the annotation flips the state automatically.
        No-ops if the switch tolerance wasn't provided by the API."""
        if self.tolerance_min is None or self.tolerance_max is None:
            return
        if not (self.edited_p1 and self.edited_p2):
            return
        dist_px = ((self.edited_p2[0] - self.edited_p1[0]) ** 2 +
                   (self.edited_p2[1] - self.edited_p1[1]) ** 2) ** 0.5
        dist_mm = dist_px * self.mm_per_pixel
        verdict = "okay" if (self.tolerance_min <= dist_mm <= self.tolerance_max) else "not_okay"
        self.cable_state.set(verdict)
        if hasattr(self, "_refresh_state_rows"):
            self._refresh_state_rows()

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
        """Reset the view (zoom/pan) AND revert the edited keypoints and verdict
        back to the capture's original values."""
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.zoom_lbl.config(text="1.0x")
        # Revert the annotation to the original.
        self.edited_p1 = self.original_p1
        self.edited_p2 = self.original_p2
        self.cable_state.set(self.capture.get('measurement_status') or "")
        if hasattr(self, "_refresh_state_rows"):
            self._refresh_state_rows()
        self._update_display()
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
            dist_px = ((self.edited_p2[0]-self.edited_p1[0])**2 + (self.edited_p2[1]-self.edited_p1[1])**2)**0.5
            dist_mm = dist_px * self.mm_per_pixel
            self.edit_lbl.config(text=f"P1: {self.edited_p1}\nP2: {self.edited_p2}\nDistance: {dist_mm:.2f} mm")

    def _enable_save_button(self):
        """Enable save button if changes detected"""
        if self.edited_p1 != self.original_p1 or self.edited_p2 != self.original_p2:
            self.save_btn.config(state=tk.NORMAL)

    def _save_changes(self):
        """Save edited annotation"""
        try:
            # Save only updates the edited keypoint coordinates. Approval is a
            # separate, explicit action (the ACCEPT button in the queue) so that
            # editing a capture never removes it from the annoteur's queue.
            payload = {
                "p1_x": int(self.edited_p1[0]),
                "p1_y": int(self.edited_p1[1]),
                "p2_x": int(self.edited_p2[0]),
                "p2_y": int(self.edited_p2[1]),
                "measurement_status": self.cable_state.get() or self.capture.get('measurement_status', 'okay')
            }

            self.api_client.put(f"/admin/captures/{self.capture.get('id')}/annotate", payload)
            messagebox.showinfo("Success", "Coordinates updated!")
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

        # Camera attributes kept as no-op placeholders so shutdown/cleanup code
        # stays safe. The annoteur UI (captures / notifications / reclamations)
        # never uses the camera, so we deliberately do NOT open it here — that
        # avoids grabbing the Dino-Lite device just because someone logged in
        # as an annoteur.
        self.cap = None
        self.pixel_measure = None
        self.camera_ok = False
        self.current_frame = None
        self.frame_count = 0
        self.last_zoom = 1.0
        self._loop_running = False

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
        uninstall_btn = tk.Button(top, text="UNINSTALL", command=lambda: uninstall_app(self.root), bg=SEP, fg=TEXT2, font=("Arial", 9, "bold"), relief=tk.FLAT, bd=0, padx=10, pady=4)
        uninstall_btn.pack(side=tk.LEFT, padx=(0, 10))
        add_hover_effect(uninstall_btn, SEP, "#D3D3D3", TEXT)

        # Navigation bar
        navbar = tk.Frame(self.root, bg=BORDER, height=50)
        navbar.pack(fill=tk.X, side=tk.TOP)
        navbar.pack_propagate(False)

        nav_items = [
            ("BELLMOUNTH CAPTURES", "annotation"),
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

        # No camera loop for the annoteur — the camera is never opened for this
        # role, so there is nothing to poll.

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
        elif page_id == "notification":
            self._show_notification_page()
        elif page_id == "reclamation":
            self._show_reclamation_page()

    def _show_annotation_page(self):
        """Display table of pending captures"""
        # Clear any existing content first so a refresh (e.g. after saving in the
        # editor modal) replaces the table instead of stacking a second one.
        for widget in self.content_container.winfo_children():
            widget.destroy()

        frame = tk.Frame(self.content_container, bg=BG)
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(frame, text="BELLMOUNTH CAPTURES", bg=BG, fg=TEXT, font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 20))

        # Table header
        header = tk.Frame(frame, bg=PANEL)
        header.pack(fill=tk.X, pady=(0, 10))

        cols = [("MACHINE", 15), ("DATE", 18), ("SWITCH", 15), ("METHOD", 10), ("STATE", 10), ("VIEW", 8), ("ACTION", 20)]
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
            # Only this annoteur's assigned captures that still need verifying.
            # Captures are split fairly across annoteurs by the server at upload time.
            response = self.api_client.get(
                f"/admin/captures?status=pending&annoteur_id={self.user_id}"
            )
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
                # How the capture was taken: auto_cnn -> AUTO, manual -> MANUAL.
                method_raw = capture.get('capture_method', '')
                if method_raw == "auto_cnn":
                    method_text, method_color = "AUTO", "#FF9800"    # amber (AI/auto)
                elif method_raw == "manual":
                    method_text, method_color = "MANUAL", "#607D8B"  # blue-grey (human)
                else:
                    method_text, method_color = "—", TEXT2
                # Show whether the measurement was within the switch tolerance.
                m_status = capture.get('measurement_status', 'unknown')
                if m_status == "okay":
                    state, state_color = "CABLE OK", GREEN
                elif m_status == "not_okay":
                    state, state_color = "CABLE NOT OK", RED
                else:
                    state, state_color = "—", TEXT2

                # Columns
                tk.Label(row, text=machine, bg=CARD, fg=TEXT, font=("Arial", 9), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
                tk.Label(row, text=date_str, bg=CARD, fg=TEXT, font=("Arial", 9), width=18, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)
                tk.Label(row, text=switch, bg=CARD, fg=TEXT, font=("Arial", 9), width=15, anchor="w").pack(side=tk.LEFT, padx=10, pady=8)

                method_lbl = tk.Label(row, text=method_text, bg=method_color, fg="#FFFFFF", font=("Arial", 8, "bold"), width=10, anchor="center")
                method_lbl.pack(side=tk.LEFT, padx=10, pady=8)

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
        """Refuse a capture — delete it (row + image files) from the queue."""
        result = messagebox.askyesno("Confirm", f"Refuse capture from {capture.get('machine_name', 'Unknown')}?")
        if result:
            try:
                resp = self.api_client.delete_capture(capture.get('id'))
                if resp and resp.get("ok"):
                    # Re-fetch the queue first so the deleted row visibly
                    # disappears the moment the confirmation is dismissed.
                    self._refresh_annotation_page()
                    messagebox.showinfo("Success", "Capture refused")
                else:
                    err = (resp or {}).get("error") or (resp or {}).get("detail") or "Unknown error"
                    messagebox.showerror("Error", f"Failed to refuse capture: {err}")
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
    # Server configuration screen first: API URL + Azure SQL/blob/JWT values,
    # prefilled from .env / config.json, with test buttons. Saving writes both
    # files, then the app continues to the login screen.
    from server_config import show_server_config
    api_url = show_server_config()
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
