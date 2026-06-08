#!/usr/bin/env python
import sqlite3
import uuid
from datetime import datetime, timedelta

conn = sqlite3.connect('api/bellmounth.db')
cursor = conn.cursor()

# Get first machine, switch, and annoteur
cursor.execute("SELECT id FROM machines LIMIT 1")
machine_id = cursor.fetchone()[0]

cursor.execute("SELECT id FROM switches WHERE machine_id = ? LIMIT 1", (machine_id,))
switch_id = cursor.fetchone()[0]

cursor.execute("SELECT id FROM users WHERE role = 'annoteur' LIMIT 1")
annoteur_id = cursor.fetchone()[0]

print(f"Machine: {machine_id}")
print(f"Switch: {switch_id}")
print(f"Annoteur: {annoteur_id}")

# Insert 5 approved captures
for i in range(5):
    capture_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO captures (
            id, machine_id, switch_id, annoteur_id,
            image_original_path, image_thresholded_path,
            p1_x, p1_y, p2_x, p2_y,
            measured_distance_mm, zoom_level,
            capture_method, measurement_status,
            delta_mm, annoteur_approved, in_training_dataset,
            quality_score, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        capture_id, machine_id, switch_id, annoteur_id,
        f"/path/to/original_{i}.jpg", f"/path/to/thresholded_{i}.jpg",
        100 + (i * 10), 200 + (i * 5), 300 + (i * 10), 200 + (i * 5),
        10.5 + (i * 0.1), 1.0,
        "manual", "okay",
        0.2 + (i * 0.05), 1, 1,
        0.95 - (i * 0.02),
        (datetime.utcnow() - timedelta(days=5-i)).isoformat()
    ))
    print(f"Inserted capture {i+1}/5: {capture_id[:8]}...")

conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM captures")
count = cursor.fetchone()[0]
print(f"\nTotal captures in database: {count}")

cursor.execute("SELECT COUNT(*) FROM captures WHERE annoteur_approved = 1")
approved = cursor.fetchone()[0]
print(f"Approved captures: {approved}")

conn.close()
