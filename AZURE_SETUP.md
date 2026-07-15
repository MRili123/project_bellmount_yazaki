# Azure Setup for Bellmounth v2.0

**Status**: ✅ **COMPLETED on 2026-07-13** — everything is live and the desktop app
is connected. This documents what exists, how it was built, and how to maintain it.
**Method**: Azure CLI (`az`), account `iliasssjb2004@gmail.com`, subscription
"Azure subscription 1".

---

## What Exists

All resources live in the resource group **`bellmounth-rg`**:

| Resource | Name | Region | Notes |
|----------|------|--------|-------|
| Resource Group | `bellmounth-rg` | West Europe | Container for everything |
| SQL Server | `bellmounth-enc5fw-fran` | France Central | Admin login: `azadmin` |
| SQL Database | `bellmounth-db` | France Central | Serverless Gen5 0.5–1 vCore, auto-pause 60 min |
| Storage Account | `bellmounthenc5fw` | North Europe | Standard LRS, containers `images` + `models` |
| App Service Plan | `bellmounth-plan` | France Central | **Basic B1**, Linux |
| App Service | `bellmounth-api-enc5fw` | France Central | Python 3.11 |

**Live API**: https://bellmounth-api-enc5fw.azurewebsites.net
(the `api/` folder of this project, deployed as a zip)

**Secrets** (DB password, blob key, JWT secret): in `.env` in this folder —
git-ignored, never commit it.

**Desktop app connection**: `config.json` → `"api_url"` points at the live API.
Machines can change it in the app's *Select API Connection* dialog.

### Seeded accounts

| Type | Login | Password |
|------|-------|----------|
| Admin | `admin` | `admin123` |
| Annoteur | `annoteur_01` / `annoteur_02` | `password123` |
| Machine | `LAB-01` / `LAB-02` | `bellmounth` |

⚠️ Change these before real production use.

### Why names/regions differ from the original plan
- Storage accounts / SQL servers / web apps need **globally unique** names, hence
  the `enc5fw` suffix.
- **West Europe and North Europe refused new SQL servers** on this subscription
  ("region not accepting new customers") — France Central accepted. Storage had
  already landed in North Europe; cross-region traffic is fine for this workload.
- The App Service plan is **B1** (not F1 Free): the free tier's 60-CPU-min/day
  quota was exhausted during setup. B1 (~$13/month, covered by trial credit) has
  no daily quota. Downgrade if desired:
  `az appservice plan update -n bellmounth-plan -g bellmounth-rg --sku F1`

---

## How It Was Built (reproducible)

```powershell
# 0. Prereqs: winget install Microsoft.AzureCLI ; az login --use-device-code
# On a fresh subscription, register providers first (else "SubscriptionNotFound"):
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.Sql
az provider register --namespace Microsoft.Web

# 1. Resource group
az group create --name bellmounth-rg --location westeurope

# 2. SQL server + serverless DB + firewall
az sql server create --name bellmounth-enc5fw-fran -g bellmounth-rg `
  --location francecentral --admin-user azadmin --admin-password "<see .env>"
az sql db create --name bellmounth-db -g bellmounth-rg --server bellmounth-enc5fw-fran `
  --edition GeneralPurpose --family Gen5 --capacity 1 `
  --compute-model Serverless --min-capacity 0.5 --auto-pause-delay 60
az sql server firewall-rule create --name AllowAzureServices -g bellmounth-rg `
  --server bellmounth-enc5fw-fran --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
az sql server firewall-rule create --name AllowClientIP -g bellmounth-rg `
  --server bellmounth-enc5fw-fran --start-ip-address <your-ip> --end-ip-address <your-ip>

# 3. Storage + containers
az storage account create --name bellmounthenc5fw -g bellmounth-rg `
  --location northeurope --sku Standard_LRS --kind StorageV2
az storage container create --name images --connection-string "<see .env>"
az storage container create --name models --connection-string "<see .env>"

# 4. App Service
az appservice plan create --name bellmounth-plan -g bellmounth-rg `
  --location francecentral --sku B1 --is-linux
az webapp create --name bellmounth-api-enc5fw -g bellmounth-rg `
  --plan bellmounth-plan --runtime "PYTHON:3.11"

# 5. App Service configuration
az webapp config appsettings set --name bellmounth-api-enc5fw -g bellmounth-rg --settings `
  DATABASE_URL="mssql+pymssql://azadmin:<urlencoded-pw>@bellmounth-enc5fw-fran.database.windows.net:1433/bellmounth-db" `
  BLOB_CONNECTION_STRING="<see .env>" BLOB_CONTAINER="images" `
  JWT_SECRET="<see .env>" JWT_EXPIRE_HOURS="24" SCM_DO_BUILD_DURING_DEPLOYMENT="true"
az webapp config set --name bellmounth-api-enc5fw -g bellmounth-rg `
  --startup-file "gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000 --timeout 600"
```

### Deploying the API (repeat after any change to `api/`)

```powershell
# Build the zip with Python — NOT Compress-Archive (it writes backslash paths
# that Linux can't read, causing "No module named 'routers'"):
py -3.11 -c "import zipfile,pathlib; src=pathlib.Path('api'); out='api.zip'; z=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED); [z.write(p, p.relative_to(src).as_posix()) for p in src.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.log','.db') and 'captures' not in p.parts]; z.close()"
az webapp deploy --name bellmounth-api-enc5fw -g bellmounth-rg --src-path api.zip --type zip

# Seed once (from api/ with .env present):
py -3.11 seed_db.py
```

### Code changes made for Azure SQL
- `api/requirements.txt`: added **pymssql** (pure-pip SQL Server driver; no ODBC
  needed on App Service).
- `api/database.py`: added an mssql compile rule that renders length-less
  `Column(String)` as `NVARCHAR(450)` — SQL Server rejects `VARCHAR(max)`
  primary keys, which every model here uses. SQLite/Postgres are unaffected.

---

## Troubleshooting (issues actually hit)

| Problem | Fix |
|---------|-----|
| `az login` opens no browser | `az login --use-device-code` |
| "No subscriptions found" | Account has no subscription — sign up at azure.microsoft.com/free |
| `SubscriptionNotFound` on create | Register resource providers (step 0) |
| SQL "region not accepting new customers" | Try another region (francecentral worked) |
| "Resource already exists in location X" after failed create | Stale name reservation — retry with a different name |
| API 503, log says `No module named 'routers'` | Zip built with Compress-Archive — rebuild with Python (see above) |
| API 403 + state `QuotaExceeded` | F1 free-tier daily CPU quota exhausted — wait 24 h or move to B1 |
| `Column 'id' ... invalid for use as a key column` | String PKs without length — handled by the compile rule in database.py |
| Local tools can't reach DB (error 40615) | Your public IP changed — update the firewall rule: `az sql server firewall-rule update --name AllowClientIP -g bellmounth-rg --server bellmounth-enc5fw-fran --start-ip-address <ip> --end-ip-address <ip>` |
| First request after idle is slow (~1 min) | Serverless DB resuming from auto-pause — expected |

---

## Useful

```powershell
az resource list -g bellmounth-rg -o table          # list everything
az webapp log download --name bellmounth-api-enc5fw -g bellmounth-rg --log-file logs.zip
az group delete --name bellmounth-rg --yes          # DELETE EVERYTHING (irreversible)
```
