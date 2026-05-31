from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from database import init_db, get_db
from routers import auth, switches, captures, admin
from models import Notification
from sqlalchemy.orm import Session

load_dotenv()

# Initialize database
init_db()

app = FastAPI(
    title="Bellmounth API",
    description="Multi-user cable measurement system",
    version="2.0.0"
)

# CORS configuration
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(switches.router)
app.include_router(captures.router)
app.include_router(admin.router)

# Notifications endpoint
@app.get("/notifications/")
def get_notifications(db: Session = Depends(get_db)):
    """Get all notifications"""
    from models import User
    from sqlalchemy import join

    notifications = db.query(Notification, User.username).join(
        User, Notification.user_id == User.id, isouter=True
    ).order_by(Notification.created_at.desc()).all()

    return [
        {
            "id": n[0].id,
            "notification_type": n[0].notification_type,
            "title": n[0].title,
            "body": n[0].body,
            "read": n[0].read,
            "username": n[1] or "Unknown",
            "created_at": n[0].created_at.isoformat() if n[0].created_at else None,
        }
        for n in notifications
    ]

@app.post("/notifications/reply")
def send_notification_reply(data: dict, db: Session = Depends(get_db)):
    """Send a reply to a notification (creates new notification for owner)"""
    try:
        # Get all admins to notify
        from models import User, UserRole
        admins = db.query(User).filter(User.role == UserRole.admin).all()

        if not admins:
            return {"ok": False, "error": "No admin to notify"}

        # Create reply notification for each admin
        for admin in admins:
            reply_notification = Notification(
                id=str(__import__('uuid').uuid4()),
                user_id=admin.id,
                notification_type="reply",
                title=f"Reply to: {data.get('notification_title', 'Notification')}",
                body=f"{data.get('replied_by', 'Unknown')}: {data.get('reply_content', '')}",
                read=False
            )
            db.add(reply_notification)

        db.commit()
        return {"ok": True, "message": "Reply sent successfully"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}

@app.get("/")
def root():
    return {
        "message": "Bellmounth API v2.0",
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    api_port = int(os.getenv("API_PORT", 8000))
    api_host = os.getenv("API_HOST", "0.0.0.0")
    uvicorn.run(app, host=api_host, port=api_port)
