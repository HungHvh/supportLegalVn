from dataclasses import dataclass
from urllib.parse import urlparse
import os


@dataclass(frozen=True)
class QdrantConnectionSettings:
    host: str
    port: int
    prefer_grpc: bool = True
    source: str = "env"


def _coerce_port(value: str | int | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_qdrant_connection(
    default_host: str = "localhost",
    default_port: int = 6334,
) -> QdrantConnectionSettings:
    """Resolve the canonical Qdrant connection contract.

    Canonical environment variables:
    - QDRANT_HOST
    - QDRANT_PORT (defaults to 6334)

    Compatibility fallback:
    - QDRANT_URL, if host/port are not explicitly set
    """
    host = (os.getenv("QDRANT_HOST") or "").strip()
    port_env = os.getenv("QDRANT_PORT")
    port = _coerce_port(port_env, default_port)
    source = "env"

    if host:
        return QdrantConnectionSettings(host=host, port=port, source=source)

    qdrant_url = (os.getenv("QDRANT_URL") or "").strip()
    if qdrant_url:
        parsed = urlparse(qdrant_url)
        if parsed.hostname:
            host = parsed.hostname
            port = parsed.port or _coerce_port(port_env, 6333)
            return QdrantConnectionSettings(host=host, port=port, source="qdrant_url")

    return QdrantConnectionSettings(host=default_host, port=port, source=source)

