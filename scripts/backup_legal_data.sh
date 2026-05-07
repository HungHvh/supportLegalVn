#!/usr/bin/env sh
set -eu

BACKUP_ROOT="${BACKUP_ROOT:-$(pwd)/backups}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
SQLITE_DB_PATH="${SQLITE_DB_PATH:-legal_poc.db}"

mkdir -p "$BACKUP_DIR"

if [ -f "$SQLITE_DB_PATH" ]; then
  cp "$SQLITE_DB_PATH" "$BACKUP_DIR/legal_poc.db"
fi

QDRANT_VOLUME="${QDRANT_VOLUME:-$(docker volume ls --format '{{.Name}}' | grep -E '(^|_)qdrant_data$' | head -n 1 || true)}"
if [ -z "$QDRANT_VOLUME" ]; then
  echo "Unable to locate the Qdrant Docker volume." >&2
  exit 1
fi

# Archive the full Qdrant storage volume so snapshots and payload data are captured together.
docker run --rm \
  -v "$QDRANT_VOLUME:/source:ro" \
  -v "$BACKUP_DIR:/backup" \
  alpine:3.20 sh -lc "mkdir -p /backup && cd /source && tar czf /backup/qdrant-storage.tar.gz ."

KEEP_COUNT="${RETENTION_COUNT:-7}"
OLD_BACKUPS=$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d | sort)
INDEX=0
for old_backup in $OLD_BACKUPS; do
  INDEX=$((INDEX + 1))
  if [ "$INDEX" -gt "$KEEP_COUNT" ]; then
    rm -rf "$old_backup"
  fi
done

echo "Backup complete: $BACKUP_DIR"


