# Professional Dark Pro UI Redesign — Bellmounth Inspection System

## Overview
Complete visual overhaul of `app.py` to match enterprise measurement software (Cognex, Keyence, professional tools like VS Code). All logic methods unchanged — only UI styling and layout redesigned.

---

## What Changed

### Color Palette: Dark Pro Theme
| Element | Old | New | Purpose |
|---------|-----|-----|---------|
| Background | #0D0F14 | #0C0C12 | Near-black for reduced eye strain |
| Panels | #141720 | #101018 | Header/sidebar backgrounds |
| Cards | #1A1E2A | #15151E | Card backgrounds |
| Borders | #252A38 | #20202E | Subtle 1px borders everywhere |
| Buttons | #4F8EF7 | #0D47A1 | Dark blue, less aggressive |
| Accent/Values | #4F8EF7 | #00BFFF | Deep sky cyan for measurements |
| Text | #E8ECF5 | #E8E8F0 | High contrast, consistent |
| Muted Labels | #6B7394 | #5C5C7A | Section headers, secondary text |

### Login Screen
**Before:** Basic Tkinter window with generic styling  
**After:**
- 480×560 centered window (not resizable)
- "YAZAKI" branding in header (12pt bold)
- "BELLMOUNTH INSPECTION SYSTEM" subtitle in cyan (22pt bold)
- Separators with subtle borders
- Consolas font (12pt) for entry fields with 1px border highlights
- Large "SIGN IN" button (44px height) in dark blue
- Error messages in red
- Footer: "v1.0 — LAB-01"

### Main App Layout
**Before:** Three simple areas (top bar, left canvas, right LabelFrames, bottom bar)  
**After:**

#### Header Bar (58px)
Professional layout with multiple sections separated by 1px vertical lines:
- Left: "YAZAKI" (13pt bold) | separator | "BELLMOUNTH INSPECTION SYSTEM" (13pt cyan)
- Center: spacer
- Right: "● LIVE" indicator (red dot) | separator | machine name | separator | live clock | separator | "QUIT" button (red)

#### Content Area (left canvas + right panel)
- **Canvas:** Wrapped in 1px border frame, fills left side
- **Right Panel (330px fixed width, PANEL background):**
  5 professional cards stacked vertically

#### Card Components
Each card has:
- Custom `_card()` method → 1px BORDER frame around CARD background
- Section title in uppercase (8pt bold, TEXT2 color)
- Horizontal separator line (1px SEP color)
- Consistent padding (12px padx, 10-12px pady)

**Card 1: MEASUREMENT**
```
         45.32
         mm
        ─────
ZOOM 34.58x    MM/PX 0.0165
        ─────
P1  (412, 305)  P2  (874, 692)
```
- Large value: Consolas 38pt bold, ACCENT color
- Unit: Arial 11, TEXT2
- Data grid: two-column layout (ZOOM | MM/PX)
- Coords: side-by-side P1 and P2

**Card 2: STATUS**
```
● Cable IN    ● Camera OK
```
- Left: colored dot (GREEN/RED) + "CABLE IN/OUT" label
- Right: green dot + "CAMERA OK" label
- Both updated every frame

