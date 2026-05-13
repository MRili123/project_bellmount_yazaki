# Bellmounth Mesure - Testing Guide

## Running the Application

```bash
py -3.11 app.py
```

## Testing Checklist

### 1. Login Screen
- [ ] Login window appears with "◈ BELLMOUNTH MESURE" title
- [ ] Machine Name field pre-filled with "LAB-01" from config.json
- [ ] Password field is masked (shows dots/bullets)
- [ ] Try wrong password → "❌ Incorrect password" error appears
- [ ] Try correct password ("bellmounth") → logs in and closes login window

### 2. Camera Detection & Startup
- [ ] Main app loads after successful login
- [ ] Window title shows "Bellmounth Mesure - LAB-01"
- [ ] Camera feed appears in left panel (black if no camera connected)
- [ ] If Dino-Lite not found → full-screen error with "⚠️ No Dino-Lite Camera Detected"
- [ ] Error screen has "Retry" and "Quit" buttons

### 3. Top Bar
- [ ] Shows "◈ BELLMOUNTH MESURE" logo/text in blue (#4F8EF7)
- [ ] Shows "Machine: LAB-01" in white text
- [ ] Red "⏻ QUIT" button on right side closes app

### 4. Camera Feed (Left Panel)
- [ ] Live video feed displays in black canvas
- [ ] Mouse scroll wheel zooms in (1x → 10x max)
- [ ] Scroll out zooms back down
- [ ] Click + drag pans around zoomed image
- [ ] Cable detection status shown on feed (green "Cable IN" or red "Cable OUT")

### 5. Mode Switching
- [ ] Default mode is "AUTO CNN" (blue button)
- [ ] Click "MANUAL" button → switches to manual mode (button turns gray, AUTO turns gray)
- [ ] In MANUAL: can place two points by clicking on camera feed
- [ ] In AUTO: clicking CAPTURE runs model inference

### 6. Auto CNN Mode
- [ ] Click "📸 CAPTURE" button
- [ ] Model loads and runs inference (may take a few seconds first time)
- [ ] P1 and P2 coordinates appear on the feed as green circles with yellow line
- [ ] Distance displays in large green text (e.g., "45.32 mm")
- [ ] P1 and P2 coordinates shown in right panel (e.g., "P1: (412, 305)")
- [ ] "💾 Save Annotation" button becomes enabled (yellow)

### 7. Manual Mode
- [ ] Switch to MANUAL mode
- [ ] Click once on camera feed → P1 placed (green circle)
- [ ] Click second time → P2 placed (green circle with yellow line connecting)
- [ ] Distance auto-calculated and shown in green text
- [ ] "💾 Save Annotation" button becomes enabled

### 8. Status Bar (Bottom)
- [ ] Shows "Zoom: --x" (updates as you scroll)
- [ ] Shows "-- mm/px" (real-time value from SDK)
- [ ] Shows "●Cable IN" or "●Cable OUT" with appropriate color
- [ ] All three values update every frame

### 9. LED Controls
- [ ] Click "ON" button → LED turns on (if hardware connected)
- [ ] Click "OFF" button → LED turns off
- [ ] Move "Brightness" slider (1-6) → adjusts brightness
- [ ] No errors if hardware not connected (silent fail)

### 10. Save Annotation
- [ ] With P1 and P2 set, click "💾 Save Annotation"
- [ ] Saves images to `model_bellmounth_mesure/dataset/original/` and `.../thresholded/`
- [ ] Creates entry in `model_bellmounth_mesure/dataset/annotations.json`
- [ ] Dataset counter increments (e.g., "Dataset: 142 items")
- [ ] Multiple saves accumulate in dataset

### 11. Annotation JSON Format
Verify saved annotations contain:
```json
{
  "id": "<uuid>",
  "filename": "capture_YYYYMMDD_HHMMSS_mmm.png",
  "original_path": "...",
  "thresholded_path": "...",
  "width": 1920,
  "height": 1440,
  "points": [
    {"label": "point_1", "x": 412, "y": 305},
    {"label": "point_2", "x": 874, "y": 692}
  ],
  "pixel_distance": 562.34,
  "timestamp": "ISO8601"
}
```

## Common Issues & Solutions

### App Won't Start
- Ensure Python 3.11+ installed: `python --version`
- Install dependencies: `pip install -r requirements.txt`
- Check config.json exists in project root

### No Camera Feed
- Ensure camera/Dino-Lite connected to computer
- Check Windows Device Manager for camera device
- Try clicking "Retry" on error screen

### Model Load Error
- Ensure `model_bellmounth_mesure/model/CNN_BELMOUNTH_MODEL_V1.h5` exists
- File should be ~1.9GB (tracked with Git LFS)
- Run `git lfs install` and `git lfs pull` if model missing

### LED Commands Not Working
- SDK may not be available or hardware not connected
- App continues silently (catch block prevents crash)
- Check SDK installation: https://dinolite.com

## Color Reference
- Background: #0D0F14
- Surface: #141720
- Card: #1A1E2A
- Accent Blue: #4F8EF7
- Success Green: #3DDB7E
- Error Red: #F75F5F
- Warning Yellow: #F7C948
- Text: #E8ECF5
- Muted: #6B7394
