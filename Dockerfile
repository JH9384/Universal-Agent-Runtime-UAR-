FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UAR_DATA_DIR=/data \
    UAR_ARTIFACT_DIR=/artifacts

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md VERSION ./
COPY uar ./uar

RUN python -m pip install --upgrade pip \
    && python -m pip install -e .

RUN mkdir -p /data /artifacts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "uar.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
