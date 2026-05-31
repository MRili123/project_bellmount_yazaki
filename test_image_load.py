#!/usr/bin/env python
"""
Test if images can be loaded and displayed.
"""

from PIL import Image
from pathlib import Path

dataset_path = Path(__file__).parent / "model_bellmounth_mesure" / "dataset"

images = [
    "capture_20260427_081507_737.png",
    "capture_20260427_081510_785.png"
]

for img_name in images:
    orig_path = dataset_path / "original" / img_name
    thresh_path = dataset_path / "thresholded" / img_name

    print(f"\n{'='*60}")
    print(f"Testing: {img_name}")
    print(f"{'='*60}")

    # Check original
    print(f"\n📸 Original Image:")
    print(f"Path: {orig_path}")
    print(f"Exists: {orig_path.exists()}")

    if orig_path.exists():
        try:
            img = Image.open(str(orig_path))
            print(f"✅ Can open: YES")
            print(f"Size: {img.size}")
            print(f"Format: {img.format}")
            print(f"Mode: {img.mode}")
        except Exception as e:
            print(f"❌ Can open: NO - {e}")

    # Check thresholded
    print(f"\n📸 Thresholded Image:")
    print(f"Path: {thresh_path}")
    print(f"Exists: {thresh_path.exists()}")

    if thresh_path.exists():
        try:
            img = Image.open(str(thresh_path))
            print(f"✅ Can open: YES")
            print(f"Size: {img.size}")
            print(f"Format: {img.format}")
            print(f"Mode: {img.mode}")
        except Exception as e:
            print(f"❌ Can open: NO - {e}")

print(f"\n{'='*60}")
print("Test complete!")
print(f"{'='*60}")
