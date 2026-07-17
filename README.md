# Bellmounth — Cable Measurement System (Yazaki)

A multi-user system for measuring cable diameters from a Dino-Lite microscope,
with AI-assisted keypoint detection, role-based access, and a cloud backend on
Microsoft Azure.

The product ships as a single Windows installer. End users don't need Python or
any dependencies — they run the installer and log in.

---

## What it does

- Captures live video from a **Dino-Lite microscope** and measures the distance
  between two points on a cable, converted to millimetres using the microscope's
  real magnification/field-of-view (read from the Dino-Lite SDK).
- A trained **CNN model** can auto-detect the two measurement points, or an
  operator can place them manually.
- **Annoteurs** label captured images to build the training dataset; an **admin**
  trains/deploys models and manages users and machines.
- All accounts, measurements, and files are stored in the **cloud** so multiple
  machines and users share the same data.

---

## Architecture

Three layers. The desktop app never talks to the database directly — it goes
through the API, which is the only component holding the database credentials.

```
Desktop app (Windows)          API (FastAPI on Azure)          Azure resources
- machine / annoteur / admin   - login + JWT tokens            - Azure SQL (data)
- Dino-Lite + CNN model    →   - all business logic        →   - Blob storage (images/models)
- knows only the API URL       - only component with DB keys
```

- **Desktop app** — Python/Tkinter. Users log in with a personal username +
  password; the app only knows the API URL (set on the server-config screen).
- **API** — FastAPI, deployed to Azure App Service. Every endpoint (except
  login/health) requires a valid JWT token. Creates and seeds the database
  schema automatically on first start.
- **Azure SQL** — serverless database holding users, machines, switches,
  measurements, captures, notifications, and model registry.
- **Azure Blob Storage** — stores captured images and (optionally) model files.

---

## Roles

| Role | Logs in as | Can do |
|------|-----------|--------|
| **Admin** | `admin` | Manage users/machines/switches, review captures, train & deploy models, read reclamations |
| **Annoteur** | e.g. `annoteur_01` | Label captured images, submit reclamations |
| **Machine** | e.g. `LAB-01` | Live measurement, capture, submit reports |

Default seed accounts (change these before production): `admin/admin123`,
`annoteur_01`/`annoteur_02` = `password123`, machines `LAB-01`/`LAB-02` =
`bellmounth`.

---

## Repository structure

```
app.py                 Desktop application (all panels + UI)
server_config.py       Startup server-config screen (connection tests gate login)
api_client.py          HTTP client the desktop app uses to call the API
camera_setup.py        Detects and opens the Dino-Lite microscope
pixelmeasure.py        Reads zoom/FOV from the Dino-Lite SDK → mm-per-pixel
dnx64.py, lib/DNX64.dll Dino-Lite SDK wrapper + library
cable_detector.py      Image processing for cable detection
threshold_utils.py     Image thresholding preprocessing
train_model.py         Trains the CNN keypoint model
make_icon.py           Generates the app icon
installer.iss          Inno Setup script for the single-file installer

api/                   FastAPI backend (deployed to Azure App Service)
  main.py              App entrypoint, routers, health endpoints
  models.py            SQLAlchemy tables + relationships
  database.py          Engine/session + SQL Server compatibility
  routers/             auth, switches, captures, admin endpoints
  reset_db.py          Wipe + reseed the database with default data
  seed_db.py           Seed default data
```

Secrets (`.env`), the trained model (`models/*.h5`), and build output
(`build/`, `dist/`) are git-ignored and never committed.

---

## Running from source (development)

Requirements: Windows, Python 3.11.

```powershell
# install dependencies
py -3.11 -m pip install -r requirements.txt

# run the desktop app
py -3.11 app.py
```

On launch the **server-config screen** appears. It runs four checks — API,
database, storage, and schema — and only lets you continue to login when all
pass. Connection details are read from / saved to a local `.env` file (see
`.env.example`).

To run the API locally instead of against Azure:

```powershell
cd api
py -3.11 -m pip install -r requirements.txt
py -3.11 -m uvicorn main:app --reload
```

---

## Building the Windows installer

Produces `dist/yazaki_bellmounth_mesure_setup.exe` — a single file end users run.

```powershell
# 1. Build the standalone app with PyInstaller
py -3.11 -m PyInstaller --noconfirm --clean --windowed --name Bellmounth ^
  --icon app_icon.ico ^
  --hidden-import dotenv --hidden-import jwt --hidden-import bcrypt ^
  --hidden-import pymssql --hidden-import sqlalchemy ^
  --hidden-import sqlalchemy.dialects.mssql.pymssql ^
  --hidden-import sqlalchemy.dialects.sqlite app.py

# 2. Copy runtime files next to the exe (api/, models/, config.json, .env, icon)
#    then compile the installer:
ISCC.exe installer.iss
```

The installer is per-user (no admin rights), creates desktop + Start Menu
shortcuts, and registers a Windows uninstaller. Each app panel also has an
in-app **UNINSTALL** button.

> Note: the trained model (~1.8 GB) is bundled inside the installer, which is
> why it is large. The installer is too big for GitHub — host it on a file
> service (or a GitHub Release split into parts) and link it here.

---

## Configuration

The desktop app reads the API URL from `config.json`. The full connection
settings (SQL, Blob, JWT) live in a git-ignored `.env`, edited through the
server-config screen. See `.env.example` for the shape of the file.

Database and schema checks go **through the API**, so client PCs never need to
be added to the Azure SQL firewall — the app works from any network.

---

## Hardware notes

- **Measurement** requires a Dino-Lite microscope with the DNX64 drivers. Without
  it, the app still runs and shows a "no Bellmounth camera" banner; measurement
  falls back to a fixed calibration constant.
- **Training** the CNN (`train_model.py`) is memory-heavy. Minimum 8 GB RAM
  (16 GB recommended); a CUDA GPU with 6–8 GB VRAM makes it far faster but is
  optional — TensorFlow falls back to CPU.
