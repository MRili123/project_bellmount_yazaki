from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import Switch
from schemas import SwitchResponse

router = APIRouter(prefix="/switches", tags=["switches"])

@router.get("/", response_model=List[SwitchResponse])
def get_switches(db: Session = Depends(get_db)):
    switches = db.query(Switch).all()
    return switches

@router.get("/{switch_id}", response_model=SwitchResponse)
def get_switch(switch_id: str, db: Session = Depends(get_db)):
    switch = db.query(Switch).filter(Switch.id == switch_id).first()
    if not switch:
        raise HTTPException(status_code=404, detail="Switch not found")
    return switch
