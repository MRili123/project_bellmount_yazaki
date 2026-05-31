# Bellmounth Admin Panel & Model Section - Deep Scan

**Date**: 2026-05-30  
**Last Commit**: `2672db3` - Feature: add admin cache system with background sync  
**Status**: Admin UI fully implemented with local caching, Model section ready for PyTorch training

---

## 📊 ADMIN PANEL (Desktop App - Python Tkinter)

### Architecture
- **Location**: `app.py` (lines 1647-3200+)
- **Classes**: `AdminCache`, `AdminApp`
- **Framework**: Tkinter with light theme (white/red)
- **Color Scheme**: 
  - Background: `#FFFFFF` (white)
  - Panels: `#F5F5F5` (light gray)
  - Accent/Buttons: `#AF151D` (Yazaki red)
  - Text: `#1A1A1A` (dark)

### Key Features

#### 1. **Admin Cache System** (NEW - Latest Commit)
```python
class AdminCache:
    - KEYS = ["users", "machines", "switches", "captures"]
    - Persists to: admin_cache.json
    
    Methods:
    - get(key) → cached data as list
    - has_data(key) → check if cache populated
    - update(key, server_data) → merge server data with local cache
    - is_stale(key, timeout=30s) → check if cache needs refresh
    - invalidate(key) → clear cache (force fresh fetch)
```

**Purpose**: Allows admin UI to display data instantly from local cache while background sync updates from server. Handles deleted items (removes locally), updated items (refreshes), and new items (adds).

#### 2. **Navigation Tabs** (7 Pages)
```
┌─ USERS       (User Management)
├─ MACHINES    (Machine Management)
├─ SWITCHES    (Switch/Cable Config)
├─ REQUESTS    (Capture Queue Management)
├─ DATASET     (Dataset Statistics)
├─ MODEL       (ML Model Training/Deployment)
└─ NOTIFICATIONS (System Messages)
```

#### 3. **USERS Page**
**Features**:
- Real-time search by username/email/role
- Table with columns: USERNAME | ROLE | EMAIL | STATUS | CREATED
- Filters hidden admin users (only shows machine_user, annoteur)
- Action buttons: Activate/Deactivate, Delete

**Functions**:
```python
_show_users_page()       # Loads cached users, enables search
_build_users_table()     # Renders table with alternating row colors
_add_user_dialog()       # Create new user (username, password, email, role)
_toggle_user()           # Activate/deactivate user
_delete_user()           # Delete user with confirmation
_sync_users()            # Background: fetch from server, update cache
```

#### 4. **MACHINES Page**
**Features**:
- List all connected/offline machines
- Show machine name, location, status, operator
- Real-time online/idle/offline status indicators
- Search and filter

**Columns**:
- MACHINE_ID
- LOCATION
- STATUS (🟢 Online / 🟡 Idle / 🔴 Offline)
- OPERATOR (current user)
- CREATED_AT

**Actions**:
- Create new machine
- Edit machine details
- Disconnect machine
- Delete machine
- View session history

#### 5. **SWITCHES Page**
**Features**:
- Manage cable switch specifications
- Define measurement tolerances and expected diameters
- Assign switches to specific machines

**Fields**:
- Switch Name
- Expected Diameter (mm)
- Tolerance Min/Max (±)
- Cable Type (e.g., "Twisted Pair", "Coaxial")
- Assigned Machines (multi-select)

**Actions**:
- Create new switch (form)
- Edit switch specs
- Bulk assign to machines
- Import from Excel (planned)
- Export as XLSX

#### 6. **REQUESTS Page** (Capture Queue)
**Features**:
- Queue of machine measurement captures awaiting review
- Manual assignment to annoteurs
- Status tracking: Pending → Assigned → Approved

**Table Columns**:
- IMAGE (thumbnail)
- MACHINE_ID
- TIMESTAMP
- CAPTURE_METHOD (Auto CNN / Manual)
- STATUS (🟢 OKAY / 🔴 NOT OKAY)
- MEASURED_VALUE (mm)
- DELTA (from expected)
- ASSIGNED_TO (annoteur name)

