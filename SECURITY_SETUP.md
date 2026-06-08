# Bellmounth Security Implementation Guide

This document explains the security layers implemented to protect your desktop application and API.

## Security Layers Overview

```
┌─────────────────────────────────────────────────────┐
│ Desktop App (Encrypted URL + API Key)               │
│ - config.json (encrypted)                           │
│ - Fernet encryption on all credentials              │
└──────────────┬──────────────────────────────────────┘
               │ HTTPS + X-API-Key Header + Login
               ↓
┌─────────────────────────────────────────────────────┐
│ API Server (Rate Limiting + IP Whitelist)           │
│ - Max 5 login attempts / 15 minutes                 │
│ - Optional IP whitelist                             │
│ - Audit logging of all access                       │
└──────────────┬──────────────────────────────────────┘
               │ Database Credentials (in .env)
               ↓
┌─────────────────────────────────────────────────────┐
│ Database (Password Protected)                        │
│ - PostgreSQL/SQLite with credentials                │
│ - Encrypted on disk (optional)                       │
└─────────────────────────────────────────────────────┘
```

---

## Installation

### 1. Install Dependencies

```bash
pip install cryptography
```

### 2. API Side Setup (.env file)

Create `.env` file in the `api/` directory:

```bash
# Database configuration
DATABASE_URL=postgresql://dbuser:YOUR_SECURE_PASSWORD@localhost:5432/bellmounth

# Or if using Azure SQL:
DATABASE_URL=postgresql://user@server:PASSWORD@server.postgres.database.azure.com:5432/bellmounth

# Optional: IP Whitelist
ENABLE_IP_WHITELIST=true  # or false to disable
```

### 3. Desktop App Initial Setup

On first run, the desktop app will:
1. Generate encryption key (`.app_key` file)
2. Create encrypted config file (`config.json`)
3. Show setup window for API URL and credentials

---

## How It Works

### Desktop App Encryption

```python
from crypto_utils import AppSecurityManager

# Save encrypted credentials during setup
AppSecurityManager.save_config(
    api_url="https://your-api.azurewebsites.net",
    api_key="sk_live_abc123xyz789..."
)

# Load encrypted credentials on startup
config = AppSecurityManager.load_config()
api_url = config["api_url"]
api_key = config["api_key"]
```

**Files Created:**
- `.app_key` — Encryption key (auto-generated, unique per installation)
- `config.json` — Encrypted API URL and API key

### API Key Generation

Generate API keys for desktop installations:

```bash
# Via Python script or API endpoint
from api.security import APIKeyAuth
from sqlalchemy.orm import Session

# Create a new API key
key = APIKeyAuth.create_key(
    db=session,
    name="Desktop App v1.0",
    user_id="optional_user_id",
    expires_days=365  # 1 year expiration
)
# Returns: "sk_live_abc123xyz789..."
# Save this key in desktop app setup
```

### Rate Limiting

Automatically limits login attempts:

```python
from api.security import RateLimiter

# Check if IP has exceeded attempts
RateLimiter.check_login_rate_limit(
    db=session,
    ip_address="192.168.1.100",
    max_attempts=5,
    window_minutes=15
)

# Log attempt
RateLimiter.log_login_attempt(
    db=session,
    ip_address="192.168.1.100",
    username="user1",
    success=True
)
```

Limits:
- **5 failed login attempts per IP per 15 minutes**
- **100 API requests per IP per hour** (configurable)
- Old attempts cleaned up after 24 hours

### IP Whitelist (Optional)

Enable in `.env`: `ENABLE_IP_WHITELIST=true`

Add allowed IPs:

```python
from api.security import IPWhitelistChecker

# Add IP to whitelist
IPWhitelistChecker.add_ip(
    db=session,
    ip_address="192.168.1.100",
    description="Office network"
)

# Check if IP is whitelisted
if IPWhitelistChecker.is_ip_whitelisted(db, "192.168.1.100"):
    # Allow request
    pass
```

---

## API Integration

### Updated APIClient

```python
from api_client import APIClient

# Initialize with API key
client = APIClient(
    api_url="https://your-api.azurewebsites.net",
    api_key="sk_live_abc123xyz789..."
)

# All requests automatically include X-API-Key header
client.login("user", "password")
client.get("/admin/captures")
```

### Request Headers

Every request includes:

```
X-API-Key: sk_live_abc123xyz789...
Authorization: Bearer <session_token>
Content-Type: application/json
```

---

## Desktop App Setup Process

### First Run

