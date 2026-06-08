"""
Security module for API authentication, rate limiting, and IP whitelisting
"""

import secrets
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional
from fastapi import HTTPException, Request, Depends
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, Boolean
from database import Base
import os

# ==================== MODELS ====================

class APIKey(Base):
    """API Key for client authentication"""
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: secrets.token_urlsafe(32))
    name = Column(String)  # e.g., "Desktop App v1.0"
    key_hash = Column(String, unique=True, index=True)
    user_id = Column(String, nullable=True)  # Optional: associated user
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Optional expiration


class IPWhitelist(Base):
    """Whitelisted IP addresses"""
    __tablename__ = "ip_whitelist"

    id = Column(String, primary_key=True)
    ip_address = Column(String, unique=True, index=True)
    description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class LoginAttempt(Base):
    """Track login attempts for rate limiting"""
    __tablename__ = "login_attempts"

    id = Column(String, primary_key=True)
    ip_address = Column(String, index=True)
    username = Column(String, nullable=True)
    success = Column(Boolean)
    timestamp = Column(DateTime, default=datetime.utcnow)


# ==================== UTILITIES ====================

def hash_api_key(key: str) -> str:
    """Hash API key for storage"""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a new API key"""
    return f"sk_live_{secrets.token_urlsafe(32)}"


def verify_api_key(key: str, key_hash: str) -> bool:
    """Verify API key against stored hash"""
    return hash_api_key(key) == key_hash


# ==================== RATE LIMITING ====================

class RateLimiter:
    """Rate limiting for login attempts"""

    @staticmethod
    def check_login_rate_limit(db: Session, ip_address: str, max_attempts: int = 5, window_minutes: int = 15):
        """Check if IP has exceeded login attempts"""
        time_window = datetime.utcnow() - timedelta(minutes=window_minutes)

        failed_attempts = db.query(LoginAttempt).filter(
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.success == False,
            LoginAttempt.timestamp >= time_window
        ).count()

        if failed_attempts >= max_attempts:
            raise HTTPException(
                status_code=429,
                detail=f"Too many login attempts. Try again in {window_minutes} minutes."
            )

    @staticmethod
    def log_login_attempt(db: Session, ip_address: str, username: Optional[str], success: bool):
        """Log a login attempt"""
        attempt = LoginAttempt(
            id=secrets.token_urlsafe(16),
            ip_address=ip_address,
            username=username,
            success=success
        )
        db.add(attempt)
        db.commit()

    @staticmethod
    def cleanup_old_attempts(db: Session, hours: int = 24):
        """Delete old login attempts"""
        old_time = datetime.utcnow() - timedelta(hours=hours)
        db.query(LoginAttempt).filter(LoginAttempt.timestamp < old_time).delete()
        db.commit()


# ==================== IP WHITELISTING ====================

class IPWhitelistChecker:
    """Check IP whitelist"""

    @staticmethod
    def is_ip_whitelisted(db: Session, ip_address: str) -> bool:
        """Check if IP is in whitelist"""
        if not os.getenv("ENABLE_IP_WHITELIST", "false").lower() == "true":
            return True  # Disabled if not configured

        whitelist = db.query(IPWhitelist).filter(
            IPWhitelist.ip_address == ip_address,
            IPWhitelist.is_active == True
        ).first()

        return whitelist is not None

    @staticmethod
    def add_ip(db: Session, ip_address: str, description: str):
        """Add IP to whitelist"""
        ip = IPWhitelist(
            id=secrets.token_urlsafe(16),
            ip_address=ip_address,
            description=description
        )
        db.add(ip)
        db.commit()
        return ip

    @staticmethod
    def remove_ip(db: Session, ip_address: str):
        """Remove IP from whitelist"""
        db.query(IPWhitelist).filter(IPWhitelist.ip_address == ip_address).delete()
        db.commit()


# ==================== API KEY AUTHENTICATION ====================

class APIKeyAuth:
    """API Key authentication"""

    @staticmethod
    def create_key(db: Session, name: str, user_id: Optional[str] = None, expires_days: Optional[int] = None) -> str:
        """Create a new API key"""
        key = generate_api_key()
        key_hash = hash_api_key(key)

        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        api_key = APIKey(
            id=secrets.token_urlsafe(16),
            name=name,
            key_hash=key_hash,
            user_id=user_id,
            expires_at=expires_at
        )
        db.add(api_key)
        db.commit()

        return key  # Only return plain key once

    @staticmethod
    def verify_key(db: Session, api_key: str) -> Optional[APIKey]:
        """Verify API key and return key object"""
        key_hash = hash_api_key(api_key)

        key_obj = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()

        if not key_obj:
            return None

        # Check expiration
        if key_obj.expires_at and key_obj.expires_at < datetime.utcnow():
            return None

        # Update last used
        key_obj.last_used = datetime.utcnow()
        db.commit()

        return key_obj

    @staticmethod
    def revoke_key(db: Session, api_key: str):
        """Revoke an API key"""
        key_hash = hash_api_key(api_key)
        key_obj = db.query(APIKey).filter(APIKey.key_hash == key_hash).first()
        if key_obj:
            key_obj.is_active = False
            db.commit()

    @staticmethod
    def list_keys(db: Session) -> list:
        """List all active API keys"""
        return db.query(APIKey).filter(APIKey.is_active == True).all()


# ==================== FASTAPI DEPENDENCIES ====================

async def verify_api_key_header(request: Request, db: Session = Depends()) -> str:
    """FastAPI dependency to verify API key from header"""
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_obj = APIKeyAuth.verify_key(db, api_key)
    if not key_obj:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")

    return api_key


async def verify_ip_whitelist(request: Request, db: Session = Depends()):
    """FastAPI dependency to verify IP is whitelisted"""
    client_ip = request.client.host

    if not IPWhitelistChecker.is_ip_whitelisted(db, client_ip):
        raise HTTPException(status_code=403, detail="IP address not whitelisted")

    return client_ip
