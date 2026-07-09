# ORION demo API + dashboard — single-container deploy (Railway).
FROM python:3.12-slim

WORKDIR /srv/orion

# Install the package first so the layer caches across code-only changes.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

# Static dashboard (served by FastAPI at /) and the seed script.
COPY frontend ./frontend
COPY scripts ./scripts

# Railway injects PORT; default to 8000 for local docker runs.
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
