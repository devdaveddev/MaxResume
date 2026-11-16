# syntax=docker/dockerfile:1.7
# Lean all-in-one image for 512 MB free hosting tiers (e.g. Render free web services).
# Same matching engine and results as the full image; differences:
#   - no LibreOffice (~250 MB memory spikes): .doc uses antiword, .odt is read natively,
#     .rtf is rejected with a clear message
#   - one parsing worker and lighter OCR settings to keep peak memory low
#   - listens on $PORT, which the host assigns
# Build from the repository root:  docker build -f deploy/render/Dockerfile .

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

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng antiword curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

RUN useradd -m -u 1000 app
USER app
ENV HOME=/home/app HF_HOME=/home/app/models
WORKDIR /home/app/srv

COPY --chown=app backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# bake the embedding model (ONNX export + tokenizer) in: no download at start-up
RUN .venv/bin/python -c "from huggingface_hub import hf_hub_download as d; [d('sentence-transformers/all-MiniLM-L6-v2', f) for f in ('tokenizer.json', 'onnx/model.onnx')]"

COPY --chown=app backend/app ./app
COPY --chown=app sample_data ./sample_data
COPY --chown=app --from=web /web/dist ./static

# STORAGE=auto: uses MONGO_URL when provided (e.g. MongoDB Atlas free tier), else in-memory.
ENV ENV=production LOG_JSON=true STORAGE=auto MONGO_URL=mongodb://127.0.0.1:27017 \
    STATIC_DIR=/home/app/srv/static SAMPLES_DIR=/home/app/srv/sample_data HF_HUB_OFFLINE=1 \
    PARSE_WORKERS=1 OCR_DPI=200 OCR_MAX_PAGES=3 MAX_BATCH=30 MAX_PDF_PAGES=10 \
    OMP_NUM_THREADS=1 MALLOC_ARENA_MAX=2 PORT=8000

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s CMD curl -fs http://localhost:${PORT}/api/health || exit 1
CMD .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips '*'
