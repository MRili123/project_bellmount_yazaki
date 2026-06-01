# Bellmounth Cable Measurement System - Complete Implementation

## System Overview

A **3-role cable measurement and annotation system** with real-time detection, field measurement, and quality control workflows.

```
MACHINE USER (Field)    →    API SERVER    ←    ANNOTEUR (QC)
  Captures cables           (Database)        Reviews & corrects
  Marks P1, P2            (Approvals)         Edits keypoints
  Uploads                 (Storage)           Labels cable state
```

---

## Three User Roles & Interfaces

### 1. **MACHINE USER** (Field Worker)
**MainApp** - Live cable detection and measurement

**Workflow:**
1. 📱 Opens MainApp with Dino-Lite camera
2. 🎥 Live camera feed shows cable detection
3. 🖱️ Manually clicks to place P1 (start point)
4. 🖱️ Manually clicks to place P2 (end point)
5. 📏 System calculates distance (mm)
6. 📸 Screenshots capture with P1/P2 overlay
7. ☁️ **Uploads to API with keypoint coordinates**

**Key Features:**
- Real-time OpenCV cable detection
- Manual keypoint placement (click-based)
- Distance calculation with zoom calibration
- Screenshot storage with metadata
- Auto-capture on 5-second cable stability

---

### 2. **ANNOTEUR** (Quality Control)
**AnnoteurInteractiveApp** - Interactive point editing and cable state annotation

**Workflow:**
1. 📋 Logs in and loads pending captures
2. 📸 Reviews image from machine user
3. ✏️ **EDITS P1 if wrong** (click & drag on canvas)
4. ✏️ **EDITS P2 if wrong** (click & drag on canvas)
5. 🔄 Watches distance update in real-time
6. 🎨 **Selects cable state:**
   - 🔴 No Cable
   - 🟠 Male End
   - 🟢 Good Cable
7. 💾 **Saves corrected annotation**
8. ➡️ **Moves to next capture**

**Key Features:**
- Interactive canvas with drag-and-drop point editing
- Original vs Edited comparison panel
- Real-time distance recalculation
- Cable state classification
- One-click save workflow
- Previous/Next navigation

---

### 3. **ADMIN** (System Management)
**AdminApp** - Full system administration

**Pages:**
- **ANNOTEUR** — User management
- **MACHINES** — Equipment management
- **SWITCHES** — Cable type/tolerance configuration
- **REQUESTS** — Capture assignment and approval
- **DATASET** — Training data management
- **MODEL** — ML model deployment tracking
- **NOTIFICATIONS** — System alerts and messaging

---

## Database Schema

### Key Tables

**Users**
- 3 roles: machine_user, annoteur, admin
- Credentials and audit timestamps

**Machines**
- LAB-01, LAB-02 (field equipment)
- Zoom calibration (34.58)
- mm_per_pixel (0.0165)
- Connection status tracking

**Switches** (Cable Types)
- Machine_id (required)
- Switch_name, cable_type
- Expected_diameter_mm
- Tolerance_min, tolerance_max

**Captures** (Field Measurements)
- image_original_path, image_thresholded_path
- **p1_x, p1_y** (start point)
- **p2_x, p2_y** (end point)
- measured_distance_mm
- annoteur_id, annoteur_approved
- quality_score, capture_method

**StateAnnotation** (Cable State Labels)
- annoteur_id
- image_path
- cable_state (no_cable, cable_male, cable_good)

---

## Data Flow

### Complete Measurement Cycle

