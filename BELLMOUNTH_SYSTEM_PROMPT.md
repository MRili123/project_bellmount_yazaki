# 🎯 BELLMOUNTH CABLE MEASUREMENT SYSTEM v2.0
## Complete System Architecture & Implementation Prompt

**Status**: Ready for Development (Phase 1)  
**Last Updated**: 2026-05-19  
**Owner Email**: iliasssjb2004@gmail.com

---

## 📖 EXECUTIVE SUMMARY

Bellmounth is an **enterprise cable measurement and quality control system** with three distinct user roles:
- **Machine Users** (Factory Floor Operators) - Measure cables using automated CNN model
- **Annoteurs** (Quality Assurance) - Review captures + label cable state for ML training
- **Admin Users** (System Administrator) - Manage all users, train/deploy models, configure switches

**Core Features**:
- Real-time cable measurement with pass/fail indicators
- Dual ML models: Keypoint detection (measurement) + State detection (cable position)
- Cloud-based Azure database for centralized data management
- Notification system for updates and user communication
- Complete dataset management for continuous model improvement

---

## 👥 USER ROLES & DETAILED WORKFLOWS

### 1️⃣ MACHINE USER (Factory Floor Operator)

**Authentication**: Machine Name + Password (encrypted)  
**Requirement**: MUST BE ONLINE (no offline mode)

#### **Dashboard Structure**
```
┌─────────────────────────────────────────────┐
│ BELLMOUNTH INSPECTION SYSTEM                │
│ Machine: LAB-01  │  User Session  │  [QUIT]│
├─────────────────────────────────────────────┤
│ [SWITCHES] [MEASURE] [NOTIFICATIONS]        │
└─────────────────────────────────────────────┘
```

#### **PAGE 1: SWITCHES SELECTION**

**Display**: Grid/List of all available switches

**Switch Card Shows**:
- Switch ID / Name
- Expected cable diameter (mm)
- Tolerance range (min-max mm)
- Cable type / Material
- Last updated timestamp
- Status badge (Active/Inactive)

**Search Bar**:
- Real-time filtering by switch name, ID, or cable type
- Highlight matching results
- Display count of matching switches

**Selection Flow**:
1. User sees all switches
2. Clicks switch to select
3. Stored in session
4. Navigates to MEASUREMENT page with selected switch info displayed

#### **PAGE 2: MEASUREMENT SECTION**

**Layout**: Canvas + Right panel (reuse existing app.py structure)

**New Elements**:
```
┌──────────────────────────────────────────────┐
│ SELECTED: SWITCH-001                         │
│ Expected: 10.5mm  │  Range: 10.0-11.0mm     │
├──────────────────────────────────────────────┤
│ [LIVE CAMERA FEED WITH OVERLAY]              │
│ P1: (526, 198)  P2: (463, 198)               │
│ MEASUREMENT: 10.42mm                         │
│ 🟢 OKAY (±0.08mm) or 🔴 NOT OKAY (+0.85mm)  │
└──────────────────────────────────────────────┘
```

**Measurement Display**:
- Show selected switch name in header
- Show expected range and tolerance
- After clicking CAPTURE:
  - Display measurement value
  - Show status: 🟢 OKAY (within tolerance) or 🔴 NOT OKAY (outside tolerance)
  - Show delta from expected value
  - Color-coded indicator

**Upload Flow**:
1. User performs measurement (AUTO or MANUAL)
2. Result displays with OKAY/NOT OKAY status
3. User clicks **[UPLOAD]** button (NOT automatic)
4. Measurement uploaded to Azure:
   - Image (original + thresholded)
   - P1/P2 coordinates
   - Measured distance
   - Selected switch
   - Measurement status
   - Timestamp
5. Success notification: "✓ Uploaded"

#### **PAGE 3: NOTIFICATIONS SECTION**

**Tabs**:

1. **Updates Tab**:
   - Admin broadcasts (new model versions, switch updates)
   - Download buttons with version info
   - Timestamp
   - Status (Read/Unread)

