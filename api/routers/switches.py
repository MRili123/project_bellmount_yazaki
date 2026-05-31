from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import join
from typing import List, Optional
from database import get_db
from models import Switch, Machine
from schemas import SwitchResponse

router = APIRouter(prefix="/switches", tags=["switches"])

@router.get("/", response_model=List[SwitchResponse])
def get_switches(machine_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Get switches, optionally filtered by machine_id"""
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

@router.get("/{switch_id}", response_model=SwitchResponse)
def get_switch(switch_id: str, db: Session = Depends(get_db)):
    switch = db.query(
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
    ).join(Machine, Switch.machine_id == Machine.id).filter(Switch.id == switch_id).first()

    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")

    return SwitchResponse(
        id=switch[0],
        machine_id=switch[1],
        machine_name=switch[2],
        switch_name=switch[3],
        expected_diameter_mm=switch[4],
        tolerance_min=switch[5],
        tolerance_max=switch[6],
        cable_type=switch[7],
        created_at=switch[8]
    )
