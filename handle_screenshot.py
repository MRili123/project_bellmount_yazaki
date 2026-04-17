# handle_screenshot.py

import cv2
import os

SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def get_next_index():
    files = [f for f in os.listdir(SCREENSHOT_DIR) if f.startswith("screenshot_")]
    if not files:
        return 1

    nums = []
    for f in files:
        try:
            num = int(f.split("_")[1])
            nums.append(num)
        except:
            pass

    return max(nums) + 1 if nums else 1


def save_screenshot(frame, zoom, mm_per_pixel):
    index = get_next_index()

    # Format values
    zoom_str = f"{zoom:.2f}".replace(".", ",") if zoom else "NA"
    mm_str = f"{mm_per_pixel:.6f}".replace(".", ",") if mm_per_pixel else "NA"

    filename = f"screenshot_{index}_Z{zoom_str}x_{mm_str}mm.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)

    cv2.imwrite(filepath, frame)
    print(f"✅ Screenshot saved: {filepath}")