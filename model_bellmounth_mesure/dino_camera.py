"""
dino_camera.py  —  shared camera/SDK bridge
============================================
Place this file inside:
    bellmounth project/model_bellmounth_mesure/dino_camera.py

It reaches UP into the parent folder to reuse:
    ../camera_setup.py   → get_camera(index)
    ../dnx64.py          → DNX64 wrapper
    ../pixelmeasure.py   → PixelMeasure (AMR + mm/pixel)

Both app.py files use this single module so camera init,
DLL path, and SDK calls are never duplicated.

Usage inside model_bellmounth_mesure/app.py:
    from dino_camera import DinoCamera
    cam = DinoCamera()          # finds the Dino-Lite automatically
    cap = cam.cap               # cv2.VideoCapture — use for frames
    sdk = cam.sdk               # DNX64 instance or None
    zoom, mm_px = cam.get_zoom_and_mm()   # live values via PixelMeasure
"""

import sys
import cv2
from pathlib import Path

# ── Resolve parent project folder ─────────────────────────────────────────────
_HERE   = Path(__file__).resolve().parent          # …/model_bellmounth_mesure/
_PARENT = _HERE.parent                             # …/bellmounth project/

# Add parent to sys.path so we can import its modules directly
if str(_PARENT) not in sys.path:
    sys.path.insert(0, str(_PARENT))

# ── Import from parent project ─────────────────────────────────────────────────
try:
    from camera_setup import get_camera as _get_camera
    _CAMERA_SETUP_OK = True
except ImportError:
    _CAMERA_SETUP_OK = False

try:
    from dnx64 import DNX64 as _DNX64Class
    _DNX64_OK = True
except ImportError:
    _DNX64_OK = False

try:
    from pixelmeasure import PixelMeasure as _PixelMeasure
    _PIXELMEASURE_OK = True
except ImportError:
    _PixelMeasure = None
    _PIXELMEASURE_OK = False

# ── Constants (same as outer app.py) ──────────────────────────────────────────
DNX64_DLL = r"C:\Program Files\DNX64\DNX64.dll"


class DinoCamera:
    """
    One-stop camera object shared between both app.py files.

    Attributes
    ----------
    cap : cv2.VideoCapture | None
        Ready-to-read capture object.  Always use this for frames.
    sdk : DNX64 | None
        Initialised SDK instance, or None if DLL/wrapper unavailable.
    pixel_measure : PixelMeasure | None
        PixelMeasure instance for live zoom + mm/pixel, or None.
    device_index : int
        The cv2 / DNX64 device index that was opened.
    """

    def __init__(self, preferred_index: int | None = None):
        """
        Parameters
        ----------
        preferred_index : int | None
            Force a specific camera index.  If None, auto-detect via SDK
            (picks the first Dino-Lite device), falling back to index 0.
        """
        self.sdk           = None
        self.cap           = None
        self.pixel_measure = None
        self.device_index  = 0
        self._device_names: list[str] = []

        self._init_sdk()
        self._init_pixelmeasure()

        # Resolve which cv2 index to open
        if preferred_index is not None:
            self.device_index = preferred_index
        elif self.sdk is not None:
            self.device_index = self._first_dinolite_index()

        self._open_cap(self.device_index)

    # ── SDK ───────────────────────────────────────────────────────────────────

    def _init_sdk(self):
        if not _DNX64_OK:
            return
        try:
            sdk = _DNX64Class(DNX64_DLL)
            sdk.Init()
            self.sdk = sdk
        except Exception as exc:
            print(f"[DinoCamera] DNX64 SDK not available: {exc}")

    def _first_dinolite_index(self) -> int:
        """Ask SDK for the first discovered device index."""
        if self.sdk is None:
            return 0
        try:
            count = self.sdk.GetVideoDeviceCount()
            self._device_names = []
            for i in range(count):
                try:
                    name = self.sdk.GetVideoDeviceName(i) or f"Device {i}"
                except Exception:
                    name = f"Device {i}"
                self._device_names.append(name)
                print(f"[DinoCamera] Found device [{i}]: {name}")
            if count > 0:
                self.sdk.SetVideoDeviceIndex(0)
                return 0
        except Exception as exc:
            print(f"[DinoCamera] Device discovery failed: {exc}")
        return 0

    # ── PixelMeasure ──────────────────────────────────────────────────────────

    def _init_pixelmeasure(self):
        if not _PIXELMEASURE_OK:
            return
        try:
            self.pixel_measure = _PixelMeasure(DNX64_DLL)
        except Exception as exc:
            print(f"[DinoCamera] PixelMeasure not available: {exc}")

    # ── cv2 capture ───────────────────────────────────────────────────────────

    def _open_cap(self, index: int):
        if _CAMERA_SETUP_OK:
            # Use the outer project's get_camera() which has its own error handling
            self.cap = _get_camera(index)
        else:
            # Fallback: plain cv2
            cap = cv2.VideoCapture(index)
            self.cap = cap if cap.isOpened() else None
            if self.cap is None:
                print(f"[DinoCamera] cv2.VideoCapture({index}) failed to open")

    def switch_device(self, index: int):
        """Switch to a different camera device index at runtime."""
        self.release()
        self.device_index = index
        if self.sdk:
            try:
                self.sdk.SetVideoDeviceIndex(index)
            except Exception:
                pass
        self._open_cap(index)

    # ── Live values ───────────────────────────────────────────────────────────

    def get_zoom_and_mm(self) -> tuple[float, float]:
        """
        Return (zoom_magnification, mm_per_pixel).
        Calls PixelMeasure.update() then .get_values() exactly like the
        outer app.py does on screenshot.
        Returns (0.0, 0.0) if SDK/PixelMeasure unavailable.
        """
        if self.pixel_measure is None:
            return 0.0, 0.0
        try:
            self.pixel_measure.update()
            return self.pixel_measure.get_values()
        except Exception:
            return 0.0, 0.0

    def get_amr(self, device_index: int | None = None) -> float:
        """Return AMR magnification from SDK, or 0.0 if unavailable."""
        if self.sdk is None:
            return 0.0
        try:
            idx = device_index if device_index is not None else self.device_index
            return float(self.sdk.GetAMR(idx))
        except Exception:
            return 0.0

    def get_fov(self, mag: float, device_index: int | None = None) -> float:
        """Return FOV in µm for given magnification, or 0.0 if unavailable."""
        if self.sdk is None or mag <= 0:
            return 0.0
        try:
            idx = device_index if device_index is not None else self.device_index
            return float(self.sdk.FOVx(idx, mag))
        except Exception:
            return 0.0

    def list_devices(self) -> list[str]:
        """Return list of device name strings discovered by SDK."""
        return list(self._device_names)

    def read_frame(self):
        """
        Convenience wrapper: returns (ret, frame) exactly like cap.read().
        Use this or self.cap.read() — both work identically.
        """
        if self.cap and self.cap.isOpened():
            return self.cap.read()
        return False, None

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def release(self):
        """Release cv2 capture. Call on app close."""
        if self.cap:
            self.cap.release()
            self.cap = None

    def __del__(self):
        self.release()