1. App launches without config
2. SetupWindow opens (already in app.py)
3. User enters API URL
4. Admin generates and provides API key
5. User enters API key
6. Credentials are encrypted and saved

```
config.json (encrypted):
{
  "api_url_encrypted": "gAAAAABm...",
  "api_key_encrypted": "gAAAAABm...",
  "version": "1.0"
}
```

### Subsequent Runs

1. App reads encrypted `config.json`
2. Decrypts using `.app_key`
3. Initializes APIClient with URL + key
4. Shows login window
5. User authenticates

---

## API Endpoint Updates Needed

Add these endpoints to your FastAPI app:

```python
# In api/routers/admin.py or new security.py

from fastapi import FastAPI, Depends
from api.security import APIKeyAuth, verify_api_key_header

app = FastAPI()

# Generate new API key (admin only)
@app.post("/admin/api-keys/generate")
def generate_api_key(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key_header),
    current_user: User = Depends(get_current_user)
):
    """Generate new API key for client"""
    new_key = APIKeyAuth.create_key(
        db=db,
        name=request.json().get("name"),
        user_id=current_user.id,
        expires_days=365
    )
    return {"api_key": new_key}

# List API keys
@app.get("/admin/api-keys")
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all API keys for current user"""
    keys = APIKeyAuth.list_keys(db)
    return {"keys": keys}

# Revoke API key
@app.post("/admin/api-keys/{api_key}/revoke")
def revoke_api_key(
    api_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revoke an API key"""
    APIKeyAuth.revoke_key(db, api_key)
    return {"status": "revoked"}
```

---

## Security Checklist

✅ **Desktop App:**
- [ ] Install cryptography package
- [ ] Test encryption/decryption with `crypto_utils.py`
- [ ] Verify `.app_key` is created and restricted
- [ ] Test setup window with encrypted save

✅ **API Server:**
- [ ] Create `.env` file with DATABASE_URL
- [ ] Add security models to database (run init)
- [ ] Add endpoints for API key generation/management
- [ ] Test API key validation middleware
- [ ] Enable rate limiting in `.env`
- [ ] Optional: Enable IP whitelist

✅ **Production Deployment:**
- [ ] Use HTTPS only (not http://)
- [ ] Store `.env` securely on server (not in git)
- [ ] Set restricted file permissions: `chmod 600 .env`
- [ ] Rotate API keys periodically
- [ ] Monitor failed login attempts
- [ ] Enable audit logging
- [ ] Use strong database passwords

---

## Troubleshooting

### "Missing API key" error

**Problem:** Request rejected without X-API-Key header

**Solution:** 
1. Verify APIClient initialized with api_key
2. Check SetupWindow saves key correctly
3. Verify config.json exists and is readable

### "Invalid or expired API key" error

**Problem:** API key validation failed

**Solution:**
1. Verify API key is valid in database
2. Check key hasn't expired
3. Generate new key and update app

### "IP address not whitelisted" error

**Problem:** Request rejected due to IP check

**Solution:**
1. Verify ENABLE_IP_WHITELIST=true in .env
2. Add IP to whitelist using IPWhitelistChecker.add_ip()
3. Or disable IP whitelist if not needed

---

## Managing API Keys

### Generate Key for Desktop App

```bash
# Admin dashboard
POST /admin/api-keys/generate
{
  "name": "Desktop App v1.0"
}

# Returns: "sk_live_abc123..."
```

### Revoke Key if Compromised

```bash
# Admin dashboard
POST /admin/api-keys/{api_key}/revoke

# Key is immediately disabled
```

### List All Keys

```bash
GET /admin/api-keys

# Returns all active keys with last_used timestamp
```

---

## Additional Security Tips

1. **API Key Rotation**
   - Rotate keys every 6-12 months
   - Revoke old keys immediately

2. **Network Security**
   - Use VPN for remote access
   - Enable IP whitelisting for sensitive operations
   - Monitor API logs for suspicious patterns

3. **Environment Variables**
   - Never commit `.env` to git
   - Use `.env.example` for documentation
   - Rotate database passwords periodically

4. **Encryption Keys**
   - `.app_key` is unique per installation
   - Don't share between devices
   - Back up securely if needed

5. **Monitoring**
   - Review login attempt logs
   - Alert on multiple failed attempts
   - Track API key usage patterns

---

## Files Modified/Created

- ✅ `api/security.py` — Security models and utilities
- ✅ `crypto_utils.py` — Desktop app encryption
- ✅ `api_client.py` — Updated with API key support
- ✅ `requirements.txt` — Added cryptography package
- ✅ `SECURITY_SETUP.md` — This guide

All security features are backward compatible and optional!
