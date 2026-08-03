FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN groupadd --system --gid 10001 nexus \
    && useradd --system --uid 10001 --gid nexus --create-home nexus

WORKDIR /app
COPY apps/api/pyproject.toml ./
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/app ./app
COPY apps/api/migrations ./migrations

RUN pip install . \
    && mkdir -p /var/lib/nexus/data \
    && chown -R nexus:nexus /app /var/lib/nexus

USER nexus
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
