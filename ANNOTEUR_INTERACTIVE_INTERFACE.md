# Interactive Annoteur Interface - Point Editing & Cable State Annotation

## Complete Workflow

### Machine User Flow (Field Worker)
1. 📱 Opens MainApp with Dino-Lite camera
2. 🎯 Captures cable image
3. 🖱️ Manually marks P1 and P2 keypoints on the image
4. 📏 System calculates distance (mm)
5. ☁️ **Uploads capture WITH P1/P2 coordinates to API**

### Annoteur Flow (Data Quality Checker)
1. 📋 Logs in and sees list of pending captures
2. 📸 Reviews the cable image from machine user
3. ✏️ **CAN EDIT P1 and P2 if they're wrong** (drag & drop)
4. 🔄 Sees real-time distance update as points move
5. 🎨 **Selects cable state** (no_cable, cable_male, cable_good)
6. 💾 Saves corrected annotation
7. ➡️ Moves to next capture

## User Interface Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│ Cable Annotation Studio                                           [LOGOUT] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────────────────┐  ┌──────────────────────────────┐  │
│  │                                 │  │   ANNOTATION PANEL           │  │
│  │  INTERACTIVE IMAGE EDITOR       │  │  ─────────────────────────   │  │
│  │  (Click & Drag to Edit Points)  │  │                              │  │
│  │                                 │  │  Capture 1/3                 │  │
│  │                                 │  │                              │  │
│  │   ┌───────────────────────────┐ │  │  ORIGINAL POINTS:            │  │
│  │   │                           │ │  │  P1: (100, 200)              │  │
│  │   │    🟢 Cable Image 🟢      │ │  │  P2: (300, 200)              │  │
│  │   │    P1●────────●P2        │ │  │  Distance: 200 px → 10 mm    │  │
│  │   │    ✨🟡✨               │ │  │                              │  │
│  │   │    Yellow line            │ │  │  EDITED POINTS: (LIVE)       │  │
│  │   │                           │ │  │  P1: (105, 205)              │  │
│  │   │    10 mm (200px)          │ │  │  P2: (305, 205)              │  │
│  │   │                           │ │  │  Distance: 200 px           │  │
│  │   └───────────────────────────┘ │  │                              │  │
│  │                                 │  │  CABLE STATE:                │  │
│  │                                 │  │  ◉ 🔴 No Cable               │  │
│  │                                 │  │  ○ 🟠 Male End               │  │
│  │                                 │  │  ○ 🟢 Good Cable             │  │
│  │                                 │  │                              │  │
│  │                                 │  │  ┌──────────────────────────┐ │  │
│  │                                 │  │  │ ✓ SAVE & NEXT           │ │  │
│  │                                 │  │  └──────────────────────────┘ │  │
│  │                                 │  │  ┌──────────────────────────┐ │  │
│  │                                 │  │  │ ⊘ SKIP                  │ │  │
│  │                                 │  │  └──────────────────────────┘ │  │
│  │                                 │  │                              │  │
│  │                                 │  │  [◀ PREV] [NEXT ▶]         │  │
│  └─────────────────────────────────┘  └──────────────────────────────┘  │
│                                                                           │
└────────────────────────────────────────────────────────────────────────┘
```

## Key Features

### 1. **Interactive Point Editing (Canvas)**
- **Left Panel:** High-res image with overlay
- **Click & Drag:** Click within 15px of P1/P2 circle to drag and move
- **Real-Time Update:** Distance recalculates as you drag
- **Visual Feedback:**
  - 🟢 Green circles at P1 and P2
  - 🟡 Yellow line connecting points
  - 📏 Distance label in the middle

### 2. **Original vs Edited Comparison**
```
ORIGINAL POINTS          EDITED POINTS (LIVE)
P1: (100, 200)           P1: (105, 205)
P2: (300, 200)      →    P2: (305, 205)
Distance: 200px          Distance: 200px
→ 10 mm
```

### 3. **Cable State Selection**
Annoteur chooses the actual cable condition:
- 🔴 **No Cable** — No cable present in image
- 🟠 **Male End** — Cable has male connector
- 🟢 **Good Cable** — Standard working cable

### 4. **Navigation**
- **PREV/NEXT:** Browse through pending captures
- **SAVE & NEXT:** Save changes and move to next
- **SKIP:** Skip without saving and move to next
- **Status:** Shows "Capture X/Y" for current position

## Interaction Examples

### Scenario 1: Points Too Close
**Original:** P1(100,200) P2(300,200) - 200px distance
**Annoteur Actions:**
1. Clicks P2 and drags right to (350, 200)
2. Sees distance update to 250px in real-time
3. Selects cable state "Good Cable"
4. Clicks "SAVE & NEXT"
**Result:** Corrected points saved to database

### Scenario 2: Misplaced Start Point
**Original:** P1(50,100) - off the cable
**Annoteur Actions:**
1. Clicks P1 circle
2. Drags it to (100, 200) - on the cable
3. Sees new distance: 200px
4. Selects "No Cable" (actually a defect)
5. Clicks "SAVE & NEXT"
**Result:** Corrected point and cable state saved

## Data Flow

```
Machine User                API Server              Annoteur
────────────              ──────────              ────────────
1. Capture image             
2. Mark P1, P2            
3. Upload                 ──[POST /captures/upload]──>
                              ↓ Store
                          ┌───────────┐
                          │ Capture   │
                          │ p1_x=100  │
                          │ p2_x=300  │
                          │ Status: OK│
                          └───────────┘
                              ↓
                          4. <──[GET /admin/captures?status=pending]──
                                         Display
                          5. Edit points and state
                          6. <──[PUT /admin/captures/{id}/annotate]──
                              ↓ Update DB
                          ┌───────────┐
                          │ Capture   │
                          │ p1_x=105  │ (edited)
                          │ p2_x=305  │ (edited)
                          │ approved  │
                          └───────────┘
