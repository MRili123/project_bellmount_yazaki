#!/usr/bin/env python
"""
Simple seed script using sqlite3 directly.
Adds test captures for the requests section.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import random

def seed_captures():
    db_path = Path(__file__).parent / "bellmounth.db"

    if not db_path.exists():
        print("❌ Database not found. Make sure to seed_db.py first.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Get first annoteur and machine
        cursor.execute("SELECT id FROM users WHERE role='annoteur' LIMIT 1")
        annoteur = cursor.fetchone()

        cursor.execute("SELECT id FROM machines LIMIT 1")
        machine = cursor.fetchone()

        cursor.execute("SELECT id FROM switches LIMIT 1")
        switch = cursor.fetchone()

        if not annoteur or not machine or not switch:
            print("❌ Missing required data (annoteur, machine, or switch)")
            return

        annoteur_id, machine_id, switch_id = annoteur[0], machine[0], switch[0]

        # Find available images
        dataset_path = Path(__file__).parent.parent / "model_bellmounth_mesure" / "dataset"
        original_dir = dataset_path / "original"

        original_images = sorted(list(original_dir.glob("*.png")))[:5]

        if not original_images:
            print("❌ No images found in dataset folder")
            return

        print(f"📸 Found {len(original_images)} images to create test captures")

        for idx, orig_img in enumerate(original_images):
            thresh_img = dataset_path / "thresholded" / orig_img.name

            capture_id = str(uuid.uuid4())
            now = datetime.utcnow() - timedelta(hours=random.randint(0, 24))

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
                capture_id, machine_id, switch_id, annoteur_id,
                str(orig_img), str(thresh_img),
                random.randint(100, 400), random.randint(100, 400),
                random.randint(100, 400), random.randint(100, 400),
                round(random.uniform(9.5, 11.5), 2),
                "auto_cnn" if idx % 2 == 0 else "manual",
                "okay" if idx % 3 != 0 else "not_okay",
                round(random.uniform(-0.5, 0.5), 2),
                0,  # annoteur_approved = False
                0,  # in_training_dataset = False
                round(random.uniform(0.7, 1.0), 2),
                now.isoformat()
            ))
            print(f"  ✓ Created capture {idx+1}: {orig_img.name}")

        conn.commit()
        print("\n✅ Test captures created successfully!")
        print(f"Machine ID: {machine_id}")
        print(f"Annoteur ID: {annoteur_id}")
        print(f"Switch ID: {switch_id}")
        print("\nThey will appear in the REQUESTS section as pending approvals.")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_captures()