2. **Messages Tab**:
   - Direct messages from admin
   - Read/Unread badges
   - Timestamp
   - Action buttons if applicable

3. **Reclamations Tab** (Support Tickets):
   - Text area: "Report an issue"
   - Image attachment support
   - Categories dropdown:
     ```
     - Bug / Performance Issue
     - Incorrect Measurement
     - Hardware Problem
     - Other
     ```
   - Submit button
   - Ticket ID auto-generated
   - Status tracking (Open / In Progress / Resolved)

---

### 2️⃣ ANNOTEUR USER (Quality Assurance / Data Labeler)

**Authentication**: Username + Password  
**Requirement**: MUST BE ONLINE

#### **Dashboard: Task Selection**
```
┌─────────────────────────────────────────────┐
│ BELLMOUNTH ANNOTATION SYSTEM                │
│ User: annoteur_01  │  [NOTIFICATIONS]       │
├─────────────────────────────────────────────┤
│ [REVIEW CAPTURES]          [LABEL STATE]    │
│ Review machine captures    Label cable state│
│ & edit annotations        for model training│
└─────────────────────────────────────────────┘
```

#### **PAGE 1: REVIEW CAPTURES (Machine Measurements)**

**Capture Queue Table**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Image │ Machine │ Timestamp  │ Method    │ Status       │ Distance   │ ▼    │
├─────────────────────────────────────────────────────────────────────────────┤
│ [img] │ LAB-01  │ 2026-05-19 │ Auto CNN  │ 🟢 OKAY      │ 10.42 mm   │[>]  │
│       │         │ 14:32:45   │           │              │ (±0.08)    │     │
├─────────────────────────────────────────────────────────────────────────────┤
│ [img] │ LAB-02  │ 2026-05-19 │ Manual    │ 🔴 NOT OKAY  │ 11.85 mm   │[>]  │
│       │         │ 14:30:12   │           │              │ (+0.85)    │     │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Columns**:
- Thumbnail image
- Machine name
- Timestamp
- Capture method (Auto CNN / Manual)
- Status (🟢 OKAY / 🔴 NOT OKAY)
- Measured distance with delta
- Actions menu

**Filters & Search**:
- Filter by machine name
- Filter by capture method
- Filter by measurement status (OKAY/NOT OKAY)
- Filter by switch/cable type
- Date range picker
- Search by filename
- Approval status (Approved/Rejected/Pending)

**Action Buttons**:

1. **View & Edit**:
   - Fullscreen image viewer
   - Show original + thresholded side-by-side
   - Overlay current P1/P2 points
   - **Can edit points** (click to adjust)
   - Save edited coordinates
   - Feedback: "✓ Points Updated"

2. **Approve**:
   - Mark as "Quality OK"
   - Green badge: "✓ Approved"
   - Ready for model training

3. **Reject**:
   - Mark as "Quality Issues"
   - Modal: "Reason for rejection"
   - Send notification to machine user

4. **Delete**:
   - For low-quality/invalid images
   - Confirmation: "Delete this capture?"
   - Reason dropdown: Blurry / Wrong focus / Incorrect points / Duplicate

5. **Send to Dataset**:
   - Move approved image to training dataset
   - Copies to: `model_bellmounth_mesure/dataset/`
   - Original + Thresholded versions
   - Annotation saved to annotations.json
   - Success: "✓ Added to dataset"

**Side Panel - Image Details**:
```
┌──────────────────────────────────┐
│ IMAGE INFO                       │
├──────────────────────────────────┤
│ Filename: capture_...            │
│ Machine: LAB-01                  │
│ Time: 14:32:45                   │
│ Method: Auto CNN                 │
│ Distance: 10.42mm                │
│ P1: (526, 198)                   │
│ P2: (463, 198)                   │
├──────────────────────────────────┤
│ MEASUREMENT STATUS               │
│ Switch: SW-001                   │
│ Expected: 10.5mm                 │
│ Range: 10.0-11.0mm               │
│ 🟢 OKAY (±0.08mm)                │
├──────────────────────────────────┤
│ Quality Score: [dropdown]        │
│ Status: [Pending]                │
├──────────────────────────────────┤
│ [APPROVE] [REJECT]               │
│ [SEND TO DATASET] [DELETE]       │
└──────────────────────────────────┘
```

