from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    user_id: str
    username: str
    machine_id: Optional[str] = None

class SwitchResponse(BaseModel):
    id: str
    machine_id: str
    machine_name: str
    switch_name: str
    expected_diameter_mm: float
    tolerance_min: float
    tolerance_max: float
    cable_type: str
    created_at: datetime

    class Config:
        from_attributes = True

class MeasurementCreate(BaseModel):
    machine_id: str
    switch_id: str
    measured_value_mm: float
    p1_x: int
    p1_y: int
    p2_x: int
    p2_y: int
    capture_method: str
    measurement_status: str

class CaptureUploadRequest(BaseModel):
    machine_id: str
    switch_id: str
    measured_value_mm: float
    p1_x: int
    p1_y: int
    p2_x: int
    p2_y: int
    capture_method: str
    measurement_status: str
    delta_mm: float

class CaptureResponse(BaseModel):
    id: str
    machine_id: str
    switch_id: str
    measured_distance_mm: float
    capture_method: str
    measurement_status: str
    delta_mm: float
    annoteur_approved: bool
    in_training_dataset: bool
    created_at: datetime

    class Config:
        from_attributes = True

class MachineResponse(BaseModel):
    id: str
    machine_name: str
    location: str
    is_connected: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    role: str

class HealthResponse(BaseModel):
    status: str
    version: str

# ==================== ADMIN SCHEMAS ====================

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None

class MachineCreate(BaseModel):
    machine_name: str
    password: str
    location: str
    firmware_version: str

class MachineFullResponse(BaseModel):
    id: str
    machine_name: str
    location: str
    firmware_version: str
    is_connected: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class MachineUpdate(BaseModel):
    location: Optional[str] = None
    firmware_version: Optional[str] = None
    is_active: Optional[bool] = None

class SwitchCreate(BaseModel):
    machine_id: str  # Required: Every switch must belong to a machine
    switch_name: str  # Required
    expected_diameter_mm: float  # Required
    tolerance_min: float  # Required
    tolerance_max: float  # Required
    cable_type: str  # Required

class SwitchUpdate(BaseModel):
    switch_name: Optional[str] = None
    expected_diameter_mm: Optional[float] = None
    tolerance_min: Optional[float] = None
    tolerance_max: Optional[float] = None
    cable_type: Optional[str] = None

class CaptureAdminResponse(BaseModel):
    id: str
    machine_id: str
    switch_id: str
    annoteur_id: Optional[str]
    annoteur_name: Optional[str] = None
    image_original_path: str
    image_thresholded_path: str
    p1_x: int
    p1_y: int
    p2_x: int
    p2_y: int
    measured_distance_mm: float
    expected_diameter_mm: Optional[float] = None
    tolerance_min: Optional[float] = None
    tolerance_max: Optional[float] = None
    machine_name: Optional[str] = None
    switch_name: Optional[str] = None
    zoom_level: Optional[float] = None
    capture_method: str
    measurement_status: str
    delta_mm: float
    cable_state: Optional[str] = None
    annoteur_approved: bool
    in_training_dataset: bool = False
    quality_score: Optional[float]
    model_type: Optional[str] = "mesure"
    created_at: datetime

    class Config:
        from_attributes = True

class AssignCaptureRequest(BaseModel):
    annoteur_id: str
