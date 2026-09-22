FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY server ./server
COPY web ./web
COPY workspace ./workspace
COPY agents ./agents
COPY rules ./rules
COPY external_system ./external_system
COPY external_robots ./external_robots
COPY multi_ai_portal ./multi_ai_portal
COPY board ./board
COPY META_RULES.md RULES.md ./

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
