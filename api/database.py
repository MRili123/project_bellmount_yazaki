import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.sqltypes import String
from dotenv import load_dotenv

load_dotenv()


@compiles(String, "mssql")
def _mssql_string_default_length(element, compiler, **kw):
    """Models declare Column(String) with no length (fine on SQLite/Postgres),
    but SQL Server renders that as VARCHAR(max), which cannot be a primary key
    or indexed column. Default to NVARCHAR(450) — 900 bytes, the max allowed
    for a clustered index key."""
    if element.length is None:
        return "NVARCHAR(450)"
    return compiler.visit_string(element, **kw)

import pathlib
project_root = pathlib.Path(__file__).parent.parent


def _normalize_db_url(raw: str) -> str:
    """Accept either a ready SQLAlchemy URL or a raw Azure SQL ADO.NET/ODBC
    connection string (as copied from the Azure portal) and return a proper
    SQLAlchemy URL.

    - "postgresql://..." / "mssql+pyodbc://..." / "sqlite://..."  -> used as-is.
    - "Server=tcp:...;Database=...;User ID=...;Password=...;"      -> wrapped for
      the pyodbc driver so it can be pasted straight from the portal.
    """
    if not raw:
        return raw
    if "://" in raw:
        return raw  # already a SQLAlchemy URL
    if "server=" in raw.lower():
        import urllib.parse
        return f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(raw)}"
    return raw


DATABASE_URL = _normalize_db_url(
    os.getenv("DATABASE_URL", f"sqlite:///{project_root}/bellmounth.db")
)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    # Cloud databases (Azure SQL / Postgres): pre-ping and recycle connections so
    # a serverless DB that auto-paused (dropping idle connections) doesn't raise
    # stale-connection errors on the next request.
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=1800,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
