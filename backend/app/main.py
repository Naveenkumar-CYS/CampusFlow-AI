"""
CampusFlow AI — single FastAPI application acting as the API gateway.

Every request passes through this one entry point in order:

    Client -> FastAPI app (gateway) -> JWT auth (app.api.auth.get_current_user, 401)
            -> RBAC (app.core.rbac.require_roles / enforce_own_* , 403) -> domain endpoint

No separate gateway process/service is introduced — this app already is
the gateway, and app.core.rbac is the shared access-control layer every
protected router depends on. /health and /auth/login stay public by
design (liveness check and the endpoint that issues tokens).
"""
from fastapi import FastAPI

from app.api import admissions, attendance, auth, analytics, audit, automation, examinations, fees, health, hostel, payments, students

app = FastAPI(title="CampusFlow AI — Student Management Service")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(admissions.router)
app.include_router(fees.router)
app.include_router(payments.router)
app.include_router(attendance.router)
app.include_router(hostel.hostels_router)
app.include_router(hostel.rooms_router)
app.include_router(hostel.allocations_router)
app.include_router(examinations.router)
app.include_router(automation.router)
app.include_router(analytics.router)
app.include_router(audit.router)
