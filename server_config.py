"""
Bellmounth server configuration tool (ADMIN ONLY).

Edits the git-ignored .env in the project root — the master connection values
for the Azure SQL database, blob storage, deployed API, and JWT settings —
with a test button for each connection.

This tool is for the administrator's PC. Regular users never need it: the
desktop app itself only reads config.json (api_url) and asks for a personal
login.

Run:  py -3.11 server_config.py
"""

import json
import sys
import threading
import time
import tkinter as tk
import urllib.parse
from pathlib import Path
from tkinter import messagebox, ttk

# Next to server_config.py in development, next to the .exe when packaged.
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent
ENV_FILE = ROOT / ".env"
CONFIG_JSON = ROOT / "config.json"

FIELDS = [
    # (env key, label, masked)
    ("API_URL", "API URL", False),
    ("SQL_SERVER", "SQL server", False),
    ("SQL_DATABASE", "SQL database", False),
    ("SQL_USER", "SQL username", False),
    ("SQL_PASSWORD", "SQL password", True),
    ("DATABASE_URL", "Database URL (auto-built)", True),
    ("BLOB_CONNECTION_STRING", "Blob connection string", True),
    ("BLOB_CONTAINER", "Blob container", False),
    ("JWT_SECRET", "JWT secret", True),
    ("JWT_ALGORITHM", "JWT algorithm", False),
    ("JWT_EXPIRE_HOURS", "JWT expire (hours)", False),
]

DEFAULTS = {
    "BLOB_CONTAINER": "images",
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRE_HOURS": "24",
}


def load_env() -> dict:
    values = dict(DEFAULTS)
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    return values


def save_env(values: dict):
    lines = [
        "# Bellmounth server configuration — written by server_config.py",
        "# Keep this file private. It is git-ignored; never commit it.",
        "",
        "# Deployed API",
        f"API_URL={values['API_URL']}",
        "",
        "# Azure SQL",
        f"SQL_SERVER={values['SQL_SERVER']}",
        f"SQL_DATABASE={values['SQL_DATABASE']}",
        f"SQL_USER={values['SQL_USER']}",
        f"SQL_PASSWORD={values['SQL_PASSWORD']}",
        f"DATABASE_URL={values['DATABASE_URL']}",
        "",
        "# Azure Blob Storage",
        f"BLOB_CONNECTION_STRING={values['BLOB_CONNECTION_STRING']}",
        f"BLOB_CONTAINER={values['BLOB_CONTAINER']}",
        "",
        "# Security (must match the App Service settings)",
        f"JWT_SECRET={values['JWT_SECRET']}",
        f"JWT_ALGORITHM={values['JWT_ALGORITHM']}",
        f"JWT_EXPIRE_HOURS={values['JWT_EXPIRE_HOURS']}",
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")


def sync_config_json(api_url: str):
    """Keep the desktop app pointing at the same API."""
    try:
        cfg = json.loads(CONFIG_JSON.read_text(encoding="utf-8")) if CONFIG_JSON.exists() else {}
    except Exception:
        cfg = {}
    cfg["api_url"] = api_url
    CONFIG_JSON.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def build_database_url(server: str, database: str, user: str, password: str) -> str:
    return (f"mssql+pymssql://{urllib.parse.quote(user)}:"
            f"{urllib.parse.quote(password)}@{server}:1433/{database}")


# ── Connection tests (each returns a result string or raises) ──────────────────

def test_api(values: dict) -> str:
    import requests
    url = values["API_URL"].rstrip("/")
    if not url:
        raise ValueError("API URL is empty")
    r = requests.get(f"{url}/auth/health", timeout=90)
    r.raise_for_status()
    return f"API OK — {r.json().get('message', 'running')}"


def _wait_for_sql(connect_fn, retries=12, delay=8):
    """The serverless Azure SQL database auto-pauses when idle. While it
    resumes (~30-60s) it actively refuses connections with error 40613
    'not currently available' — so retry until it is awake instead of
    reporting a failure."""
    last = None
    for attempt in range(retries):
        try:
            return connect_fn()
        except Exception as e:  # noqa: BLE001 - only resume errors are retried
            message = str(e)
            if ("40613" not in message
                    and "not currently available" not in message
                    and "severity 20" not in message):
                raise
            last = e
            time.sleep(delay)
    raise last


def test_database(values: dict) -> str:
    import pymssql
    conn = _wait_for_sql(lambda: pymssql.connect(
        server=values["SQL_SERVER"], user=values["SQL_USER"],
        password=values["SQL_PASSWORD"], database=values["SQL_DATABASE"],
        port=1433, login_timeout=90,
    ))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sys.tables")
    tables = cur.fetchone()[0]
    conn.close()
    return f"Database OK — {tables} tables"


def test_storage(values: dict) -> str:
    from azure.storage.blob import BlobServiceClient
    service = BlobServiceClient.from_connection_string(values["BLOB_CONNECTION_STRING"])
    container = service.get_container_client(values["BLOB_CONTAINER"] or "images")
    if not container.exists():
        raise ValueError(f"container '{values['BLOB_CONTAINER']}' not found")
    blobs = sum(1 for _ in container.list_blobs())
    return f"Storage OK — {blobs} files in '{values['BLOB_CONTAINER']}'"


def test_schema(values: dict) -> str:
    """Verify the database structure against the app's models.

    - Empty database        → create every table + relation, insert default data
    - Complete schema       → use it as-is (seed defaults if it has no users)
    - Anything in between   → 'incompatible database', login stays blocked
    """
    import sys
    api_dir = str(ROOT / "api")
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)
    from sqlalchemy import create_engine, inspect
    from sqlalchemy.orm import sessionmaker
    import database  # defines Base + the mssql String(450) compile rule
    import models
    from reset_db import seed_defaults

    engine = create_engine(values["DATABASE_URL"], pool_pre_ping=True)
    _wait_for_sql(lambda: engine.connect()).close()  # let a paused DB resume
    expected = database.Base.metadata.tables
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    if not existing:
        database.Base.metadata.create_all(bind=engine)
        db = sessionmaker(bind=engine)()
        try:
            seed_defaults(db)
        finally:
            db.close()
        return (f"Empty database — created {len(expected)} tables + relations "
                "and default data (admin/admin123)")

    problems = []
    missing_tables = set(expected) - existing
    if missing_tables:
        problems.append("missing tables: " + ", ".join(sorted(missing_tables)))
    for name, table in expected.items():
        if name in missing_tables:
            continue
        db_columns = {c["name"] for c in inspector.get_columns(name)}
        missing_columns = {c.name for c in table.columns} - db_columns
        if missing_columns:
            problems.append(f"table '{name}' missing columns: "
                            + ", ".join(sorted(missing_columns)))
        expected_fks = {(fk.parent.name, fk.column.table.name)
                        for fk in table.foreign_keys}
        db_fks = set()
        for fk in inspector.get_foreign_keys(name):
            for col in fk["constrained_columns"]:
                db_fks.add((col, fk["referred_table"]))
        missing_fks = expected_fks - db_fks
        if missing_fks:
            problems.append(f"table '{name}' missing relations: "
                            + ", ".join(f"{c}→{t}" for c, t in sorted(missing_fks)))
    if problems:
        raise ValueError("Incompatible database — " + "; ".join(problems))

    db = sessionmaker(bind=engine)()
    try:
        if db.query(models.User).count() == 0:
            seed_defaults(db)
            return (f"Schema OK ({len(expected)} tables) — no users found, "
                    "default data added (admin/admin123)")
    finally:
        db.close()
    return f"Schema OK — {len(expected)} tables, all relations verified"