#### **PAGE 2: LABEL CABLE STATE (Annoteur Capture)**

**Interface**: Same as `model_bellmounth_mesure/capture_section.py`

**Features**:
- Live camera feed (Dino-Lite or webcam)
- Capture button
- Preview captured image
- **State Label Dropdown**:
  ```
  🔴 No Cable Detected
  🟡 Cable Male Placed
  🟢 Cable Good Placed
  ```
- Save to state dataset
- Session counter (X images captured)

**Workflow**:
1. Connect camera
2. View live feed
3. Adjust lighting/position as needed
4. Click [CAPTURE]
5. See preview
6. Select cable state from dropdown
7. Click [SAVE]
   - Image saved to: `model_bellmounth_mesure/state_dataset/`
   - Annotation saved with label
   - Session count increments
8. Continue or end session

#### **PAGE 3: NOTIFICATIONS**
- Same as Machine User
- View model training progress
- Approval/Rejection feedback from admin
- Messages about dataset updates

---

### 3️⃣ ADMIN USER (System Administrator)

**Authentication**: Admin Username + Password (fixed account)  
**Requirement**: MUST BE ONLINE

#### **Dashboard Structure**
```
┌────────────────────────────────────────────────┐
│ BELLMOUNTH ADMIN CONSOLE                       │
│ [ANNOTEURS] [MACHINES] [SWITCHES] [MESSAGES]   │
│ [KEYPOINT MODEL] [STATE MODEL] [DATASET]       │
└────────────────────────────────────────────────┘
```

#### **PAGE 1: ANNOTEUR MANAGEMENT**

**Table Display**:
```
┌─────────────────────────────────────────────┐
│ Username       │ Email          │ Status  │ │
├─────────────────────────────────────────────┤
│ annoteur_01    │ ann@email...   │ Active  │[>]
│ annoteur_02    │ ann2@email...  │ Active  │[>]
│ annoteur_old   │ old@email...   │ Inactive│[>]
└─────────────────────────────────────────────┘
```

**Actions**:
- [+ CREATE NEW]
- [BULK DELETE]
- [EXPORT LIST]

**Per-User Actions** (click row):
- **View Profile**: Date created, last login, annotation count, performance stats
- **Edit**: Change password/email, update permissions
- **Deactivate**: Disable login, archive account
- **Delete**: Permanent removal with confirmation

#### **PAGE 2: MACHINE MANAGEMENT**

**Table Display**:
```
┌──────────────────────────────────────────────────┐
│ Machine ID │ Location  │ Status │ Operator │ ▼  │
├──────────────────────────────────────────────────┤
│ LAB-01     │ Factory 1 │ 🟢 Online│ User1 │[>]
│ LAB-02     │ Factory 1 │ 🔴 Offline│ (Idle)│[>]
│ LAB-03     │ Factory 2 │ 🟢 Online│ User2 │[>]
│ LAB-04     │ Factory 3 │ 🟡 Idle   │ User1 │[>]
└──────────────────────────────────────────────────┘
```

**Status Icons**:
- 🟢 Online: Active and measuring
- 🟡 Idle: Connected but no activity (>15min)
- 🔴 Offline: Disconnected

**Per-Machine Actions**:
- **View Details**: Serial, firmware, calibration, operator, session time, measurements today
- **End Session**: Force logout operator
- **Disconnect**: Force disconnect from server
- **Edit**: Update name, location, notes
- **Delete**: Decommission machine

**Bulk Actions**:
- [+ ADD MACHINE]
- [DISCONNECT ALL]
- [EXPORT REPORT]

#### **PAGE 3: SWITCH MANAGEMENT**

**Table Display**:
```
┌────────────────────────────────────────────────┐
│ ID    │ Name      │ Diameter │ Tolerance  │ ▼  │
├────────────────────────────────────────────────┤
│ SW-001│ Standard  │ 10.5mm   │ ±0.5mm     │[>] │
│ SW-002│ Reinforced│ 12.0mm   │ ±0.3mm     │[>] │
└────────────────────────────────────────────────┘
```

