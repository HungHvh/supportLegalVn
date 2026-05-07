#!/usr/bin/env sh
set -eu

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup-directory>" >&2
  exit 1
fi

BACKUP_DIR="$1"
SQLITE_DB_PATH="${SQLITE_DB_PATH:-legal_poc.db}"

if [ ! -d "$BACKUP_DIR" ]; then
  echo "Backup directory not found: $BACKUP_DIR" >&2
  exit 1
fi

if [ -f "$BACKUP_DIR/legal_poc.db" ]; then
  cp "$BACKUP_DIR/legal_poc.db" "$SQLITE_DB_PATH"
fi

QDRANT_VOLUME="${QDRANT_VOLUME:-$(docker volume ls --format '{{.Name}}' | grep -E '(^|_)qdrant_data$' | head -n 1 || true)}"
if [ -z "$QDRANT_VOLUME" ]; then
  echo "Unable to locate the Qdrant Docker volume." >&2
  exit 1
fi

if [ ! -f "$BACKUP_DIR/qdrant-storage.tar.gz" ]; then
  echo "Missing Qdrant archive: $BACKUP_DIR/qdrant-storage.tar.gz" >&2
  exit 1
fi

docker run --rm \
  -v "$QDRANT_VOLUME:/target" \
  -v "$BACKUP_DIR:/backup:ro" \
  alpine:3.20 sh -lc "find /target -mindepth 1 -maxdepth 1 -exec rm -rf {} + && tar xzf /backup/qdrant-storage.tar.gz -C /target"

echo "Restore complete from: $BACKUP_DIR"


