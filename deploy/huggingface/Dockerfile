# syntax=docker/dockerfile:1.7
# All-in-one image for Hugging Face Spaces (Docker SDK): the React build is served by
# the FastAPI process on port 7860, running as uid 1000 as Spaces requires.
# deploy.py copies this file to the root of the Space repository.

# ---------- 1. build the frontend
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 2. API + static site
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

# OCR (scanned PDFs) + converters for .doc/.rtf/.odt
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng antiword \
      libreoffice-writer-nogui curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user HF_HOME=/home/user/models
WORKDIR /home/user/app

COPY --chown=user backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# bake the embedding model in: no download at start-up
RUN .venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY --chown=user backend/app ./app
COPY --chown=user sample_data ./sample_data
COPY --chown=user --from=web /web/dist ./static

# STORAGE=auto uses MONGO_URL when set as a Space secret (e.g. MongoDB Atlas), otherwise
# in-memory storage (data resets when the Space restarts or sleeps).
ENV ENV=production LOG_JSON=true STORAGE=auto MONGO_URL=mongodb://127.0.0.1:27017 \
    STATIC_DIR=/home/user/app/static SAMPLES_DIR=/home/user/app/sample_data \
    FRAME_ANCESTORS=https://huggingface.co HF_HUB_OFFLINE=1 PARSE_WORKERS=2

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s CMD curl -fs http://localhost:7860/api/health || exit 1
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