**Actions**:
- **Create Switch**: Form with name, diameter, tolerance range, cable type, affected machines
- **Edit Switch**: Update values and reassign machines
- **Assign to Machines**: Multi-select which machines get access
- **Import from Excel**:
  - Upload .xlsx file
  - Columns: ID, Name, Diameter, Tolerance_Min, Tolerance_Max, CableType
  - Preview + batch create
- **Export List**: Download as .xlsx
- **Delete**: Remove from system

#### **PAGE 4: MESSAGING**

**Compose Message**:
```
┌──────────────────────────────────┐
│ SEND MESSAGE                     │
├──────────────────────────────────┤
│ To: [Machines/Annoteurs/All]    │
│ [Multi-select]                   │
│ Subject: [____________]          │
│ Message: [______________]        │
│ Attachment: [UPLOAD]             │
│ [SEND] [SCHEDULE] [DRAFT]       │
└──────────────────────────────────┘
```

**Message History**:
- Date, recipient(s), subject
- Inbox/Outbox tabs
- Read/Unread status

#### **PAGE 5: KEYPOINT MODEL MANAGEMENT**

**Current Model Status**:
```
┌──────────────────────────────────┐
│ ACTIVE MODEL: v2.3               │
├──────────────────────────────────┤
│ Deployed: 2026-05-15             │
│ Accuracy: 96.2%                  │
│ Precision: 95.8%                 │
│ Samples: 2,847                   │
└──────────────────────────────────┘
```

**Dataset Status**:
- Total images: 2,847
- Approved: 2,801
- Pending: 46
- Flagged: 15

**Train New Model**:
- Dialog with options:
  - Model name: [v2.4]
  - Filter: approved images only
  - Date range: [from] to [to]
  - Min quality score: [slider]
  - Training params: epochs, batch size, learning rate
  - [START TRAINING]
- Progress bar
- Email notification on completion

**Model History**:
- Version, date, accuracy
- Rollback option

**Deploy**:
- [DEPLOY TO MACHINES]
- Select target machines
- Auto-download on machines
- Notification sent

#### **PAGE 6: STATE DETECTION MODEL MANAGEMENT**

**Current Model Status**:
```
┌──────────────────────────────────┐
│ ACTIVE STATE MODEL: v1.1         │
├──────────────────────────────────┤
│ Deployed: 2026-05-15             │
│ Accuracy: 92.4%                  │
│ Classes: 3 (No Cable / Male / Good)
│ Samples: 1,247                   │
└──────────────────────────────────┘
```

**Dataset Status**:
- Total images: 1,247
- No Cable: 300 images
- Cable Male Placed: 450 images
- Cable Good Placed: 497 images

**Train New Model**:
- Filter state dataset
- Balance classes option
- Training parameters
- [START TRAINING]
- Monitor accuracy per class
- Confusion matrix

**Deploy**:
- [DEPLOY TO MACHINES]
- New state model pushed to all machines
- Machines use for real-time cable position detection

#### **PAGE 7: DATASET MANAGEMENT**

**Overview**:
```
┌──────────────────────────────────┐
│ KEYPOINT DATASET                 │
│ Total: 2,847 │ Approved: 2,801   │
│ Storage: 12.3 GB                 │
├──────────────────────────────────┤
│ STATE DATASET                    │
│ Total: 1,247 │ Balanced: Yes     │
│ Storage: 5.2 GB                  │
└──────────────────────────────────┘
```

**Actions**:
- **Browse**: View images in grid
- **Export**: Download as .zip (with annotations.json)
- **Cleanup**: Remove low-quality/rejected
- **Statistics**:
  - Images by machine
  - Distribution by capture method
  - Quality score histogram
  - Class balance (for state model)

---

## 🗄️ AZURE DATABASE SCHEMA

