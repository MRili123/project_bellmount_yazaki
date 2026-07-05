# Google Drive Integration Setup Guide

This guide helps you set up Google Drive integration for automatically uploading and sharing model files.

## Prerequisites
- Google Account
- 5 minutes of setup time

## Step-by-Step Setup

### 1. Create Google Cloud Project

1. Go to **[Google Cloud Console](https://console.cloud.google.com/)**
2. Click **"Select a Project"** → **"New Project"**
3. Name: `Bellmouth Models` (or your choice)
4. Click **"Create"**
5. Wait for project creation (1-2 minutes)

### 2. Enable Google Drive API

1. In Cloud Console, search for **"Google Drive API"**
2. Click on it → **"Enable"**
3. Wait for it to enable

### 3. Create OAuth 2.0 Credentials

1. Go to **"Credentials"** in left sidebar
2. Click **"Create Credentials"** → **"OAuth 2.0 Client ID"**
3. Select **"Desktop application"**
4. Click **"Create"**
5. Click **"Download"** (a JSON file will download)

### 4. Configure in App (Flexible Path)

Instead of placing files manually, you can specify the path directly in the app:

**Option A: Use Settings UI (Recommended)**
1. Start the app: `py -3.11 app.py`
2. Click **"⚙ SETTINGS"** button (top right)
3. Click **"📁 Browse"** button
4. Select your `google_credentials.json` file (from wherever you saved it)
5. Check **"Enable Google Drive auto-upload"**
6. Click **"💾 SAVE SETTINGS"**
7. Done! ✅

**Option B: Manual Path**
- Just point to your credentials file anywhere:
  - `C:\Users\YourName\Downloads\client_secret_xxx.json`
  - `D:\Credentials\google_creds.json`
  - `C:\BellmouthProject\app\google_credentials.json`
  - Anywhere you want! 🎯

## First Use

1. Start the app: `py -3.11 app.py`
2. Go to **MODEL** section
3. Click **"🚀 SEND MODELS TO MACHINES"**
4. Select **"📁 Google Drive (Recommended)"**
5. Click **"📤 PREPARE & SEND"**
6. A browser window will open asking for permission
7. Click **"Allow"** to authorize
8. Done! Your models are now on Google Drive! 🎉

## What Happens

✅ **Admin side:**
- Click button → Authenticate with Google → Zip models → Upload to Google Drive
- Get shareable download link automatically
- Link works for any machine (no login needed)

✅ **What gets uploaded:**
- All model versions (V1, V2)
- Metadata files
- MANIFEST.json with version info
- One ZIP file (~2-3 GB with trained models)

✅ **Google Drive file:**
- Automatically public (anyone with link can download)
- Organized in your Google Drive
- Can see upload status in real-time

## Troubleshooting

**"google_credentials.json not found"**
- Make sure file is in `C:\BellmouthProject\app\`
- Check the filename exactly (case-sensitive)

**"Google Drive libraries not installed"**
- Run: `pip install -r requirements.txt`
- Then restart the app

**Browser doesn't open for authorization**
- Check your firewall/antivirus
- Or manually go to the URL printed in console

**Upload takes too long**
- Models are large files (1-3 GB)
- Upload time depends on internet speed
- Check your Google Drive afterward

## Security Notes

✅ **Safe:**
- Credentials are local only (not shared)
- Files are encrypted during upload
- Token is saved locally for convenience

⚠️ **Best practices:**
- Keep `google_credentials.json` private
- Don't share credentials file
- You can always disable credentials in Google Cloud Console

## Need Help?

- Check console output for detailed error messages
- Verify credentials file location
- Make sure Google Drive API is enabled
- Check internet connection
