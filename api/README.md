# Bellmounth API - FastAPI Backend

Local development backend for the Bellmounth cable measurement system.

## Setup

1. **Install dependencies**:
```bash
cd api
pip install -r requirements.txt
```

2. **Create .env file** (copy from ../.env.example):
```bash
cp ../.env.example .env
```

3. **Run the API**:
```bash
python main.py
```

Or with uvicorn directly:
```bash
uvicorn main:app --reload --port 8000
```

## API will start at:
- http://localhost:8000
- Docs: http://localhost:8000/docs (Swagger UI)
- ReDoc: http://localhost:8000/redoc

## Database

SQLite database will be created automatically at:
- `./bellmounth.db`

## Endpoints (Phase 1)

### Authentication
- `POST /auth/login` - Login (username + password)
- `GET /auth/health` - Health check

### Switches
- `GET /switches/` - List all switches
- `GET /switches/{switch_id}` - Get switch details

### Captures
- `POST /captures/upload` - Upload measurement (multipart form)
- `GET /captures/queue?annoteur_id=...` - Get review queue
- `PUT /captures/{id}/approve` - Approve capture
- `PUT /captures/{id}/reject` - Reject capture
- `DELETE /captures/{id}` - Delete capture

## Test Login

Use Swagger UI at http://localhost:8000/docs to test:
1. Create users/machines first via database
2. POST /auth/login with credentials
3. Get JWT token
4. Use token in Authorization header

## Files Structure

```
api/
├── main.py           # FastAPI app + router setup
├── database.py       # SQLite connection
├── models.py         # SQLAlchemy ORM models
├── schemas.py        # Pydantic request/response
├── auth.py           # JWT + bcrypt utilities
├── requirements.txt  # Dependencies
├── routers/
│   ├── auth.py       # Login endpoints
│   ├── switches.py   # Switch CRUD
│   └── captures.py   # Upload & review
└── README.md         # This file
```
