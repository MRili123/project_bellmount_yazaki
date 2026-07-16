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

# Initialize database: create tables, then seed default data if it's empty.
# Doing this server-side means a fresh/empty database becomes usable without
# the desktop app ever connecting to SQL directly.
init_db()
try:
    from database import SessionLocal
    from reset_db import seed_defaults
    _seed_db = SessionLocal()
    try:
        if _seed_db.query(User).count() == 0:
            seed_defaults(_seed_db)
            print("Empty database detected on startup — seeded default data.")
    finally:
        _seed_db.close()
except Exception as _seed_err:
    print(f"Startup seed check skipped: {_seed_err}")

app = FastAPI(
    title="Bellmounth API",
    description="Multi-user cable measurement system",
    version="2.0.0"
)

# Endpoints reachable WITHOUT a login token. Everything else is protected.
PUBLIC_PATHS = {
    "/",
    "/auth/login",
    "/auth/health",
    "/health/db",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Require a valid login token on every non-public endpoint.

    This is the door lock for the whole API: without it, anyone who knows the
    server URL could read or modify data without logging in. Public paths (login,
    health, docs) are exempt; CORS preflight (OPTIONS) is always allowed.
    """
    path = request.url.path
    if request.method == "OPTIONS" or path in PUBLIC_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    token = auth_header[len("Bearer "):].strip()

    from auth import JWT_SECRET, JWT_ALGORITHM
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=401, content={"detail": "Session expired, please log in again"})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=401, content={"detail": "Invalid authentication token"})

    # Reject tokens whose account has since been deactivated.
    user_id = payload.get("sub")
    if user_id:
        db = next(get_db())
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user and not user.is_active:
                return JSONResponse(status_code=403, content={"detail": "Your account is deactivated"})
            machine = db.query(Machine).filter(Machine.id == user_id).first()
            if machine and not machine.is_active:
                return JSONResponse(status_code=403, content={"detail": "Your account is deactivated"})
        finally:
            db.close()

    return await call_next(request)

# CORS configuration. Desktop clients aren't subject to CORS, but a web frontend
# would be — so allow overriding the allowed origins via the CORS_ORIGINS env var
# (comma-separated). Defaults to localhost for development.
_default_origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]
_env_origins = os.getenv("CORS_ORIGINS", "")
origins = [o.strip() for o in _env_origins.split(",") if o.strip()] or _default_origins

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


@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """Public health check for the database and schema, verified server-side.

    The desktop app calls this instead of connecting to Azure SQL directly, so
    it works from any PC/network without SQL firewall changes. Reports whether
    every expected table exists and how many users/tables are present.
    """
    from sqlalchemy import inspect
    from database import Base, engine

    expected = set(Base.metadata.tables.keys())
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = sorted(expected - existing)

    users = db.query(User).count() if not missing else 0
    return {
        "ok": len(missing) == 0,
        "tables_expected": len(expected),
        "tables_present": len(existing & expected),
        "missing_tables": missing,
        "users": users,
    }

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
        from models import User, UserRole
        import uuid

        machine_name = data.get("machine_name", "Unknown machine")
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        category = data.get("category", "other")

        if not title or not description:
            return {"ok": False, "error": "Title and description are required"}

        # The report goes TO the admins. notifications.user_id is a foreign key
        # to users.id (the recipient) — a machine id is NOT a valid user id, so
        # create one notification per admin, with the machine named in the body.
        admins = db.query(User).filter(User.role == UserRole.admin).all()
        if not admins:
            return {"ok": False, "error": "No admin to notify"}

        for admin in admins:
            db.add(Notification(
                id=str(uuid.uuid4()),
                user_id=admin.id,
                notification_type="reclamation",
                title=f"🛠 Report ({machine_name}): {title}",
                body=f"""Machine: {machine_name}
Category: {category}
Subject: {title}

{description}""",
                read=False,
            ))
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
