import asyncio
import os
import sqlite3
from urllib.error import URLError
from urllib.request import urlopen
from typing import Any, Dict

from core.constants import SQLITE_PATH
from core.qdrant_config import resolve_qdrant_connection


SERVICE_NAME = "legal-api"
API_VERSION = "1.0.0"


def _check_sqlite(db_path: str) -> bool:
    try:
        if not os.path.exists(db_path):
            return False
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            conn.execute("SELECT 1")
            return True
        finally:
            conn.close()
    except Exception:
        return False


def _check_qdrant() -> bool:
    try:
        settings = resolve_qdrant_connection()
        http_port = 6333 if settings.port == 6334 else settings.port
        with urlopen(f"http://{settings.host}:{http_port}/healthz", timeout=5) as response:
            return 200 <= getattr(response, "status", 200) < 500
    except (URLError, OSError, ValueError):
        return False


async def build_health_status() -> Dict[str, Any]:
    db_path = os.getenv("SQLITE_DB_PATH", SQLITE_PATH)
    db_connected, qdrant_connected = await asyncio.gather(
        asyncio.to_thread(_check_sqlite, db_path),
        asyncio.to_thread(_check_qdrant),
    )
    status = "ok" if db_connected and qdrant_connected else "degraded"
    return {
        "status": status,
        "service": SERVICE_NAME,
        "version": API_VERSION,
        "db_connected": db_connected,
        "qdrant_connected": qdrant_connected,
    }



