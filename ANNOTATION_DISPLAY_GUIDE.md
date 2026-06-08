# Annotation Display Guide

## Overview

The Bellmounth system now includes a complete annotation viewing and editing interface for the Annoteur role. This guide covers all features for displaying, annotating, and managing cable measurement data.

---

## Dataset Seeding

### What Was Seeded

The `seed_approved_captures.py` script loads 500 approved cable measurement images from the training dataset into the database.

**What gets created:**
- ✅ 500 approved Capture records
- ✅ Random annoteur assignment (from existing annoteur users)
- ✅ Random zoom levels (1.0x - 40.0x)
- ✅ Automatic thresholded image generation
- ✅ Measurement distance calculations
- ✅ Default Machine and Switch if not exist

**How to run:**
```bash
python seed_approved_captures.py
```

**Output:**
```
🌱 Seeding approved captures from dataset...
📋 Loaded 500 annotations
✅ Seeding complete!
   Created: 500 approved captures
   Skipped: 0
```

---

## Annotation Display Features

### 1. **Image Display**

#### Original vs Thresholded Toggle
- **Button:** 🔀 THREAD toggle in toolbar
- **Original View:** Full RGB color cable image
- **Thresholded View:** Binary (black/white) processed image used for ML training
- **Configuration:** kernel=21, C=5 (optimized for cable detection)

#### Automatic Thresholding
- If thresholded image doesn't exist, it's auto-generated using the standard config
- Uses `apply_threshold()` from `utils.py`
- Cached for faster toggling on subsequent uses

### 2. **Zoom & Pan Controls**

#### Zoom Levels
- **Range:** 0.5x to 5.0x
- **Controls:**
  - 🔍− button: Zoom out (decrease by 10%)
  - 🔍+ button: Zoom in (increase by 10%)
  - ⟲ Reset: Return to 1.0x zoom
  - **Mouse Scroll:** Scroll wheel to zoom in/out
- **Display:** Current zoom shown in label (e.g., "2.3x")

#### Pan (Move Image)
- **Method:** Click and drag empty area to pan
- **Bounds:** Automatically clamped to prevent over-panning
- **Works with:** All zoom levels and both image modes

**Key Insight:** When zoomed in, you can freely drag to explore details. The image stays within bounds.

### 3. **Annotation Display**

#### Point Markers
- **P1 (First Point):** Green circle + "P1" label
- **P2 (Second Point):** Green circle + "P2" label
- **Size:** Scales with zoom level for visibility

#### Connecting Line
- **Color:** Yellow
- **Shows:** Direct distance between P1 and P2
- **Updates:** In real-time as points move

#### Distance Calculation
- **Pixel Distance:** Calculated from point coordinates
- **Real Distance:** `pixel_distance × mm_per_pixel`
- **Display:** Shows in pixels and estimated mm
- **Calibration:** Uses SDK zoom values for accuracy

#### Annotation on Both Views
- **Original Image:** Shows P1, P2, and line
- **Thresholded Image:** Same annotations overlaid
- **Purpose:** Verify points align with cable features in both representations

### 4. **Point Editing**

#### Click & Drag
- **Detection:** Clicking within 15px (scaled by zoom) selects a point
- **Dragging:** Selected point follows mouse
- **Feedback:** Point becomes highlighted
- **Real-time:** Display updates as you move

#### Coordinate Transformations
- **Zoom Applied:** `x_zoomed = x * zoom_level`
- **Pan Applied:** `x_display = x_zoomed + pan_x`
- **Reverse Transform:** Click coordinates converted back to image space
- **Tolerance:** Scales with zoom (15px / zoom_level) for consistent clickability

#### Point Validation
- **Required:** Both P1 and P2 must be set
- **Display:** Disabled save button if incomplete
- **Feedback:** Error message if attempting to save without both points

### 5. **Cable State Classification**

#### Three States
1. **🔴 No Cable:** Empty switch, no cable present
2. **🟠 Male End:** Cable with connector/male end visible
3. **🟢 Good Cable:** Proper cable connection/configuration

#### Selection
- **Method:** Radio button selection
- **Color:** Selected option highlighted in red
- **Required:** Must select before approving capture

#### Use Case
- Annoteurs verify cable quality and type
- Data used to train cable state detection model
- Critical for ML accuracy

---

## Annoteur Workflow

### 1. **Login**
```
Username: annoteur_1
Password: [provided by admin]
```

### 2. **Navigate to Annotation**
- Click "BELLMOUNTH CAPTURES" tab
- Shows table of pending captures

### 3. **Review Capture**
- Click "VIEW" button to open editor modal
- Image loads with existing annotations (P1, P2)

### 4. **Verify/Edit Annotations**
```
Option 1: Accept existing points
  - Check if P1/P2 are correctly positioned
  - Select cable state
  - Click ✓ SAVE

Option 2: Adjust points (if misaligned)
  - Zoom in (🔍+ or scroll) to see details
  - Drag points to correct position
  - View thresholded image (🔀 THREAD) for reference
  - Pan to explore (drag empty area)
  - Select cable state
  - Click ✓ SAVE
```

### 5. **View Thresholded Reference**
```
Why toggle to thresholded:
  - Verify points align with cable contours
  - Check for noise or processing artifacts
  - Ensure points are on actual cable structure
  - Binary view easier for verification
```

### 6. **Save Annotations**
- ✓ SAVE button submits to API
- API endpoint: `PUT /admin/captures/{id}/annotate`
- Data sent:
  - Edited P1/P2 coordinates
  - Selected cable state
  - Quality score (auto-set to 0.95)

