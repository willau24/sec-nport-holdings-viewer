FROM node:20-slim AS frontend

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/static \
    PORT=8000

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/nport ./nport
RUN pip install --no-cache-dir .

COPY --from=frontend /build/dist /app/static

RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/api/health').status==200 else 1)"

CMD ["sh", "-c", "uvicorn nport.api:app --host 0.0.0.0 --port ${PORT}"]
