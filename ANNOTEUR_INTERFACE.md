# Annoteur Interface - Cable State Annotation System

## Overview
The annoteur UI is now fully implemented and ready for cable measurement annotation. Annoteurs can review pending captures from field measurements and approve them for training dataset inclusion.

## Interface Layout

```
┌─────────────────────────────────────────────────────────────────┐
│ Annotation Interface                    Username    HH:MM:SS  [LOGOUT] │
├─────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Cable State Annotation              [🔄 REFRESH]                  │
│  Capture 1 of 3                                                    │
│                                                                      │
│  ┌──────────────────────────┐  ┌───────────────────────────────┐  │
│  │                          │  │  APPROVE CAPTURE              │  │
│  │                          │  │  ─────────────────────────    │  │
│  │                          │  │                               │  │
│  │     CABLE IMAGE          │  │  Measured: 10.2 mm            │  │
│  │   (700×600 pixels)       │  │  Status: okay                 │  │
│  │                          │  │  Method: manual               │  │
│  │    [Real microscope      │  │  Quality: 0.85                │  │
│  │     cable photo from     │  │                               │  │
│  │     capture_20260427...]  │  │                               │  │
│  │                          │  │  ┌─────────────────────────┐  │  │
│  │                          │  │  │ ✓ APPROVE               │  │  │
│  │                          │  │  └─────────────────────────┘  │  │
│  │                          │  │  ┌─────────────────────────┐  │  │
│  │                          │  │  │   SKIP                  │  │  │
│  │                          │  │  └─────────────────────────┘  │  │
│  │                          │  │                               │  │
│  │                          │  │ [◀ PREV] ... [NEXT ▶]         │  │
│  └──────────────────────────┘  └───────────────────────────────┘  │
│                                                                      │
│  Machine: f2114106...  Switch: fc619508...                         │
│  Measured: 10.2 mm  Status: okay  Method: manual                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Features

### Image Display
- **Left Panel:** Full-size cable measurement image (700×600 pixels)
- **Real Images:** Uses actual Dino-Lite microscope captures
- **Details:** Machine, switch, and measurement info below image
- **Responsive:** Scales to fit while maintaining aspect ratio

### Annotation Controls (Right Panel)
- **Approval Button:** Click to approve measurement
- **Skip Button:** Defer to next capture without approving
- **Navigation:** Previous/Next buttons to browse captures
- **Status:** Shows current position (e.g., "Capture 1 of 3")
- **Refresh:** Reload queue for new captures

### Measurement Details
Each capture displays:
- **Measured Distance:** e.g., "10.2 mm"
- **Measurement Status:** "okay" or other statuses
- **Capture Method:** "manual" or "auto_cnn"
- **Quality Score:** 0.0-1.0 rating

## Sample Captures

Three real cable images are pre-loaded for testing:

### Capture 1
- **Image:** capture_20260427_081507_737.png
- **Machine:** LAB-01
- **Switch:** Standard Cable
- **Measured:** 10.2 mm
- **Status:** Okay

### Capture 2
- **Image:** capture_20260427_081510_785.png
- **Machine:** LAB-01
- **Switch:** Reinforced Cable
- **Measured:** 11.8 mm
- **Status:** Okay

### Capture 3
- **Image:** capture_20260427_140211_885.png
- **Machine:** LAB-02
- **Switch:** Coaxial Cable
- **Measured:** 14.9 mm
- **Status:** Okay

## Login Credentials

```
Username: annoteur_01
Password: password123
```

Or use:
```
Username: annoteur_02
Password: password123
```

## Workflow

1. **Login** → Select "annoteur_01" with password "password123"
2. **Load Queue** → App automatically loads pending (unassigned) captures
3. **Review Image** → View the cable measurement photo
4. **Inspect Details** → Check measurement value, status, quality
5. **Approve** → Click "✓ APPROVE" to mark as reviewed
6. **Next** → Automatically advances to next pending capture
7. **Repeat** → Continue until all captures are reviewed
8. **Done** → "All Caught Up!" message when queue is empty

## API Integration

The AnnoteurApp uses:
- `GET /admin/captures?status=pending` → Load unassigned captures
- `PUT /admin/captures/{capture_id}/approve` → Approve a measurement

## Technical Details

- **Framework:** Tkinter (Python GUI)
- **Color Scheme:** Professional dark theme with red accents
- **Resolution:** Auto-maximized to fill screen
- **Image Format:** PNG/JPEG support
- **Performance:** Lightweight, no heavy processing

## Notes

- Images are from the actual Dino-Lite microscope captures
- All real measurement metadata is included
- Interface is ready for production use
- Supports multiple annoteurs working in parallel
