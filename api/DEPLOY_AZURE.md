# Deploying the Bellmounth API to Azure

This deploys **only the `api/` folder** to Azure App Service. The desktop app
(camera/TensorFlow) stays on the machines — it just points at the cloud URL.

## Prerequisites (create in the Azure Portal — see `../AZURE_SETUP.md`)
1. **Resource Group**
2. **Database** — Azure Database for **PostgreSQL** (recommended) or Azure SQL
3. **Storage Account** + a Blob **container** named `images`
4. **App Service** — Linux, **Python 3.11**

Collect three values: the DB connection string, the Blob connection string, and
the App Service URL.

## 1. Configure the App Service
In the App Service → **Configuration → Application settings**, add:

| Name | Value |
|------|-------|
| `DATABASE_URL` | `postgresql://USER:PASS@HOST:5432/bellmounth` (or paste the Azure SQL ADO.NET string as-is) |
| `BLOB_CONNECTION_STRING` | `DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net` |
| `BLOB_CONTAINER` | `images` |
| `JWT_SECRET` | a long random secret — `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `JWT_EXPIRE_HOURS` | `24` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` |

In **Configuration → General settings → Startup Command**, set:
```
gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers 2 --bind 0.0.0.0:8000 --timeout 600
```

## 2. Open the database firewall
- **Azure SQL**: SQL Server → Networking → enable **"Allow Azure services..."**.
- **Postgres**: Networking → add firewall rule **"Allow public access from Azure services"**.

## 3. Deploy the code
**Easiest (VS Code):** install the *Azure App Service* extension → sign in →
right-click the **`api`** folder → **Deploy to Web App** → pick your App Service.

**CLI alternative:**
```bash
cd api
az webapp up --name <your-app-service-name> --runtime "PYTHON:3.11"
```

App Service installs from `api/requirements.txt` automatically.

## 4. Initialize the database
Tables are created automatically on first start (`init_db()`), but you still need
the admin/machines/switches. Seed once — either run `api/seed_db.py` locally with
`DATABASE_URL` pointed at the cloud DB, or via the App Service SSH console:
```bash
python seed_db.py
```

## 5. Point the machines at it
Launch the desktop app → **Select API Connection** dialog → **Change API** →
enter `https://<your-app-service>.azurewebsites.net` → **Test Connection** →
**Save**.

## Notes / gotchas
- **Images must use Blob in the cloud.** App Service local disk is wiped on
  restart; without `BLOB_CONNECTION_STRING` set, uploaded images would disappear.
- **The API now requires a login token on every endpoint** (except `/`,
  `/auth/login`, `/auth/health`, docs). This is what makes the public URL safe.
- **`/docs` is publicly reachable** (schema only — endpoints still require auth).
  To hide it, add `docs_url=None, redoc_url=None` to the `FastAPI(...)` call.
- **First request after idle may be slow** if the DB auto-paused (serverless) —
  the connection pool pre-ping handles the reconnection.