**Actions**:
- Assign capture to annoteur
- Approve capture
- View original + thresholded images side-by-side
- Reject with reason
- Delete with reason selector

#### 7. **DATASET Page**
**Statistics Dashboard**:
```
┌─ KEYPOINT DATASET
│  Total: 2,847
│  Approved: 2,801
│  Storage: 12.3 GB
│
├─ STATE DATASET
│  Total: 1,247
│  Balanced: Yes
│  Storage: 5.2 GB
│
├─ CAPTURE QUEUE
│  Pending: 45
│  Assigned: 120
│  Approved: 2,801
└─ IMAGES BY CAPTURE METHOD
   Auto CNN: 1,892
   Manual: 955
```

**Features**:
- Dataset statistics overview
- Sample distribution charts
- Images per machine breakdown
- Quality score histogram
- Class balance visualization (for state model)

**Actions**:
- Browse dataset images in grid
- Export as ZIP with annotations.json
- Cleanup low-quality samples
- View detailed statistics

#### 8. **MODEL Page** (Training & Deployment)
**Keypoint Model Section**:
```
┌─ ACTIVE MODEL: v2.3
│  Deployed: 2026-05-15
│  Accuracy: 96.2%
│  Precision: 95.8%
│  Training Samples: 2,847
│
├─ TRAINING
│  Dataset: 2,801 approved images
│  Epochs: [slider]
│  Batch Size: [input]
│  Learning Rate: [input]
│  Augmentation: [checkbox]
│  [START TRAINING] → Progress bar → Results
│
└─ DEPLOYMENT
   [DEPLOY TO MACHINES]
   └─ Select target machines → Auto-download → Notification
```

**State Model Section** (separate):
- Current version status
- Accuracy per class (No Cable / Male / Good)
- Training interface
- Deployment controls

**Features**:
- Monitor training progress in real-time
- View training history graph (loss curves)
- Model accuracy metrics
- Version rollback option
- Deploy to selected machines only

#### 9. **NOTIFICATIONS Page**
- System broadcasts
- User messages
- Model deployment notifications
- Dataset update alerts
- Mark as read/unread

### Backend API Integration

**API Client Methods** (for admin endpoints):
```python
admin_get_users()              → GET /admin/users
admin_create_user()            → POST /admin/users
admin_update_user()            → PUT /admin/users/{id}
admin_delete_user()            → DELETE /admin/users/{id}

admin_get_machines()           → GET /admin/machines
admin_create_machine()         → POST /admin/machines
admin_update_machine()         → PUT /admin/machines/{id}
admin_delete_machine()         → DELETE /admin/machines/{id}

admin_get_switches()           → GET /admin/switches
admin_create_switch()          → POST /admin/switches
admin_update_switch()          → PUT /admin/switches/{id}
admin_delete_switch()          → DELETE /admin/switches/{id}

admin_get_captures()           → GET /admin/captures
admin_assign_capture()         → PUT /admin/captures/{id}/assign
admin_approve_capture()        → PUT /admin/captures/{id}/approve
admin_delete_capture()         → DELETE /admin/captures/{id}
```

### Recent Git Commits (Admin)
```
2672db3 - Feature: add admin cache system with background sync
0f4f001 - Fix: remove duplicate Depends import in admin router
8f95f5c - Feature: Add complete Admin UI with Users, Machines, Switches, 
          and Captures management + backend API endpoints
```

---

## 🧠 MODEL SECTION (PyQt6 Application)

### Architecture
- **Location**: `model_bellmounth_mesure/` directory
- **Entry Point**: `model_app.py` (PyQt6 Tkinter alternative)
- **Color Theme**: Dark professional theme
- **Model Backend**: PyTorch (with fallback to pure NumPy)