TESTS = [
    ("Test API", test_api),
    ("Test database", test_database),
    ("Test storage", test_storage),
    ("Test schema", test_schema),
]


# ── UI ──────────────────────────────────────────────────────────────────────────

class ServerConfigApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.result = None  # set to the API URL on "Save and continue"
        self.title("Bellmounth — Server configuration (admin)")
        self.configure(bg="#FFFFFF")
        self.resizable(False, False)
        icon = ROOT / "app_icon.ico"
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except Exception:
                pass

        style = ttk.Style(self)
        style.configure("TLabel", background="#FFFFFF")
        style.configure("TCheckbutton", background="#FFFFFF")

        self.vars: dict[str, tk.StringVar] = {}
        self.entries: dict[str, ttk.Entry] = {}

        frame = ttk.Frame(self, padding=16)
        frame.grid(sticky="nsew")

        ttk.Label(frame, text="Server connection settings",
                  font=("Segoe UI", 13, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 2))
        ttk.Label(frame, foreground="#B00020",
                  text="Admin only — these are the master keys. "
                       "Saved to .env (git-ignored).").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(0, 2))
        ttk.Label(frame, foreground="#666666",
                  text="Fields start empty for security. Leave a field empty to "
                       "keep its saved value; type to replace it.").grid(
            row=2, column=0, columnspan=4, sticky="w", pady=(0, 12))

        row = 3
        for key, label, masked in FIELDS:
            saved_mark = "  ●" if load_env().get(key) else ""
            ttk.Label(frame, text=label + saved_mark).grid(
                row=row, column=0, sticky="w", pady=3)
            var = tk.StringVar(value="")
            entry = ttk.Entry(frame, textvariable=var, width=64,
                              show="•" if masked else "")
            entry.grid(row=row, column=1, columnspan=2, sticky="we", pady=3, padx=(8, 4))
            self.vars[key] = var
            self.entries[key] = entry
            if masked:
                shown = tk.BooleanVar(value=False)

                def toggle(e=entry, s=shown):
                    e.configure(show="" if s.get() else "•")

                ttk.Checkbutton(frame, text="show", variable=shown,
                                command=toggle).grid(row=row, column=3, padx=(0, 2))
            row += 1

        ttk.Button(frame, text="Load saved values",
                   command=self.load_saved).grid(
            row=row, column=0, sticky="we", pady=(6, 12))
        ttk.Button(frame, text="Build Database URL from the SQL fields",
                   command=self.build_url).grid(
            row=row, column=1, sticky="w", pady=(6, 12), padx=(8, 0))
        row += 1

        sep = ttk.Separator(frame)
        sep.grid(row=row, column=0, columnspan=4, sticky="we", pady=4)
        row += 1

        self.status_labels = {}
        for label, fn in TESTS:
            ttk.Button(frame, text=label,
                       command=lambda f=fn, n=label: self.run_test(n, f)).grid(
                row=row, column=0, sticky="we", pady=3)
            status = ttk.Label(frame, text="—", foreground="#666666")
            status.grid(row=row, column=1, columnspan=3, sticky="w", padx=(8, 0))
            self.status_labels[label] = status
            row += 1

        sep2 = ttk.Separator(frame)
        sep2.grid(row=row, column=0, columnspan=4, sticky="we", pady=8)
        row += 1

        ttk.Button(frame, text="Save", command=self.save).grid(
            row=row, column=0, sticky="we", pady=(2, 0))
        self.save_status = ttk.Label(frame, text="", foreground="#2E7D32")
        self.save_status.grid(row=row, column=1, columnspan=3, sticky="w", padx=(8, 0))
        row += 1

        self.continue_btn = ttk.Button(
            frame, text="Verify all and continue to login  →",
            command=self.save_and_continue)
        self.continue_btn.grid(row=row, column=0, columnspan=2, sticky="w",
                               pady=(10, 0))

    def current_values(self) -> dict:
        """Merge: what the admin typed wins; empty fields fall back to the
        values already saved in .env, so secrets never need to be displayed."""
        saved = load_env()
        merged = {}
        for key, var in self.vars.items():
            typed = var.get().strip()
            merged[key] = typed if typed else saved.get(key, "")
        return merged

    def load_saved(self):
        """Explicitly reveal the saved values in the fields (admin's choice)."""
        saved = load_env()
        for key, var in self.vars.items():
            var.set(saved.get(key, ""))

    def build_url(self):
        v = self.current_values()
        missing = [k for k in ("SQL_SERVER", "SQL_DATABASE", "SQL_USER", "SQL_PASSWORD")
                   if not v[k]]
        if missing:
            messagebox.showwarning("Missing fields",
                                   "Fill in first: " + ", ".join(missing))
            return
        self.vars["DATABASE_URL"].set(build_database_url(
            v["SQL_SERVER"], v["SQL_DATABASE"], v["SQL_USER"], v["SQL_PASSWORD"]))

    def run_test(self, name: str, fn):
        status = self.status_labels[name]
        status.configure(text="testing… (a sleeping server can take ~1 min)",
                         foreground="#666666")
        values = self.current_values()

        def job():
            try:
                result = fn(values)
                self.after(0, lambda: status.configure(text=result,
                                                       foreground="#2E7D32"))
            except Exception as e:
                msg = str(e).replace("\n", " ")[:110]
                self.after(0, lambda: status.configure(text=f"FAILED — {msg}",
                                                       foreground="#B00020"))

        threading.Thread(target=job, daemon=True).start()

    def save(self):
        v = self.current_values()
        if not v["DATABASE_URL"] and v["SQL_SERVER"]:
            v["DATABASE_URL"] = build_database_url(
                v["SQL_SERVER"], v["SQL_DATABASE"], v["SQL_USER"], v["SQL_PASSWORD"])
            self.vars["DATABASE_URL"].set(v["DATABASE_URL"])
        save_env(v)
        if v["API_URL"]:
            sync_config_json(v["API_URL"])
        self.save_status.configure(
            text="Saved to .env — and config.json now points at this API")

    def save_and_continue(self):
        """Gate to the login screen: every connection test must pass."""
        v = self.current_values()
        if not v["API_URL"]:
            messagebox.showwarning("Missing API URL",
                                   "Enter the API URL before continuing.")
            return
        self.continue_btn.configure(state="disabled", text="Verifying connections…")

        def job():
            failures = []
            for name, fn in TESTS:
                label = self.status_labels[name]
                self.after(0, lambda l=label: l.configure(
                    text="testing… (a sleeping server can take ~1 min)",
                    foreground="#666666"))
                try:
                    result = fn(v)
                    self.after(0, lambda l=label, r=result: l.configure(
                        text=r, foreground="#2E7D32"))
                except Exception as e:
                    msg = str(e).replace("\n", " ")[:110]
                    failures.append(f"{name}: {msg}")
                    self.after(0, lambda l=label, m=msg: l.configure(
                        text=f"FAILED — {m}", foreground="#B00020"))

            def finish():
                self.continue_btn.configure(
                    state="normal", text="Verify all and continue to login  →")
                if failures:
                    messagebox.showerror(
                        "Connection check failed",
                        "Login is blocked until every connection works.\n\n"
                        + "\n\n".join(failures))
                else:
                    self.save()
                    self.result = v["API_URL"]
                    self.destroy()

            self.after(0, finish)

        threading.Thread(target=job, daemon=True).start()


def show_server_config():
    """Run the config window as the app's first screen. Returns the API URL
    when the user clicks 'Save and continue', or None if they close it."""
    app = ServerConfigApp()
    app.mainloop()
    return app.result


def main():
    app = ServerConfigApp()
    app.mainloop()


if __name__ == "__main__":
    main()
