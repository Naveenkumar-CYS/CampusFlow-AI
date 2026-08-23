#!/usr/bin/env bash
#
# CampusFlow AI -- PostgreSQL restore script (Person E, Step 3).
#
# Restores a dump produced by backup_db.sh (pg_dump custom format).
# Matching simplicity to backup_db.sh: one file in, target database
# restored, nothing fancier.
#
# Connection is entirely env-driven, same variables as backup_db.sh /
# app/core/config.py -- NOTHING is hardcoded here.
#
# USAGE
#   # From backend/, with your .env already exported into the shell:
#   set -a; source .env; set +a
#   ./scripts/restore_db.sh backups/campusflow_20260824_120000.dump
#
#   # Or pass connection values inline for one run:
#   POSTGRES_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=campusflow \
#   POSTGRES_USER=postgres POSTGRES_PASSWORD=devpassword \
#   ./scripts/restore_db.sh backups/campusflow_20260824_120000.dump
#
#   # Against the docker-compose Postgres container instead of a local one:
#   cat backups/campusflow_20260824_120000.dump | \
#     docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" campusflow-db \
#     pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists
#
# WARNING
#   --clean --if-exists drops existing objects in the target database
#   before recreating them from the dump. This is a destructive
#   operation on whatever POSTGRES_DB currently points at -- point it
#   at the intended database, not a database you want to keep untouched.
#
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <path-to-dump-file>" >&2
    exit 1
fi

DUMP_FILE="$1"

if [[ ! -f "${DUMP_FILE}" ]]; then
    echo "ERROR: dump file not found: ${DUMP_FILE}" >&2
    exit 1
fi

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-campusflow}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"

if ! command -v pg_restore >/dev/null 2>&1; then
    echo "ERROR: pg_restore not found on PATH. Install the postgresql-client package." >&2
    exit 1
fi

echo "Restoring '${DUMP_FILE}' into '${POSTGRES_DB}' at ${POSTGRES_HOST}:${POSTGRES_PORT}"
echo "This will drop and recreate existing objects in that database (--clean --if-exists)."
read -r -p "Continue? [y/N] " CONFIRM
if [[ "${CONFIRM}" != "y" && "${CONFIRM}" != "Y" ]]; then
    echo "Aborted."
    exit 1
fi

PGPASSWORD="${POSTGRES_PASSWORD}" pg_restore \
    -h "${POSTGRES_HOST}" \
    -p "${POSTGRES_PORT}" \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --clean \
    --if-exists \
    --no-owner \
    "${DUMP_FILE}"

echo "Restore complete."