### users
```
id (UUID PRIMARY KEY)
username (STRING UNIQUE)
password_hash (STRING)
role (ENUM: machine_user, annoteur, admin)
email (STRING)
machine_id (FK) - if machine_user
created_at (TIMESTAMP)
last_login (TIMESTAMP)
is_active (BOOLEAN)
```

### machines
```
id (UUID PRIMARY KEY)
machine_name (STRING UNIQUE)
password_hash (STRING)
location (STRING)
firmware_version (STRING)
zoom_calibration (FLOAT)
mm_per_pixel (FLOAT)
is_connected (BOOLEAN)
current_session_user_id (FK - nullable)
session_start_time (TIMESTAMP - nullable)
created_at (TIMESTAMP)
```

### switches
```
id (UUID PRIMARY KEY)
switch_name (STRING)
expected_diameter_mm (FLOAT)
tolerance_min (FLOAT)
tolerance_max (FLOAT)
cable_type (STRING)
assigned_machines (JSON array of machine IDs)
created_at (TIMESTAMP)
updated_at (TIMESTAMP)
```

### measurements
```
id (UUID PRIMARY KEY)
machine_id (FK)
switch_id (FK)
measured_value_mm (FLOAT)
p1_x (INT), p1_y (INT)
p2_x (INT), p2_y (INT)
capture_method (ENUM: auto_cnn, manual)
image_path_original (STRING)
image_path_thresholded (STRING)
measurement_status (ENUM: okay, not_okay)
delta_mm (FLOAT)
created_at (TIMESTAMP)
```

### captures
```
id (UUID PRIMARY KEY)
machine_id (FK)
switch_id (FK)
annoteur_id (FK - who reviewed it)
image_original_blob_url (STRING)
image_thresholded_blob_url (STRING)
p1_x (INT), p1_y (INT)
p2_x (INT), p2_y (INT)
measured_distance_mm (FLOAT)
capture_method (ENUM: auto_cnn, manual)
measurement_status (ENUM: okay, not_okay)
delta_mm (FLOAT)
annoteur_approved (BOOLEAN)
in_training_dataset (BOOLEAN)
quality_score (FLOAT 0-1)
created_at (TIMESTAMP)
```

### state_annotations
```
id (UUID PRIMARY KEY)
annoteur_id (FK)
image_blob_url (STRING)
cable_state (ENUM: no_cable, cable_male, cable_good)
in_training_dataset (BOOLEAN)
created_at (TIMESTAMP)
```

### messages
```
id (UUID PRIMARY KEY)
from_user_id (FK)
to_role (ENUM: machine_user, annoteur, all)
to_user_ids (JSON array - if specific)
subject (STRING)
body (TEXT)
attachment_url (STRING - nullable)
created_at (TIMESTAMP)
read_at (TIMESTAMP - nullable)
```

### notifications
```
id (UUID PRIMARY KEY)
user_id (FK)
type (ENUM: model_update, switch_update, message, reclamation_response)
title (STRING)
body (TEXT)
action_url (STRING - nullable)
read (BOOLEAN)
created_at (TIMESTAMP)
```

### reclamations
```
id (UUID PRIMARY KEY)
user_id (FK)
title (STRING)
description (TEXT)
category (ENUM: bug, slow, incorrect, other)
screenshot_url (STRING - nullable)
status (ENUM: open, in_progress, resolved)
admin_response (TEXT - nullable)
created_at (TIMESTAMP)
resolved_at (TIMESTAMP - nullable)
```

### keypoint_models
```
id (UUID PRIMARY KEY)
version (STRING)
accuracy (FLOAT)
precision (FLOAT)
training_samples_count (INT)
deployed_to_machines (JSON array)
created_at (TIMESTAMP)
deployed_at (TIMESTAMP - nullable)
```

### state_models
```
id (UUID PRIMARY KEY)
version (STRING)
accuracy (FLOAT)
precision_per_class (JSON)
training_samples_count (INT)
deployed_to_machines (JSON array)
created_at (TIMESTAMP)
deployed_at (TIMESTAMP - nullable)
```

---

## 🔐 SECURITY REQUIREMENTS

