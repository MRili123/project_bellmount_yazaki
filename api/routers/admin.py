from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
import uuid
from database import get_db
from models import User, Machine, Switch, Capture, UserRole
from schemas import (
    UserCreate, UserUpdate, UserResponse,
    MachineCreate, MachineFullResponse,
    SwitchCreate, SwitchUpdate, SwitchResponse,
    CaptureAdminResponse, AssignCaptureRequest
)
from auth import hash_password
from fastapi import Depends

router = APIRouter(prefix="/admin", tags=["admin"])

# ==================== USERS ====================

@router.get("/users", response_model=List[UserResponse])
def get_users(role: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Get all users, optionally filtered by role"""
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    return query.all()

@router.post("/users", response_model=UserResponse)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(400, "Username already taken")

    user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        password_hash=hash_password(body.password),
        email=body.email,
        role=body.role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, body: UserUpdate, db: Session = Depends(get_db)):
    """Update a user (partial update - only non-None fields)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        user.role = body.role
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.email is not None:
        user.email = body.email

    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    """Delete a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    db.delete(user)
    db.commit()
    return {"status": "deleted", "user_id": user_id}

# ==================== MACHINES ====================

@router.get("/machines", response_model=List[MachineFullResponse])
def get_machines(db: Session = Depends(get_db)):
    """Get all machines"""
    return db.query(Machine).all()

@router.post("/machines", response_model=MachineFullResponse)
def create_machine(body: MachineCreate, db: Session = Depends(get_db)):
    """Create a new machine"""
    existing = db.query(Machine).filter(Machine.machine_name == body.machine_name).first()
    if existing:
        raise HTTPException(400, "Machine name already exists")

    machine = Machine(
        id=str(uuid.uuid4()),
        machine_name=body.machine_name,
        password_hash=hash_password(body.password),
        location=body.location,
        firmware_version=body.firmware_version,
        is_connected=False
    )
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine

@router.delete("/machines/{machine_id}")
def delete_machine(machine_id: str, db: Session = Depends(get_db)):
    """Delete a machine"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(404, "Machine not found")

    db.delete(machine)
    db.commit()
    return {"status": "deleted", "machine_id": machine_id}

# ==================== SWITCHES ====================

@router.post("/switches", response_model=SwitchResponse)
def create_switch(body: SwitchCreate, db: Session = Depends(get_db)):
    """Create a new switch"""
    switch = Switch(
        id=str(uuid.uuid4()),
        switch_name=body.switch_name,
        expected_diameter_mm=body.expected_diameter_mm,
        tolerance_min=body.tolerance_min,
        tolerance_max=body.tolerance_max,
        cable_type=body.cable_type,
        assigned_machines=[]
    )
    db.add(switch)
    db.commit()
    db.refresh(switch)
    return switch

@router.put("/switches/{switch_id}", response_model=SwitchResponse)
def update_switch(switch_id: str, body: SwitchUpdate, db: Session = Depends(get_db)):
    """Update a switch (partial update)"""
    switch = db.query(Switch).filter(Switch.id == switch_id).first()
    if not switch:
        raise HTTPException(404, "Switch not found")

    if body.switch_name is not None:
        switch.switch_name = body.switch_name
    if body.expected_diameter_mm is not None:
        switch.expected_diameter_mm = body.expected_diameter_mm
    if body.tolerance_min is not None:
        switch.tolerance_min = body.tolerance_min
    if body.tolerance_max is not None:
        switch.tolerance_max = body.tolerance_max
    if body.cable_type is not None:
        switch.cable_type = body.cable_type

    db.commit()
    db.refresh(switch)
    return switch

@router.delete("/switches/{switch_id}")
def delete_switch(switch_id: str, db: Session = Depends(get_db)):
    """Delete a switch"""
    switch = db.query(Switch).filter(Switch.id == switch_id).first()
    if not switch:
        raise HTTPException(404, "Switch not found")

    db.delete(switch)
    db.commit()
    return {"status": "deleted", "switch_id": switch_id}

# ==================== CAPTURES ====================

@router.get("/captures", response_model=List[CaptureAdminResponse])
def get_captures(status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Get all captures, optionally filtered by status (pending|assigned|approved)"""
    query = db.query(Capture)

    if status == "pending":
        query = query.filter(Capture.annoteur_id == None)
    elif status == "assigned":
        query = query.filter(
            (Capture.annoteur_id != None) & (Capture.annoteur_approved == False)
        )
    elif status == "approved":
        query = query.filter(Capture.annoteur_approved == True)

    return query.all()

@router.put("/captures/{capture_id}/assign", response_model=CaptureAdminResponse)
def assign_capture(capture_id: str, body: AssignCaptureRequest, db: Session = Depends(get_db)):
    """Assign a capture to an annoteur"""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(404, "Capture not found")

    annoteur = db.query(User).filter(User.id == body.annoteur_id).first()
    if not annoteur or annoteur.role != "annoteur":
        raise HTTPException(400, "Invalid annoteur_id - user must have annoteur role")

    capture.annoteur_id = body.annoteur_id
    db.commit()
    db.refresh(capture)
    return capture
