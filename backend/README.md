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

## Event Bus (Stage 1 — Redis Streams foundation)

The automation backbone (`app/automation/*`) previously only had two
callers: the manual/dummy trigger endpoints (`app/api/automation.py`)
and Person A's synchronous `publish()` (`app/events/publisher.py`).
Stage 1 adds a real, swappable transport underneath those — a Redis
Streams-backed event bus — without changing how the Rule Engine or
Workflow Engine work.

**Layout (`app/events/`):**

- `bus.py` — the `EventBus` abstract interface (`publish`,
  `create_consumer_group`, `consume`, `ack`) plus `InMemoryEventBus`, a
  no-Redis-required fake used by tests and local dev.
- `redis_bus.py` — `RedisStreamEventBus`, the real implementation using
  `XADD` / `XGROUP CREATE` / `XREADGROUP` / `XACK`. This is the only
  module in the codebase that imports `redis`.
- `factory.py` — `get_redis_event_bus()` builds a configured
  `RedisStreamEventBus` from `Settings` (see env vars below).
- `runner.py` — `EventBusRunner`, a small bridge that reads
  `StreamMessage`s off any `EventBus` and feeds well-formed ones into
  the existing `EventConsumer.consume()`, then acks. Malformed messages
  are logged and acked (dropped) rather than left pending forever.

**What did *not* change:** `app/automation/consumer.py`,
`rules.py`, `workflows.py`, `store.py`, `actions.py`, the manual trigger
endpoints, and `app/events/publisher.py` are untouched. Both existing
paths — the dummy-event HTTP endpoints and Person A's `publish()` —
still call `EventConsumer.consume()` directly and work exactly as
before. The Redis event bus is an additional, opt-in transport for this
stage, not a replacement.

**Config (env vars, see `.env.example`):**

- `REDIS_URL` (default `redis://localhost:6379/0`)
- `REDIS_STREAM_NAME` (default `campusflow.events`)
- `REDIS_CONSUMER_GROUP` (default `campusflow-automation`)
- `REDIS_CONSUMER_NAME` (default `automation-worker-1`)

**Local Redis for dev/testing:**

```bash
docker run -p 6379:6379 -d redis:7
```

**Quick manual smoke test:**

```python
from app.events.factory import get_redis_event_bus
from app.events.runner import EventBusRunner
from app.automation.consumer import EventConsumer
from app.automation.rules import RuleEngine
from app.automation.workflows import WorkflowEngine
from app.automation.store import InMemoryExecutionStore
from app.automation.producer import make_attendance_marked_event

bus = get_redis_event_bus()
bus.create_consumer_group()
bus.publish(make_attendance_marked_event(attendance_percentage=50))

store = InMemoryExecutionStore()
consumer = EventConsumer(RuleEngine(), WorkflowEngine(store), store)
runner = EventBusRunner(bus, consumer)
print(runner.run_once())
```

**Tests:** `tests/test_event_bus.py`. `InMemoryEventBus` tests always
run. `RedisStreamEventBus` tests are integration tests against a real
Redis and are skipped automatically (`pytest.mark.skipif`) if Redis
isn't reachable at `REDIS_URL`.

**Known limitations / not in scope for Stage 1:**

- No long-running worker process (systemd/supervisor wiring) — `EventBusRunner.run_once()` is a single batch; looping it forever is future work.
- No dead-letter stream for malformed/poison messages beyond logging + dropping — matches the existing `ExecutionStore`-based dead-letter handling for *valid* events that fail downstream, but a truly malformed stream entry has nowhere else to go yet.
- No consumer-side claim/reclaim (`XCLAIM`/`XAUTOCLAIM`) for messages left pending by a crashed consumer — a future stage's concern.
- The Rule/Workflow Engine redesign, AI model, notification redesign, and new ERP modules are explicitly out of scope per the Stage 1 brief.