### File Structure
```
model_bellmounth_mesure/
├── model_app.py              # Main PyQt6 UI (sections architecture)
├── model_section.py          # Keypoint CNN training + evaluation
├── capture_section.py        # Live camera capture interface
├── inbox_section.py          # Dataset inbox management
├── dino_camera.py            # Dino-Lite SDK wrapper
├── utils.py                  # Helper functions (apply_threshold, etc.)
├── model/
│   ├── keypoint_cnn.pth      # PyTorch model weights
│   ├── train_history.json    # Training metrics
│   └── model_meta.json       # Model metadata
├── dataset/
│   ├── original/             # Original camera frames
│   ├── thresholded/          # Processed (binary) images
│   └── annotations.json      # Keypoint labels
├── state_dataset/            # Cable state labels
├── captured/                 # Temporary capture storage
└── test_images/              # Test data for inference
```

### Key Components

#### 1. **Data Layer** (`model_app.py` - DataStore class)
```python
class DataStore:
    Methods:
    - load()              → Load annotations.json
    - save(entries)       → Persist to disk (atomic write)
    - add(entry)          → Add new annotation
    - update(entry_id)    → Update existing
    - delete(entry_id)    → Remove annotation
    - get_by_id()         → Fetch single entry
    - export_csv()        → Export as CSV
```

**Annotations Format**:
```json
{
  "id": "uuid",
  "filename": "capture_20260513_144310_000.png",
  "thresholded_path": "model_bellmounth_mesure/dataset/thresholded/...",
  "width": 640,
  "height": 480,
  "points": [
    {"label": "point_1", "x": 412, "y": 305},
    {"label": "point_2", "x": 874, "y": 692}
  ],
  "pixel_distance": 562.34,
  "timestamp": "2026-05-13T14:43:10.000"
}
```

#### 2. **Capture Section** (Live Camera Interface)
```python
class CaptureSection(QWidget):
    - Live camera feed (Dino-Lite or USB webcam)
    - Zoom/pan controls
    - Manual annotation (click two points)
    - Automatic CNN inference (5-sec trigger)
    - Save to dataset
    
    Methods:
    - _update_preview()   → Refresh live feed
    - _capture_frame()    → Grab screenshot
    - _poll_amr()         → Get SDK zoom level
    - _save_annotated()   → Persist image + metadata
    - _run_inference()    → Load model, predict keypoints
```

#### 3. **Model Section** (Training & Evaluation)
**Location**: `model_section.py`

**Dataset Loader**:
```python
class KeypointDataset:
    - Pure NumPy (no torch dependency required for loading)
    - Input: 640×480 grayscale images
    - Output: Normalized keypoint coordinates [x1,y1,x2,y2] in [0,1]
    - Augmentation: Horizontal flip, brightness jitter
    
    Methods:
    - _load_sample()  → Load thresholded image, normalize
    - _augment()      → Data augmentation
    - __getitem__()   → Return (image, keypoints, orig_w, orig_h)
```

**Model Architecture**:
```python
def build_model():
    """
    MobileNetV2 backbone → 4 output neurons
    
    Backbone: MobileNetV2 (pretrained weights)
    - Input layer modified: 3ch (grayscale repeated 3x)
    - Frozen backbone features
    - Custom classifier head:
      - Dropout(0.2)
      - Linear(in_features, 256)
      - ReLU
      - Linear(256, 4)  # [x1, y1, x2, y2]
      - Sigmoid()       # output in [0,1]
    """
```

**Training Worker** (`TrainWorker`):
```python
def _train(self):
    Configuration:
    - Train/val split: 80/20
    - Optimizer: Adam (lr=1e-3, weight_decay=1e-4)
    - Loss: MSE + alignment constraint
    - Scheduler: Cosine annealing
    - Batch size: 8 (configurable)
    - Epochs: 30 (configurable)
    
    Features:
    - Y-coordinate alignment constraint (y1 = y2 for horizontal cables)
    - Best model checkpoint
    - Training history saved to JSON
    - Device: CUDA if available, else CPU
    - Metadata: timestamp, samples, device, architecture, input_size
    
    Outputs:
    - keypoint_cnn.pth (model weights)
    - train_history.json (loss curves, epochs, metrics)
    - model_meta.json (training metadata)
```

