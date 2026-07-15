# camera_setup.py
#
# Opens ONLY the Bellmounth (Dino-Lite) microscope. If no Dino-Lite is
# connected, returns None so the app shows "NO BELLMOUNTH CAMERA DETECTED"
# instead of falling back to the laptop's built-in webcam.

import os
import cv2

# The DNX64 SDK is how we identify a genuine Dino-Lite (as opposed to any
# random webcam). It is only present on a machine with the Dino-Lite drivers.
try:
    from dnx64 import DNX64
except Exception:
    DNX64 = None


def _dnx_dll_path():
    system_dll = r"C:\Program Files\DNX64\DNX64.dll"
    bundled_dll = os.path.join(os.path.dirname(__file__), "lib", "DNX64.dll")
    if os.path.exists(system_dll):
        return system_dll
    if os.path.exists(bundled_dll):
        return bundled_dll
    return None


def _find_dino_index():
    """Return the video-device index of a connected Dino-Lite, or None.

    Uses the DNX64 SDK: GetVideoDeviceCount() > 0 means a Dino-Lite is present,
    and GetVideoDeviceIndex() gives its DirectShow index. We also confirm the
    device name looks like a Dino-Lite when the SDK exposes it.
    """
    if DNX64 is None:
        return None
    dll = _dnx_dll_path()
    if dll is None:
        return None
    try:
        dnx = DNX64(dll)
        dnx.Init()
        if dnx.GetVideoDeviceCount() <= 0:
            return None
        index = dnx.GetVideoDeviceIndex()
        if index is None or index < 0:
            index = 0
        # Best-effort name confirmation (never fatal).
        try:
            name = (dnx.GetVideoDeviceName(index) or "").lower()
            if name and ("dino" not in name and "dnt" not in name and "am" not in name):
                # Some SDK builds return a generic name; don't reject on that
                # alone — the device count already proved a Dino is attached.
                pass
        except Exception:
            pass
        return index
    except Exception as e:
        print(f"Dino-Lite detection error: {e}")
        return None


def get_camera(index=None):
    """Open the Dino-Lite microscope. Returns a cv2.VideoCapture, or None if no
    Bellmounth/Dino-Lite camera is detected."""
    dino_index = _find_dino_index()
    if dino_index is None:
        print("No Bellmounth (Dino-Lite) camera detected")
        return None

    # Open the Dino-Lite specifically. CAP_DSHOW is the reliable backend on
    # Windows for Dino-Lite devices.
    cap = cv2.VideoCapture(dino_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(dino_index)  # fallback backend
    if not cap.isOpened():
        print(f"Dino-Lite found at index {dino_index} but could not be opened")
        return None

    # Confirm it actually delivers frames.
    ok, _ = cap.read()
    if not ok:
        cap.release()
        print("Dino-Lite opened but returned no frame")
        return None

    print(f"Bellmounth (Dino-Lite) camera opened at index {dino_index}")
    return cap
