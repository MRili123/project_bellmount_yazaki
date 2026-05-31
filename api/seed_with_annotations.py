#!/usr/bin/env python
"""
Seed test captures using real annotations from annotations.json
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import json

def seed_captures():
    db_path = Path(__file__).parent / "bellmounth.db"
    annotations_file = Path(__file__).parent.parent / "model_bellmounth_mesure" / "dataset" / "annotations.json"

    if not db_path.exists():
        print("❌ Database not found. Make sure to run seed_db.py first.")
        return

    if not annotations_file.exists():
        print("❌ Annotations file not found")
        return

    try:
        with open(annotations_file, 'r') as f:
            annotations = json.load(f)
    except Exception as e:
        print(f"❌ Error reading annotations: {e}")
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

        # Delete old test captures
        cursor.execute("DELETE FROM captures WHERE annoteur_id = ?", (annoteur_id,))

        # Take first 5 annotations with real coordinates
        for idx, annotation in enumerate(annotations[:5]):
            capture_id = str(uuid.uuid4())

            # Get real coordinates from annotation
            points = annotation.get('points', [])
            if len(points) < 2:
                print(f"⚠️  Skipping {annotation['filename']} - missing points")
                continue

            p1_x = int(points[0].get('x', 0))
            p1_y = int(points[0].get('y', 0))
            p2_x = int(points[1].get('x', 0))
            p2_y = int(points[1].get('y', 0))

            # Get image paths
            orig_path = annotation.get('original_path', '')
            thresh_path = annotation.get('thresholded_path', '')

            # Calculate pixel distance
            pixel_dist = ((p2_x - p1_x)**2 + (p2_y - p1_y)**2)**0.5

            # Estimate mm distance (using 0.0165 mm/pixel)
            measured_distance_mm = round(pixel_dist * 0.0165, 2)

            # Zoom levels: 2x, 3x, 4x, 5x, 6x (test data)
            zoom_level = 2.0 + (idx % 5)

            now = datetime.utcnow() - timedelta(hours=5-idx)

            cursor.execute("""
                INSERT INTO captures (
                    id, machine_id, switch_id, annoteur_id,
                    image_original_path, image_thresholded_path,
                    p1_x, p1_y, p2_x, p2_y,
                    measured_distance_mm, zoom_level, capture_method, measurement_status,
                    delta_mm, annoteur_approved, in_training_dataset,
                    quality_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                capture_id, machine_id, switch_id, annoteur_id,
                orig_path, thresh_path,
                p1_x, p1_y, p2_x, p2_y,
                measured_distance_mm,
                zoom_level,
                "manual",
                "okay",
                0.1,
                0,  # annoteur_approved = False
                0,  # in_training_dataset = False
                0.95,
                now.isoformat()
            ))
            print(f"✅ Capture {idx+1}: {annotation['filename']}")
            print(f"   P1: ({p1_x}, {p1_y}) → P2: ({p2_x}, {p2_y})")
            print(f"   Distance: {measured_distance_mm}mm | Zoom: {zoom_level:.1f}x")

        conn.commit()
        print("\n✅ Test captures created with real annotations!")
        print(f"Annoteur ID: {annoteur_id}")
        print("\nThey will appear in the REQUESTS section as pending approvals.")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_captures()
