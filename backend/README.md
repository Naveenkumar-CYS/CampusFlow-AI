# CampusFlow AI — Backend (Day 1)

Student Management service for SIH25103. Day-1 scope only: health check,
Postgres connectivity, Student schema/migration, Student CRUD.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2.x (see "Why SQLAlchemy" below)
- PostgreSQL
- Alembic for migrations

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # edit DB credentials if needed
```

## Database

Point `.env` at any Postgres instance (Docker, local install, or a
teammate's shared dev DB). Minimal local Docker option if you don't have
Postgres yet:

```bash
docker run --name campusflow-pg -e POSTGRES_PASSWORD=devpassword \
  -e POSTGRES_DB=campusflow -p 5432:5432 -d postgres:16
```

## Run migrations

```bash
alembic upgrade head          # apply
alembic downgrade -1          # roll back one revision
alembic revision --autogenerate -m "message"   # create a new migration
```

Verify the table exists:

```bash
psql -d campusflow -c '\d students'
```

## Run the server

```bash
uvicorn app.main:app --reload
```

- App: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- DB health: http://localhost:8000/health/db

## API

| Method | Endpoint              | Purpose                |
|--------|-----------------------|-------------------------|
| GET    | /health                | Liveness check          |
| GET    | /health/db             | Verifies DB connectivity (`SELECT 1`) |
| POST   | /students               | Create a student         |
| GET    | /students/{student_id}  | Fetch one student by enrollment/roll number |
| GET    | /students               | List all students        |

## Why SQLAlchemy (not SQLModel)

SQLModel is a thin, opinionated layer on top of SQLAlchemy + Pydantic. For
a Day-1 foundation that other people will extend under time pressure,
plain SQLAlchemy 2.x + separate Pydantic schemas is more explicit about
where the DB model ends and the API contract begins — which matters once
fees/hostel/exam modules start adding their own models and events.
SQLAlchemy's docs, ecosystem, and Alembic integration are also more
mature, which reduces risk on a hackathon timeline.

## Student schema decisions

- `id` (UUID, PK): stable internal identifier, referenced by other
  services/events. Never changes.
- `student_id` (string, unique): human-readable enrollment/roll number
  (e.g. `STU2026001`). Kept separate from the PK so correcting it later
  never touches foreign keys.
- `email` (unique, indexed): natural dedup point for a person.
- `department`, `course`, `enrollment_year`: required, minimal fields
  other modules will filter/join on.
- `phone`: optional — not everyone provides it Day 1.
- `created_at` / `updated_at`: server-side defaults, not app-side, so
  they're correct regardless of which service writes the row later.

Deliberately NOT added yet: soft-delete flag, status/enum field,
hostel/fees foreign keys, auth fields — those belong to their owning
modules, not the anchor entity.
