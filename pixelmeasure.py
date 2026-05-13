# pixelmeasure.py

from dnx64 import DNX64
import time
import sys
import os

class PixelMeasure:
    def __init__(self, dll_path=None, camera_width=1920):
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
        self.device_index = 0

        if self.dnx.GetVideoDeviceCount() > 0:
            self.dnx.SetVideoDeviceIndex(self.device_index)

        # Restore stdout
        sys.stdout = sys.__stdout__

        self.camera_width = camera_width  # Camera frame width in pixels
        self.current_zoom = None
        self.mm_per_pixel = None
        self.last_refresh = time.time()

    def update(self):
        zoom = self.dnx.GetAMR(self.device_index)

        if zoom and zoom != self.current_zoom:
            self.current_zoom = zoom
            # Get FOV from SDK directly
            try:
                fov_micrometers = self.dnx.FOVx(self.device_index, zoom)
                if fov_micrometers and fov_micrometers > 0:
                    micrometers_per_pixel = fov_micrometers / self.camera_width
                    self.mm_per_pixel = micrometers_per_pixel / 1000.0
            except Exception as e:
                print(f"FOVx error: {e}")

        # silent refresh every 1 second
        if time.time() - self.last_refresh > 1:
            sys.stdout = open(os.devnull, 'w')
            self.dnx.SetVideoDeviceIndex(self.device_index)
            sys.stdout = sys.__stdout__
            self.last_refresh = time.time()

    def get_values(self):
        return self.current_zoom, self.mm_per_pixel