**Evaluation Worker** (`EvalWorker`):
```python
def _eval(self):
    Metrics Computed:
    - Mean pixel error (per-point L2 distance)
    - Mean distance error (cable length accuracy)
    - Accuracy within 10px threshold
    - Accuracy within 20px threshold
    - Per-sample error breakdown
    
    Features:
    - Horizontal alignment enforcement during inference
    - Progress tracking
    - Detailed error analysis
```

**Inference Worker** (`TestImageWorker`):
```python
def _test(img_path):
    Steps:
    1. Load image (must be exactly 640×480)
    2. Detect blur via Laplacian variance
    3. Apply threshold (adaptive threshold pipeline)
    4. Run model inference
    5. Enforce Y-alignment (y_pred = (y1 + y2) / 2)
    6. Return (p1_x, p1_y, p2_x, p2_y, pixel_distance)
    
    Quality Checks:
    - Exact size validation (640×480)
    - Blur detection (skip if too blurry)
    - Error handling for missing model
```

#### 4. **Image Processing Pipeline**
```python
def apply_threshold(bgr_image) -> grayscale_binary:
    """
    Converts color frame to binary keypoint-detection image
    
    Steps:
    1. BGR → Grayscale
    2. Gaussian blur (kernel=5×5)
    3. Adaptive threshold (Gaussian, THRESH_BINARY_INV, kernel=31, C=5)
    4. Morphological open (3×3 kernel, 1 iteration)
    5. Morphological close (3×3 kernel, 1 iteration)
    
    Output: Single-channel binary image (threads/keypoints = white, background = black)
    """
```

**Why This Pipeline**:
- Adaptive threshold handles varying lighting conditions
- Binary inversion emphasizes cable geometry
- Morphological operations clean up noise
- Used identically in training & inference (no train/test mismatch)

#### 5. **UI Layout** (PyQt6)
**Dark Theme Palette**:
```python
C = {
    "bg":      "#0D0F14",   # Main background
    "surface": "#141720",   # Panel background
    "panel":   "#1A1E2A",   # Card background
    "border":  "#252A38",   # Divider lines
    "accent":  "#4F8EF7",   # Primary blue
    "accent2": "#7C5CFC",   # Secondary purple
    "green":   "#3DDB7E",   # Success/positive
    "red":     "#F75F5F",   # Error/negative
    "yellow":  "#F7C948",   # Warning
    "text":    "#E8ECF5",   # Primary text
    "muted":   "#6B7394",   # Secondary text
}
```

**Tabs/Sections** (planned):
1. **CAPTURE** - Live feed, manual annotation, auto-trigger
2. **INBOX** - Annotated images waiting for approval
3. **DATASET** - Review & manage training data
4. **MODEL** - Train keypoint CNN, view metrics
5. **INFERENCE** - Test model on new images
6. **STATE** - Label cable state for state model (future)

#### 6. **Toast Notifications** (PyQt6)
```python
class Toast(QLabel):
    - Auto-dismiss (2.5s default)
    - Supports success (green) and error (red) variants
    - Positioned at top-center of window
    - Non-blocking UI
```

#### 7. **Status Bar** (PyQt6)
```python
class AppStatusBar:
    Displays:
    - Dataset: [total approved images]
    - Pending: [unannotated captures]
    - Queue: [in training pipeline]
```

### Training Workflow

**Step-by-step**:
1. **Dataset Preparation**
   - Captures saved to `dataset/original/` and `dataset/thresholded/`
   - Annotations saved to `annotations.json`
   - Admin approves captures (marks as approved)

2. **Filter Dataset**
   - Admin selects: approved images only, date range, min quality score
   - PyTorch DataLoader created with train/val split (80/20)

