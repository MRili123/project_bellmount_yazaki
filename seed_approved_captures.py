"""
Seeder: Load approved dataset from model_bellmounth_mesure into database

Reads annotations.json and creates Capture records with:
- Random annoteur assignment
- Random zoom levels (1.0 - 40.0x)
- Random cable states (for state annotations)
- Marks as approved and in training dataset
"""

import json
import uuid
import random
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import models
import sys
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "api"))

from models import Capture, User, Machine, Switch, CableState, CaptureMethod, MeasurementStatus
from database import DATABASE_URL

# Configuration
DATASET_DIR = Path(__file__).parent / "model_bellmounth_mesure" / "dataset"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
MM_PER_PIXEL = 0.0165  # Default calibration
ZOOM_MIN = 1.0
ZOOM_MAX = 40.0

def load_annotations():
    """Load annotations from JSON file"""
    if not ANNOTATIONS_FILE.exists():
        print(f"❌ Annotations file not found: {ANNOTATIONS_FILE}")
        return []

    try:
        with open(ANNOTATIONS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading annotations: {e}")
        return []

def seed_approved_captures():
    """Seed approved captures into database"""

    # Connect to database
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Load annotations
        annotations = load_annotations()
        if not annotations:
            print("❌ No annotations to seed")
            return

        print(f"📋 Loaded {len(annotations)} annotations")

        # Get or create default machine
        machine = db.query(Machine).filter(Machine.machine_name == "Default Machine").first()
        if not machine:
            machine = Machine(
                id=str(uuid.uuid4()),
                machine_name="Default Machine",
                password_hash="",
                location="Lab",
                firmware_version="1.0",
                zoom_calibration=34.58,
                mm_per_pixel=MM_PER_PIXEL,
                is_connected=True,
                is_active=True
            )
            db.add(machine)
            db.commit()
            print(f"✅ Created default machine: {machine.id}")

        # Get or create default switch
        switch = db.query(Switch).filter(Switch.machine_id == machine.id).first()
        if not switch:
            switch = Switch(
                id=str(uuid.uuid4()),
                machine_id=machine.id,
                switch_name="Default Switch",
                expected_diameter_mm=5.0,
                tolerance_min=4.5,
                tolerance_max=5.5,
                cable_type="Standard"
            )
            db.add(switch)
            db.commit()
            print(f"✅ Created default switch: {switch.id}")

        # Get all annoteur users
        annoteurs = db.query(User).filter(User.role == "annoteur").all()
        if not annoteurs:
            print("⚠️  No annoteur users found. Creating sample annoteurs...")
            for i in range(3):
                annoteur = User(
                    id=str(uuid.uuid4()),
                    username=f"annoteur_{i+1}",
                    password_hash="",
                    role="annoteur",
                    email=f"annoteur{i+1}@bellmounth.local",
                    is_active=True
                )
                db.add(annoteur)
            db.commit()
            annoteurs = db.query(User).filter(User.role == "annoteur").all()
            print(f"✅ Created {len(annoteurs)} annoteur users")

        print(f"👥 Using {len(annoteurs)} annoteurs for random assignment")

        # Seed captures
        cable_states = [CableState.no_cable, CableState.cable_male, CableState.cable_good]
        created_count = 0
        skipped_count = 0

        # Cache existing paths for faster lookup
        existing_paths = set(p[0] for p in db.query(Capture.image_original_path).all())

        for i, annotation in enumerate(annotations, 1):
            try:
                # Check if already exists
                orig_path = annotation.get('original_path', '')
                if not orig_path or orig_path in existing_paths:
                    skipped_count += 1
                    continue

                # Extract points
                points = annotation.get('points', [])
                p1 = next((p for p in points if p.get('label') == 'point_1'), None)
                p2 = next((p for p in points if p.get('label') == 'point_2'), None)

                if not p1 or not p2:
                    print(f"⚠️  Skipping {annotation.get('filename')} - missing points")
                    skipped_count += 1
                    continue

                # Calculate distance in mm
                pixel_distance = annotation.get('pixel_distance', 0)
                measured_distance_mm = pixel_distance * MM_PER_PIXEL

                # Random values
                random_annoteur = random.choice(annoteurs)
                random_zoom = round(random.uniform(ZOOM_MIN, ZOOM_MAX), 2)
                random_state = random.choice(cable_states)

                # Create capture (without model_type - not in current DB schema)
                capture = Capture(
                    id=str(uuid.uuid4()),
                    machine_id=machine.id,
                    switch_id=switch.id,
                    annoteur_id=random_annoteur.id,
                    image_original_path=annotation.get('original_path', ''),
                    image_thresholded_path=annotation.get('thresholded_path', ''),
                    p1_x=int(p1.get('x', 0)),
                    p1_y=int(p1.get('y', 0)),
                    p2_x=int(p2.get('x', 0)),
                    p2_y=int(p2.get('y', 0)),
                    measured_distance_mm=measured_distance_mm,
                    zoom_level=random_zoom,
                    capture_method=CaptureMethod.manual,
                    measurement_status=MeasurementStatus.okay,
                    delta_mm=0.0,
                    annoteur_approved=True,
                    in_training_dataset=True,
                    quality_score=0.95
                )

                db.add(capture)
                created_count += 1

                # Progress indicator
                if i % 50 == 0:
                    print(f"  📦 Processed {i}/{len(annotations)} annotations...")

            except Exception as e:
                print(f"❌ Error processing annotation {i}: {e}")
                skipped_count += 1
                continue

        # Commit all
        db.commit()
        print(f"\n✅ Seeding complete!")
        print(f"   Created: {created_count} approved captures")
        print(f"   Skipped: {skipped_count} (duplicates or errors)")
        print(f"   Total:   {len(annotations)}")

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🌱 Seeding approved captures from dataset...\n")
    seed_approved_captures()
    print("\n✨ Done!")