### 7. **Move to Next Capture**
- Table auto-refreshes after save
- Move to next pending capture

---

## Technical Implementation

### Canvas-Based Rendering

**Why Canvas?**
- Efficient zoom/pan transformations
- Fast point drawing and updates
- Smooth mouse interactions
- Works with Tkinter natively

**Architecture:**
```python
class CaptureEditorModal:
    # Image management
    self.current_image_pil          # Original RGB image
    self.thresholded_image_pil      # Binary thresholded image
    
    # Annotation state
    self.edited_p1 = (x, y)         # Point 1 coordinates
    self.edited_p2 = (x, y)         # Point 2 coordinates
    
    # Display state
    self.zoom_level = 2.0           # Current zoom (0.5 - 5.0)
    self.pan_x, self.pan_y = 0, 0   # Pan offset in pixels
    self.thread_mode = False        # Toggle: original vs thresholded
```

### Key Methods

#### `_load_image()`
```python
# Loads original and thresholded images from paths
# Generates thresholded if missing
# Stores both as PIL Images for fast rendering
```

#### `_redraw_canvas()`
```python
# Called on: zoom change, pan, point drag, mode toggle
# Process:
#   1. Apply zoom to image (crop + resize)
#   2. Apply pan offset
#   3. Display on canvas
#   4. Draw P1/P2 with zoom-scaled coordinates
#   5. Draw connecting line
#   6. Draw labels
```

#### `_on_canvas_drag(event)`
```python
# Detects: click on point vs empty area
# If point: drag point, update coordinates
# If empty: pan image
# Coordinate transformation: canvas → image space → display
```

### Annotation Persistence

**Database Schema:**
```sql
Capture (
  id: UUID,
  machine_id: FK,
  switch_id: FK,
  annoteur_id: FK,
  image_original_path: String,
  image_thresholded_path: String,
  p1_x, p1_y, p2_x, p2_y: Integer,
  measured_distance_mm: Float,
  zoom_level: Float,
  annoteur_approved: Boolean,
  in_training_dataset: Boolean,
  quality_score: Float,
  cable_state: Enum,  -- From StateAnnotation table
)
```

**Update Flow:**
```
User clicks ✓ SAVE
  ↓
CaptureEditorModal._save_changes()
  ↓
api_client.put("/admin/captures/{id}/annotate", {
  "p1_x": 526,
  "p1_y": 198,
  "p2_x": 463,
  "p2_y": 198,
  "cable_state": "cable_good"
})
  ↓
API validates and updates Capture record
  ↓
Database persists changes
  ↓
Modal closes, table refreshes
```

---

## Performance Considerations

### Image Caching
- **Original:** Loaded once at modal open
- **Thresholded:** Generated once on first toggle, cached
- **Benefit:** Fast switching between views

### Zoom Efficiency
- **Avoid expensive transforms:** Only applied during display
- **Point coordinates:** Stored in original image space
- **Display transform:** Applied only for rendering (not stored)

### Pan Bounds
- **Computed:** `max_pan_x = (w - new_w) / 2`
- **Clamped:** Prevents transparent areas
- **Smooth:** No visual jitter when dragging to bounds

### Mouse Responsiveness
- **Tolerance scaling:** `15px / zoom_level`
- **Consistent:** Points clickable at any zoom
- **Example:** At 2x zoom, 7.5px clickable radius

---

## Troubleshooting

### Image Not Displaying
- ✓ Check image path exists in database
- ✓ Verify original_path and thresholded_path are correct
- ✓ Check file permissions

### Points Not Visible
- ✓ Try zooming in (🔍+)
- ✓ Check zoom level is between 0.5x - 5.0x
- ✓ Toggle to thresholded view to see different details

### Can't Move Image
- ✓ Make sure you're clicking empty area, not on points
- ✓ Only works when zoomed in (zoom > 1.0x)
- ✓ Try dragging in different direction

### Thresholding Slow
- ✓ First toggle takes 1-2 seconds (generation)
- ✓ Subsequent toggles instant (cached)
- ✓ This is normal

### Points Jump When Dragging
- ✓ Likely missing pan offset in coordinate conversion
- ✓ Check pan_x/pan_y application in mouse event handler
- ✓ Test with pan_x=0, pan_y=0 first

---

## Future Enhancements

### Potential Improvements
1. **Measurement Mode**
   - Show real distance in mm during annotation
   - Multi-point annotations (more than 2 points)
   - Distance from known reference

2. **Advanced Visualization**
   - Overlay grid for alignment
   - Measurement history (previous annotations)
   - Confidence score per point

3. **Batch Operations**
   - Approve multiple captures at once
   - Copy annotations from similar captures
   - Template-based annotation

4. **ML Integration**
   - Auto-suggest P1/P2 positions
   - Confidence score for suggestions
   - Train on-the-fly as annotateurs work

---

## Summary

The annotation display system provides:

✅ **Professional UI** - Dark theme, intuitive controls  
✅ **Flexible Zoom** - 0.5x to 5.0x with smooth interactions  
✅ **Free Panning** - Click and drag to explore  
✅ **Dual Views** - Toggle original ↔ thresholded  
✅ **Point Editing** - Drag points for pixel-perfect placement  
✅ **Real-time Feedback** - Distance, zoom level, coordinates  
✅ **Data Persistence** - Saves to database automatically  
✅ **Production Ready** - Fully tested with 500 approved captures  

**Ready to use!** Annoteurs can now review and edit cable measurements with full visual control.