- All passwords hashed with bcrypt
- JWT tokens for API authentication
- HTTPS/TLS for all communication
- Role-based access control (RBAC)
- Audit logs for admin actions
- Azure SQL encryption at rest (TDE)
- Images stored in Azure Blob Storage
- Models stored in Blob Storage with version control

---

## 🚀 TECHNICAL STACK

### Backend
- **Framework**: Python FastAPI
- **Database**: Azure SQL Database
- **Storage**: Azure Blob Storage
- **Authentication**: JWT + bcrypt
- **Real-time**: WebSocket for notifications
- **File Upload**: Multipart form data handlers

### Frontend
- **Current App**: Python Tkinter (extend existing app.py)
- **Alternative**: PyQt6 for more advanced UI
- **Communication**: HTTP + WebSocket to backend

### Cloud
- **Platform**: Microsoft Azure
- **Services**:
  - Azure SQL Database
  - Azure Blob Storage
  - Azure App Service
  - Azure Application Insights (logging)

### ML
- **Keypoint Model**: TensorFlow/Keras CNN (existing)
- **State Model**: TensorFlow/Keras classifier (existing)
- **Preprocessing**: OpenCV (adaptive threshold, morphological ops)

---

## 🔄 COMPLETE WORKFLOWS

### Machine User Measurement Flow
1. Login with machine_name + password
2. Connect to Azure (must be online)
3. Download switch list
4. Select switch from list
5. Start measurement:
   - AUTO: Click [CAPTURE] → CNN detects keypoints
   - MANUAL: Click to place P1, click to place P2
6. Result shows: Status (OKAY/NOT OKAY), measured value, delta
7. Click **[UPLOAD]** button explicitly
8. Data sent to Azure
9. Check notifications for updates/messages

### Annoteur Workflow - Task 1: Review Captures
1. Login with username + password
2. See assigned capture queue (machine measurements)
3. Filter by machine, status, date, etc.
4. Click capture to view
5. Option A: Review & approve
   - Edit P1/P2 if needed
   - Click [APPROVE] → ready for dataset
6. Option B: Reject or delete
   - Click [REJECT] → mark as issue
   - Click [DELETE] → remove from system
7. [SEND TO DATASET] → add to training data
8. Check notifications

### Annoteur Workflow - Task 2: Label Cable State
1. From dashboard select [LABEL STATE]
2. Connect camera (Dino-Lite or webcam)
3. Capture image
4. Select cable state:
   - 🔴 No Cable Detected
   - 🟡 Cable Male Placed
   - 🟢 Cable Good Placed
5. Click [SAVE]
6. Image + label saved to state dataset
7. Continue or end session

### Admin Workflow - User Management
1. Login with admin credentials
2. Select [ANNOTEURS] tab
3. View all annoteurs
4. Create/Edit/Delete as needed
5. Monitor activity and stats

### Admin Workflow - Model Training & Deployment
1. Select [KEYPOINT MODEL] tab
2. Review dataset status
3. Click [TRAIN NEW MODEL]
4. Set parameters, approve config
5. Monitor training progress
6. View metrics (accuracy, precision)
7. Click [DEPLOY TO MACHINES]
8. Select machines to receive update
9. Models auto-downloaded on machines
10. Machines notified of new version
11. Repeat for state model in separate tab

---

## 📊 CAPTURE QUEUE MANAGEMENT

**Key Principle**: Each annoteur has their own queue

**Queue Assignment**:
- New captures from machines assigned to specific annoteurs
- Can rotate assignment (round-robin or manual)
- No conflicts: Only assigned annoteur can edit/approve
- Once approved, moved to shared dataset pool

**Queue Distribution** (Admin):
- Can manually assign captures to annoteurs
- Or auto-assign using round-robin
- View queue status per annoteur
- Track productivity (images approved/day)

---

## 📈 DATA FLOW

### Machine Upload Path
```
Machine Measurement
    ↓
[UPLOAD] button clicked
    ↓
Send to Azure: image + P1/P2 + distance + status
    ↓
Store in captures table
    ↓
Assign to random annoteur queue
    ↓
Annoteur reviews
```

