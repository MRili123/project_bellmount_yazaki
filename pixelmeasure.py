# pixelmeasure.py

from dnx64 import DNX64
import time
import sys
import os

class PixelMeasure:
    def __init__(self, dll_path=None):
        if dll_path is None:
            # Try system SDK first (required for dependencies)
            system_dll = r"C:\Program Files\DNX64\DNX64.dll"
            bundled_dll = os.path.join(os.path.dirname(__file__), "lib", "DNX64.dll")

            if os.path.exists(system_dll):
                dll_path = system_dll
            elif os.path.exists(bundled_dll):
                dll_path = bundled_dll
            else:
                raise FileNotFoundError("DNX64.dll not found. Install Dino-Lite SDK or ensure lib/DNX64.dll exists")
        # Hide SDK spam
        sys.stdout = open(os.devnull, 'w')

        self.dnx = DNX64(dll_path)

        if self.dnx.GetVideoDeviceCount() > 0:
            self.dnx.SetVideoDeviceIndex(0)

        # Restore stdout
        sys.stdout = sys.__stdout__

        # Calibration (you can change later)
        self.CALIB_ZOOM = 34.58
        self.CALIB_MM_PER_PIXEL = 0.0165

        self.current_zoom = None
        self.mm_per_pixel = None
        self.last_refresh = time.time()

    def update(self):
        zoom = self.dnx.GetAMR(0)

        if zoom and zoom != self.current_zoom:
            self.current_zoom = zoom
            self.mm_per_pixel = self.CALIB_MM_PER_PIXEL * (self.CALIB_ZOOM / zoom)

        # silent refresh every 1 second
        if time.time() - self.last_refresh > 1:
            sys.stdout = open(os.devnull, 'w')
            self.dnx.SetVideoDeviceIndex(0)
            sys.stdout = sys.__stdout__
            self.last_refresh = time.time()

    def get_values(self):
        return self.current_zoom, self.mm_per_pixel