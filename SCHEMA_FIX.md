# Schema Fix: Switch ↔ Machine Relationship

**Date**: 2026-05-30  
**Issue**: Switches relationship was backwards  
**Status**: ✅ Fixed

---

## Problem

The original schema had:
```python
# WRONG: One switch assigned to many machines
class Switch:
    assigned_machines = Column(JSON, default=list)
```

This doesn't match the real-world requirement: **each switch/cable type belongs to ONE specific machine**.

---

## Solution

Changed to:
```python
# CORRECT: Each switch belongs to one machine
class Switch:
    machine_id = Column(String, ForeignKey("machines.id"))
```

### Why This Makes Sense

**Factory Floor Reality**:
- Machine LAB-01 (Position A): Measures thin twisted pair cables (10mm ± 0.5mm)
- Machine LAB-02 (Position B): Measures thick coaxial cables (15mm ± 1mm)
- Machine LAB-03 (Position C): Measures shielded twisted pair (12mm ± 0.3mm)

Each machine has its **own set of cable specifications** (switches) it needs to measure.

---

## Files Changed

### 1. `api/models.py`

**Before**:
```python
class Switch(Base):
    assigned_machines = Column(JSON, default=list)
    # No machine_id
```

**After**:
```python
class Switch(Base):
    machine_id = Column(String, ForeignKey("machines.id"))
    # Each switch belongs to ONE machine
```

---

### 2. `api/schemas.py`

**SwitchResponse** - Added machine_id:
```python
class SwitchResponse(BaseModel):
    id: str
    machine_id: str  # NEW
    switch_name: str
    expected_diameter_mm: float
    tolerance_min: float
    tolerance_max: float
    cable_type: str
```

**SwitchCreate** - Requires machine_id:
```python
class SwitchCreate(BaseModel):
    machine_id: str  # NEW - Required when creating
    switch_name: str
    expected_diameter_mm: float
    tolerance_min: float
    tolerance_max: float
    cable_type: str
```

---

### 3. `api/routers/admin.py`

**New Endpoint**: Get switches for a machine
```python
@router.get("/switches", response_model=List[SwitchResponse])
def get_switches(machine_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Get all switches, optionally filtered by machine_id"""
    query = db.query(Switch)
    if machine_id:
        query = query.filter(Switch.machine_id == machine_id)
    return query.all()
```

**Updated**: Create switch now validates machine exists
```python
@router.post("/switches", response_model=SwitchResponse)
def create_switch(body: SwitchCreate, db: Session = Depends(get_db)):
    # Verify machine exists
    machine = db.query(Machine).filter(Machine.id == body.machine_id).first()
    if not machine:
        raise HTTPException(400, "Machine not found")
    
    switch = Switch(
        machine_id=body.machine_id,  # Assign to machine
        switch_name=body.switch_name,
        # ... rest of fields
    )
```

---

## API Changes

### Before
```
GET    /admin/switches                    → all switches (with assigned_machines JSON)
POST   /admin/switches                    → create switch (no machine association)
PUT    /admin/switches/{id}               → update (can't change assigned_machines easily)
```

### After
```
GET    /admin/switches                    → all switches
GET    /admin/switches?machine_id=...     → switches for specific machine
POST   /admin/switches                    → create switch (must specify machine_id)
PUT    /admin/switches/{id}               → update switch
```

---

## Machine User Workflow (App)

**When a machine user logs in**:

```
1. Machine LAB-01 connects
   └─ request: GET /admin/switches?machine_id=<LAB-01-uuid>
   
2. Server returns only switches for LAB-01:
   ├─ SWITCH-001: 10.5mm ± 0.5mm (twisted pair)
   ├─ SWITCH-002: 10.2mm ± 0.3mm (thin gauge)
   └─ SWITCH-003: 11.0mm ± 0.8mm (reinforced)
   
3. Operator selects SWITCH-001
   └─ Measurement knows: expected diameter, tolerance, cable type
   
4. After measurement: result compared to SWITCH-001 specs
   └─ Status: 🟢 OKAY or 🔴 NOT OKAY
```

---

## Database Migration (If Needed)

For existing databases, run:
```sql
ALTER TABLE switches ADD COLUMN machine_id VARCHAR;
ALTER TABLE switches ADD CONSTRAINT fk_switch_machine 
    FOREIGN KEY (machine_id) REFERENCES machines(id);
ALTER TABLE switches DROP COLUMN assigned_machines;
```

---

## Implementation Status

### ✅ Completed
1. ✅ Updated models.py — Switch.machine_id foreign key
2. ✅ Updated schemas.py — Added machine_id to SwitchCreate/SwitchResponse
3. ✅ Updated admin router — GET /admin/switches?machine_id filter
4. ✅ Updated auth endpoints — LoginResponse includes machine_id
5. ✅ Updated APIClient — get_switches(machine_id) parameter + admin_get_switches()
6. ✅ Updated app.py (MainApp) — Fetches only its machine's switches
7. ✅ Git commits (2): Schema fix + machine-scoped filtering

### 📋 Remaining (Optional)
1. Update admin UI (SWITCHES page) to show machine → switches hierarchy
2. Update Admin cache to handle machine-scoped switches
3. Database migration (if production database exists)

---

## Admin UI Changes (TODO)

### MACHINES Page
Add section:
```
Machine: LAB-01
├─ Location: Factory A, Position 1
├─ Status: 🟢 Online
├─ Switches (3):
│  ├─ SWITCH-001: 10.5mm ± 0.5mm
│  ├─ SWITCH-002: 10.2mm ± 0.3mm
│  └─ SWITCH-003: 11.0mm ± 0.8mm
└─ [+ ADD SWITCH] [VIEW DETAILS]
```

### SWITCHES Page
Reorganize hierarchy:
```
LAB-01 (Factory A)
├─ SWITCH-001: 10.5mm ± 0.5mm [EDIT] [DELETE]
├─ SWITCH-002: 10.2mm ± 0.3mm [EDIT] [DELETE]
└─ SWITCH-003: 11.0mm ± 0.8mm [EDIT] [DELETE]

LAB-02 (Factory B)
├─ SWITCH-004: 15.0mm ± 1.0mm [EDIT] [DELETE]
└─ SWITCH-005: 14.8mm ± 0.8mm [EDIT] [DELETE]

[+ ADD NEW MACHINE] [+ ADD NEW SWITCH]
```

---

## Testing Checklist

- [ ] Create switch with machine_id → succeeds
- [ ] Create switch without machine_id → fails with 400
- [ ] Create switch with non-existent machine → fails with 400
- [ ] Get switches by machine_id → returns only that machine's switches
- [ ] Delete machine → cascading delete switches (or handle constraint)
- [ ] Update switch → machine_id stays unchanged
- [ ] Admin UI loads switches for selected machine
- [ ] Machine app fetches only its own switches

---

**Status**: Schema refactored, API endpoints updated, ready for frontend integration  
**Owner**: iliasssjb2004@gmail.com
