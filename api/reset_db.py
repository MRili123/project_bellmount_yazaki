#!/usr/bin/env python
"""
Reset the Bellmounth database to a clean starting state.

DROPS EVERY TABLE (all users, captures, measurements — everything), recreates
the schema from models.py, then seeds:
  - admin user            admin / admin123
  - the mesure model      registered in keypoint_models (file stays local)
  - example annoteurs     annoteur_01, annoteur_02 / password123
  - example machines      LAB-01, LAB-02 / bellmounth (+ their switches)

Points at whatever DATABASE_URL says (.env) — cloud or local.

Usage:
    py -3.11 reset_db.py --yes
"""

import sys

sys.path.insert(0, '.')

from database import engine, SessionLocal, Base, init_db
from models import User, Machine, Switch, UserRole, KeypointModel
from auth import hash_password


def drop_everything():
    """users<->machines reference each other, so plain drop_all can't order the
    drops. On SQL Server: drop every FK constraint first, then every table."""
    from sqlalchemy import text
    if engine.dialect.name == "mssql":
        with engine.begin() as conn:
            fk_drops = conn.execute(text(
                "SELECT 'ALTER TABLE ' + QUOTENAME(OBJECT_SCHEMA_NAME(parent_object_id))"
                " + '.' + QUOTENAME(OBJECT_NAME(parent_object_id))"
                " + ' DROP CONSTRAINT ' + QUOTENAME(name) FROM sys.foreign_keys"
            )).fetchall()
            for (stmt,) in fk_drops:
                conn.execute(text(stmt))
            tables = conn.execute(text("SELECT name FROM sys.tables")).fetchall()
            for (table,) in tables:
                conn.execute(text(f"DROP TABLE [{table}]"))
    else:
        Base.metadata.drop_all(bind=engine)


def seed_defaults(db):
    """Insert the standard starting data into an empty database. Used by the
    app's startup schema check (server_config.py) and by this reset script."""
    admin = User(
        username="admin",
        password_hash=hash_password("admin123"),
        role=UserRole.admin,
        email="admin@bellmounth.local",
        is_active=True,
    )
    db.add(admin)

    for name in ("annoteur_01", "annoteur_02"):
        db.add(User(
            username=name,
            password_hash=hash_password("password123"),
            role=UserRole.annoteur,
            email=f"{name}@bellmounth.local",
            is_active=True,
        ))
    db.commit()

    machine1 = Machine(machine_name="LAB-01",
                       password_hash=hash_password("bellmounth"),
                       location="Factory 1", firmware_version="1.0.0")
    machine2 = Machine(machine_name="LAB-02",
                       password_hash=hash_password("bellmounth"),
                       location="Factory 2", firmware_version="1.0.0")
    db.add_all([machine1, machine2])
    db.commit()

    db.add_all([
        Switch(machine_id=machine1.id, switch_name="Standard Cable",
               expected_diameter_mm=10.5, tolerance_min=10.0,
               tolerance_max=11.0, cable_type="Standard"),
        Switch(machine_id=machine1.id, switch_name="Reinforced Cable",
               expected_diameter_mm=12.0, tolerance_min=11.5,
               tolerance_max=12.5, cable_type="Reinforced"),
        Switch(machine_id=machine2.id, switch_name="Coaxial Cable",
               expected_diameter_mm=15.0, tolerance_min=14.5,
               tolerance_max=15.5, cable_type="Coaxial"),
    ])

    # Register the measurement model. The .h5 file itself ships with the app
    # (models/mesure/CNN_BELMOUNTH_MODEL_V1.h5) — this row is the registry
    # the admin panel shows.
    db.add(KeypointModel(
        version="CNN_BELMOUNTH_MODEL_V1",
        deployed_to_machines=[machine1.id, machine2.id],
    ))
    db.commit()


def reset_db():
    print("Dropping all tables...")
    drop_everything()

    print("Recreating schema (tables + relations)...")
    init_db()

    db = SessionLocal()
    try:
        print("Seeding starter data...")
        seed_defaults(db)
        print()
        print("[OK] Database reset complete!")
        print("=" * 60)
        print("Admin:      admin / admin123")
        print("Annoteurs:  annoteur_01, annoteur_02 / password123")
        print("Machines:   LAB-01, LAB-02 / bellmounth")
        print("Model:      CNN_BELMOUNTH_MODEL_V1 (registered, file stays local)")
        print("=" * 60)
    except Exception as e:
        print(f"[ERROR] {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if "--yes" not in sys.argv:
        print("This DELETES ALL DATA in the database pointed at by DATABASE_URL")
        print("and replaces it with the starter data. To confirm, run:")
        print("    py -3.11 reset_db.py --yes")
        sys.exit(1)
    reset_db()