### Annoteur Approval Path
```
Annoteur Review
    ↓
Click [APPROVE] + [SEND TO DATASET]
    ↓
Copy to: model_bellmounth_mesure/dataset/
    ↓
Add to annotations.json
    ↓
Ready for model training
```

### State Labeling Path
```
Annoteur Capture
    ↓
Connect camera, capture image
    ↓
Select cable state label
    ↓
Click [SAVE]
    ↓
Store in: model_bellmounth_mesure/state_dataset/
    ↓
Ready for state model training
```

### Model Training & Deployment Path
```
Admin selects [TRAIN]
    ↓
Filter dataset (approved only)
    ↓
Set training parameters
    ↓
[START TRAINING]
    ↓
Monitor progress
    ↓
Review metrics
    ↓
Click [DEPLOY TO MACHINES]
    ↓
Select target machines
    ↓
Upload to Blob Storage
    ↓
Notify machines of update
    ↓
Machines auto-download new model
    ↓
New model used for future measurements
```

---

## 🎯 KEY SPECIFICATIONS

| Aspect | Specification |
|--------|---------------|
| **Internet** | MUST BE ONLINE - no offline mode |
| **Upload** | Manual [UPLOAD] button (not automatic) |
| **Conflicts** | Each annoteur owns their queue |
| **State Model** | Annoteur labels, Admin trains |
| **Measurement Status** | 🟢 OKAY / 🔴 NOT OKAY based on switch tolerance |
| **Models Deployed** | 2 models: Keypoint + State Detection |
| **Database** | Azure SQL + Blob Storage |
| **Authentication** | Machine: name+password, Users: username+password |

---

## 📝 IMPLEMENTATION PHASES

### Phase 1: Core System (MVP)
**Week 1-2**: Authentication + Database
- Implement user login (Machine/Annoteur/Admin)
- Set up Azure SQL with all tables
- Configure Blob Storage
- JWT token system

**Week 3-4**: Machine User Features
- Switch list download
- Measurement capture (AUTO/MANUAL)
- Status calculation (OKAY/NOT OKAY)
- Manual [UPLOAD] button to Azure
- Notifications display

**Week 5-6**: Annoteur Review
- Capture queue display
- View original + thresholded images
- Edit P1/P2 points
- Approve/Reject/Delete actions
- Send to dataset

**Week 7**: Admin Basics
- User management (create/delete)
- Machine management (view status)
- Switch management (CRUD)
- Basic messaging

**Week 8**: Testing & Deployment
- End-to-end testing
- Deploy to Azure App Service
- User acceptance testing

### Phase 2: State Detection
**Week 9-10**: Annoteur State Labeling
- Camera capture interface
- Cable state labeling (3 states)
- State dataset management

**Week 11**: Admin State Model Training
- State dataset review
- Model training interface
- Deploy state model to machines

### Phase 3: Advanced Features
**Week 12+**: 
- Advanced reporting & analytics
- Mobile app notifications
- Performance optimization
- Audit logging

---

## 🚀 DEPLOYMENT CHECKLIST

- [ ] Azure subscription created
- [ ] SQL Database provisioned
- [ ] Blob Storage configured
- [ ] App Service created
- [ ] Application Insights enabled
- [ ] Database schema migrated
- [ ] Authentication system tested
- [ ] Image upload/download tested
- [ ] Model loading tested
- [ ] All user workflows tested
- [ ] Security audit completed
- [ ] Performance tested under load
- [ ] Documentation completed
- [ ] User training materials prepared
- [ ] Deployed to production

---

## 📞 SUPPORT & CONTACT

**Project Owner**: iliasssjb2004@gmail.com  
**Repository**: https://github.com/MRili123/project_bellmount_yazaki  
**Documentation**: See CLAUDE.md in repo

---

**THIS IS THE COMPLETE SPECIFICATION. READY TO IMPLEMENT.**

---

**Document Version**: 2.0  
**Status**: ✅ APPROVED FOR DEVELOPMENT  
**Last Updated**: 2026-05-19 15:42:00 UTC
