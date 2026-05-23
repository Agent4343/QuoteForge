# QuoteForge production image (§18).
# One service: builds the React frontend, then serves API + static files via FastAPI.

# --- Stage 1: build the frontend ---
# TODO: Restore the web build stage once apps/web/ is committed to the repo.
# FROM node:22-slim AS web
# WORKDIR /web
# COPY apps/web/package*.json ./
# RUN if [ -f package-lock.json ]; then npm ci; fi
# COPY apps/web/ ./
# RUN if [ -f package.json ] && [ -d src ]; then npm run build; else mkdir -p dist; fi

# --- Stage 2: API runtime ---
FROM python:3.12-slim AS api

# WeasyPrint (§6) needs Pango/Cairo/GDK-Pixbuf at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    libffi8 shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# Pin data dir explicitly so path resolution is independent of install location.
ENV DATA_DIR=/app/data LOGO_STORAGE_DIR=/app/var/logos
WORKDIR /app

COPY apps/api/ apps/api/
RUN pip install --upgrade pip && pip install ./apps/api

COPY data/ data/
# TODO: Replace with COPY --from=web /web/dist/ apps/api/static/ once the frontend is built.
RUN mkdir -p apps/api/static/

WORKDIR /app/apps/api
EXPOSE 8000
CMD ["sh", "-c", "uvicorn quoteforge_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
