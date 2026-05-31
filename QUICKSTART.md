# Bellmounth v2.0 - Quick Start Guide

Get the complete multi-user system running in 5 minutes.

---

## Step 1: Install Dependencies

### Backend (API) - Terminal 1

```bash
cd api
pip install -r requirements.txt
```

### Frontend (App) - Terminal 2

```bash
# From project root
pip install requests pillow
```

---

## Step 2: Setup Database

### Terminal 1 (in api/ directory)

```bash
python seed_db.py
```

**Output:**
```
✅ Database seeded successfully!

Test Credentials:
==================================================

Machine Users:
  Machine: LAB-01, Password: bellmounth
  Machine: LAB-02, Password: bellmounth

Annoteur Users:
  Username: annoteur_01, Password: password123
  Username: annoteur_02, Password: password123

Admin User:
  Username: admin, Password: admin123

Switches:
  1. Standard Cable (10.5mm, ±0.5mm)
  2. Reinforced Cable (12.0mm, ±0.5mm)
==================================================
```

---

## Step 3: Start Backend API

### Terminal 1 (in api/ directory)

```bash
python main.py
```

**Or use uvicorn directly:**
```bash
uvicorn main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**Test it:** Open http://localhost:8000/docs in browser → Swagger UI appears

---

## Step 4: Start Frontend App

### Terminal 2 (from project root)

```bash
python app.py
```

**First Launch:**
1. SetupWindow appears asking for API URL
2. Type: `http://localhost:8000`
3. Click **[TEST CONNECTION]** → green checkmark
4. Click **[SAVE & CONTINUE]**

**Login Screen:**
1. Username field appears
2. Try one of the test credentials:
   - **Machine User**: LAB-01 / bellmounth
   - **Annoteur**: annoteur_01 / password123
   - **Admin**: admin / admin123

**Machine User (after login):**
- Camera feed loads
- Measure cable like before
- Click **[UPLOAD]** to send to server
- Check API logs for upload confirmation

---

## Complete Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ TERMINAL 1: FastAPI Backend                                     │
│                                                                  │
│ $ python api/main.py                                            │
│ → SQLite database (bellmounth.db)                               │
│ → Captures folder (/captures/original, /captures/thresholded)   │
│ → API listening on http://localhost:8000                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TERMINAL 2: Tkinter Application                                 │
│                                                                  │
│ $ python app.py                                                 │
│ → SetupWindow (first time: configure API URL)                  │
│ → LoginWindow (authenticate via API)                            │
│ → MainApp or AnnoteurUI or AdminUI (based on role)              │
│ → Camera + Measurement + Upload to API                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Test Workflow

### As Machine User (LAB-01)

1. Login with `LAB-01` / `bellmounth`
2. Camera feed shows
3. Measure a cable:
   - AUTO mode: click [CAPTURE]
   - MANUAL mode: click P1, then P2
4. Click **[UPLOAD]** button
5. Check Terminal 1 logs for: `POST /captures/upload`
6. Database now contains capture record

### Verify Upload in Database

```bash
# Terminal 1, in api/ directory
python -c "
from database import SessionLocal
from models import Capture
db = SessionLocal()
captures = db.query(Capture).all()
print(f'Total captures: {len(captures)}')
for c in captures:
    print(f'  - {c.id}: {c.measured_distance_mm}mm, status={c.measurement_status}')
"
```

---

## Swagger API Documentation

Open http://localhost:8000/docs in browser:

- **Authorize** (top-right) - login first to get JWT token
- **POST /auth/login** - test authentication
- **GET /switches/** - list available switches
- **POST /captures/upload** - upload measurement
- **GET /captures/queue** - get review queue (annoteur)
- **PUT /captures/{id}/approve** - approve capture (annoteur)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ConnectionRefusedError` | Make sure API is running in Terminal 1 |
| `Cannot connect to API` | Check if `http://localhost:8000/auth/health` works |
| Database file not found | Run `python seed_db.py` to create and seed |
| Camera not detected | Make sure camera is connected and OpenCV can access it |
| Login failed | Use test credentials from `seed_db.py` output |

---

## Next Steps

After testing locally:

1. **Annoteur UI** - Review captures queue and approve/reject
2. **Admin UI** - User management, switch management
3. **Azure Deployment** - Follow `AZURE_SETUP.md` to deploy to cloud
4. **State Detection** - Add cable state labeling (Phase 2)
5. **Model Training** - Train and deploy ML models

---

## Quick Reference

| Component | Command | URL |
|-----------|---------|-----|
| API Server | `python api/main.py` | http://localhost:8000 |
| Swagger Docs | Open in browser | http://localhost:8000/docs |
| Database | SQLite file | `./bellmounth.db` |
| App | `python app.py` | Tkinter window |
| Captures | Local folder | `./captures/` |
