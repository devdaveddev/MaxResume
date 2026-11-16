# syntax=docker/dockerfile:1.7
# Build from the repository root:  docker build -f backend/Dockerfile -t maxresume-api .
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    HF_HOME=/models

# OCR (scanned PDFs) + converters for .doc/.rtf/.odt
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng antiword \
      libreoffice-writer-nogui curl \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv
WORKDIR /app

# dependencies first (cached layer), then the app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# bake the embedding model into the image: no download at container start
RUN /app/.venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY backend/app ./app
COPY sample_data ./sample_data

RUN useradd --system --uid 10001 --home /app app && chown -R app:app /app /models
USER app

ENV ENV=production LOG_JSON=true SAMPLES_DIR=/app/sample_data HF_HUB_OFFLINE=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD curl -fs http://localhost:8000/api/health || exit 1
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