**Card 3: ANALYSIS MODE**
```
[AUTO CNN]  [MANUAL]
```
- Two buttons side by side
- Active mode: dark blue (#0D47A1)
- Inactive mode: charcoal (#1C1C28)
- Toggle updates button colors

**Card 4: ACTIONS**
```
[CAPTURE]
[SAVE ANNOTATION]
500 samples
```
- CAPTURE: dark blue button, full width, 44px height
- SAVE ANNOTATION: amber (#FFB300) when enabled, charcoal (#1C1C28) when disabled
- Dataset counter: right-aligned, small text

**Card 5: ILLUMINATION**
```
[LED ON]  [LED OFF]
BRIGHTNESS ──●───
```
- ON button: green (#00E676)
- OFF button: charcoal
- Slider: styled with cyan active background

#### Bottom Status Bar (30px)
- 1px top border (SEP color)
- Left: "YAZAKI INSPECTION SYSTEM  v1.0"
- Right: (reserved for future additions)
- Clock display automatically updates every 1 second

### Camera Canvas Improvements
**Drawing enhancements:**
- **Points:** 16px cyan ring (#00BFFF) with 5px white center dot
- **Line:** Dashed cyan line (segments every 16px) connecting P1 to P2
- **Distance Label:** Floating semi-transparent pill at midpoint
  - Black background box
  - Cyan text: "45.32 mm"
  - Positioned above the line midpoint
- **Manual Mode Hint:** Bottom-left overlay text
  - Black background
  - Cyan text: "CLICK TO PLACE P1" (or P2)
  - Disappears when both points placed

---

## Typography
| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| App name | Arial | 13 | bold | ACCENT |
| Section headers | Arial | 8 | bold | TEXT2 |
| Measurement values | Consolas | 38 | bold | ACCENT |
| Data values | Consolas | 12 | normal | TEXT |
| Coordinates | Consolas | 9 | normal | TEXT2 |
| Button text | Arial | 9-11 | bold | TEXT |
| Labels | Arial | 10 | normal | TEXT |
| Small text | Arial | 8 | normal | TEXT2 |

---

## Professional Details
1. **Borders:** 1px subtle borders everywhere create visual separation without heaviness
2. **Padding:** Consistent 12px horizontal, 10-12px vertical inside cards
3. **Color hierarchy:** Clear primary (TEXT) → secondary (TEXT2) → actionable (BTN/ACCENT)
4. **Disabled states:** Disabled buttons show SEP (charcoal) background, TEXT2 text
5. **State indication:** Active mode buttons dark blue, inactive charcoal
6. **Visual feedback:** Save button color changes (AMBER enabled → SEP disabled)
7. **Status indicators:** Colored dots (GREEN/RED) for cable detection
8. **Clock:** Real-time updates every second in header
9. **Spacing:** 8-12px gaps between cards, 20px padx around panels

---

## Testing Checklist

### Login Screen
- [ ] Window 480×560, centered on screen
- [ ] "YAZAKI" header visible at top
- [ ] Machine name field pre-filled with "LAB-01" (Consolas font)
- [ ] Password field shows bullet points (●) masked
- [ ] "SIGN IN" button is 44px tall, dark blue, spans full width
- [ ] Wrong password shows red error text
- [ ] Correct password ("bellmounth") allows login

### Main App - Header
- [ ] "YAZAKI" branding visible on left
- [ ] "BELLMOUNTH INSPECTION SYSTEM" in cyan
- [ ] Red "● LIVE" indicator visible
- [ ] Machine name shown ("LAB-01")
- [ ] Clock shows current time and updates every second
- [ ] Red "QUIT" button on right closes app

### Main App - Camera
- [ ] Canvas fills left side of window
- [ ] Camera feed displays live video (or black if no camera)
- [ ] 1px gray border frame around canvas
- [ ] Scroll wheel zooms in/out
- [ ] Click + drag pans when zoomed
- [ ] Points and line draw in cyan with white centers
- [ ] MANUAL mode shows "CLICK TO PLACE P1" text at bottom-left

### Right Panel - Measurement Card
- [ ] Distance displays large (38pt) in cyan (#00BFFF)
- [ ] "mm" unit shows below distance
- [ ] ZOOM value updates in real-time (Consolas font)
- [ ] MM/PX value updates in real-time
- [ ] P1 coordinates update when point is placed
- [ ] P2 coordinates update when second point is placed

### Right Panel - Status Card
- [ ] Colored dot for cable status (green IN / red OUT)
- [ ] "Cable IN" or "Cable OUT" label updates
- [ ] Green dot for camera (always green)
- [ ] "CAMERA OK" label visible

### Right Panel - Analysis Mode Card
- [ ] AUTO CNN button: dark blue initially
- [ ] MANUAL button: charcoal initially
- [ ] Click MANUAL → AUTO becomes charcoal, MANUAL becomes dark blue
- [ ] Click AUTO → colors toggle back

### Right Panel - Actions Card
- [ ] "CAPTURE" button: dark blue, full width
- [ ] "SAVE ANNOTATION" button: amber when enabled
- [ ] SAVE becomes charcoal/disabled when no points set
- [ ] Dataset counter shows number of saved samples
- [ ] Clicking CAPTURE in AUTO mode runs inference, populates points
- [ ] Clicking SAVE saves annotation and increments counter

### Right Panel - LED Control Card
- [ ] "LED ON" button: green
- [ ] "LED OFF" button: charcoal
- [ ] "BRIGHTNESS" label visible
- [ ] Slider moves 1-6, styled with cyan active state

### Bottom Status Bar
- [ ] 1px dark separator line at top
- [ ] "YAZAKI INSPECTION SYSTEM v1.0" text visible

---

## What Stayed the Same
✓ All measurement logic (CNN inference, manual distance calculation)  
✓ All SDK interactions (zoom, mm/pixel, LED control)  
✓ All data saving (annotation export to JSON)  
✓ All mouse interactions (scroll, drag, click)  
✓ Cable detection algorithm and display  
✓ Dataset counter and management  

---

## Ready for Yazaki
This UI is now professional enough for client presentations. It demonstrates:
- ✓ Enterprise-grade dark theme (no eye strain)
- ✓ Clear information hierarchy (measurements prominent)
- ✓ Professional typography (Consolas for numbers, Arial for labels)
- ✓ Precise color coding (green OK, red errors, cyan critical values)
- ✓ Responsive interactive elements (buttons, sliders, toggles)
- ✓ Clean, uncluttered layout
- ✓ Real-time status indicators
- ✓ Professional header with branding

---

## Run
```bash
py -3.11 app.py
```

Login: **LAB-01** / **bellmounth**  
Enjoy the professional inspection system!
