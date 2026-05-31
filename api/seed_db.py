#!/usr/bin/env python
"""
Seed the SQLite database with test data for development.
Run once before starting the API.
"""

import sys
sys.path.insert(0, '.')

from database import SessionLocal, init_db
from models import User, Machine, Switch, UserRole
from auth import hash_password

def seed_db():
    # Initialize database schema
    init_db()
    db = SessionLocal()

    try:
        # Clear existing data (optional)
        print("Creating test data...")

        # Create machines
        machine1 = Machine(
            machine_name="LAB-01",
            password_hash=hash_password("bellmounth"),
            location="Factory 1",
            firmware_version="1.0.0"
        )
        machine2 = Machine(
            machine_name="LAB-02",
            password_hash=hash_password("bellmounth"),
            location="Factory 2",
            firmware_version="1.0.0"
        )
        db.add(machine1)
        db.add(machine2)
        db.commit()

        # Create annoteur users
        annoteur1 = User(
            username="annoteur_01",
            password_hash=hash_password("password123"),
            role=UserRole.annoteur,
            email="annoteur1@bellmounth.local",
            is_active=True
        )
        annoteur2 = User(
            username="annoteur_02",
            password_hash=hash_password("password123"),
            role=UserRole.annoteur,
            email="annoteur2@bellmounth.local",
            is_active=True
        )
        db.add(annoteur1)
        db.add(annoteur2)
        db.commit()

        # Create admin user
        admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            role=UserRole.admin,
            email="admin@bellmounth.local",
            is_active=True
        )
        db.add(admin)
        db.commit()

        # Create switches
        switch1 = Switch(
            switch_name="Standard Cable",
            expected_diameter_mm=10.5,
            tolerance_min=10.0,
            tolerance_max=11.0,
            cable_type="Standard",
            assigned_machines=[machine1.id, machine2.id]
        )
        switch2 = Switch(
            switch_name="Reinforced Cable",
            expected_diameter_mm=12.0,
            tolerance_min=11.5,
            tolerance_max=12.5,
            cable_type="Reinforced",
            assigned_machines=[machine1.id]
        )
        db.add(switch1)
        db.add(switch2)
        db.commit()

        print("[OK] Database seeded successfully!")
        print("\nTest Credentials:")
        print("=" * 50)
        print("\nMachine Users:")
        print("  Machine: LAB-01, Password: bellmounth")
        print("  Machine: LAB-02, Password: bellmounth")
        print("\nAnnoteur Users:")
        print("  Username: annoteur_01, Password: password123")
        print("  Username: annoteur_02, Password: password123")
        print("\nAdmin User:")
        print("  Username: admin, Password: admin123")
        print("\nSwitches:")
        print("  1. Standard Cable (10.5mm, +/-0.5mm)")
        print("  2. Reinforced Cable (12.0mm, +/-0.5mm)")
        print("=" * 50)
        print("\nAPI Endpoints:")
        print("  POST   /auth/login")
        print("  GET    /switches/")
        print("  POST   /captures/upload")
        print("  GET    /captures/queue?annoteur_id=...")
        print("\nSwagger Docs: http://localhost:8000/docs")

    except Exception as e:
        print(f"[ERROR] Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
