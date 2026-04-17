from dnx64 import DNX64
import time
import ctypes
import ctypes.wintypes
import threading
from collections import deque

dll_path = r"C:\Program Files\DNX64\DNX64.dll"

# ── Win32-level console suppression ──────────────────────────────────────────
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

def _open_nul():
    return kernel32.CreateFileW("nul", 0x40000000, 0, None, 3, 0, None)

def silence():
    nul = _open_nul()
    kernel32.SetStdHandle(-11, nul)
    kernel32.SetStdHandle(-12, nul)

def restore():
    kernel32.SetStdHandle(-11, _real_stdout)
    kernel32.SetStdHandle(-12, _real_stderr)

_real_stdout = kernel32.GetStdHandle(-11)
_real_stderr = kernel32.GetStdHandle(-12)

# ── Shared buffer ─────────────────────────────────────────────────────────────
# deque(maxlen=7) acts as a sliding window — always holds the last 7 readings.
# Thread-safe for append/read without a lock in CPython.
BUFFER_SIZE = 7
buffer = deque(maxlen=BUFFER_SIZE)
buffer_lock = threading.Lock()

# ── Reader thread — runs as fast as the SDK allows ───────────────────────────
# Reinits every read (required for fresh hardware value).
# No sleep — just hammers the SDK and pushes values into the buffer.
def reader_thread():
    while True:
        try:
            silence()
            dnx = DNX64(dll_path)
            dnx.SetVideoDeviceIndex(0)
            v = dnx.GetAMR(0)
            restore()
            if v and v > 0:
                with buffer_lock:
                    buffer.append(v)
        except Exception:
            restore()

# ── Median from buffer ────────────────────────────────────────────────────────
def get_median():
    with buffer_lock:
        if not buffer:
            return None
        sorted_vals = sorted(buffer)
    return sorted_vals[len(sorted_vals) // 2]

# ── Init ──────────────────────────────────────────────────────────────────────
silence()
dnx = DNX64(dll_path)
count = dnx.GetVideoDeviceCount()
restore()

if count == 0:
    print("Error: No camera found")
    exit()

print(f"Camera found ({count} device(s)). Watching zoom...\n")

# Start reader thread as daemon (auto-kills when main script exits)
t = threading.Thread(target=reader_thread, daemon=True)
t.start()

# Wait for buffer to fill before starting
while len(buffer) < BUFFER_SIZE:
    time.sleep(0.01)

current_zoom = None
CHANGE_THRESHOLD = 0.5

# ── Main loop — just reads median and prints changes ─────────────────────────
while True:
    zoom = get_median()

    if zoom is not None:
        if current_zoom is None or abs(zoom - current_zoom) >= CHANGE_THRESHOLD:
            current_zoom = zoom
            print(f"Zoom: {current_zoom:.2f}x")

    time.sleep(0.03)   # check for changes every 30ms