# Imperium backend — production image (FastAPI + agents + RKB).
# Python 3.12 (stable wheels for tree-sitter / psycopg / langchain).
FROM python:3.12-slim

# System deps: git (gitpython repo loading), build tools for any sdist wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first (layer cache): copy only the package metadata, then the code.
COPY pyproject.toml ./
COPY imperium ./imperium
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN pip install --upgrade pip && pip install -e .

# Container Apps sets the listening port via ingress; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# Release step: apply DB migrations, then serve. Migrations are idempotent.
CMD ["sh", "-c", "alembic upgrade head && uvicorn imperium.main:app --host 0.0.0.0 --port ${PORT}"]
