FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Versiones fijas de T8, sin las herramientas de desarrollo.
COPY requirements.lock.txt .
RUN grep -vE '^(pytest|hypothesis|ruff|iniconfig|pluggy|sortedcontainers)==' \
        requirements.lock.txt > requirements.prod.txt \
    && pip install --no-cache-dir -r requirements.prod.txt

COPY alembic.ini .
COPY app/ app/

RUN useradd --create-home --uid 1000 cuadre
USER cuadre

EXPOSE 8000
# Un solo worker: el barrido no debe correr en paralelo (AGENTS.md).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