```
┌─────────────────────────────────────────────────────────────┐
│ 1. MACHINE USER CAPTURES                                     │
├─────────────────────────────────────────────────────────────┤
│  Live camera → Detect cable → Mark P1 → Mark P2 → Upload   │
│                                                              │
│  POST /captures/upload {                                     │
│    machine_id: "LAB-01"                                      │
│    switch_id: "fc619508-..."                                │
│    p1_x: 100, p1_y: 200                                     │
│    p2_x: 300, p2_y: 200                                     │
│    measured_distance_mm: 10.2                               │
│  }                                                           │
│                                                              │
│  API Response: ✓ Capture created                            │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. ANNOTEUR REVIEWS & EDITS                                 │
├─────────────────────────────────────────────────────────────┤
│  GET /admin/captures?status=pending → Load queue            │
│                                                              │
│  Display image with P1, P2 overlay                          │
│  Annoteur reviews:                                           │
│    • P1 looks wrong? → Drag to correct position             │
│    • P2 looks wrong? → Drag to correct position             │
│    • Distance updates in real-time                          │
│    • Selects cable state: "cable_good"                      │
│                                                              │
│  PUT /admin/captures/{id}/annotate {                        │
│    p1_x: 105, p1_y: 205    (edited)                        │
│    p2_x: 305, p2_y: 205    (edited)                        │
│    cable_state: "cable_good"                                │
│    annoteur_approved: true                                  │
│  }                                                           │
│                                                              │
│  API Response: ✓ Capture updated and approved               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. DATASET & TRAINING                                        │
├─────────────────────────────────────────────────────────────┤
│  Approved captures → Training dataset                       │
│  • Correct keypoint positions (from annoteur edits)        │
│  • Cable state classifications                              │
│  • Image pairs (original + thresholded)                     │
│                                                              │
│  Ready for ML model training:                               │
│  • Keypoint CNN model (predict P1, P2)                     │
│  • State classification model (no_cable, male, good)       │
└─────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### Public (All authenticated users)
- `GET /switches` — List switches with optional machine filter
- `GET /switches/{switch_id}` — Get switch details

### Machines (Machine user)
- `POST /captures/upload` — Submit field measurement
- `GET /captures/queue` — Get assigned captures

### Annoteur (Quality control)
- `GET /admin/captures?status=pending` — Load unreviewed captures
- `PUT /admin/captures/{id}/annotate` — Save edited points

### Admin (System management)
- `GET/POST /admin/users` — User management
- `GET/POST /admin/machines` — Equipment management
- `GET/POST /admin/switches` — Cable type configuration
- `GET/POST /admin/captures` — Capture management

---

## Test Data

### Pending Captures Ready for Annotation
```
Capture 1:
  Machine: LAB-01
  Switch: Standard Cable (10.5mm expected)
  Image: capture_20260427_081507_737.png
  P1: (100, 200) → Editable
  P2: (300, 200) → Editable
  Measured: 10.2 mm

Capture 2:
  Machine: LAB-01
  Switch: Reinforced Cable (12.0mm expected)
  Image: capture_20260427_081510_785.png
  P1: (110, 210) → Editable
  P2: (310, 210) → Editable
  Measured: 11.8 mm

Capture 3:
  Machine: LAB-02
  Switch: Coaxial Cable (15.0mm expected)
  Image: capture_20260427_140211_885.png
  P1: (120, 220) → Editable
  P2: (320, 220) → Editable
  Measured: 14.9 mm
```

### Login Credentials
```
Machine User:
  Username: LAB-01 (or LAB-02)
  Password: LAB-01 (or LAB-02)
  Role: machine_user

Annoteur:
  Username: annoteur_01 (or annoteur_02)
  Password: password123
  Role: annoteur

Admin:
  Username: admin
  Password: admin123
  Role: admin
```

---

## Key Technologies

- **Frontend:** Tkinter (Python GUI)
- **Backend:** FastAPI (Python)
- **Database:** SQLAlchemy ORM + SQLite
- **Camera:** Dino-Lite DNX64 SDK
- **Image Processing:** OpenCV
- **ML Model:** TensorFlow/Keras CNN
- **File Storage:** Local filesystem

---

## Recent Updates

| Commit | Description |
|--------|-------------|
| **b668f4e** | Fix: Move tk.StringVar() after root window |
| **1d29e87** | Redesign: Interactive point editing + cable state |
| **e41eee9** | Add: Keypoint visualization on images |
| **50a6218** | Implement: Complete AnnoteurApp interface |

---

## How to Use

### Start the System
```bash
# Terminal 1: Start API server
cd api
python main.py

# Terminal 2: Start client application
python app.py
```

### Machine User Workflow
1. Login: LAB-01 / LAB-01
2. Detect cable in live feed
3. Mark P1 point (click)
4. Mark P2 point (click)
5. Upload capture

### Annoteur Workflow
1. Login: annoteur_01 / password123
2. See pending captures
3. Review cable image
4. Drag P1 to correct position (if needed)
5. Drag P2 to correct position (if needed)
6. Select cable state
7. Click SAVE & NEXT

### Admin Workflow
1. Login: admin / admin123
2. Navigate tabs (Users, Machines, Switches, etc.)
3. Add/edit equipment and configurations
4. Monitor captures and approvals

---

## System Benefits

✅ **Field Teams** — Easy-to-use measurement app  
✅ **Quality Control** — Interactive editing workflow  
✅ **Admins** — Full system management dashboard  
✅ **Data Quality** — Human-in-the-loop validation  
✅ **ML Ready** — High-quality labeled dataset  
✅ **Scalable** — Multi-user, multi-machine support  

---

## Production Checklist

- ✅ Three user roles implemented
- ✅ Three distinct interfaces (Machine, Annoteur, Admin)
- ✅ Real cable image test data
- ✅ Interactive point editing
- ✅ API endpoints for all workflows
- ✅ Database schema with relationships
- ✅ Error handling and validation
- ✅ Git versioning and documentation

**System is ready for deployment!** 🚀

---

**Last Updated:** June 1, 2026  
**Version:** 2.0.0  
**Status:** ✓ Production Ready
