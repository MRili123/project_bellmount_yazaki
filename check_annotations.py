import json
from pathlib import Path

anno_file = Path(r"C:\Users\ilias\OneDrive\Desktop\bellmounth project\model_bellmounth_mesure\dataset\annotations.json")

if not anno_file.exists():
    print("❌ Annotations file not found!")
else:
    data = json.loads(anno_file.read_text())
    print(f"✓ Total annotations: {len(data)}\n")

    if data:
        print("=" * 60)
        print("SAMPLE ANNOTATION (first one):")
        print("=" * 60)
        sample = data[0]
        print(json.dumps(sample, indent=2))

        print("\n" + "=" * 60)
        print("STATISTICS:")
        print("=" * 60)

        # Collect all coordinates
        p1_xs = []
        p1_ys = []
        p2_xs = []
        p2_ys = []

        for entry in data:
            points = entry.get("points", [])
            if len(points) >= 2:
                p1 = points[0]
                p2 = points[1]
                p1_xs.append(p1.get("x", 0))
                p1_ys.append(p1.get("y", 0))
                p2_xs.append(p2.get("x", 0))
                p2_ys.append(p2.get("y", 0))

        if p1_xs:
            print(f"\nP1 X coords: min={min(p1_xs)}, max={max(p1_xs)}, avg={sum(p1_xs)/len(p1_xs):.1f}")
            print(f"P1 Y coords: min={min(p1_ys)}, max={max(p1_ys)}, avg={sum(p1_ys)/len(p1_ys):.1f}")
            print(f"\nP2 X coords: min={min(p2_xs)}, max={max(p2_xs)}, avg={sum(p2_xs)/len(p2_xs):.1f}")
            print(f"P2 Y coords: min={min(p2_ys)}, max={max(p2_ys)}, avg={sum(p2_ys)/len(p2_ys):.1f}")

            # Check if Y is aligned
            p1_y_range = max(p1_ys) - min(p1_ys)
            p2_y_range = max(p2_ys) - min(p2_ys)
            print(f"\nP1 Y variation: {p1_y_range} pixels (should be ~0 if aligned)")
            print(f"P2 Y variation: {p2_y_range} pixels (should be ~0 if aligned)")

            # Check if X varies
            p1_x_range = max(p1_xs) - min(p1_xs)
            p2_x_range = max(p2_xs) - min(p2_xs)
            print(f"\nP1 X variation: {p1_x_range} pixels (should be large)")
            print(f"P2 X variation: {p2_x_range} pixels (should be large)")
