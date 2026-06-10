"""
Comprehensive Seeder for Approved Dataset

Seeds both MESURE and STATE datasets into the approved database:
1. MESURE Dataset - Cable measurement annotations (keypoint detection training)
2. STATE Dataset - Cable state classifications (cable state detection training)

Loads from: model_bellmounth_mesure/dataset/annotations.json
"""

import json
import uuid
import random
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, str(Path(__file__).parent / "api"))

from models import Capture, User, Machine, Switch, CableState, CaptureMethod, MeasurementStatus, StateAnnotation
from database import DATABASE_URL

DATASET_DIR = Path(__file__).parent / "model_bellmounth_mesure" / "dataset"
ANNOTATIONS_FILE = DATASET_DIR / "annotations.json"
MM_PER_PIXEL = 0.0165
ZOOM_MIN, ZOOM_MAX = 1.0, 40.0

CABLE_STATES = [CableState.no_cable, CableState.cable_male, CableState.cable_good]

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

def seed_approved_dataset():
    """Seed both MESURE and STATE datasets"""

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        # Load annotations
        annotations = load_annotations()
        if not annotations:
            print("❌ No annotations to seed")
            return

        print(f"📋 Loaded {len(annotations)} annotations\n")

        # Get or create default machine & switch
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
            print(f"✅ Created default machine")

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
            print(f"✅ Created default switch\n")

        # Get or create annoteurs
        annoteurs = db.query(User).filter(User.role == "annoteur").all()
        if not annoteurs:
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
            print(f"✅ Created {len(annoteurs)} annoteur users\n")

        print(f"📊 Starting dataset seeding...\n")

        # Cache existing paths (skip model_type check since DB schema may not have it yet)
        try:
            existing_mesure = set(p[0] for p in db.query(Capture.image_original_path).all())
        except:
            existing_mesure = set()

        try:
            existing_state = set(p[0] for p in db.query(StateAnnotation.image_path).all())
        except:
            existing_state = set()

        mesure_created = 0
        state_created = 0
        skipped = 0

        for i, annotation in enumerate(annotations, 1):
            try:
                orig_path = annotation.get('original_path', '')
                if not orig_path:
                    skipped += 1
                    continue

                # MESURE DATASET - Cable measurement
                if orig_path not in existing_mesure:
                    points = annotation.get('points', [])
                    p1 = next((p for p in points if p.get('label') == 'point_1'), None)
                    p2 = next((p for p in points if p.get('label') == 'point_2'), None)

                    if p1 and p2:
                        pixel_distance = annotation.get('pixel_distance', 0)
                        measured_distance_mm = pixel_distance * MM_PER_PIXEL

                        capture = Capture(
                            id=str(uuid.uuid4()),
                            machine_id=machine.id,
                            switch_id=switch.id,
                            annoteur_id=random.choice(annoteurs).id,
                            image_original_path=orig_path,
                            image_thresholded_path=annotation.get('thresholded_path', ''),
                            p1_x=int(p1.get('x', 0)),
                            p1_y=int(p1.get('y', 0)),
                            p2_x=int(p2.get('x', 0)),
                            p2_y=int(p2.get('y', 0)),
                            measured_distance_mm=measured_distance_mm,
                            zoom_level=round(random.uniform(ZOOM_MIN, ZOOM_MAX), 2),
                            capture_method=CaptureMethod.manual,
                            measurement_status=MeasurementStatus.okay,
                            delta_mm=0.0,
                            annoteur_approved=True,
                            in_training_dataset=True,
                            quality_score=0.95
                        )
                        db.add(capture)
                        mesure_created += 1

                # STATE DATASET - Cable state classification
                if orig_path not in existing_state:
                    state_annotation = StateAnnotation(
                        id=str(uuid.uuid4()),
                        annoteur_id=random.choice(annoteurs).id,
                        image_path=orig_path,
                        cable_state=random.choice(CABLE_STATES),
                        in_training_dataset=True
                    )
                    db.add(state_annotation)
                    state_created += 1

                if i % 100 == 0:
                    print(f"  ⏳ Processed {i}/{len(annotations)} annotations...")

            except Exception as e:
                print(f"❌ Error on annotation {i}: {e}")
                skipped += 1
                continue

        # Commit all changes
        db.commit()

        print(f"\n✅ Seeding complete!")
        print(f"   📏 MESURE dataset:  {mesure_created} captures")
        print(f"   🎯 STATE dataset:   {state_created} annotations")
        print(f"   ⏭️  Skipped:        {skipped}")
        print(f"   📊 Total processed: {len(annotations)}")

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🌱 Seeding approved dataset (MESURE + STATE)...\n")
    seed_approved_dataset()
    print("\n✨ Done!")
