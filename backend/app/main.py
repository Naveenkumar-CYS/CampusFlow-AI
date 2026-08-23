from fastapi import FastAPI

from app.api import admissions, analytics, audit, automation, fees, health, students

app = FastAPI(title="CampusFlow AI — Student Management Service")

app.include_router(health.router)
app.include_router(students.router)
app.include_router(admissions.router)
app.include_router(fees.router)
app.include_router(automation.router)
app.include_router(analytics.router)
app.include_router(audit.router)
