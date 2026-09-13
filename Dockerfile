# Build the React surface separately so the runtime image contains only the
# compiled UI and the small FastAPI service. Pass --platform linux/arm64 to
# docker buildx when publishing for AgentCore Runtime.
# node:22-alpine manifest digest pinned for reproducible multi-architecture builds.
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS web-build
WORKDIR /web
COPY frontend/package*.json ./
# Installing without lifecycle scripts avoids an Alpine/overlayfs race where
# esbuild's postinstall can observe its just-extracted binary as busy. Rebuild
# that one native helper in a separate layer before compiling the UI.
RUN npm ci --ignore-scripts --no-audit --no-fund \
    && npm rebuild esbuild --foreground-scripts --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# python:3.12-slim manifest digest pinned for reproducible multi-architecture builds.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REENTRY_MODE=demo \
    PORT=8080
WORKDIR /app
COPY pyproject.toml README.md LICENSE requirements-runtime.lock ./
COPY backend/ ./backend/
RUN python -m pip install --no-cache-dir --default-timeout=120 -r requirements-runtime.lock \
    && python -m pip install --no-cache-dir --default-timeout=120 --no-deps .
COPY --from=web-build /web/dist ./frontend/dist
RUN groupadd --system reentry \
    && useradd --system --gid reentry --home-dir /app --no-create-home --shell /usr/sbin/nologin reentry \
    && chown -R reentry:reentry /app
USER reentry
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8080"]
