#!/usr/bin/env bash
#
# CampusFlow AI -- PostgreSQL backup script (Person E, Step 3).
#
# Creates a single compressed pg_dump of the CampusFlow database.
# Deliberately simple for a hackathon-scale deployment: one file in,
# one file out, no retention policy, no cloud upload -- see
# restore_db.sh for the matching restore path.
#
# Connection is entirely env-driven -- NOTHING is hardcoded here. Reads
# the same POSTGRES_*/DATABASE_URL variables the app itself uses (see
# app/core/config.py and .env.example), so this script works against
# whatever .env the caller already has set up for the app.
#
# USAGE
#   # From backend/, with your .env already exported into the shell:
#   set -a; source .env; set +a
#   ./scripts/backup_db.sh
#
#   # Or pass values inline for one run without touching .env:
#   POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=campusflow \
#   POSTGRES_USER=postgres POSTGRES_PASSWORD=devpassword \
#   ./scripts/backup_db.sh
#
#   # Against the docker-compose Postgres container instead of a local one:
#   docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" campusflow-db \
#     pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c \
#     > backups/campusflow_$(date +%Y%m%d_%H%M%S).dump
#
# OUTPUT
#   backups/campusflow_<UTC timestamp>.dump  (pg_dump custom format,
#   restorable with restore_db.sh / pg_restore)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/../backups}"

# Same defaults as app/core/config.py's Settings -- never invent real
# credentials, these mirror the documented dev-only fallback values.
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-campusflow}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "ERROR: pg_dump not found on PATH. Install the postgresql-client package." >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
OUTPUT_FILE="${BACKUP_DIR}/campusflow_${TIMESTAMP}.dump"

echo "Backing up '${POSTGRES_DB}' from ${POSTGRES_HOST}:${POSTGRES_PORT} -> ${OUTPUT_FILE}"

# -F c = pg_dump's custom format: compressed, and restorable selectively
# (single table/schema) via pg_restore -- more useful here than plain
# SQL for a project with this many tables.
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    -F c \
    -f "${OUTPUT_FILE}"

echo "Backup complete: ${OUTPUT_FILE}"