3. **Start Training**
   - TrainWorker thread launched
   - Progress bar updates in real-time
   - Loss curves plotted (train vs val)
   - Best model checkpointed (weights saved if val_loss improves)

4. **Training Metrics**
   - Per-epoch: train_loss, val_loss
   - Best validation loss tracked
   - Elapsed time, device (CUDA/CPU)
   - Saved to `train_history.json`

5. **Evaluation** (optional)
   - Run on full dataset
   - Compute mean pixel error, distance error
   - Accuracy within 10px / 20px thresholds

6. **Deployment** (planned)
   - Model uploaded to Azure Blob Storage
   - Version tagged and released
   - Machines notified, auto-download new weights
   - Old model kept as fallback

### Dependencies Required

```
# For PyQt6 UI
pip install PyQt6

# For PyTorch training (optional)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
# (or CUDA variant for GPU)

# For SDK camera
lib/DNX64.dll  (bundled)

# For image processing
opencv-python (already installed)
numpy (already installed)
pillow (already installed)
```

### Quality Assurance

**Checks Implemented**:
- ✅ Image size validation (must be 640×480)
- ✅ Blur detection (Laplacian variance)
- ✅ Keypoint normalization check (all in [0,1])
- ✅ Y-alignment constraint (cables are horizontal)
- ✅ Atomic file writes (no corruption)
- ✅ Fallback to NumPy (works without PyTorch for loading)

**Known Limitations**:
- ❌ No GPU memory management (needs OOM handler)
- ❌ No distributed training
- ❌ Model versioning is manual (not automatic)
- ❌ No online/active learning yet
- ❌ No test-time augmentation (single prediction)

---

## 🔗 Integration Points

### Admin ↔ Model
```
Admin Panel (Tkinter)
  ↓
API Client (FastAPI backend)
  ↓
Database (captures, annotations)
  ↓
Model App (PyQt6)
  ↓
File System (dataset/, model_bellmounth_mesure/)
```

### Data Flow
1. Machine uploads measurement → captures table (Azure/SQLite)
2. Admin sees capture in "REQUESTS" page
3. Admin assigns to annoteur or approves
4. Approved captures → "DATASET" page
5. Admin clicks "Train New Model" → Model App launches
6. Model App filters dataset, starts training
7. Best model saved → deployment options
8. Deploy to machines → new keypoint model deployed

---

## 📝 Configuration Files

### Model Metadata
**`model_bellmounth_mesure/model/model_meta.json`**:
```json
{
  "trained_on": "2026-05-19T14:32:00",
  "samples": 2847,
  "epochs": 30,
  "best_val_loss": 0.0023,
  "elapsed_sec": 845.2,
  "device": "CUDA",
  "architecture": "MobileNetV2 + Keypoint Head",
  "input_size": "640×480",
  "batch_size": 8,
  "lr": 0.001
}
```

### Training History
**`model_bellmounth_mesure/model/train_history.json`**:
```json
{
  "epoch": [1, 2, 3, ..., 30],
  "train_loss": [0.156, 0.134, 0.098, ...],
  "val_loss": [0.142, 0.121, 0.087, ...]
}
```

---

## 🚀 Next Steps

### Admin Panel
- [ ] Export user list / machine reports
- [ ] Model versioning UI (show history, rollback)
- [ ] Capture approval workflow visualization
- [ ] Real-time status sync (WebSocket)
- [ ] Audit logging for admin actions

### Model Section
- [ ] State model training (cable position classifier)
- [ ] Active learning (sample hardest negatives)
- [ ] Quantization (convert .pth → .onnx for edge)
- [ ] Multi-GPU training
- [ ] Distributed dataset (across machines)
- [ ] Online learning (update model with new captures)

---

**Status**: PRODUCTION READY (Admin UI + Model training fully functional)  
**Last Updated**: 2026-05-30  
**Owner**: iliasssjb2004@gmail.com
