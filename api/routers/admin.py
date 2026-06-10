from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel
import uuid
from database import get_db
from models import User, Machine, Switch, Capture, Notification, UserRole
from schemas import (
    UserCreate, UserUpdate, UserResponse,
    MachineCreate, MachineFullResponse, MachineUpdate,
    SwitchCreate, SwitchUpdate, SwitchResponse,
    CaptureAdminResponse, AssignCaptureRequest
)
from auth import hash_password

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

@router.put("/machines/{machine_id}", response_model=MachineFullResponse)
def update_machine(machine_id: str, body: MachineUpdate, db: Session = Depends(get_db)):
    """Update a machine (partial update - only non-None fields)"""
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(404, "Machine not found")

    if body.location is not None:
        machine.location = body.location
    if body.firmware_version is not None:
        machine.firmware_version = body.firmware_version
    if body.is_active is not None:
        machine.is_active = body.is_active

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

@router.get("/switches", response_model=List[SwitchResponse])
def get_switches(machine_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Get all switches, optionally filtered by machine_id"""
    query = db.query(
        Switch.id,
        Switch.machine_id,
        Machine.machine_name,
        Switch.switch_name,
        Switch.expected_diameter_mm,
        Switch.tolerance_min,
        Switch.tolerance_max,
        Switch.cable_type,
        Switch.created_at,
        Switch.updated_at
    ).join(Machine, Switch.machine_id == Machine.id)

    if machine_id:
        query = query.filter(Switch.machine_id == machine_id)

    results = query.all()
    return [
        SwitchResponse(
            id=r[0],
            machine_id=r[1],
            machine_name=r[2],
            switch_name=r[3],
            expected_diameter_mm=r[4],
            tolerance_min=r[5],
            tolerance_max=r[6],
            cable_type=r[7],
            created_at=r[8]
        )
        for r in results
    ]

@router.post("/switches", response_model=SwitchResponse)
def create_switch(body: SwitchCreate, db: Session = Depends(get_db)):
    """Create a new switch for a specific machine"""
    # Verify machine exists
    machine = db.query(Machine).filter(Machine.id == body.machine_id).first()
    if not machine:
        raise HTTPException(400, "Machine not found")

    switch = Switch(
        id=str(uuid.uuid4()),
        machine_id=body.machine_id,
        switch_name=body.switch_name,
        expected_diameter_mm=body.expected_diameter_mm,
        tolerance_min=body.tolerance_min,
        tolerance_max=body.tolerance_max,
        cable_type=body.cable_type
    )
    db.add(switch)
    db.commit()
    db.refresh(switch)

    return SwitchResponse(
        id=switch.id,
        machine_id=switch.machine_id,
        machine_name=machine.machine_name,
        switch_name=switch.switch_name,
        expected_diameter_mm=switch.expected_diameter_mm,
        tolerance_min=switch.tolerance_min,
        tolerance_max=switch.tolerance_max,
        cable_type=switch.cable_type,
        created_at=switch.created_at
    )

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

    # Get machine name for response
    machine = db.query(Machine).filter(Machine.id == switch.machine_id).first()
    machine_name = machine.machine_name if machine else "Unknown"

    return SwitchResponse(
        id=switch.id,
        machine_id=switch.machine_id,
        machine_name=machine_name,
        switch_name=switch.switch_name,
        expected_diameter_mm=switch.expected_diameter_mm,
        tolerance_min=switch.tolerance_min,
        tolerance_max=switch.tolerance_max,
        cable_type=switch.cable_type,
        created_at=switch.created_at
    )

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

@router.get("/captures")
def get_captures(status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Get all captures, optionally filtered by status (pending|assigned|approved)"""
    from models import Switch
    import json

    query = db.query(Capture, Switch.expected_diameter_mm).join(
        Switch, Capture.switch_id == Switch.id, isouter=True
    )

    if status == "pending":
        query = query.filter(Capture.annoteur_id == None)
    elif status == "assigned":
        query = query.filter(
            (Capture.annoteur_id != None) & (Capture.annoteur_approved == False)
        )
    elif status == "approved":
        query = query.filter(Capture.annoteur_approved == True)

    results = []
    for capture, expected_mm in query.all():
        capture_dict = {k: v for k, v in capture.__dict__.items() if not k.startswith('_sa_')}
        capture_dict['expected_diameter_mm'] = expected_mm
        response_obj = CaptureAdminResponse(**capture_dict)
        results.append(json.loads(response_obj.json()))

    return results

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

@router.put("/captures/{capture_id}/approve", response_model=CaptureAdminResponse)
def approve_capture(capture_id: str, db: Session = Depends(get_db)):
    """Approve a capture"""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(404, "Capture not found")

    capture.annoteur_approved = True
    db.commit()
    db.refresh(capture)
    return capture

class CaptureAnnotateRequest(BaseModel):
    p1_x: Optional[int] = None
    p1_y: Optional[int] = None
    p2_x: Optional[int] = None
    p2_y: Optional[int] = None
    cable_state: Optional[str] = None
    annoteur_approved: Optional[bool] = None

@router.put("/captures/{capture_id}/annotate", response_model=CaptureAdminResponse)
def annotate_capture(capture_id: str, body: CaptureAnnotateRequest, db: Session = Depends(get_db)):
    """Update capture with annoteur corrections and cable state label"""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(404, "Capture not found")

    # Update edited points
    if body.p1_x is not None:
        capture.p1_x = body.p1_x
    if body.p1_y is not None:
        capture.p1_y = body.p1_y
    if body.p2_x is not None:
        capture.p2_x = body.p2_x
    if body.p2_y is not None:
        capture.p2_y = body.p2_y

    # Update approval status
    if body.annoteur_approved is not None:
        capture.annoteur_approved = body.annoteur_approved

    db.commit()
    db.refresh(capture)
    return capture
