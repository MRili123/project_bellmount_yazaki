#!/usr/bin/env python
"""
Seed dummy notifications for testing the notifications UI.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import uuid

def seed_notifications():
    db_path = Path(__file__).parent / "bellmounth.db"

    if not db_path.exists():
        print("❌ Database not found. Make sure to run seed_db.py first.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Get admin user ID
        cursor.execute("SELECT id FROM users WHERE role='admin' LIMIT 1")
        admin = cursor.fetchone()

        if not admin:
            print("❌ No admin user found")
            return

        admin_id = admin[0]

        # Delete old test notifications
        cursor.execute("DELETE FROM notifications WHERE user_id = ?", (admin_id,))

        # Sample notifications with different types
        notifications = [
            {
                "type": "info",
                "title": "New Capture Request",
                "body": "5 new captures are waiting for annotation review. Please check the REQUESTS section.",
                "read": False,
            },
            {
                "type": "warning",
                "title": "Low Quality Captures",
                "body": "Machine LAB-01 has produced 3 low-quality captures. Quality score below 0.7. Review recommended.",
                "read": False,
            },
            {
                "type": "success",
                "title": "Dataset Updated",
                "body": "15 new approved captures added to the training dataset. Ready for model training.",
                "read": True,
            },
            {
                "type": "alert",
                "title": "Machine Connection Lost",
                "body": "Machine LAB-02 has disconnected. Last seen 2 hours ago. Please check the connection.",
                "read": False,
            },
            {
                "type": "info",
                "title": "Annoteur Performance Report",
                "body": "Weekly performance report is ready. annoteur_01 has reviewed 42 captures with 98% accuracy.",
                "read": True,
            },
            {
                "type": "warning",
                "title": "Switch Configuration Change",
                "body": "Switch 'Standard Cable' tolerance limits were updated. Affects 23 pending captures.",
                "read": False,
            },
            {
                "type": "success",
                "title": "Model Training Complete",
                "body": "CNN model training finished successfully. Accuracy: 96.2%. Ready for deployment.",
                "read": True,
            },
            {
                "type": "info",
                "title": "System Maintenance Scheduled",
                "body": "Database maintenance scheduled for tomorrow at 2:00 AM. Expected downtime: 30 minutes.",
                "read": False,
            },
        ]

        for idx, notif in enumerate(notifications):
            notif_id = str(uuid.uuid4())
            now = datetime.utcnow() - timedelta(hours=8-idx)

            cursor.execute("""
                INSERT INTO notifications (
                    id, user_id, notification_type, title, body, read, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                notif_id,
                admin_id,
                notif["type"],
                notif["title"],
                notif["body"],
                1 if notif["read"] else 0,
                now.isoformat()
            ))

            status = "✓ READ" if notif["read"] else "● NEW"
            print(f"✅ {status} - {notif['title']}")

        conn.commit()
        print(f"\n✅ {len(notifications)} test notifications created!")
        print(f"Admin ID: {admin_id}")
        print("\nThey will appear in the NOTIFICATIONS section.")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_notifications()
