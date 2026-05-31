import uuid
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum

class UserRole(str, enum.Enum):
    machine_user = "machine_user"
    annoteur = "annoteur"
    admin = "admin"

class MeasurementStatus(str, enum.Enum):
    okay = "okay"
    not_okay = "not_okay"

class CaptureMethod(str, enum.Enum):
    auto_cnn = "auto_cnn"
    manual = "manual"

class CableState(str, enum.Enum):
    no_cable = "no_cable"
    cable_male = "cable_male"
    cable_good = "cable_good"

class ReclamationCategory(str, enum.Enum):
    bug = "bug"
    slow = "slow"
    incorrect = "incorrect"
    other = "other"

class ReclamationStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(Enum(UserRole))
    email = Column(String)
    machine_id = Column(String, ForeignKey("machines.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

class Machine(Base):
    __tablename__ = "machines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    machine_name = Column(String, unique=True, index=True)
    password_hash = Column(String)
    location = Column(String)
    firmware_version = Column(String)
    zoom_calibration = Column(Float, default=34.58)
    mm_per_pixel = Column(Float, default=0.0165)
    is_connected = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    current_session_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    session_start_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Switch(Base):
    __tablename__ = "switches"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    machine_id = Column(String, ForeignKey("machines.id"))
    switch_name = Column(String)
    expected_diameter_mm = Column(Float)
    tolerance_min = Column(Float)
    tolerance_max = Column(Float)
    cable_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    machine_id = Column(String, ForeignKey("machines.id"))
    switch_id = Column(String, ForeignKey("switches.id"))
    measured_value_mm = Column(Float)
    p1_x = Column(Integer)
    p1_y = Column(Integer)
    p2_x = Column(Integer)
    p2_y = Column(Integer)
    capture_method = Column(Enum(CaptureMethod))
    image_path_original = Column(String)
    image_path_thresholded = Column(String)
    measurement_status = Column(Enum(MeasurementStatus))
    delta_mm = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

class Capture(Base):
    __tablename__ = "captures"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    machine_id = Column(String, ForeignKey("machines.id"))
    switch_id = Column(String, ForeignKey("switches.id"))
    annoteur_id = Column(String, ForeignKey("users.id"), nullable=True)
    image_original_path = Column(String)
    image_thresholded_path = Column(String)
    p1_x = Column(Integer)
    p1_y = Column(Integer)
    p2_x = Column(Integer)
    p2_y = Column(Integer)
    measured_distance_mm = Column(Float)
    zoom_level = Column(Float, nullable=True)
    capture_method = Column(Enum(CaptureMethod))
    measurement_status = Column(Enum(MeasurementStatus))
    delta_mm = Column(Float)
    annoteur_approved = Column(Boolean, default=False)
    in_training_dataset = Column(Boolean, default=False)
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class StateAnnotation(Base):
    __tablename__ = "state_annotations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    annoteur_id = Column(String, ForeignKey("users.id"))
    image_path = Column(String)
    cable_state = Column(Enum(CableState))
    in_training_dataset = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    from_user_id = Column(String, ForeignKey("users.id"))
    to_role = Column(String)
    to_user_ids = Column(JSON, nullable=True)
    subject = Column(String)
    body = Column(Text)
    attachment_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    notification_type = Column(String)
    title = Column(String)
    body = Column(Text)
    action_url = Column(String, nullable=True)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Reclamation(Base):
    __tablename__ = "reclamations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"))
    title = Column(String)
    description = Column(Text)
    category = Column(Enum(ReclamationCategory))
    screenshot_path = Column(String, nullable=True)
    status = Column(Enum(ReclamationStatus), default=ReclamationStatus.open)
    admin_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

class KeypointModel(Base):
    __tablename__ = "keypoint_models"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    version = Column(String)
    accuracy = Column(Float)
    precision = Column(Float)
    training_samples_count = Column(Integer)
    deployed_to_machines = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)

class StateModel(Base):
    __tablename__ = "state_models"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    version = Column(String)
    accuracy = Column(Float)
    precision_per_class = Column(JSON)
    training_samples_count = Column(Integer)
    deployed_to_machines = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)
