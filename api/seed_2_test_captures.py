#!/usr/bin/env python
"""
Create exactly 2 test captures with real images from dataset.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import uuid

def seed():
    db_path = Path(__file__).parent / "bellmounth.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Get first annoteur, machine, switch
        cursor.execute("SELECT id FROM users WHERE role='annoteur' LIMIT 1")
        annoteur = cursor.fetchone()[0]

        cursor.execute("SELECT id FROM machines LIMIT 1")
        machine = cursor.fetchone()[0]

        cursor.execute("SELECT id FROM switches LIMIT 1")
        switch = cursor.fetchone()[0]

        # Delete old test captures
        cursor.execute("DELETE FROM captures WHERE annoteur_id = ?", (annoteur,))

        # 2 real images from dataset
        images = [
            "capture_20260427_081507_737.png",
            "capture_20260427_081510_785.png"
        ]

        dataset_path = Path(__file__).parent.parent / "model_bellmounth_mesure" / "dataset"

        for idx, img_name in enumerate(images):
            orig_path = dataset_path / "original" / img_name
            thresh_path = dataset_path / "thresholded" / img_name

            if not orig_path.exists():
                print(f"❌ {img_name} not found!")
                continue

            capture_id = str(uuid.uuid4())

            # Insert with actual image paths and annotation points
            cursor.execute("""
                INSERT INTO captures (
                    id, machine_id, switch_id, annoteur_id,
                    image_original_path, image_thresholded_path,
                    p1_x, p1_y, p2_x, p2_y,
                    measured_distance_mm, capture_method, measurement_status,
                    delta_mm, annoteur_approved, in_training_dataset,
                    quality_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                capture_id, machine, switch, annoteur,
                str(orig_path), str(thresh_path),
                150 + idx*50, 120 + idx*40,  # P1 points
                320 + idx*50, 280 + idx*40,  # P2 points
                10.5 + idx*0.3,  # distance
                "auto_cnn",
                "okay" if idx == 0 else "not_okay",
                0.2 if idx == 0 else -0.3,  # delta
                0, 0, 0.95,
                datetime.utcnow().isoformat()
            ))

            print(f"✅ Capture {idx+1}: {img_name}")
            print(f"   Original: {orig_path}")
            print(f"   Thresholded: {thresh_path}")
            print(f"   P1: (150, 120) → P2: (320, 280)")
            print()

        conn.commit()
        print("✅ Done! 2 test captures created with real images")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed()
