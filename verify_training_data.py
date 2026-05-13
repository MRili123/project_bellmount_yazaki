import json
import cv2
import numpy as np
from pathlib import Path

anno_file = Path(r"C:\Users\ilias\OneDrive\Desktop\bellmounth project\model_bellmounth_mesure\dataset\annotations.json")
data = json.loads(anno_file.read_text())

print(f"Total annotations: {len(data)}\n")

# Check first 5 images
for i in range(min(5, len(data))):
    entry = data[i]
    thresh_path = Path(entry.get("thresholded_path", ""))

    if not thresh_path.exists():
        print(f"[{i}] ❌ Thresholded image NOT FOUND: {thresh_path}")
        continue

    img = cv2.imread(str(thresh_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"[{i}] ❌ Failed to load image")
        continue

    w, h = entry["width"], entry["height"]
    pts = entry["points"]

    p1 = pts[0]
    p2 = pts[1]

    print(f"[{i}] {entry['filename']}")
    print(f"    Image size: {w}×{h}")
    print(f"    P1: ({p1['x']}, {p1['y']})")
    print(f"    P2: ({p2['x']}, {p2['y']})")
    print(f"    Distance: {np.linalg.norm(np.array([p1['x']-p2['x'], p1['y']-p2['y']])):.1f} px")

    # Check if coordinates are within bounds
    if p1['x'] < 0 or p1['x'] > w or p1['y'] < 0 or p1['y'] > h:
        print(f"    ⚠️  P1 OUT OF BOUNDS!")
    if p2['x'] < 0 or p2['x'] > w or p2['y'] < 0 or p2['y'] > h:
        print(f"    ⚠️  P2 OUT OF BOUNDS!")

    # Visualize
    vis = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    cv2.circle(vis, (p1['x'], p1['y']), 5, (0, 255, 0), -1)
    cv2.circle(vis, (p2['x'], p2['y']), 5, (255, 0, 0), -1)
    cv2.line(vis, (p1['x'], p1['y']), (p2['x'], p2['y']), (0, 0, 255), 2)

    # Save visualization
    out_path = Path(f"test_viz_{i}.png")
    cv2.imwrite(str(out_path), vis)
    print(f"    ✓ Saved visualization to: {out_path}\n")

print("Done! Check the test_viz_*.png files to see if points are on the cable.")
