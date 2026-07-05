# pixelmeasure.py

import time
import sys
import os

# The DNX64 SDK is only available on a machine with the Dino-Lite drivers.
# Import it defensively so the app still runs (in default-calibration mode)
# on machines without the SDK / camera.
try:
    from dnx64 import DNX64
    _DNX_AVAILABLE = True
except Exception:
    DNX64 = None
    _DNX_AVAILABLE = False

# Default calibration used whenever a real mm/pixel value can't be obtained
# from the SDK (no camera connected, SDK missing, or FOV not yet read).
# The real value is computed from the microscope's FOV at the current zoom;
# this constant is only the fallback. Change it to match your setup.
DEFAULT_MM_PER_PIXEL = 0.0165  # mm per pixel


class PixelMeasure:
    def __init__(self, dll_path=None, camera_width=1920, default_mm_per_pixel=DEFAULT_MM_PER_PIXEL):
        self.camera_width = camera_width  # Camera frame width in pixels
        self.current_zoom = None
        self.default_mm_per_pixel = default_mm_per_pixel
        # Start with the default so a value is always available, even before the
        # SDK reports a real FOV (or when no camera / SDK is present at all).
        self.mm_per_pixel = default_mm_per_pixel
        self.last_refresh = time.time()
        self.sdk_available = False
        self.dnx = None
        self.device_index = 0

        # No SDK installed -> stay in default-calibration mode.
        if not _DNX_AVAILABLE:
            return

        if dll_path is None:
            # Try system SDK first (required for dependencies)
            system_dll = r"C:\Program Files\DNX64\DNX64.dll"
            bundled_dll = os.path.join(os.path.dirname(__file__), "lib", "DNX64.dll")

            if os.path.exists(system_dll):
                dll_path = system_dll
            elif os.path.exists(bundled_dll):
                dll_path = bundled_dll
            else:
                # No DLL found -> stay in default-calibration mode instead of crashing.
                return

        # Hide SDK spam
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            devnull = open(os.devnull, 'w')
            sys.stdout = devnull
            sys.stderr = devnull

            self.dnx = DNX64(dll_path)
            self.device_index = 0

            if self.dnx.GetVideoDeviceCount() > 0:
                self.dnx.SetVideoDeviceIndex(self.device_index)
            self.sdk_available = True
        except Exception:
            # SDK present but failed to initialise (e.g. no device) -> default mode.
            self.dnx = None
            self.sdk_available = False
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            try:
                devnull.close()
            except:
                pass

    def update(self):
        # Without a working SDK there is nothing to read; keep the default value.
        if not self.sdk_available or self.dnx is None:
            return

        old_stdout = sys.stdout
        old_stderr = sys.stderr
        try:
            devnull = open(os.devnull, 'w')
            sys.stdout = devnull
            sys.stderr = devnull

            try:
                zoom = self.dnx.GetAMR(self.device_index)
                if zoom and zoom != self.current_zoom:
                    self.current_zoom = zoom
                    try:
                        fov_micrometers = self.dnx.FOVx(self.device_index, zoom)
                        if fov_micrometers and fov_micrometers > 0:
                            micrometers_per_pixel = fov_micrometers / self.camera_width
                            self.mm_per_pixel = micrometers_per_pixel / 1000.0
                    except:
                        pass
            except:
                pass
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            try:
                devnull.close()
            except:
                pass

    def get_values(self):
        # mm_per_pixel is never None: it is the real SDK value when available,
        # otherwise the default calibration.
        return self.current_zoom, self.mm_per_pixel

    def close(self):
        pass
