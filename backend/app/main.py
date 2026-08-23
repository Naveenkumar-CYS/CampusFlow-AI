from fastapi import FastAPI

from app.api import health, students

app = FastAPI(title="CampusFlow AI — Student Management Service")

app.include_router(health.router)
app.include_router(students.router)