```

## Technical Implementation

### Mouse Interaction
```python
def _on_canvas_press(event):
    # Check if click is within 15px of P1 or P2
    if distance(click, P1) < 15:
        self.dragging_point = "p1"
    elif distance(click, P2) < 15:
        self.dragging_point = "p2"

def _on_canvas_drag(event):
    # Update point position
    if self.dragging_point == "p1":
        self.edited_p1 = (event.x, event.y)
    # Redraw canvas with new points

def _on_canvas_release(event):
    self.dragging_point = None
```

### Distance Calculation
```python
pixel_distance = sqrt((p2_x - p1_x)² + (p2_y - p1_y)²)
measured_mm = pixel_distance * mm_per_pixel
```

### API Endpoint for Saving
```
PUT /admin/captures/{capture_id}/annotate
{
    "p1_x": 105,
    "p1_y": 205,
    "p2_x": 305,
    "p2_y": 205,
    "cable_state": "cable_good",
    "annoteur_approved": true
}
```

## Benefits

✅ **Quality Assurance** — Annoteurs can fix bad measurements from field  
✅ **No Re-measurement** — Edit points instead of re-capturing  
✅ **Cable State Labeling** — Classify cable condition for dataset  
✅ **Visual Feedback** — See changes in real-time  
✅ **Efficient Workflow** — Navigate and review quickly  
✅ **Data Accuracy** — Ensure consistent, high-quality annotations  

## Testing

### Test Data
3 pending captures loaded automatically with:
- Real Dino-Lite cable images
- Pre-marked P1 and P2 points
- Measurement data (10.2mm, 11.8mm, 14.9mm)

### Login
```
Username: annoteur_01
Password: password123
```

## Next Steps for Annoteur

1. ✏️ **Edit Points** if needed (drag/drop)
2. 🎨 **Select Cable State** (radio button)
3. 💾 **Save Annotation** (button click)
4. ➡️ **Next Capture** (auto-advance)

Simple, intuitive, professional workflow! 🚀
