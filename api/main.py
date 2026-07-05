from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
from database import init_db, get_db
from routers import auth, switches, captures, admin
from models import Notification, User, Machine
from sqlalchemy.orm import Session
from auth import verify_token
import jwt

load_dotenv()

# Initialize database
init_db()

app = FastAPI(
    title="Bellmounth API",
    description="Multi-user cable measurement system",
    version="2.0.0"
)

# Middleware to check if user/machine is still active on each request
@app.middleware("http")
async def check_active_status_middleware(request: Request, call_next):
    """Check if authenticated user/machine is still active"""
    # Skip auth check for login and health endpoints
    if request.url.path in ["/auth/login", "/auth/health", "/"]:
        return await call_next(request)

    # Get token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        # No token, let the endpoint handle it
        return await call_next(request)

    token = auth_header.replace("Bearer ", "").strip()

    # Verify token and check active status
    try:
        from auth import JWT_SECRET, JWT_ALGORITHM
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")

        if user_id:
            # Get database session
            db = next(get_db())
            try:
                # Check if it's a user
                user = db.query(User).filter(User.id == user_id).first()
                if user and not user.is_active:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Your account is deactivated"}
                    )

                # Check if it's a machine
                machine = db.query(Machine).filter(Machine.id == user_id).first()
                if machine and not machine.is_active:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Your account is deactivated"}
                    )
            finally:
                db.close()
    except jwt.ExpiredSignatureError:
        pass
    except jwt.InvalidTokenError:
        pass
    except Exception:
        pass

    return await call_next(request)

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

@app.delete("/notifications/{notification_id}")
def delete_notification(notification_id: str, db: Session = Depends(get_db)):
    """Delete a single notification by ID."""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return {"ok": True, "deleted": notification_id}

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

@app.post("/notifications/report")
def submit_machine_report(data: dict, db: Session = Depends(get_db)):
    """Submit an issue report from a machine panel. Creates a notification
    visible to admins in the notification section."""
    try:
        from models import Machine
        import uuid

        machine_name = data.get("machine_name", "Unknown machine")
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        category = data.get("category", "other")

        if not title or not description:
            return {"ok": False, "error": "Title and description are required"}

        # Resolve the machine so the notification is attributed to it.
        machine = db.query(Machine).filter(Machine.machine_name == machine_name).first()

        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=machine.id if machine else None,
            notification_type="reclamation",
            title=f"🛠 Report ({machine_name}): {title}",
            body=f"""Machine: {machine_name}
Category: {category}
Subject: {title}

{description}""",
            read=False,
        )
        db.add(notification)
        db.commit()
        return {"ok": True, "message": "Report submitted"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}

@app.post("/notifications/send-models")
def send_model_update_notifications(data: dict, db: Session = Depends(get_db)):
    """Send model update notification to all machines"""
    try:
        from models import Machine
        import uuid

        machines = db.query(Machine).filter(Machine.is_active == True).all()

        if not machines:
            return {"ok": False, "error": "No active machines to notify"}

        # Get notification type from request (mesure-upload, state-upload, or info)
        notification_type = data.get('notification_type', 'model_update')

        # Map notification types to titles
        type_titles = {
            'mesure-upload': '📊 MESURE Model Update',
            'state-upload': '🔍 STATE Model Update',
            'info': '📦 New Model Update'
        }
        title = type_titles.get(notification_type, '📦 New Model Update')

        # Create notification for each machine
        for machine in machines:
            notification = Notification(
                id=str(uuid.uuid4()),
                user_id=machine.id,
                notification_type=notification_type,
                title=title,
                body=f"""Models updated: {data.get('models', 'MESURE, STATE')}

Download link: {data.get('download_link', '')}

Your machine will automatically download and update when it next connects.""",
                read=False
            )
            db.add(notification)

        db.commit()
        return {"ok": True, "message": f"Notifications sent to {len(machines)} machines"}
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
