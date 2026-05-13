# Bellmounth Cable Measurement System - Setup Guide

## Prerequisites

### 1. Python Installation
- Python 3.8 or higher
- Install from: https://www.python.org/downloads/

### 2. Dino-Lite SDK (Already Included)

The DNX64 SDK DLL is already included in the `lib/` directory of this project. No separate installation needed!

The project uses the DNX64 SDK from Dino-Lite for microscope integration and pixel measurement. The DLL is bundled, so the app will work on any Windows PC without additional SDK installation.

### 3. Python Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `opencv-python` - Camera and image processing
- `numpy` - Numerical computing
- `Pillow` - Image handling
- `tensorflow` - For the CNN model (if using model features)
- `keras` - Deep learning framework

### 4. Camera Setup

Ensure a compatible camera is connected to your computer. The system uses OpenCV's default camera detection.

## Running the Application

### Main Cable Detection Application
```bash
python app.py
```

### Model Training/Inference Application
```bash
cd model_bellmounth_mesure
python model_app.py
```

## Project Structure

```
bellmounth-project/
├── app.py                           # Main cable detection GUI
├── cable_detector.py               # Cable detection logic
├── camera_setup.py                 # Camera initialization
├── interaction_setup.py            # Mouse/zoom controls
├── pixelmeasure.py                 # SDK wrapper for measurements
├── handle_screenshot.py            # Screenshot saving
├── model_bellmounth_mesure/        # ML model directory
│   ├── model_app.py               # Model training/inference UI
│   ├── model/                     # Trained models
│   │   └── CNN_BELMOUNTH_MODEL_V1.h5
│   ├── dino_camera.py             # Dino camera utilities
│   └── utils.py                   # Helper functions
└── requirements.txt               # Python dependencies
```

## Features

### Cable Detection
- Real-time camera feed with OpenCV
- Automatic cable detection using contour detection
- Cable position validation (IN/OUT status)
- Visual overlay with bounding boxes

### Interaction Controls
- **Scroll Wheel** - Zoom in/out (1x to 10x)
- **Click & Drag** - Pan when zoomed

### Screenshot Capture
- Capture current frame with measurement data
- Zoom level and mm/pixel ratio stored in filename

### ML Model
- CNN model for advanced cable classification
- Training capability with captured datasets
- Integration with live camera feed

## Troubleshooting

### DNX64 SDK Issues
- If you get "DNX64.dll not found", reinstall the Dino-Lite SDK
- Verify the DLL path in `app.py` matches your installation

### Camera Not Detected
- Check camera connection and Windows Device Manager
- Try changing camera index in `camera_setup.py`:
  ```python
  cap = get_camera(index=1)  # Try different index
  ```

### TensorFlow/Model Issues
- Models require TensorFlow/Keras: `pip install tensorflow`
- H5 model file should be in `model_bellmounth_mesure/model/`

## Contact & Support

For Dino-Lite SDK support: http://www.dinolite.com.cn/En/

---
**Last Updated:** May 2026
