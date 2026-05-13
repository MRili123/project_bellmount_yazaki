# Bellmounth Cable Measurement System - Project Context

## Project Overview

**Bellmounth Cable Measurement System** is a Python application for detecting and measuring cables using a Dino-Lite microscope camera with real-time image processing and machine learning model integration.

**GitHub:** https://github.com/MRili123/project_bellmount_yazaki  
**Git User:** MRili123  
**Owner Email:** iliasssjb2004@gmail.com

## What This Project Does

1. **Live Cable Detection** - Real-time camera feed with OpenCV-based cable detection
2. **Position Validation** - Detects if cable is IN (between validation zones) or OUT
3. **Interactive Controls** - Mouse zoom (1x-10x) and pan for precise viewing
4. **Screenshot Capture** - Takes screenshots with zoom level and mm/pixel measurements
5. **ML Model Integration** - CNN model for advanced cable classification
6. **Dino-Lite Microscope Integration** - Uses DNX64 SDK for precise measurements

## Key Technologies

- **Python 3.8+**
- **OpenCV** - Image processing and cable detection
- **TensorFlow/Keras** - ML model (CNN_BELMOUNTH_MODEL_V1.h5)
- **Tkinter** - GUI
- **Pillow** - Image handling
- **Git LFS** - For large model files (1.9 GB)
- **DNX64 SDK** - Dino-Lite camera integration (bundled in `lib/DNX64.dll`)

## Project Structure

```
bellmounth-project/
├── app.py                              # Main cable detection application
├── cable_detector.py                   # Cable detection logic with contour analysis
├── camera_setup.py                     # OpenCV camera initialization
├── interaction_setup.py                # Mouse/zoom interaction handlers
├── pixelmeasure.py                     # DNX64 SDK wrapper (uses bundled DLL)
├── handle_screenshot.py                # Screenshot saving with metadata
├── requirements.txt                    # Python dependencies
├── SETUP.md                            # Setup guide for new users
├── CLAUDE.md                           # This file - project context
├── lib/
│   └── DNX64.dll                      # Dino-Lite SDK (bundled - no install needed)
├── model_bellmounth_mesure/           # ML training module
│   ├── model_app.py                   # Training/inference UI
│   ├── model_section.py               # Model section handlers
│   ├── capture_section.py             # Data capture for training
│   ├── inbox_section.py               # Data inbox management
│   ├── dino_camera.py                 # Camera utilities
│   ├── utils.py                       # Helper functions
│   └── model/
│       └── CNN_BELMOUNTH_MODEL_V1.h5  # Trained CNN model (1.9 GB, via Git LFS)
├── check_annotations.py                # Data validation tool
├── verify_training_data.py             # Training data verification
└── .gitignore                          # Excludes screenshots, test images, cache

```

## Important Configuration Details

### DNX64 SDK (Dino-Lite Microscope)
- **Bundled in:** `lib/DNX64.dll` (1.1 MB)
- **No external installation needed** - DLL is included in the repo
- **Auto-loaded by:** `pixelmeasure.py` (looks for local DLL first)
- **Calibration values in pixelmeasure.py:**
  - `CALIB_ZOOM = 34.58`
  - `CALIB_MM_PER_PIXEL = 0.0165`

### Git LFS (Large File Storage)
- **Model file tracked via Git LFS:** `model_bellmounth_mesure/model/CNN_BELMOUNTH_MODEL_V1.h5` (1.9 GB)
- **Configuration:** `.gitattributes` (tracks `*.h5` files)
- **Why:** GitHub 100MB file limit requires LFS for large models

### .gitignore Configuration
- Excludes: screenshots, test images, Python cache, IDE files
- Keep this intact when adding new files
- Current patterns exclude:
  - `screenshot/` and `screenshots/`
  - `test_viz_*.png` and `*.png`
  - `model_bellmounth_mesure/screenshots/` and `model_bellmounth_mesure/captured/`
  - `__pycache__/`, `*.pyc`

## What I (Claude) Have Done

### Session: May 13, 2026

1. **Analyzed Project** - Read all main modules to understand architecture
2. **Created Documentation** - Added comprehensive `SETUP.md`
3. **Updated Dependencies** - Added TensorFlow/Keras to `requirements.txt`
4. **Git LFS Setup** - Configured for large `.h5` model files
5. **First Push Attempt** - Encountered GitHub 100MB limit on model file
6. **Fixed with Git LFS** - Properly tracked large files for successful push
7. **Added SDK DLL** - Bundled `DNX64.dll` in `lib/` directory
8. **Updated Code** - Modified `pixelmeasure.py` and `app.py` to use local DLL
9. **Final Push** - Successfully pushed to GitHub with:
   - Latest commit: `b0da199` - "Include DNX64 SDK DLL for standalone operation"
   - Previous: `1370cc8` - "Add CNN model, ML training module, and setup documentation with Git LFS"

### Files Created/Modified
- **Created:** `SETUP.md`, `.gitattributes`, `CLAUDE.md`
- **Modified:** `.gitignore`, `requirements.txt`, `pixelmeasure.py`, `app.py`
- **Added:** `lib/DNX64.dll`, entire `model_bellmounth_mesure/` directory

## How to Use This Repository

### For New Developers (Cloning)
```bash
git clone https://github.com/MRili123/project_bellmount_yazaki.git
cd bellmounth-project
pip install -r requirements.txt
python app.py
```

No SDK installation needed - DLL is bundled!

### For Running the Application
```bash
python app.py              # Main cable detection with live camera
```

### For Model Training/Inference
```bash
cd model_bellmounth_mesure
python model_app.py        # ML training and inference UI
```

## Important Notes

### Cable Detection Algorithm
- Uses OpenCV Canny edge detection
- Filters contours by width > 2× height
- Minimum area threshold: 2000 pixels
- Validates position using center-third zones (1/3 to 2/3 of frame height)
- Needs 10+ consecutive frames to confirm "IN" or "OUT" status

### Git Workflow
- **Main branch:** Production ready (has branch protection considerations)
- **Ilias branch:** Exists as alternative branch
- **Push method:** Use normal push (force push was used to resolve initial conflicts)
- **Large files:** Always tracked with Git LFS

### Performance Considerations
- Frame update interval: 10ms (100 FPS)
- SDK refresh: Every 1 second (to avoid verbose output)
- Zoom range: 1x to 10x

## Future Improvements (Not Yet Implemented)

- Error handling for missing camera
- Fallback UI when SDK DLL missing
- Cross-platform support (currently Windows-only due to DLL)
- Unit tests for cable detection algorithm
- Export detection logs/statistics

## Contact & Support

- **Project Owner:** iliasssjb2004@gmail.com
- **Dino-Lite Support:** http://www.dinolite.com.cn/En/
- **GitHub:** https://github.com/MRili123/project_bellmount_yazaki

---

**Last Updated:** May 13, 2026  
**Created by:** Claude (Haiku 4.5)  
**Status:** Ready for deployment - all dependencies bundled, no external SDK installation needed
