"""
Image storage abstraction for captures.

Two backends, selected automatically at runtime:

- Azure Blob Storage  -> used when BLOB_CONNECTION_STRING is set. Required in the
  cloud, because Azure App Service's local disk is ephemeral and is wiped on
  every restart/redeploy.
- Local filesystem    -> the default when no blob connection is configured
  (i.e. local development). Behaviour is unchanged from before.

The database stores one small "key" string per image:
- Blob mode:  "original/<file>.png"  (relative blob name inside the container)
- Local mode: the full local path      (unchanged, backwards compatible)

A single deployment is always one mode or the other, so `read`/`delete`
interpret the key based on the active backend. The azure-storage-blob package is
imported lazily, so local development does NOT need it installed.
"""

import os
import threading

BLOB_CONNECTION_STRING = os.getenv("BLOB_CONNECTION_STRING")
BLOB_CONTAINER = os.getenv("BLOB_CONTAINER", "images")
CAPTURES_DIR = os.getenv("CAPTURES_DIR", "./captures")

# Blob storage is the active backend only when a connection string is provided.
USE_BLOB = bool(BLOB_CONNECTION_STRING)

_container_client = None
_lock = threading.Lock()


def _get_container():
    """Lazily create and cache the Azure Blob container client (thread-safe)."""
    global _container_client
    if _container_client is None:
        with _lock:
            if _container_client is None:
                from azure.storage.blob import BlobServiceClient
                service = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
                client = service.get_container_client(BLOB_CONTAINER)
                try:
                    client.create_container()
                except Exception:
                    pass  # container already exists — fine
                _container_client = client
    return _container_client


def ensure_dirs():
    """Local mode: make sure the capture folders exist. No-op in blob mode."""
    if not USE_BLOB:
        os.makedirs(f"{CAPTURES_DIR}/original", exist_ok=True)
        os.makedirs(f"{CAPTURES_DIR}/thresholded", exist_ok=True)


def save_image(subdir: str, filename: str, data: bytes) -> str:
    """Persist an image and return the key to store in the DB.

    `subdir` is 'original' or 'thresholded'.
    """
    if USE_BLOB:
        key = f"{subdir}/{filename}"
        _get_container().upload_blob(name=key, data=data, overwrite=True)
        return key

    # Local: store the full path (matches existing rows).
    path = f"{CAPTURES_DIR}/{subdir}/{filename}"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def read_image(key: str):
    """Return raw image bytes for a stored key, or None if it can't be found."""
    if not key:
        return None
    if USE_BLOB:
        try:
            return _get_container().download_blob(key).readall()
        except Exception:
            return None
    if os.path.exists(key):
        with open(key, "rb") as f:
            return f.read()
    return None


def delete_image(key: str) -> None:
    """Best-effort delete of a stored image. Never raises."""
    if not key:
        return
    if USE_BLOB:
        try:
            _get_container().delete_blob(key)
        except Exception:
            pass
        return
    try:
        if os.path.exists(key):
            os.remove(key)
    except Exception:
        pass
