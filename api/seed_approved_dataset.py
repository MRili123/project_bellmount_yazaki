#!/usr/bin/env python
"""
Seed approved captures for the dataset
"""

import sys
sys.path.insert(0, '.')

from database import SessionLocal, init_db
from models import Capture, User, Machine, Switch, MeasurementStatus, CaptureMethod
from datetime import datetime, timedelta
import uuid

def seed_approved_captures():
    init_db()
    db = SessionLocal()

    try:
        print("Creating approved captures for dataset...")

        # Get first machine and switch
        machine = db.query(Machine).first()
        if not machine:
            print("[ERROR] No machines found. Run seed_db.py first.")
            return

        switches = db.query(Switch).filter(Switch.machine_id == machine.id).all()
        if not switches:
            print("[ERROR] No switches found for machine.")
            return

        # Get first annoteur
        annoteur = db.query(User).filter(User.role == "annoteur").first()
        if not annoteur:
            print("[ERROR] No annoteur found. Run seed_db.py first.")
            return

        switch = switches[0]

        # Create 5 approved captures
        for i in range(5):
            capture = Capture(
                id=str(uuid.uuid4()),
                machine_id=machine.id,
                switch_id=switch.id,
                annoteur_id=annoteur.id,
                image_original_path=f"/path/to/original_{i}.jpg",
                image_thresholded_path=f"/path/to/thresholded_{i}.jpg",
                p1_x=100 + (i * 10),
                p1_y=200 + (i * 5),
                p2_x=300 + (i * 10),
                p2_y=200 + (i * 5),
                measured_distance_mm=10.5 + (i * 0.1),
                zoom_level=1.0,
                capture_method=CaptureMethod.manual,
                measurement_status=MeasurementStatus.okay,
                delta_mm=0.2 + (i * 0.05),
                annoteur_approved=True,
                in_training_dataset=True,
                quality_score=0.95 - (i * 0.02),
                created_at=datetime.utcnow() - timedelta(days=5-i)
            )
            db.add(capture)
            print(f"  Added capture {i+1}/5")

        db.commit()

        # Verify
        count = db.query(Capture).count()
        print(f"[OK] Created {count} approved captures in dataset!")

    except Exception as e:
        print(f"[ERROR] Error seeding approved captures: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_approved_captures()
