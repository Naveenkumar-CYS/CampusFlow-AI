FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Shell form (not exec-array) so ${PORT:-8000} actually expands -- most
# cloud PaaS targets (Render/Railway/etc., see CampusFlow_AI_Architecture.md
# "Technology Stack") inject PORT and expect the container to listen on
# it; local/docker-compose runs are unaffected since PORT is unset there
# and this falls back to 8000, matching the EXPOSE above and the compose
# port mapping.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}