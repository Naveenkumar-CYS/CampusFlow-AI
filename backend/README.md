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

## Run tests

```bash
pytest tests/ -v
```

Runs against whatever DB `.env` points to (no separate test DB in Day 2 —
tests use randomized IDs so repeated runs don't collide with existing data).

## Run the server

```bash
uvicorn app.main:app --reload
```

- App: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
- DB health: http://localhost:8000/health/db

## API

| Method | Endpoint                    | Purpose                |
|--------|------------------------------|-------------------------|
| GET    | /health                      | Liveness check          |
| GET    | /health/db                   | Verifies DB connectivity (`SELECT 1`) |
| POST   | /students                     | Create a student         |
| GET    | /students/{student_id}        | Fetch one student by enrollment/roll number |
| GET    | /students                     | List all students        |
| PATCH  | /students/{student_id}        | Partial update            |
| DELETE | /students/{student_id}        | Delete (blocked if admissions reference it) |
| POST   | /admissions                    | Create an admission application |
| GET    | /admissions/{application_number} | Fetch one admission     |
| GET    | /admissions                    | List all admissions      |
| PATCH  | /admissions/{application_number} | Partial update / status transition |
| DELETE | /admissions/{application_number} | Delete an admission     |

Full request/response examples: see `API_CONTRACT.md`.

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

## Admission schema decisions (Day 2)

- `Admission.student_id` is a **nullable** FK to `students.id`, set only
  once an admission is approved. An application isn't a Student until
  it's accepted — keeping this nullable and separate avoids treating
  every applicant as a Student prematurely.
- Applicant data (`applicant_name`, `applicant_email`, etc.) is stored
  directly on Admission rather than requiring a Student to exist first.
  This does duplicate a few fields once a Student is created from it,
  but that's intentional: the applicant's submitted data and the
  Student's live record are allowed to diverge (e.g. course changes
  during review).
- **Relationship: one Student → many Admissions.** A person can have
  multiple admission records over time (reapplication after rejection,
  lateral entry, etc.), but each Admission links to at most one Student.
- **On Student delete, Admission FK is `ON DELETE RESTRICT`** — deleting
  a Student that has admission history is blocked rather than cascaded
  or nulled out. Admission is the historical record of *how* that
  student joined; silently cascading would destroy institutional record,
  and `SET NULL` would leave orphaned admissions with no way to trace
  back who they belonged to. If a Student truly needs to be removed,
  the admission history should be handled explicitly first.

## Admission → Student workflow

Chosen approach: **approval automatically creates/links the Student**
(`PATCH /admissions/{id}` with `{"status": "APPROVED"}`). This fits the
"Smart Automation" theme and avoids a second manual step. The operation
is idempotent — re-approving an already-linked admission does not create
a duplicate Student; it's a no-op. The Student's `student_id` is
deterministically derived from the admission's `application_number`
(`APP2026001` → `STU2026001`) — see `API_CONTRACT.md` for details and
its Day-2 limitations.
