from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from database import get_db
from models import User, Machine
from schemas import LoginRequest, LoginResponse
from auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    # Try to find as regular user
    user = db.query(User).filter(User.username == request.username).first()

    if user and verify_password(request.password, user.password_hash) and user.is_active:
        token = create_access_token({"sub": user.id, "role": user.role})
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            role=user.role,
            user_id=user.id,
            username=user.username,
            machine_id=user.machine_id
        )

    # Try to find as machine user
    machine = db.query(Machine).filter(Machine.machine_name == request.username).first()

    if machine and verify_password(request.password, machine.password_hash):
        token = create_access_token({"sub": machine.id, "role": "machine_user"})
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            role="machine_user",
            user_id=machine.id,
            username=machine.machine_name,
            machine_id=machine.id
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials"
    )

@router.get("/health")
def health():
    return {"status": "ok", "message": "API is running"}
