# CampusFlow AI

## Project Overview

AI-powered intelligent student management and automation platform
(SIH25103). A modular-monolith FastAPI backend (Student, Admission,
Fee, Hostel, Examination, Attendance, JWT+RBAC auth, AI advisory
analytics) driving an event-based automation layer (Rule Engine →
Workflow Engine → Action Executor → Notifications → Audit), backed by
PostgreSQL and Redis, with a Next.js frontend. See
`CampusFlow_AI_Architecture.md` for the full architecture writeup and
`backend/README.md` for backend-specific detail.

## Architecture

```text
Frontend (Next.js)
     ↓
FastAPI (API Gateway + JWT + RBAC)
     ↓
Domain Services (Student, Admission, Fee, Hostel, Examination, Attendance)
     ↓
PostgreSQL
     ↓
Domain Events
     ↓
Redis Streams  →  Event Worker (separate process)
     ↓
Rule Engine → Workflow Engine → Action Executor
     ↓
Notification (email/SMS) · AI Advisory · Audit
```

The API server and the event worker are two separate processes —
running the API alone is not enough for `AUTOMATION_TRANSPORT=redis`
to actually deliver anything (see "Automation Transport" below).

## Prerequisites

- Docker + Docker Compose (recommended), **or** Python 3.12+, Node 22+,
  and a local PostgreSQL 16 + Redis 7 if running services natively.

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in real values
(never commit `.env`). Key variables:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Full Postgres connection string (or the individual `POSTGRES_*` vars) |
| `REDIS_URL` | Redis instance backing the event bus and rate limiter |
| `JWT_SECRET` | Signing secret for auth tokens — set a real value per environment |
| `PAYMENT_WEBHOOK_SECRET` | HMAC secret verifying `POST /payments/webhook` |
| `ENCRYPTION_KEY` | Fernet key encrypting sensitive fields (e.g. `Student.phone`) at rest |
| `AUTOMATION_TRANSPORT` | `in_process` (default) or `redis` — see below |
| `NOTIFICATION_PROVIDER_MODE` | `mock` (default, no network calls) or `live` |
| `SMTP_*` | Real email provider config, only used when notifications are `live` |
| `SMS_*` | Real SMS webhook config, only used when notifications are `live` |
| `RATE_LIMIT_*` | Login/webhook rate-limit tuning — see `.env.example` for the full list |

`docker-compose.yml` sets working local-dev defaults for all of these
already; you only need `backend/.env` for running services natively.

## Local Setup

**Docker Compose (recommended — starts everything, worker included):**

```bash
docker compose up --build
```

This starts, in order: `db` (Postgres), `redis`, `backend` (FastAPI,
migrations still need to be run once — see below), `worker` (the event
worker, `AUTOMATION_TRANSPORT=redis` in this stack), and `frontend`.

Run migrations once against the compose stack:

```bash
docker compose exec backend alembic upgrade head
```

**Native (no Docker):**

## Start Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DB/Redis credentials if needed
alembic upgrade head
uvicorn app.main:app --reload
```
- App: http://localhost:8000 · Docs: http://localhost:8000/docs

## Start Redis Worker

Only needed when `AUTOMATION_TRANSPORT=redis`. Requires the same `.env`
as the backend (same `REDIS_URL`, `DATABASE_URL`, etc.):

```bash
cd backend
python -m app.worker
```

Stops cleanly on Ctrl+C (finishes the in-flight batch first).

## Start Frontend

```bash
cd frontend
npm ci
npm run dev
```
- App: http://localhost:3000
- Set `NEXT_PUBLIC_API_URL` if the backend isn't at the default `http://localhost:8000`.

## Run Tests

```bash
cd backend
pytest tests/ -v
```

Runs against whatever DB `.env` points to. Redis-dependent tests are
skipped automatically if Redis isn't reachable.

## Payment Webhook

`POST /payments/webhook` — public endpoint (no JWT), trust comes from
an `X-Webhook-Signature` HMAC-SHA256 header verified against
`PAYMENT_WEBHOOK_SECRET`. Rate-limited per-IP (`RATE_LIMIT_WEBHOOK_*`).

## Automation Transport

`AUTOMATION_TRANSPORT` controls how a domain event (e.g. `fee.paid`,
`attendance.marked`) reaches the Rule Engine / Workflow Engine / Action
Executor chain:

- **`in_process`** (local/simple dev, default): `Domain Service → in-process automation`, synchronous, same request, no worker needed. What the unit test suite exercises.
- **`redis`** (integrated/demo mode): `Domain Service → Redis Stream → Event Worker → Automation`. The API process publishes and returns immediately; `app/worker.py`, running as its own process, is what actually drains the stream. `docker-compose.yml` sets this mode for both `backend` and `worker` so they stay in sync — this is the mode to demo the event-driven automation story in.

Both modes stay supported; `in_process` isn't going away since existing
tests depend on it.

## Backup/Restore

```bash
cd backend
./scripts/backup_db.sh                                    # creates backups/campusflow_<timestamp>.dump
./scripts/restore_db.sh backups/campusflow_<timestamp>.dump
```

Both are plain `pg_dump`/`pg_restore` wrappers, fully env-driven (same
`POSTGRES_*`/`DATABASE_URL` as the app) — see the scripts for running
them against the docker-compose `db` container instead of a local
Postgres. `restore_db.sh` is destructive (`--clean --if-exists`) —
point it at the intended database.

## Health Checks

- `GET /health` — liveness only.
- `GET /health/db` — also verifies Postgres connectivity (`SELECT 1`).
