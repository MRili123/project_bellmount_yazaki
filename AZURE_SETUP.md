# Azure Setup Guide for Bellmounth v2.0

**Objective**: Provision Azure resources for the multi-user cable measurement system.  
**Time**: ~30 minutes  
**Requirements**: Azure subscription with credit/payment method

---

## Overview

You'll create:
1. **Resource Group** (`bellmounth-rg`) — Container for all resources
2. **Azure SQL Database** (`bellmounth-db`) — Multi-user data storage
3. **Azure Blob Storage** (`bellmounthassets`) — Image and model file storage
4. **Azure App Service** (`bellmounth-api`) — Backend API server (Python/FastAPI)

At the end, you'll collect connection strings to paste into the app.

---

## Step 1: Create Resource Group

1. Go to [Azure Portal](https://portal.azure.com)
2. Search bar (top) → type **"Resource groups"** → click on it
3. Click **[+ Create]** button
4. Fill in:
   - **Subscription**: (select your subscription)
   - **Resource group name**: `bellmounth-rg`
   - **Region**: `West Europe` (or closest to you)
5. Click **[Review + Create]** → **[Create]**
6. Wait ~30 seconds for creation

✅ **Resource Group created**

---

## Step 2: Create Azure SQL Database

1. In Azure Portal, go to **Home** (click Azure logo top-left)
2. Search bar → type **"SQL Databases"** → click it
3. Click **[+ Create]** (or **Create SQL database**)
4. Fill in:
   - **Subscription**: (your subscription)
   - **Resource group**: `bellmounth-rg` (select from dropdown)
   - **Database name**: `bellmounth-db`
   - **Server**: Click **[Create new]**
     - **Server name**: `bellmounth-server-<random>` (must be globally unique, e.g., `bellmounth-server-123`)
     - **Server admin login**: `azadmin`
     - **Password**: `SecurePass123!@#` (use a strong password, save it!)
     - **Confirm password**: (repeat above)
     - **Location**: `West Europe`
     - Click **[OK]**
   - **Compute + storage**: Click **[Configure database]**
     - Select **Serverless** (cheaper for dev)
     - **Min vCores**: 0.5
     - **Max vCores**: 1
     - Click **[Apply]**
5. Click **[Review + Create]** → **[Create]**
6. Wait ~3 minutes for deployment

✅ **Azure SQL Database created**

### Get SQL Connection String

1. After creation, click **[Go to resource]** (or search for `bellmounth-db`)
2. Left sidebar → **Connection strings**
3. Find **ADO.NET (SQL authentication)**
4. Click **[Copy]** icon (or copy manually)
5. **Paste into Notepad** and replace:
   - `{your_username}` → `azadmin`
   - `{your_password}` → `SecurePass123!@#`

**Example:**
```
Server=tcp:bellmounth-server-123.database.windows.net,1433;Initial Catalog=bellmounth-db;Persist Security Info=False;User ID=azadmin;Password=SecurePass123!@#;MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;
```

Save this — you'll need it later.

---

## Step 3: Create Azure Blob Storage Account

1. Azure Portal search bar → type **"Storage accounts"** → click it
2. Click **[+ Create]** (or **Create storage account**)
3. Fill in:
   - **Subscription**: (your subscription)
   - **Resource group**: `bellmounth-rg`
   - **Storage account name**: `bellmounthassets` (must be lowercase, globally unique)
   - **Region**: `West Europe`
   - **Performance**: Standard
   - **Redundancy**: Locally-redundant storage (LRS)
4. Click **[Review + Create]** → **[Create]**
5. Wait ~1 minute

✅ **Blob Storage account created**

### Create Containers

1. Go to the storage account (click [Go to resource] or search for `bellmounthassets`)
2. Left sidebar → **Containers** (under "Data storage")
3. Click **[+ Container]**
4. **Name**: `images` → **Public access level**: Private → **[Create]**
5. Repeat: Create another container named `models` (Private)

✅ **Two containers created: `images` and `models`**

### Get Blob Connection String

1. Still in the storage account page
2. Left sidebar → **Access keys**
3. Under "key1", click **[Show keys]**
4. **Connection string** field → click **[Copy]**

**Looks like:**
```
DefaultEndpointsProtocol=https;AccountName=bellmounthassets;AccountKey=XXXXXXX...;EndpointSuffix=core.windows.net
```

Save this too.

---

## Step 4: Create Azure App Service (Backend API)

1. Azure Portal search bar → type **"App Services"** → click it
2. Click **[+ Create]** (or **Create App Service**)
3. Fill in:
   - **Subscription**: (your subscription)
   - **Resource group**: `bellmounth-rg`
   - **Name**: `bellmounth-api` (must be unique, becomes `bellmounth-api.azurewebsites.net`)
   - **Runtime stack**: `Python 3.11`
   - **Operating System**: `Linux`
   - **Region**: `West Europe`
4. Click **[Review + Create]** → **[Create]**
5. Wait ~2 minutes

✅ **App Service created**

### Get App Service URL

1. After creation, click **[Go to resource]** (or search `bellmounth-api`)
2. Top right, copy the **URL**: `https://bellmounth-api.azurewebsites.net`

**Save this URL** — you'll paste it into the Tkinter app's setup screen.

---

## Step 5: Summary — Connection Info to Save

Create a file called `.env` in the Bellmounth project root with:

```
# Azure SQL Database
DATABASE_URL=Server=tcp:bellmounth-server-123.database.windows.net,1433;Initial Catalog=bellmounth-db;Persist Security Info=False;User ID=azadmin;Password=SecurePass123!@#;MultipleActiveResultSets=False;Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;

# Azure Blob Storage
BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=bellmounthassets;AccountKey=XXXXXXX...;EndpointSuffix=core.windows.net

# App Service
API_URL=https://bellmounth-api.azurewebsites.net

# Security
JWT_SECRET=your-super-secret-key-change-this-in-production-123456
```

---

## Next Steps

Once you have these three values:
1. ✅ **DATABASE_URL** (Azure SQL connection string)
2. ✅ **BLOB_CONNECTION_STRING** (Azure Blob connection string)
3. ✅ **API_URL** (App Service URL)

Tell me, and I'll:
1. Build the FastAPI backend
2. Deploy it to the App Service
3. Update app.py with the setup screen

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Storage account name taken | Add random numbers, e.g., `bellmounthassets123` |
| SQL server name taken | Add suffix, e.g., `bellmounth-server-prod` |
| Can't find resource | Search by name in the top search bar |
| Connection fails | Check firewall: SQL Database → Networking → Allow Azure services |
| Out of quota | Check subscription limits in Cost Management |

---

**Once done, post the 3 connection strings here and we'll deploy the backend!**
