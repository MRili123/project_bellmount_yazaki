#!/usr/bin/env python
"""
Seed test capture data to display in requests section.
Uses real images from the dataset folder.
"""

import sys
sys.path.insert(0, '.')

from database import SessionLocal, init_db
from models import Capture, Machine, Switch, User
from datetime import datetime, timedelta
from pathlib import Path
import random

def seed_test_captures():
    init_db()
    db = SessionLocal()

    try:
        # Get first annoteur and machine
        annoteur = db.query(User).filter(User.role == "annoteur").first()
        machine = db.query(Machine).first()
        switch = db.query(Switch).first()

        if not annoteur or not machine or not switch:
            print("❌ Error: Missing required data (annoteur, machine, or switch)")
            return

        # Find available images
        dataset_path = Path(__file__).parent.parent / "model_bellmounth_mesure" / "dataset"
        original_dir = dataset_path / "original"
        thresholded_dir = dataset_path / "thresholded"

        original_images = sorted(list(original_dir.glob("*.png")))[:5]

        if not original_images:
            print("❌ No images found in dataset folder")
            return

        print(f"📸 Found {len(original_images)} images to create test captures")

        for idx, orig_img in enumerate(original_images):
            # Find corresponding thresholded image
            thresh_img = thresholded_dir / orig_img.name
            if not thresh_img.exists():
                thresh_img = None

            # Create capture record
            capture = Capture(
                machine_id=machine.id,
                switch_id=switch.id,
                annoteur_id=annoteur.id,
                image_original_path=str(orig_img),
                image_thresholded_path=str(thresh_img) if thresh_img else str(orig_img),
                p1_x=random.randint(100, 400),
                p1_y=random.randint(100, 400),
                p2_x=random.randint(100, 400),
                p2_y=random.randint(100, 400),
                measured_distance_mm=round(random.uniform(9.5, 11.5), 2),
                capture_method="auto_cnn" if idx % 2 == 0 else "manual",
                measurement_status="okay" if idx % 3 != 0 else "not_okay",
                delta_mm=round(random.uniform(-0.5, 0.5), 2),
                annoteur_approved=False,  # Mark as pending request
                in_training_dataset=False,
                quality_score=round(random.uniform(0.7, 1.0), 2),
                created_at=datetime.utcnow() - timedelta(hours=random.randint(0, 24))
            )
            db.add(capture)
            print(f"  ✓ Created capture {idx+1}: {orig_img.name}")

        db.commit()
        print("\n✅ Test captures created successfully!")
        print(f"Annoteur: {annoteur.username}")
        print(f"Machine: {machine.machine_name}")
        print(f"Switch: {switch.switch_name}")
        print("\nThey will appear in the REQUESTS section of the admin panel as pending approvals.")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_test_captures()
